from app.developer_portal.auth import hash_api_key
from app.developer_portal.models import DeveloperProject


def test_landing_page_renders(client):
    resp = client.get("/developer/")
    assert resp.status_code == 200
    assert b"Wallet-Ownership" in resp.data or b"Wallet-Ownership-Verification" in resp.data


def test_signup_form_renders(client):
    resp = client.get("/developer/signup")
    assert resp.status_code == 200


def test_signup_creates_project_and_returns_key_once(client, app):
    resp = client.post("/developer/signup", data={
        "name": "Acme Wallet",
        "contact_email": "dev@acme.example",
        "webhook_url": "https://acme.example/webhooks/aml18",
    })
    assert resp.status_code == 200
    assert b"aml18_sk_" in resp.data

    with app.app_context():
        rows = DeveloperProject.query.filter_by(name="Acme Wallet").all()
        assert len(rows) == 1
        row = rows[0]
        assert row.contact_email == "dev@acme.example"
        assert row.webhook_url == "https://acme.example/webhooks/aml18"
        assert row.is_active is True
        assert row.api_key_hash != ""
        # the plaintext key must never be persisted anywhere
        assert "aml18_sk_" not in (row.api_key_hash or "")


def test_signup_rejects_invalid_email(client):
    resp = client.post("/developer/signup", data={
        "name": "Bad Email Co",
        "contact_email": "not-an-email",
    })
    assert resp.status_code == 400


def test_signup_rejects_missing_name(client):
    resp = client.post("/developer/signup", data={
        "contact_email": "dev@example.com",
    })
    assert resp.status_code == 400


def test_api_key_rotate_issues_new_key_and_invalidates_old(client, app, auth_headers):
    old_check = client.get(
        "/wallet-ownership/requirement?transfer_amount_eur=500", headers=auth_headers
    )
    assert old_check.status_code == 200

    rotate_resp = client.post("/developer/api-key/rotate", headers=auth_headers)
    assert rotate_resp.status_code == 200
    new_key = rotate_resp.get_json()["api_key"]
    assert new_key.startswith("aml18_sk_")

    old_key_check = client.get(
        "/wallet-ownership/requirement?transfer_amount_eur=500", headers=auth_headers
    )
    assert old_key_check.status_code == 401

    new_headers = {"Authorization": f"Bearer {new_key}"}
    new_key_check = client.get(
        "/wallet-ownership/requirement?transfer_amount_eur=500", headers=new_headers
    )
    assert new_key_check.status_code == 200


def test_api_key_rotate_requires_valid_key(client):
    resp = client.post("/developer/api-key/rotate")
    assert resp.status_code == 401


def test_gated_endpoints_reject_revoked_key(client, app, auth_headers):
    with app.app_context():
        key_hash = hash_api_key(auth_headers["Authorization"].split(" ", 1)[1])
        project = DeveloperProject.query.filter_by(api_key_hash=key_hash).first()
        project.is_active = False
        from app.extensions import db
        db.session.commit()

    resp = client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=auth_headers)
    assert resp.status_code == 401

    resp = client.post("/age-verify/check", json={
        "subject_reference": "user-x",
        "proof_token": "mock:over18",
    }, headers=auth_headers)
    assert resp.status_code == 401
