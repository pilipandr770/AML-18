import logging

from flask import Blueprint, current_app, jsonify, render_template, request

from app.developer_portal.auth import generate_api_key, hash_api_key, require_api_key
from app.developer_portal.models import DeveloperProject
from app.developer_portal.schemas import ProjectSignupRequest
from app.extensions import db
from app.i18n import localized

developer_portal_bp = Blueprint(
    "developer_portal", __name__, url_prefix="/developer", template_folder="templates"
)

logger = logging.getLogger(__name__)


@developer_portal_bp.get("/")
def landing():
    return render_template(localized("landing.html"))


@developer_portal_bp.get("/signup")
def signup_form():
    return render_template("signup.html")


@developer_portal_bp.get("/pricing")
def pricing():
    return render_template(
        localized("pricing.html"),
        billing_enabled=current_app.config["BILLING_ENABLED"],
        free_tier_monthly_call_limit=current_app.config["FREE_TIER_MONTHLY_CALL_LIMIT"],
    )


_signup_hits: dict = {}


def _signup_rate_limited() -> bool:
    """Per-IP sliding window, in memory (per worker -- approximate by design;
    the point is to stop casual scripted abuse, not to be a perfect limiter)."""
    import time
    limit = current_app.config["SIGNUP_RATE_LIMIT_PER_HOUR"]
    now = time.time()
    hits = [t for t in _signup_hits.get(request.remote_addr, []) if now - t < 3600]
    if len(hits) >= limit:
        _signup_hits[request.remote_addr] = hits
        return True
    hits.append(now)
    _signup_hits[request.remote_addr] = hits
    return False


@developer_portal_bp.post("/signup")
def signup_submit():
    if _signup_rate_limited():
        return render_template("signup.html", error="Too many registrations from your address. Try again later."), 429
    raw = request.form.to_dict()
    try:
        body = ProjectSignupRequest.model_validate(
            {k: v for k, v in raw.items() if v != ""}
        )
    except Exception as exc:
        return render_template("signup.html", error=str(exc), form=raw), 400

    api_key = generate_api_key()
    row = DeveloperProject(
        name=body.name,
        contact_email=body.contact_email,
        webhook_url=body.webhook_url,
        api_key_prefix=api_key[:16],
        api_key_hash=hash_api_key(api_key),
        is_active=not current_app.config["SIGNUP_APPROVAL_REQUIRED"],
    )
    db.session.add(row)
    db.session.commit()

    logger.info("developer project registered project_id=%s name=%s active=%s", row.public_id, row.name, row.is_active)

    return render_template("signup_success.html", project=row, api_key=api_key, pending=not row.is_active)


@developer_portal_bp.post("/api-key/rotate")
def rotate_api_key():
    project, error = require_api_key()
    if error:
        return error

    new_key = generate_api_key()
    project.api_key_prefix = new_key[:16]
    project.api_key_hash = hash_api_key(new_key)
    db.session.commit()

    logger.info("developer project rotated api key project_id=%s", project.public_id)

    return jsonify({
        "project_id": project.public_id,
        "api_key": new_key,
        "api_key_prefix": project.api_key_prefix,
        "message": "store this key now -- it will not be shown again",
    }), 200
