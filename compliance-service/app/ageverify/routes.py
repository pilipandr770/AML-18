import logging

import qrcode
import qrcode.image.svg
from flask import Blueprint, Response, current_app, jsonify, render_template, request

from app.ageverify.adapters import AdapterError, AdapterNotConfiguredError
from app.ageverify.models import AgeVerification
from app.ageverify.presentation import PresentationError, request_value_to_av_uri
from app.ageverify.schemas import (
    AgeVerificationReply,
    AgeVerificationRequest,
    AgeVerificationSessionReply,
    AgeVerificationSessionRequest,
)
from app.ageverify.session_service import create_session, refresh_session
from app.ageverify.service import verify_and_persist
from app.extensions import db

ageverify_bp = Blueprint("ageverify", __name__, url_prefix="/age-verify", template_folder="templates")

logger = logging.getLogger(__name__)


def _session_reply(row) -> AgeVerificationSessionReply:
    verification = None
    if row.verification_id:
        verification = db.session.get(AgeVerification, row.verification_id)

    return AgeVerificationSessionReply(
        session_id=row.public_id,
        subject_reference=row.subject_reference,
        adapter=row.adapter,
        status=row.status,
        min_age=row.min_age,
        transaction_id=row.external_transaction_id,
        request_value=row.request_value,
        verification_id=row.verification_id,
        verified=None if verification is None else verification.verified,
        method=None if verification is None else verification.method,
        last_error=row.last_error,
    )


def _get_session_or_404(session_id):
    row = refresh_session(session_id, config=current_app.config)
    if row is None:
        return None, (jsonify({"error": "not found"}), 404)
    return row, None


def _load_session_or_404(session_id):
    from app.ageverify.models import AgeVerificationSession

    row = AgeVerificationSession.query.filter_by(public_id=session_id).first()
    if row is None:
        return None, (jsonify({"error": "not found"}), 404)
    return row, None


@ageverify_bp.post("/check")
def age_verify_check():
    try:
        body = AgeVerificationRequest.model_validate(request.get_json(force=True))
    except Exception:
        return jsonify({"error": "bad request"}), 400

    adapter_name = body.adapter or current_app.config["AGEVERIFY_DEFAULT_ADAPTER"]
    min_age = current_app.config["AGEVERIFY_MIN_AGE"]

    try:
        row = verify_and_persist(
            subject_reference=body.subject_reference,
            proof_token=body.proof_token,
            adapter_name=adapter_name,
            min_age=min_age,
            config=current_app.config,
        )
    except AdapterNotConfiguredError as exc:
        logger.warning("age verification adapter not configured: %s", exc)
        return jsonify({"error": "adapter not configured"}), 503
    except AdapterError as exc:
        logger.warning("age verification request rejected: %s", exc)
        return jsonify({"error": "bad request"}), 400

    reply = AgeVerificationReply(
        verification_id=row.id,
        subject_reference=row.subject_reference,
        adapter=row.adapter,
        verified=row.verified,
        min_age=min_age,
        method=row.method,
        verified_at=row.verified_at,
        expires_at=row.expires_at,
    )
    return jsonify(reply.model_dump(mode="json")), 200


@ageverify_bp.post("/sessions")
def age_verify_start_session():
    try:
        body = AgeVerificationSessionRequest.model_validate(request.get_json(force=True))
    except Exception:
        return jsonify({"error": "bad request"}), 400

    adapter_name = body.adapter or current_app.config["AGEVERIFY_DEFAULT_ADAPTER"]
    min_age = body.min_age or current_app.config["AGEVERIFY_MIN_AGE"]

    try:
        row = create_session(
            subject_reference=body.subject_reference,
            adapter_name=adapter_name,
            min_age=min_age,
            config=current_app.config,
        )
    except AdapterNotConfiguredError as exc:
        logger.warning("age verification adapter not configured: %s", exc)
        return jsonify({"error": "adapter not configured"}), 503
    except AdapterError as exc:
        logger.warning("age verification session rejected: %s", exc)
        return jsonify({"error": "bad request"}), 400

    return jsonify(_session_reply(row).model_dump(mode="json")), 201


@ageverify_bp.get("/sessions/<session_id>")
def age_verify_get_session(session_id):
    try:
        row = refresh_session(session_id, config=current_app.config)
    except AdapterNotConfiguredError as exc:
        logger.warning("age verification adapter not configured: %s", exc)
        return jsonify({"error": "adapter not configured"}), 503

    if row is None:
        return jsonify({"error": "not found"}), 404

    return jsonify(_session_reply(row).model_dump(mode="json")), 200


@ageverify_bp.get("/sessions/<session_id>/launch")
def age_verify_launch_page(session_id):
    row, error = _load_session_or_404(session_id)
    if error:
        return error

    av_uri = None
    av_uri_error = None
    if row.request_value:
        try:
            av_uri = request_value_to_av_uri(row.request_value)
        except PresentationError as exc:
            av_uri_error = str(exc)

    return render_template(
        "ageverify_session_launch.html",
        session=row,
        av_uri=av_uri,
        av_uri_error=av_uri_error,
    )


@ageverify_bp.get("/sessions/<session_id>/qr.svg")
def age_verify_session_qr(session_id):
    row, error = _load_session_or_404(session_id)
    if error:
        return error
    if not row.request_value:
        return jsonify({"error": "missing request value"}), 400

    try:
        av_uri = request_value_to_av_uri(row.request_value)
    except PresentationError as exc:
        return jsonify({"error": str(exc)}), 400

    image = qrcode.make(av_uri, image_factory=qrcode.image.svg.SvgPathImage)
    svg = image.to_string().decode("utf-8")
    return Response(svg, mimetype="image/svg+xml")