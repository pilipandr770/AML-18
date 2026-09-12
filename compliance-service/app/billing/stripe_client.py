from datetime import datetime, timezone

import stripe

from app.developer_portal.models import DeveloperProject
from app.extensions import db


class BillingNotConfiguredError(Exception):
    pass


def _utcnow():
    return datetime.now(timezone.utc)


def _require_configured(config) -> None:
    if not config.get("STRIPE_SECRET_KEY") or not config.get("STRIPE_PRICE_ID"):
        raise BillingNotConfiguredError("Stripe is not configured on this deployment")


def get_or_create_customer(project: DeveloperProject, config) -> str:
    _require_configured(config)
    stripe.api_key = config["STRIPE_SECRET_KEY"]

    if project.stripe_customer_id:
        return project.stripe_customer_id

    customer = stripe.Customer.create(
        email=project.contact_email,
        name=project.name,
        metadata={"developer_project_public_id": project.public_id},
    )
    project.stripe_customer_id = customer.id
    db.session.commit()
    return customer.id


def create_checkout_session(project: DeveloperProject, config) -> str:
    _require_configured(config)
    stripe.api_key = config["STRIPE_SECRET_KEY"]

    customer_id = get_or_create_customer(project, config)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=project.public_id,
        line_items=[{"price": config["STRIPE_PRICE_ID"], "quantity": 1}],
        success_url=config["STRIPE_CHECKOUT_SUCCESS_URL"],
        cancel_url=config["STRIPE_CHECKOUT_CANCEL_URL"],
    )
    return session.url


def verify_webhook_signature(payload: bytes, sig_header: str, config):
    _require_configured(config)
    return stripe.Webhook.construct_event(payload, sig_header, config["STRIPE_WEBHOOK_SECRET"])


def apply_subscription_event(event, config) -> None:
    """Stripe redelivers events at-least-once; every branch here is an
    idempotent set, so no dedup table is needed. checkout.session.completed
    is the only event carrying our own project identifier
    (client_reference_id) -- it's where stripe_customer_id gets linked to a
    DeveloperProject for the first time. Every later subscription event only
    carries Stripe's own customer/subscription IDs, so those look the
    project up by stripe_customer_id, never by anything in the event body."""
    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        project = DeveloperProject.query.filter_by(public_id=data.get("client_reference_id")).first()
        if project is None:
            return
        project.stripe_customer_id = data.get("customer")
        project.stripe_subscription_id = data.get("subscription")
        project.plan_status = "active"
        project.plan_updated_at = _utcnow()
        db.session.commit()
        return

    if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        project = DeveloperProject.query.filter_by(stripe_customer_id=data.get("customer")).first()
        if project is None:
            return
        project.stripe_subscription_id = data.get("id")
        project.plan_status = "canceled" if event_type == "customer.subscription.deleted" else data.get("status", project.plan_status)
        project.plan_updated_at = _utcnow()
        db.session.commit()
        return
