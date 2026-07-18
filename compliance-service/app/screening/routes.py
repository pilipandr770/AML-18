"""REST entry point for one-off name screening, for callers that have no
Travel Rule counterpart VASP to exchange IVMS101 messages with (e.g. a
custodial exchanger doing single-party KYC on its own client). Reuses the
same matcher/decision engine as the Travel Rule webhook -- just skips the
IVMS101 parsing and the ScreeningDecision/ScreeningMatch persistence, since
there is no Envoy transaction_id to hang that audit trail off of here.
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from app.developer_portal.auth import require_api_key
from app.extensions import db
from app.sanctions.models import SanctionedEntity
from app.screening.decision import corroborating_fields, decide
from app.screening.matcher import match_name
from app.screening.schemas import CheckNameReply, CheckNameRequest, MatchDetail

screening_bp = Blueprint("screening", __name__, url_prefix="/screening")

logger = logging.getLogger(__name__)

_DECISION_SEVERITY = {"accepted": 0, "review": 1, "rejected": 2}


@screening_bp.post("/check-name")
def check_name_route():
    project, error = require_api_key()
    if error:
        return error

    try:
        body = CheckNameRequest.model_validate(request.get_json(force=True))
    except Exception:
        return jsonify({"error": "bad request"}), 400

    candidates = match_name(body.name)
    if not candidates:
        reply = CheckNameReply(decision="accepted", score=0.0, matches=[])
        return jsonify(reply.model_dump()), 200

    party = {
        "country": body.country,
        "date_of_birth": body.date_of_birth,
        "national_ids": [],
        "lei": None,
    }

    matches = []
    worst_decision = "accepted"
    for candidate in candidates:
        entity = db.session.get(SanctionedEntity, candidate["entity_id"])
        corroborating = corroborating_fields(party, entity)
        outcome = decide(candidate["name_score"], corroborating, candidate["name_type"], current_app.config)

        matches.append(MatchDetail(
            entity_id=candidate["entity_id"],
            sanctioned_name=candidate["sanctioned_name"],
            name_score=candidate["name_score"],
            name_type=candidate["name_type"],
            corroborating_fields=corroborating,
            rule_branch=outcome["rule_branch"],
            decision=outcome["decision"],
        ))

        if _DECISION_SEVERITY[outcome["decision"]] > _DECISION_SEVERITY[worst_decision]:
            worst_decision = outcome["decision"]

    top_score = candidates[0]["name_score"]
    logger.info(
        "check-name decision=%s score=%.1f project=%s",
        worst_decision, top_score, project.public_id,
    )

    reply = CheckNameReply(decision=worst_decision, score=top_score, matches=matches)
    return jsonify(reply.model_dump()), 200
