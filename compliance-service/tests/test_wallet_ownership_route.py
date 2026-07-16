from eth_account import Account
from eth_account.messages import encode_defunct

from app.wallet_ownership.models import WalletOwnershipVerification


def _sign(private_key: str, message: str) -> str:
    signable = encode_defunct(text=message)
    signed = Account.sign_message(signable, private_key=private_key)
    signature = signed.signature.hex()
    return signature if signature.startswith("0x") else f"0x{signature}"


def test_requirement_check_requires_api_key(client):
    resp = client.get("/wallet-ownership/requirement?transfer_amount_eur=500")
    assert resp.status_code == 401


def test_requirement_check_rejects_invalid_api_key(client):
    resp = client.get(
        "/wallet-ownership/requirement?transfer_amount_eur=500",
        headers={"Authorization": "Bearer not-a-real-key"},
    )
    assert resp.status_code == 401


def test_requirement_check_below_threshold(client, auth_headers):
    resp = client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["required"] is False
    assert data["threshold_eur"] == 1000


def test_requirement_check_at_and_above_threshold(client, auth_headers):
    resp = client.get("/wallet-ownership/requirement?transfer_amount_eur=1000", headers=auth_headers)
    assert resp.get_json()["required"] is True

    resp = client.get("/wallet-ownership/requirement?transfer_amount_eur=5000", headers=auth_headers)
    assert resp.get_json()["required"] is True


def test_requirement_check_rejects_non_numeric(client, auth_headers):
    resp = client.get("/wallet-ownership/requirement?transfer_amount_eur=not-a-number", headers=auth_headers)
    assert resp.status_code == 400


def test_signed_message_flow_verifies_correct_signer(client, app, auth_headers):
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
        "transfer_amount_eur": 1500,
        "transaction_id": "txn-123",
    }, headers=auth_headers)
    assert verify_resp.status_code == 201
    data = verify_resp.get_json()
    assert data["status"] == "verified"
    assert data["verified"] is True
    assert data["method"] == "signed_message"
    assert data["evidence"]["recovered_address"].lower() == account.address.lower()

    with app.app_context():
        row = WalletOwnershipVerification.query.filter_by(public_id=data["verification_id"]).first()
        assert row is not None
        assert row.transaction_id == "txn-123"
        assert row.transfer_amount_eur == 1500


def test_signed_message_flow_rejects_wrong_signer(client, auth_headers):
    owner = Account.create()
    impostor = Account.create()

    challenge_resp = client.post("/wallet-ownership/challenges", json={
        "network": "ETH",
        "address": owner.address,
    }, headers=auth_headers)
    challenge = challenge_resp.get_json()

    signature = _sign(impostor.key, challenge["message"])

    verify_resp = client.post("/wallet-ownership/verifications", json={
        "method": "signed_message",
        "challenge_id": challenge["challenge_id"],
        "signature": signature,
    }, headers=auth_headers)
    assert verify_resp.status_code == 201
    data = verify_resp.get_json()
    assert data["status"] == "failed"
    assert data["verified"] is False


def test_signed_message_flow_rejects_replayed_challenge(client, auth_headers):
    account = Account.create()

    challenge_resp = client.post("/wallet-ownership/challenges", json={
        "network": "ETH",
        "address": account.address,
    }, headers=auth_headers)
    challenge = challenge_resp.get_json()
    signature = _sign(account.key, challenge["message"])

    first = client.post("/wallet-ownership/verifications", json={
        "method": "signed_message",
        "challenge_id": challenge["challenge_id"],
        "signature": signature,
    }, headers=auth_headers)
    assert first.status_code == 201

    second = client.post("/wallet-ownership/verifications", json={
        "method": "signed_message",
        "challenge_id": challenge["challenge_id"],
        "signature": signature,
    }, headers=auth_headers)
    assert second.status_code == 400


def test_signed_message_flow_rejects_unknown_challenge(client, auth_headers):
    resp = client.post("/wallet-ownership/verifications", json={
        "method": "signed_message",
        "challenge_id": "does-not-exist",
        "signature": "0x" + "00" * 65,
    }, headers=auth_headers)
    assert resp.status_code == 400


def test_verification_rejects_unknown_method(client, auth_headers):
    resp = client.post("/wallet-ownership/verifications", json={
        "method": "carrier_pigeon",
    }, headers=auth_headers)
    assert resp.status_code == 400


def test_test_transfer_requires_configuration(client, auth_headers):
    resp = client.post("/wallet-ownership/verifications", json={
        "method": "test_transfer",
        "network": "ETH",
        "address": "0x668bb685f8e3891e11Ae5aca9012C59326A87fa0",
        "transfer_amount_eur": 2000,
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "not configured" in resp.get_json()["error"]


def test_test_transfer_flow_reaches_verified(client, app, auth_headers, monkeypatch):
    sender = Account.create()
    beneficiary_address = "0x668bb685f8e3891e11Ae5aca9012C59326A87fa0"

    app.config["WALLET_OWNERSHIP_EVM_RPC_URL"] = "https://example-evm-rpc.local"
    app.config["WALLET_OWNERSHIP_EVM_SENDER_PRIVATE_KEY"] = sender.key.hex()

    rpc_state = {"receipt_calls": 0}

    class _FakeResponse:
        def __init__(self, result=None, error=None):
            self._result = result
            self._error = error

        def raise_for_status(self):
            return None

        def json(self):
            if self._error is not None:
                return {"error": self._error}
            return {"result": self._result}

    def _fake_post(url, json=None, timeout=None):
        method = json["method"]
        if method == "eth_getTransactionCount":
            return _FakeResponse(result="0x1")
        if method == "eth_gasPrice":
            return _FakeResponse(result="0x3b9aca00")
        if method == "eth_sendRawTransaction":
            return _FakeResponse(result="0xfeedface")
        if method == "eth_getTransactionReceipt":
            rpc_state["receipt_calls"] += 1
            if rpc_state["receipt_calls"] < 2:
                return _FakeResponse(result=None)
            return _FakeResponse(result={"status": "0x1", "blockNumber": "0x10"})
        if method == "eth_blockNumber":
            return _FakeResponse(result="0x10")
        raise AssertionError(f"unexpected RPC method {method}")

    monkeypatch.setattr("app.wallet_ownership.adapters.requests.post", _fake_post)

    start_resp = client.post("/wallet-ownership/verifications", json={
        "method": "test_transfer",
        "network": "ETH",
        "address": beneficiary_address,
        "transfer_amount_eur": 2500,
    }, headers=auth_headers)
    assert start_resp.status_code == 201
    started = start_resp.get_json()
    assert started["status"] == "pending"
    assert started["evidence"]["tx_hash"] == "0xfeedface"

    first_poll = client.get(f"/wallet-ownership/verifications/{started['verification_id']}", headers=auth_headers)
    assert first_poll.get_json()["status"] == "pending"

    second_poll = client.get(f"/wallet-ownership/verifications/{started['verification_id']}", headers=auth_headers)
    data = second_poll.get_json()
    assert data["status"] == "verified"
    assert data["verified"] is True
    assert data["evidence"]["confirmations"] == 1

    with app.app_context():
        row = WalletOwnershipVerification.query.filter_by(public_id=started["verification_id"]).first()
        assert row is not None
        assert row.verified is True
