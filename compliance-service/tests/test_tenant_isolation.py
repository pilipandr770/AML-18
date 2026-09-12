from eth_account import Account
from eth_account.messages import encode_defunct


def _sign(private_key: str, message: str) -> str:
    signable = encode_defunct(text=message)
    signed = Account.sign_message(signable, private_key=private_key)
    signature = signed.signature.hex()
    return signature if signature.startswith("0x") else f"0x{signature}"


def test_wallet_ownership_verification_not_readable_by_other_project(client, auth_headers, other_auth_headers):
    account = Account.create()

    challenge_resp = client.post("/wallet-ownership/challenges", json={
        "network": "ETH",
        "address": account.address,
    }, headers=auth_headers)
    assert challenge_resp.status_code == 201
    challenge = challenge_resp.get_json()
    signature = _sign(account.key, challenge["message"])

    verify_resp = client.post("/wallet-ownership/verifications", json={
        "method": "signed_message",
        "challenge_id": challenge["challenge_id"],
        "signature": signature,
    }, headers=auth_headers)
    assert verify_resp.status_code == 201
    verification_id = verify_resp.get_json()["verification_id"]

    leak_resp = client.get(f"/wallet-ownership/verifications/{verification_id}", headers=other_auth_headers)
    assert leak_resp.status_code == 404


def test_wallet_ownership_challenge_not_usable_by_other_project(client, auth_headers, other_auth_headers):
    account = Account.create()

    challenge_resp = client.post("/wallet-ownership/challenges", json={
        "network": "ETH",
        "address": account.address,
    }, headers=auth_headers)
    challenge = challenge_resp.get_json()
    signature = _sign(account.key, challenge["message"])

    # Project B never saw this challenge -- attempting to consume project
    # A's challenge_id with project B's key must fail exactly like an
    # unknown challenge, not succeed or leak the underlying row.
    verify_resp = client.post("/wallet-ownership/verifications", json={
        "method": "signed_message",
        "challenge_id": challenge["challenge_id"],
        "signature": signature,
    }, headers=other_auth_headers)
    assert verify_resp.status_code == 400
    assert "unknown challenge" in verify_resp.get_json()["error"]


def test_ageverify_session_not_readable_by_other_project(client, app, auth_headers, other_auth_headers, monkeypatch):
    class _FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"transaction_id": "txn-tenant-isolation", "request": "jwt-request-value"}

    app.config["AGEVERIFY_EU_VERIFIER_BASE_URL"] = "https://example-verifier.local"
    monkeypatch.setattr("app.ageverify.adapters.requests.post", lambda *a, **k: _FakeResponse())

    resp = client.post("/age-verify/sessions", json={
        "subject_reference": "user-tenant-a",
        "adapter": "eu_oid4vp",
    }, headers=auth_headers)
    assert resp.status_code == 201
    session_id = resp.get_json()["session_id"]

    leak_resp = client.get(f"/age-verify/sessions/{session_id}", headers=other_auth_headers)
    assert leak_resp.status_code == 404
