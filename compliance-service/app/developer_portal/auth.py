import hashlib
import secrets
from datetime import datetime, timezone

from flask import current_app, g, jsonify, request

from app.developer_portal.models import DeveloperProject
from app.extensions import db

API_KEY_PREFIX = "aml18_sk_"


def _utcnow():
    return datetime.now(timezone.utc)


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def require_api_key():
    """Call at the top of a gated view function. Returns
    (DeveloperProject, None) on success, or (None, (response, status)) that
    the caller must return immediately on failure -- matches the existing
    `_get_session_or_404`-style explicit-check pattern used elsewhere in
    this codebase rather than a hidden blueprint before_request hook, since
    a handful of routes (age-verify's launch page / QR code) must stay
    unauthenticated within an otherwise-gated blueprint."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None, (jsonify({"error": "missing or invalid Authorization header"}), 401)

    key = auth_header.split(" ", 1)[1].strip()
    if not key:
        return None, (jsonify({"error": "missing or invalid Authorization header"}), 401)

    project = DeveloperProject.query.filter_by(api_key_hash=hash_api_key(key), is_active=True).first()
    if project is None:
        return None, (jsonify({"error": "invalid or revoked API key"}), 401)

    project.last_used_at = _utcnow()

    if current_app.config.get("BILLING_ENABLED"):
        # Local import: self-hosted deployments (BILLING_ENABLED=False, the
        # default) never import app.billing at all on this hot path, so
        # they pay zero cost for a feature they don't use.
        from app.billing.metering import enforce_quota_and_record
        quota_error = enforce_quota_and_record(project)
        if quota_error:
            db.session.commit()  # still persist last_used_at even when quota-blocked
            return None, quota_error

    db.session.commit()
    g.current_project = project
    return project, None
