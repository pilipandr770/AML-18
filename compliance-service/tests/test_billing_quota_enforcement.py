import pytest

from app import create_app
from app.developer_portal.auth import generate_api_key, hash_api_key
from app.developer_portal.models import DeveloperProject
from app.extensions import db
from tests.conftest import TestConfig


class BillingTestConfig(TestConfig):
    BILLING_ENABLED = True
    FREE_TIER_MONTHLY_CALL_LIMIT = 2


@pytest.fixture
def billing_app():
    app = create_app(BillingTestConfig)
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def billing_client(billing_app):
    return billing_app.test_client()


def _mint(billing_app, **overrides):
    with billing_app.app_context():
        api_key = generate_api_key()
        project = DeveloperProject(
            name="Billing Test Project",
            contact_email="billing@example.com",
            api_key_prefix=api_key[:16],
            api_key_hash=hash_api_key(api_key),
            **overrides,
        )
        db.session.add(project)
        db.session.commit()
    return {"Authorization": f"Bearer {api_key}"}


def test_free_tier_project_blocked_after_quota_exceeded(billing_client, billing_app):
    headers = _mint(billing_app)

    first = billing_client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=headers)
    assert first.status_code == 200

    second = billing_client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=headers)
    assert second.status_code == 200

    third = billing_client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=headers)
    assert third.status_code == 402
    body = third.get_json()
    assert body["free_tier_monthly_call_limit"] == 2
    assert "checkout_url" in body


def test_active_subscription_is_never_quota_blocked(billing_client, billing_app):
    headers = _mint(billing_app, plan_status="active")

    for _ in range(5):
        resp = billing_client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=headers)
        assert resp.status_code == 200


def test_billing_own_endpoints_are_never_quota_blocked(billing_client, billing_app):
    headers = _mint(billing_app)

    # Exhaust the free-tier quota on a billable endpoint first.
    billing_client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=headers)
    billing_client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=headers)
    blocked = billing_client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=headers)
    assert blocked.status_code == 402

    # Checking usage or requesting checkout must still work -- these are
    # account-management calls, not billable API calls.
    usage_resp = billing_client.get("/billing/usage", headers=headers)
    assert usage_resp.status_code == 200
    assert usage_resp.get_json()["plan_status"] == "free"


def test_self_hosted_deployment_never_enforces_quota(client, auth_headers):
    # The default `client`/`auth_headers` fixtures use TestConfig, which
    # has BILLING_ENABLED unset (defaults to False) -- unlimited calls.
    for _ in range(10):
        resp = client.get("/wallet-ownership/requirement?transfer_amount_eur=500", headers=auth_headers)
        assert resp.status_code == 200
