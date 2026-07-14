import json
from pathlib import Path

from app.webhook.auth import HMACSigner

FIXTURES = Path(__file__).parent / "fixtures"

KEY_ID = "01JXTESTKEYID0000000000000"
KEY = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def _signed_headers(transaction_id: str, timestamp: str) -> dict:
    signer = HMACSigner(KEY_ID, KEY)
    signer.append("X-Transfer-ID", transaction_id)
    signer.append("X-Transfer-Timestamp", timestamp)
    return {
        "Authorization": signer.authorization(),
        "X-Transfer-ID": transaction_id,
        "X-Transfer-Timestamp": timestamp,
        "Content-Type": "application/json",
    }


def test_webhook_rejects_missing_auth(client):
    body = _load("request.json")
    resp = client.post("/webhook/travel-rule", json=body)
    assert resp.status_code == 401


def test_webhook_rejects_tampered_signature(client):
    body = _load("request.json")
    headers = _signed_headers(body["transaction_id"], body["timestamp"])
    headers["X-Transfer-Timestamp"] = "2099-01-01T00:00:00Z"  # tamper after signing
    resp = client.post("/webhook/travel-rule", json=body, headers=headers)
    assert resp.status_code == 401


def test_webhook_defers_to_default_when_nothing_to_screen(client):
    # request.json's payload is `{}` -- no identity/transaction attached.
    # Envoy's own webhook.Payload.IsZero() would nilify an echoed-back empty
    # shell anyway, so we must use transfer_action="default" here, not
    # "review" with an unusable payload.
    body = _load("request.json")
    headers = _signed_headers(body["transaction_id"], body["timestamp"])
    resp = client.post("/webhook/travel-rule", json=body, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["transaction_id"] == body["transaction_id"]
    assert data["transfer_action"] == "default"
    assert "payload" not in data


def test_webhook_extracts_parties_from_full_identity_payload(client, caplog):
    request_body = _load("request.json")
    transaction_payload = _load("request_transaction_payload.json")
    request_body["payload"] = transaction_payload

    headers = _signed_headers(request_body["transaction_id"], request_body["timestamp"])

    with caplog.at_level("INFO"):
        resp = client.post("/webhook/travel-rule", json=request_body, headers=headers)

    assert resp.status_code == 200
    reply = resp.get_json()
    # No sanctions data is seeded in this test's database, so the real
    # screening engine (exercised end-to-end here, not mocked) correctly
    # finds no match and accepts -- see tests/test_engine.py for decision
    # band coverage against seeded sanctions data.
    assert reply["transfer_action"] == "accepted"
    # A real transaction payload must be echoed back non-empty -- Envoy
    # requires this to construct its outgoing envelope.
    assert reply["payload"]["identity"]

    # Confirm the mapper actually ran against the real IVMS101 fixture data
    # (Carvalho/Flordelis natural persons, DigiGreen/Jounty VASPs) rather
    # than silently no-op'ing on a payload shape it didn't understand.
    # (Beneficiary surname has an accented character; asserting on the
    # ASCII forename instead avoids source-encoding round-trip issues.)
    logged = "\n".join(r.message for r in caplog.records)
    assert "Carvalho" in logged
    assert "Flordelis" in logged
    assert "DigiGreen" in logged
    assert "Jounty" in logged
    assert "originator_vasp" in logged
    assert "beneficiary_vasp" in logged
