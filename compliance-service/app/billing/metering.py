from datetime import datetime, timezone

from flask import current_app, jsonify, request

from app.billing.models import UsageEvent
from app.extensions import db

_UNLIMITED_STATUSES = ("active", "trialing")

# Only these blueprints are billable -- account-management calls into
# app/billing/ or app/developer_portal/ itself (checking usage, rotating a
# key) must never be metered or blocked by their own quota check.
_BILLABLE_BLUEPRINTS = ("wallet_ownership", "ageverify")


def _utcnow():
    return datetime.now(timezone.utc)


def _period_start(now=None) -> datetime:
    now = now or _utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def record_usage(project_id: int, module: str, endpoint: str) -> None:
    db.session.add(UsageEvent(
        developer_project_id=project_id,
        module=module or "unknown",
        endpoint=endpoint or "unknown",
    ))
    db.session.commit()


def get_current_period_usage(project_id: int, now=None) -> int:
    return UsageEvent.query.filter(
        UsageEvent.developer_project_id == project_id,
        UsageEvent.occurred_at >= _period_start(now),
    ).count()


def enforce_quota_and_record(project):
    """Called from require_api_key() when BILLING_ENABLED is true. Returns
    None to let the request proceed (and records the call), or a
    (response, status) pair for the caller to return immediately -- same
    shape require_api_key() already uses for its own auth failures, so no
    call site needs to handle a new error format."""
    if request.blueprint not in _BILLABLE_BLUEPRINTS:
        return None

    if project.plan_status not in _UNLIMITED_STATUSES:
        limit = current_app.config["FREE_TIER_MONTHLY_CALL_LIMIT"]
        if get_current_period_usage(project.id) >= limit:
            return jsonify({
                "error": "monthly free-tier call quota exceeded",
                "free_tier_monthly_call_limit": limit,
                "checkout_url": "/billing/checkout",
            }), 402

    record_usage(project.id, module=request.blueprint, endpoint=request.endpoint)
    return None
