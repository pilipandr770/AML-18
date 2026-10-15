"""The agent's entire capability surface. Each tool is a thin wrapper over an
existing service; the agent has no database, key or filesystem access of
its own. Tools are bound to one project and one case through ToolContext --
the model cannot choose which tenant or which amounts an operation applies
to. Strings that originate outside the system (counterparty name, memo) are
untrusted data and are always returned JSON-quoted and length-limited."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from app.agent import journal
from app.agent.models import (
    CLASS_CLEAR, CLASS_NEEDS_REVIEW, CLASS_RECOMMEND_BLOCK, AgentAuditEntry, AgentCase,
)
from app.agent.policy import (
    ALL_OPERATIONS, DENIED, EXECUTE, NEEDS_HUMAN, RECOMMEND_ONLY, Proposal, evaluate,
)
from app.extensions import db
from app.sanctions.freshness import get_freshness
from app.screening.engine import screen_parties
from app.wallet_ownership.models import WalletOwnershipVerification

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_SEVERITY = {CLASS_CLEAR: 0, CLASS_NEEDS_REVIEW: 1, CLASS_RECOMMEND_BLOCK: 2}
_FLOOR_FROM_DETERMINISTIC = {"accepted": CLASS_CLEAR, "review": CLASS_NEEDS_REVIEW, "rejected": CLASS_RECOMMEND_BLOCK}


def untrusted(value, limit: int = 300):
    """Marks and bounds externally supplied text before it reaches the model."""
    if value is None:
        return None
    return {"untrusted_text": _CONTROL.sub("", str(value))[:limit]}


@dataclass
class ToolContext:
    project: object
    case: AgentCase
    config: object
    ledger: object
    executor: object
    mode: str
    policy: object
    kill_switch: bool
    decision_recorded: bool = False
    log: list = field(default_factory=list)


def _floor(case: AgentCase) -> str:
    floor = _FLOOR_FROM_DETERMINISTIC.get(case.deterministic_decision or "", CLASS_NEEDS_REVIEW)
    funds_ok = bool((case.funds_check or {}).get("verified"))
    coverage_ok = bool(((case.evidence or {}).get("coverage") or {}).get("ok", False))
    if (not funds_ok or not coverage_ok) and _SEVERITY[floor] < _SEVERITY[CLASS_NEEDS_REVIEW]:
        floor = CLASS_NEEDS_REVIEW
    return floor


def _counterparty_known(case: AgentCase) -> bool:
    if not case.counterparty_name:
        return False
    prior = AgentCase.query.filter(
        AgentCase.developer_project_id == case.developer_project_id,
        AgentCase.id != case.id,
        AgentCase.resolution == "cleared",
    ).all()
    name = case.counterparty_name.strip().lower()
    return any((p.counterparty_name or "").strip().lower() == name for p in prior)


def _spent_today(project_id: int) -> Decimal:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total = Decimal("0")
    for e in AgentAuditEntry.query.filter_by(developer_project_id=project_id, event_type="operation_executed").all():
        at = e.occurred_at if e.occurred_at.tzinfo else e.occurred_at.replace(tzinfo=timezone.utc)
        if at >= start:
            total += Decimal(str(e.payload.get("amount", "0")))
    return total


# ---- tools ---------------------------------------------------------------

def screen_transfer(ctx: ToolContext, args: dict) -> dict:
    case = ctx.case
    if not (case.counterparty_name or "").strip():
        # Nothing to screen (e.g. a deposit seen on-chain with no KYC data from
        # the client): that is not a clean result, it needs a human.
        return {"decision": "review", "rule_branch": "counterparty_unidentified", "top_candidates": [], "counterparty": None}
    result = screen_parties(
        [{"name": case.counterparty_name or "", "country": case.counterparty_country, "role": "originator",
          "national_ids": [], "lei": None, "date_of_birth": None}],
        ctx.config,
    )
    party = result["party_results"][0]
    decision, rule_branch = result["decision"], party["rule_branch"]
    review_threshold = ctx.config["SCREENING_REVIEW_THRESHOLD"]
    # Stricter than the Travel Rule screening on purpose: for the agent, ANY
    # candidate at or above the review threshold counts as a hit (the existing
    # mid-band "uncorroborated -> accepted" shortcut is not allowed to clear
    # a fuzzy match automatically).
    if decision == "accepted" and party["candidates"] and party["candidates"][0]["name_score"] >= review_threshold:
        decision, rule_branch = "review", "agent_fuzzy_hit_escalated"
    return {
        "decision": decision,
        "rule_branch": rule_branch,
        "top_candidates": [
            {"sanctioned_name": c["sanctioned_name"], "score": round(c["name_score"], 1), "name_type": c["name_type"]}
            for c in party["candidates"][:3]
        ],
        "counterparty": untrusted(case.counterparty_name),
    }


def get_sanctions_freshness(ctx: ToolContext, args: dict) -> dict:
    return {"sources": [
        {"source": f["source"], "age_days": f["age_days"], "record_count": f["record_count"],
         "activated_at": f["activated_at"].isoformat() if f["activated_at"] else None}
        for f in get_freshness()
    ]}


def check_wallet_ownership(ctx: ToolContext, args: dict) -> dict:
    address = str(args.get("address", "")).strip()
    row = (
        WalletOwnershipVerification.query
        .filter(
            WalletOwnershipVerification.developer_project_id == ctx.project.id,
            db.func.lower(WalletOwnershipVerification.address) == address.lower(),
            WalletOwnershipVerification.verified.is_(True),
        )
        .order_by(WalletOwnershipVerification.created_at.desc())
        .first()
    )
    if row is None:
        return {"address": address, "ownership_verified": False}
    return {"address": address, "ownership_verified": True, "method": row.method,
            "verified_at": row.verified_at.isoformat() if row.verified_at else None}


def verify_incoming_funds(ctx: ToolContext, args: dict) -> dict:
    case = ctx.case
    if not case.tx_hash:
        check = {"found": False, "verified": False, "detail": "no tx hash supplied"}
    else:
        from app.agent.chain import ChainError
        try:
            check = ctx.ledger.verify(case.tx_hash, case.deposit_address, case.amount).as_dict()
        except ChainError as exc:
            check = {"found": False, "verified": False, "detail": f"chain lookup failed: {exc}"}
    case.funds_check = check
    db.session.commit()
    return check


def list_pending_reviews(ctx: ToolContext, args: dict) -> dict:
    rows = (
        AgentCase.query.filter_by(developer_project_id=ctx.project.id, status="awaiting_human")
        .order_by(AgentCase.created_at.desc()).limit(20).all()
    )
    return {"pending": [
        {"case_id": r.public_id, "classification": r.classification, "amount": str(r.amount), "asset": r.asset,
         "counterparty": untrusted(r.counterparty_name, 80)}
        for r in rows
    ]}


def record_decision(ctx: ToolContext, args: dict) -> dict:
    case = ctx.case
    requested = args.get("classification")
    if requested not in _SEVERITY:
        return {"error": "classification must be one of clear, needs_review, recommend_block"}
    floor = _floor(case)
    final = requested if _SEVERITY[requested] >= _SEVERITY[floor] else floor
    case.classification = final
    case.explanation = str(args.get("explanation", ""))[:4000]
    evidence = [str(e)[:300] for e in (args.get("evidence") or [])][:10]
    case.evidence = {**(case.evidence or {}), "llm_evidence": evidence}
    db.session.commit()
    ctx.decision_recorded = True
    journal.append(
        ctx.project.id, "agent", "decision_recorded",
        {"requested": requested, "final": final, "floor": floor, "raised_by_policy_floor": final != requested},
        case.public_id,
    )
    return {"recorded": True, "final_classification": final, "raised_to_floor": final != requested}


def execute_operation(ctx: ToolContext, args: dict) -> dict:
    case = ctx.case
    operation = args.get("operation")
    if operation not in ALL_OPERATIONS:
        return {"error": "unknown operation"}
    proposal = Proposal(
        operation=operation, amount=Decimal(str(case.amount)), asset=case.asset, chain=case.chain,
        counterparty_country=case.counterparty_country, counterparty_known=_counterparty_known(case),
        deterministic_decision=case.deterministic_decision or "review",
        funds_verified=bool((case.funds_check or {}).get("verified")),
        spent_today=_spent_today(ctx.project.id),
        llm_classification=case.classification if ctx.decision_recorded else None,
    )
    verdict = evaluate(proposal, ctx.policy, ctx.mode, ctx.kill_switch)
    journal.append(
        ctx.project.id, "policy_engine", "policy_verdict",
        {"operation": operation, "outcome": verdict.outcome, "reasons": verdict.reasons, "mode": ctx.mode,
         "agent_reason": str(args.get("reason", ""))[:500]},
        case.public_id,
    )
    if verdict.outcome == EXECUTE:
        try:
            result = ctx.executor.execute(operation, case, ctx.project)
        except Exception as exc:  # delivery failure must never look like success
            case.status = "awaiting_human"
            db.session.commit()
            journal.append(ctx.project.id, "system", "operation_failed",
                           {"operation": operation, "error": type(exc).__name__}, case.public_id)
            return {"outcome": NEEDS_HUMAN, "reasons": ["delivery_failed"]}
        case.status = "operated"
        case.resolution = operation
        db.session.commit()
        journal.append(ctx.project.id, "system", "operation_executed",
                       {"operation": operation, "amount": str(case.amount), "result": result}, case.public_id)
    elif verdict.outcome == NEEDS_HUMAN:
        case.status = "awaiting_human"
        db.session.commit()
    return {"outcome": verdict.outcome, "reasons": verdict.reasons}


def write_report(ctx: ToolContext, args: dict) -> dict:
    case = ctx.case
    case.evidence = {**(case.evidence or {}), "report": str(args.get("summary", ""))[:6000]}
    db.session.commit()
    journal.append(ctx.project.id, "agent", "report_written", {"chars": len(case.evidence["report"])}, case.public_id)
    return {"written": True}


def notify_owner(ctx: ToolContext, args: dict) -> dict:
    severity = args.get("severity") if args.get("severity") in ("info", "warning", "critical") else "info"
    journal.append(ctx.project.id, "agent", "owner_notified",
                   {"severity": severity, "message": str(args.get("message", ""))[:1000]}, ctx.case.public_id)
    return {"queued": True}


TOOLS = {
    "screen_transfer": screen_transfer,
    "get_sanctions_freshness": get_sanctions_freshness,
    "check_wallet_ownership": check_wallet_ownership,
    "verify_incoming_funds": verify_incoming_funds,
    "list_pending_reviews": list_pending_reviews,
    "record_decision": record_decision,
    "execute_operation": execute_operation,
    "write_report": write_report,
    "notify_owner": notify_owner,
}


def _schema(props: dict, required: list | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or []}


TOOL_SPECS = [
    {"name": "screen_transfer", "description": "Run deterministic sanctions screening on this case's counterparty. Takes no arguments.", "input_schema": _schema({})},
    {"name": "get_sanctions_freshness", "description": "Age and size of the active sanctions lists per source.", "input_schema": _schema({})},
    {"name": "check_wallet_ownership", "description": "Whether ownership of an address was previously verified for this project.", "input_schema": _schema({"address": {"type": "string"}}, ["address"])},
    {"name": "verify_incoming_funds", "description": "Check on-chain that the transfer exists, has enough confirmations, matches the amount and the expected deposit address. Takes no arguments.", "input_schema": _schema({})},
    {"name": "list_pending_reviews", "description": "Other cases currently waiting for a human decision.", "input_schema": _schema({})},
    {"name": "record_decision", "description": "Record your classification and explanation. This is required exactly once. Policy may raise but never lower it.", "input_schema": _schema({
        "classification": {"type": "string", "enum": ["clear", "needs_review", "recommend_block"]},
        "explanation": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "string"}}}, ["classification", "explanation"])},
    {"name": "execute_operation", "description": "Propose an operation for this case. It is checked by the policy engine and may be executed, escalated to a human, denied, or only recorded as a recommendation. Call record_decision first.", "input_schema": _schema({
        "operation": {"type": "string", "enum": list(ALL_OPERATIONS)}, "reason": {"type": "string"}}, ["operation", "reason"])},
    {"name": "write_report", "description": "Write the final human-readable report for the owner.", "input_schema": _schema({"summary": {"type": "string"}}, ["summary"])},
    {"name": "notify_owner", "description": "Alert the owner.", "input_schema": _schema({
        "severity": {"type": "string", "enum": ["info", "warning", "critical"]}, "message": {"type": "string"}}, ["severity", "message"])},
]
