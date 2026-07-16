import logging

from flask import Blueprint, jsonify, render_template, request

from app.developer_portal.auth import generate_api_key, hash_api_key, require_api_key
from app.developer_portal.models import DeveloperProject
from app.developer_portal.schemas import ProjectSignupRequest
from app.extensions import db

developer_portal_bp = Blueprint(
    "developer_portal", __name__, url_prefix="/developer", template_folder="templates"
)

logger = logging.getLogger(__name__)


@developer_portal_bp.get("/")
def landing():
    return render_template("landing.html")


@developer_portal_bp.get("/signup")
def signup_form():
    return render_template("signup.html")


@developer_portal_bp.post("/signup")
def signup_submit():
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
    )
    db.session.add(row)
    db.session.commit()

    logger.info("developer project registered project_id=%s name=%s", row.public_id, row.name)

    return render_template("signup_success.html", project=row, api_key=api_key)


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
