import logging

from flask import Blueprint, current_app, jsonify, request

from app.wallet_ownership.adapters import AdapterError, AdapterNotConfiguredError
from app.wallet_ownership.models import WalletOwnershipVerification
from app.wallet_ownership.schemas import (
    ChallengeReply,
    ChallengeRequest,
    SignedMessageVerifyRequest,
    TestTransferVerifyRequest,
    VerificationReply,
)
from app.wallet_ownership.service import (
    create_challenge,
    is_verification_required,
    refresh_test_transfer,
    start_test_transfer,
    verify_signed_message,
)

wallet_ownership_bp = Blueprint("wallet_ownership", __name__, url_prefix="/wallet-ownership")

logger = logging.getLogger(__name__)


def _verification_reply(row: WalletOwnershipVerification) -> dict:
    return VerificationReply(
        verification_id=row.public_id,
        network=row.network,
        address=row.address,
        method=row.method,
        status=row.status,
        verified=row.verified,
        threshold_eur=row.threshold_eur,
        transfer_amount_eur=row.transfer_amount_eur,
        evidence=row.evidence,
        last_error=row.last_error,
    ).model_dump()


@wallet_ownership_bp.get("/requirement")
def check_requirement_route():
    raw_amount = request.args.get("transfer_amount_eur")
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        return jsonify({"error": "transfer_amount_eur query param is required and must be numeric"}), 400

    threshold_eur = current_app.config["WALLET_OWNERSHIP_THRESHOLD_EUR"]
    required = is_verification_required(amount, threshold_eur)
    return jsonify({
        "required": required,
        "threshold_eur": threshold_eur,
        "transfer_amount_eur": amount,
    })


@wallet_ownership_bp.post("/challenges")
def create_challenge_route():
    try:
        body = ChallengeRequest.model_validate(request.get_json(force=True))
    except Exception:
        return jsonify({"error": "bad request"}), 400

    ttl_seconds = current_app.config["WALLET_OWNERSHIP_CHALLENGE_TTL_SECONDS"]
    row = create_challenge(network=body.network, address=body.address, ttl_seconds=ttl_seconds)

    reply = ChallengeReply(
        challenge_id=row.public_id,
        network=row.network,
        address=row.address,
        message=row.message,
        expires_at=row.expires_at.isoformat(),
    )
    return jsonify(reply.model_dump()), 201


@wallet_ownership_bp.post("/verifications")
def create_verification_route():
    raw = request.get_json(force=True) or {}
    method = raw.get("method")
    threshold_eur = current_app.config["WALLET_OWNERSHIP_THRESHOLD_EUR"]

    if method == "signed_message":
        try:
            body = SignedMessageVerifyRequest.model_validate(raw)
        except Exception:
            return jsonify({"error": "bad request"}), 400
        try:
            row = verify_signed_message(
                challenge_public_id=body.challenge_id,
                signature=body.signature,
                transfer_amount_eur=body.transfer_amount_eur,
                transaction_id=body.transaction_id,
                threshold_eur=threshold_eur,
            )
        except AdapterError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(_verification_reply(row)), 201

    if method == "test_transfer":
        try:
            body = TestTransferVerifyRequest.model_validate(raw)
        except Exception:
            return jsonify({"error": "bad request"}), 400
        try:
            row = start_test_transfer(
                network=body.network,
                address=body.address,
                transfer_amount_eur=body.transfer_amount_eur,
                transaction_id=body.transaction_id,
                threshold_eur=threshold_eur,
                config=current_app.config,
            )
        except AdapterNotConfiguredError as exc:
            logger.warning("wallet ownership test-transfer adapter not configured: %s", exc)
            return jsonify({"error": "test_transfer adapter not configured"}), 400
        return jsonify(_verification_reply(row)), 201

    return jsonify({"error": "unknown or missing method"}), 400


@wallet_ownership_bp.get("/verifications/<verification_id>")
def get_verification_route(verification_id):
    try:
        row = refresh_test_transfer(verification_id, config=current_app.config)
    except AdapterNotConfiguredError as exc:
        logger.warning("wallet ownership test-transfer adapter not configured: %s", exc)
        return jsonify({"error": "test_transfer adapter not configured"}), 400

    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_verification_reply(row))
