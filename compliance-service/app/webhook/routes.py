import logging

from flask import Blueprint, current_app, jsonify, request

from app.screening.engine import screen_and_persist
from app.webhook.auth import HMACError, HMACSigner, verify_request
from app.webhook.mapper import extract_parties
from app.webhook.schemas import WebhookRequest

webhook_bp = Blueprint("webhook", __name__, url_prefix="/webhook")

logger = logging.getLogger(__name__)


def _configured_key() -> bytes:
    key_hex = current_app.config["WEBHOOK_AUTH_KEY_SECRET"]
    if not key_hex:
        return b""
    return bytes.fromhex(key_hex)


def _has_echoable_payload(p) -> bool:
    """Mirrors envoy's own webhook.Payload.IsZero(): a payload only counts as
    real if it has an identity AND a transaction/pending/sunrise body --
    Envoy's Payload.Proto() requires both to construct a valid envelope, and
    Envoy nilifies an all-empty payload before it ever reaches its own
    decision switch, so echoing back an empty shell would just resurface
    the same "no error or payload" failure under a different name."""
    if p is None:
        return False
    return bool(p.identity) and bool(p.pending or p.transaction or p.sunrise)


@webhook_bp.post("/travel-rule")
def travel_rule_webhook():
    key_id = current_app.config["WEBHOOK_AUTH_KEY_ID"]
    key = _configured_key()

    try:
        verify_request(
            request.headers.get("Authorization"),
            request.headers.get,
            key_id,
            key,
        )
    except HMACError as exc:
        logger.warning("webhook auth failed: %s", exc)
        return jsonify({"error": "unauthorized"}), 401

    try:
        payload = WebhookRequest.model_validate(request.get_json(force=True))
    except Exception as exc:
        logger.warning("could not parse webhook request: %s", exc)
        return jsonify({"error": "bad request"}), 400

    incoming_payload = payload.payload
    parties = []
    if incoming_payload and incoming_payload.identity:
        parties = extract_parties(incoming_payload.identity)

    logger.info(
        "travel rule webhook received transaction_id=%s parties=%s",
        payload.transaction_id,
        parties,
    )

    if not _has_echoable_payload(incoming_payload):
        # Nothing to screen (e.g. a bare state-transition ping with no
        # identity/transaction attached) -- defer to Envoy's own default
        # handling rather than echo back a payload Envoy would nilify anyway.
        reply = {"transaction_id": payload.transaction_id, "transfer_action": "default"}
    else:
        transfer_action = screen_and_persist(
            payload.transaction_id,
            parties,
            raw_request=request.get_json(force=True),
            config=current_app.config,
        )
        logger.info(
            "screening decision transaction_id=%s transfer_action=%s",
            payload.transaction_id,
            transfer_action,
        )

        # Envoy's WebhookResponse requires a non-nil payload or error on
        # every reply -- a bare transfer_action alone is not enough, it
        # falls through to an internal error. So we always echo the
        # incoming payload back unchanged alongside our decision.
        reply = {
            "transaction_id": payload.transaction_id,
            "transfer_action": transfer_action,
            "payload": incoming_payload.model_dump(exclude_none=True),
        }

    response = jsonify(reply)

    if current_app.config["WEBHOOK_SIGN_REPLIES"] and key:
        response.headers["X-Transfer-ID"] = payload.transaction_id
        signer = HMACSigner(key_id, key)
        signer.append("X-Transfer-ID", payload.transaction_id)
        response.headers["Server-Authorization"] = signer.authorization()

    return response, 200
