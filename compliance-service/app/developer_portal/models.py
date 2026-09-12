from datetime import datetime, timezone
from uuid import uuid4

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class DeveloperProject(db.Model):
    """A third-party project registered to call the wallet-ownership and
    age-verify REST APIs. Self-service signup, MVP: no login system --
    losing the API key means registering a new project (see
    developer_portal/routes.py). The Travel Rule/TRISA pillar has no
    equivalent record here; it's a separate, infrastructure-level
    integration (run your own TRISA node), not a per-request API caller."""

    __tablename__ = "developer_projects"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), nullable=False, unique=True, default=lambda: uuid4().hex)
    name = db.Column(db.String(128), nullable=False)
    contact_email = db.Column(db.String(256), nullable=False)
    webhook_url = db.Column(db.String(512), nullable=True)
    api_key_prefix = db.Column(db.String(16), nullable=False)  # for recognition only, never the full key
    api_key_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Billing (see app/billing/). Only meaningful when the deployment has
    # BILLING_ENABLED=true (the hosted SaaS instance) -- on a self-hosted
    # deployment these stay at their defaults and are never read.
    # plan_status is a cache of the last processed Stripe webhook, not a
    # live lookup: require_api_key() reads it on every gated request and
    # must never make a network call to Stripe just to check quota.
    plan_status = db.Column(db.String(16), nullable=False, default="free")  # free | active | trialing | past_due | canceled
    stripe_customer_id = db.Column(db.String(64), nullable=True, unique=True, index=True)
    stripe_subscription_id = db.Column(db.String(64), nullable=True, unique=True)
    plan_updated_at = db.Column(db.DateTime(timezone=True), nullable=True)
