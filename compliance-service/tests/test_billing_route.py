import json

import pytest

from app import create_app
from app.billing import routes as billing_routes
from app.developer_portal.auth import generate_api_key, hash_api_key
from app.developer_portal.models import DeveloperProject
from app.extensions import db
from tests.conftest import TestConfig


class BillingTestConfig(TestConfig):
    BILLING_ENABLED = True
    STRIPE_SECRET_KEY = "sk_test_fake"
    STRIPE_WEBHOOK_SECRET = "whsec_fake"
    STRIPE_PRICE_ID = "price_fake"


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
            name="Billing Route Project",
            contact_email="billing-route@example.com",
            api_key_prefix=api_key[:16],
            api_key_hash=hash_api_key(api_key),
            **overrides,
        )
        db.session.add(project)
        db.session.commit()
        project_id = project.id
    return project_id, {"Authorization": f"Bearer {api_key}"}


def test_billing_routes_404_when_disabled(client, auth_headers):
    assert client.post("/billing/checkout", headers=auth_headers).status_code == 404
    assert client.get("/billing/usage", headers=auth_headers).status_code == 404
    assert client.post("/billing/webhook", data=b"{}").status_code == 404


def test_checkout_requires_api_key(billing_client):
    resp = billing_client.post("/billing/checkout")
    assert resp.status_code == 401


def test_checkout_returns_url_from_stripe_client(billing_client, billing_app, monkeypatch):
    _project_id, headers = _mint(billing_app)

    monkeypatch.setattr(
        billing_routes, "create_checkout_session", lambda project, config: "https://checkout.stripe.com/fake"
    )

    resp = billing_client.post("/billing/checkout", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["checkout_url"] == "https://checkout.stripe.com/fake"


def test_webhook_rejects_invalid_signature(billing_client, monkeypatch):
    def _raise(*args, **kwargs):
        raise ValueError("bad payload")

    monkeypatch.setattr(billing_routes, "verify_webhook_signature", _raise)

    resp = billing_client.post("/billing/webhook", data=b"{}", headers={"Stripe-Signature": "bad"})
    assert resp.status_code == 400


def test_webhook_checkout_completed_activates_plan(billing_client, billing_app, monkeypatch):
    project_id, _headers = _mint(billing_app)

    with billing_app.app_context():
        public_id = db.session.get(DeveloperProject, project_id).public_id

    fake_event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "client_reference_id": public_id,
            "customer": "cus_fake123",
            "subscription": "sub_fake123",
        }},
    }
    monkeypatch.setattr(billing_routes, "verify_webhook_signature", lambda payload, sig, config: fake_event)

    resp = billing_client.post(
        "/billing/webhook",
        data=json.dumps(fake_event).encode("utf-8"),
        headers={"Stripe-Signature": "irrelevant-because-mocked", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    with billing_app.app_context():
        project = db.session.get(DeveloperProject, project_id)
        assert project.plan_status == "active"
        assert project.stripe_customer_id == "cus_fake123"
        assert project.stripe_subscription_id == "sub_fake123"


def test_webhook_subscription_deleted_reverts_plan(billing_client, billing_app, monkeypatch):
    project_id, _headers = _mint(
        billing_app, plan_status="active", stripe_customer_id="cus_fake456", stripe_subscription_id="sub_fake456"
    )

    fake_event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_fake456", "customer": "cus_fake456", "status": "canceled"}},
    }
    monkeypatch.setattr(billing_routes, "verify_webhook_signature", lambda payload, sig, config: fake_event)

    resp = billing_client.post(
        "/billing/webhook",
        data=json.dumps(fake_event).encode("utf-8"),
        headers={"Stripe-Signature": "irrelevant-because-mocked"},
    )
    assert resp.status_code == 200

    with billing_app.app_context():
        project = db.session.get(DeveloperProject, project_id)
        assert project.plan_status == "canceled"
