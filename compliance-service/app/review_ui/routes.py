from collections import OrderedDict
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from sqlalchemy import select

from app.audit.models import AuditLog
from app.extensions import db
from app.sanctions.freshness import get_freshness
from app.screening.models import ScreeningDecision, ScreeningMatch

review_bp = Blueprint("review_ui", __name__, url_prefix="/review", template_folder="templates")

PAGE_SIZE = 25
VALID_DECISIONS = {"accepted", "review", "rejected"}

# Internal values (DB rows, CSS classes, Envoy's transfer_action vocabulary)
# stay in English; only the rendered label is German.
DECISION_LABELS = {"accepted": "Akzeptiert", "review": "Zu prüfen", "rejected": "Abgelehnt"}
PARTY_ROLE_LABELS = {
    "originator": "Auftraggeber",
    "beneficiary": "Begünstigter",
    "originator_vasp": "Auftraggeber-VASP",
    "beneficiary_vasp": "Begünstigten-VASP",
}


@review_bp.context_processor
def inject_labels():
    return {
        "decision_labels": DECISION_LABELS,
        "party_role_labels": PARTY_ROLE_LABELS,
        "sanctions_freshness": get_freshness(),
        "sanctions_staleness_warning_days": current_app.config["SANCTIONS_STALENESS_WARNING_DAYS"],
    }


@review_bp.get("/health")
def health():
    return {"status": "ok"}


@review_bp.get("/")
def list_decisions():
    decision_filter = request.args.get("decision")
    page = max(1, request.args.get("page", 1, type=int))

    stmt = select(ScreeningDecision).order_by(ScreeningDecision.created_at.desc())
    if decision_filter in VALID_DECISIONS:
        stmt = stmt.where(ScreeningDecision.decision == decision_filter)
    else:
        decision_filter = None

    pagination = db.paginate(stmt, page=page, per_page=PAGE_SIZE, error_out=False)

    return render_template(
        "decisions_list.html",
        decisions=pagination.items,
        current_filter=decision_filter,
        page=page,
        has_prev=pagination.has_prev,
        has_next=pagination.has_next,
    )


@review_bp.get("/<int:decision_id>")
def decision_detail(decision_id):
    decision = db.session.get(ScreeningDecision, decision_id)
    if decision is None:
        abort(404)

    matches = (
        ScreeningMatch.query
        .filter_by(screening_decision_id=decision_id)
        .order_by(ScreeningMatch.party_role, ScreeningMatch.rank)
        .all()
    )

    matches_by_role = OrderedDict()
    for match in matches:
        matches_by_role.setdefault(match.party_role, []).append(match)

    return render_template(
        "decision_detail.html",
        decision=decision,
        matches_by_role=matches_by_role,
    )


@review_bp.post("/<int:decision_id>/override")
def override_decision(decision_id):
    decision = db.session.get(ScreeningDecision, decision_id)
    if decision is None:
        abort(404)

    override_by = (request.form.get("override_by") or "").strip()
    override_decision_value = request.form.get("override_decision")
    reason = (request.form.get("reason") or "").strip()

    if not override_by or override_decision_value not in VALID_DECISIONS or not reason:
        abort(400)

    decision.human_override = True
    decision.human_override_by = override_by
    decision.human_override_decision = override_decision_value
    decision.human_override_reason = reason
    decision.human_override_at = datetime.now(timezone.utc)

    db.session.add(AuditLog(
        actor=override_by,
        action="screening_decision_override",
        target_type="screening_decision",
        target_id=str(decision_id),
        detail={
            "original_decision": decision.decision,
            "override_decision": override_decision_value,
            "reason": reason,
        },
    ))

    db.session.commit()

    return redirect(url_for("review_ui.decision_detail", decision_id=decision_id))
