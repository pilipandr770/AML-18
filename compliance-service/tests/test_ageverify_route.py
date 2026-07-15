import hashlib
import json
from base64 import urlsafe_b64encode

import requests

from app.ageverify.models import AgeVerification


def _jwt_for_payload(payload):
    header = urlsafe_b64encode(json.dumps({"alg": "ES256", "typ": "JWT"}).encode("utf-8")).rstrip(b"=").decode("ascii")
    body = urlsafe_b64encode(json.dumps(payload).encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"{header}.{body}.signature"


def test_ageverify_check_mock_over18(client, app):
    resp = client.post("/age-verify/check", json={
        "subject_reference": "user-123",
        "proof_token": "mock:over18",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["subject_reference"] == "user-123"
    assert data["adapter"] == "mock"
    assert data["verified"] is True
    assert data["min_age"] == 18

    with app.app_context():
        rows = AgeVerification.query.filter_by(subject_reference="user-123").all()
        assert len(rows) == 1
        row = rows[0]
        assert row.verified is True
        assert row.proof_token_hash == hashlib.sha256("mock:over18".encode("utf-8")).hexdigest()
        assert row.proof_token_hash != "mock:over18"


def test_ageverify_check_mock_under18(client, app):
    resp = client.post("/age-verify/check", json={
        "subject_reference": "user-456",
        "proof_token": "mock:under18",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["verified"] is False


def test_ageverify_rejects_unknown_adapter(client):
    resp = client.post("/age-verify/check", json={
        "subject_reference": "user-789",
        "proof_token": "mock:over18",
        "adapter": "unsupported",
    })
    assert resp.status_code == 400


def test_ageverify_reports_unconfigured_eu_adapter(client):
    resp = client.post("/age-verify/check", json={
        "subject_reference": "user-eu",
        "proof_token": "opaque-proof",
        "adapter": "eu_oid4vp",
    })
    assert resp.status_code == 400


def test_ageverify_eu_adapter_requires_session_flow(client, app):
    app.config["AGEVERIFY_EU_VERIFIER_BASE_URL"] = "https://example-verifier.local"

    resp = client.post("/age-verify/check", json={
        "subject_reference": "user-eu-bad",
        "proof_token": "opaque-proof",
        "adapter": "eu_oid4vp",
    })
    assert resp.status_code == 400


def test_ageverify_session_start_eu_adapter(client, app, monkeypatch):
    class _FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"transaction_id": "txn-eu-1", "request": "jwt-request-value"}

    def _fake_post(url, json=None, data=None, timeout=None):
        assert url == "https://example-verifier.local/ui/presentations"
        assert json["dcql_query"]["credentials"][0]["claims"][0]["path"] == ["eu.europa.ec.av.1", "age_over_18"]
        assert timeout == 3.5
        return _FakeResponse()

    app.config["AGEVERIFY_EU_VERIFIER_BASE_URL"] = "https://example-verifier.local"
    app.config["AGEVERIFY_EU_VERIFIER_TIMEOUT_SECONDS"] = 3.5
    monkeypatch.setattr("app.ageverify.adapters.requests.post", _fake_post)

    resp = client.post("/age-verify/sessions", json={
        "subject_reference": "user-eu-session",
        "adapter": "eu_oid4vp",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "pending"
    assert data["transaction_id"] == "txn-eu-1"
    assert data["request_value"] == "jwt-request-value"


def test_ageverify_session_poll_eu_adapter_completes(client, app, monkeypatch):
    class _InitResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"transaction_id": "txn-eu-2", "request": "jwt-request-value"}

    class _PollResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"vp_token": {"proof_of_age": "encoded-device-response"}}

    class _ValidationResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [{"docType": "eu.europa.ec.av.1", "attributes": {"eu.europa.ec.av.1": {"age_over_18": True}}}]

    def _fake_post(url, json=None, data=None, timeout=None):
        if url.endswith("/ui/presentations"):
            return _InitResponse()
        if url.endswith("/utilities/validations/msoMdoc/deviceResponse"):
            assert data["device_response"] == "encoded-device-response"
            return _ValidationResponse()
        raise AssertionError(url)

    def _fake_get(url, timeout=None):
        assert url == "https://example-verifier.local/ui/presentations/txn-eu-2"
        return _PollResponse()

    app.config["AGEVERIFY_EU_VERIFIER_BASE_URL"] = "https://example-verifier.local"
    monkeypatch.setattr("app.ageverify.adapters.requests.post", _fake_post)
    monkeypatch.setattr("app.ageverify.adapters.requests.get", _fake_get)

    started = client.post("/age-verify/sessions", json={
        "subject_reference": "user-eu-complete",
        "adapter": "eu_oid4vp",
    })
    session_id = started.get_json()["session_id"]

    resp = client.get(f"/age-verify/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "verified"
    assert data["verified"] is True
    assert data["method"] == "eu_oid4vp_mso_mdoc"

    with app.app_context():
        row = AgeVerification.query.filter_by(subject_reference="user-eu-complete").first()
        assert row is not None
        assert row.adapter == "eu_oid4vp"
        assert row.verified is True


def test_ageverify_session_poll_eu_adapter_pending_on_not_submitted(client, app, monkeypatch):
    class _InitResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"transaction_id": "txn-eu-3", "request": "jwt-request-value"}

    class _PendingPollResponse:
        status_code = 400
        text = "pending"

        def json(self):
            return {"cause": "Presentation should be in Submitted state but is in eu.europa.ec.eudi.verifier.endpoint.domain.Presentation$RequestObjectRetrieved"}

    def _fake_post(url, json=None, data=None, timeout=None):
        return _InitResponse()

    def _fake_get(url, timeout=None):
        return _PendingPollResponse()

    app.config["AGEVERIFY_EU_VERIFIER_BASE_URL"] = "https://example-verifier.local"
    monkeypatch.setattr("app.ageverify.adapters.requests.post", _fake_post)
    monkeypatch.setattr("app.ageverify.adapters.requests.get", _fake_get)

    started = client.post("/age-verify/sessions", json={
        "subject_reference": "user-eu-pending",
        "adapter": "eu_oid4vp",
    })
    session_id = started.get_json()["session_id"]

    resp = client.get(f"/age-verify/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "pending"


def test_ageverify_session_poll_eu_adapter_surfaces_validation_error_detail(client, app, monkeypatch):
    class _InitResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"transaction_id": "txn-eu-4", "request": "jwt-request-value"}

    class _PollResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"vp_token": {"proof_of_age": ["encoded-device-response"]}}

    class _ValidationResponse:
        status_code = 400
        text = ""

        def raise_for_status(self):
            raise requests.HTTPError(response=self)

        def json(self):
            return {
                "type": "InvalidDocuments",
                "invalidDocuments": [{"index": 0, "documentType": "eu.europa.ec.av.1", "errors": ["ExpiredValidityInfo"]}],
            }

    def _fake_post(url, json=None, data=None, timeout=None):
        if url.endswith("/ui/presentations"):
            return _InitResponse()
        if url.endswith("/utilities/validations/msoMdoc/deviceResponse"):
            return _ValidationResponse()
        raise AssertionError(url)

    def _fake_get(url, timeout=None):
        return _PollResponse()

    app.config["AGEVERIFY_EU_VERIFIER_BASE_URL"] = "https://example-verifier.local"
    monkeypatch.setattr("app.ageverify.adapters.requests.post", _fake_post)
    monkeypatch.setattr("app.ageverify.adapters.requests.get", _fake_get)

    started = client.post("/age-verify/sessions", json={
        "subject_reference": "user-eu-expired",
        "adapter": "eu_oid4vp",
    })
    session_id = started.get_json()["session_id"]

    resp = client.get(f"/age-verify/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "failed"
    assert data["last_error"] == "eu_oid4vp device response validation failed: InvalidDocuments: ExpiredValidityInfo"


def test_ageverify_launch_page_renders_av_uri_and_qr(client, app):
    payload = {
        "response_type": "vp_token",
        "response_mode": "direct_post",
        "response_uri": "https://localhost/wallet/direct_post/demo",
        "dcql_query": {
            "credentials": [
                {
                    "id": "proof_of_age",
                    "format": "mso_mdoc",
                    "meta": {"doctype_value": "eu.europa.ec.av.1"},
                    "claims": [{"path": ["eu.europa.ec.av.1", "age_over_18"]}],
                }
            ]
        },
        "nonce": "demo-nonce",
        "state": "demo-state",
    }

    with app.app_context():
        from app.ageverify.models import AgeVerificationSession
        from app.extensions import db

        row = AgeVerificationSession(
            subject_reference="user-launch",
            adapter="eu_oid4vp",
            min_age=18,
            status="pending",
            external_transaction_id="txn-launch",
            request_value=_jwt_for_payload(payload),
        )
        db.session.add(row)
        db.session.commit()
        session_id = row.public_id

    page = client.get(f"/age-verify/sessions/{session_id}/launch")
    assert page.status_code == 200
    assert b"Wallet auf diesem Gerat offnen" not in page.data  # encoding sanity; actual text rendered in UTF-8
    assert b"AV URI" in page.data
    assert b"av://?response_type=vp_token" in page.data

    qr = client.get(f"/age-verify/sessions/{session_id}/qr.svg")
    assert qr.status_code == 200
    assert qr.mimetype == "image/svg+xml"
    assert b"<svg" in qr.data


def test_ageverify_bad_request_on_missing_fields(client):
    resp = client.post("/age-verify/check", json={
        "subject_reference": "",
    })
    assert resp.status_code == 400