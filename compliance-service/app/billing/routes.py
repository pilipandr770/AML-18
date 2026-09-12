import logging

import stripe
from flask import Blueprint, current_app, jsonify, request

from app.billing.metering import get_current_period_usage
from app.billing.schemas import UsageReply
from app.billing.stripe_client import (
    BillingNotConfiguredError,
    apply_subscription_event,
    create_checkout_session,
    verify_webhook_signature,
)
from app.developer_portal.auth import require_api_key

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")

logger = logging.getLogger(__name__)


def _require_billing_enabled():
    if not current_app.config["BILLING_ENABLED"]:
        return jsonify({"error": "billing is not enabled on this deployment"}), 404
    return None


@billing_bp.post("/checkout")
def checkout():
    error = _require_billing_enabled()
    if error:
        return error

    project, error = require_api_key()
    if error:
        return error

    try:
        checkout_url = create_checkout_session(project, current_app.config)
    except BillingNotConfiguredError as exc:
        logger.warning("billing checkout requested but Stripe is not configured: %s", exc)
        return jsonify({"error": "billing is not configured on this deployment"}), 503

    return jsonify({"checkout_url": checkout_url}), 200


@billing_bp.post("/webhook")
def webhook():
    error = _require_billing_enabled()
    if error:
        return error

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = verify_webhook_signature(payload, sig_header, current_app.config)
    except BillingNotConfiguredError as exc:
        logger.warning("stripe webhook received but Stripe is not configured: %s", exc)
        return jsonify({"error": "billing is not configured on this deployment"}), 503
    except (ValueError, stripe.error.SignatureVerificationError):
        logger.warning("stripe webhook signature verification failed")
        return jsonify({"error": "invalid signature"}), 400

    apply_subscription_event(event, current_app.config)
    return jsonify({"received": True}), 200


@billing_bp.get("/usage")
def usage():
    error = _require_billing_enabled()
    if error:
        return error

    project, error = require_api_key()
    if error:
        return error

    reply = UsageReply(
        plan_status=project.plan_status,
        period_usage=get_current_period_usage(project.id),
        free_tier_monthly_call_limit=current_app.config["FREE_TIER_MONTHLY_CALL_LIMIT"],
    )
    return jsonify(reply.model_dump()), 200
