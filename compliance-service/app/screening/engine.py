"""Orchestrates screening: extract_parties() output -> match each party's
name -> corroborate -> decide -> aggregate worst-case across parties ->
persist the full explainability trail.
"""

from app.extensions import db
from app.sanctions.models import SanctionedEntity
from app.screening.decision import corroborating_fields, decide
from app.screening.matcher import match_name
from app.screening.models import ScreeningDecision, ScreeningMatch

_DECISION_SEVERITY = {"accepted": 0, "review": 1, "rejected": 2}


def screen_parties(parties: list, config) -> dict:
    """Pure screening logic, no DB writes: screens each party, returns the
    aggregate worst-case decision plus per-party detail for persistence.
    {"decision": "accepted"|"review"|"rejected", "party_results": [...]}"""
    party_results = []
    worst_decision = "accepted"

    for party in parties:
        candidates = match_name(party.get("name") or "")

        if not candidates:
            party_results.append({
                "party": party,
                "decision": "accepted",
                "rule_branch": "no_candidates",
                "corroborating": {},
                "candidates": [],
            })
            continue

        top = candidates[0]
        entity = db.session.get(SanctionedEntity, top["entity_id"])
        corroborating = corroborating_fields(party, entity)
        outcome = decide(top["name_score"], corroborating, top["name_type"], config)

        party_results.append({
            "party": party,
            "decision": outcome["decision"],
            "rule_branch": outcome["rule_branch"],
            "corroborating": corroborating,
            "candidates": candidates,
        })

        if _DECISION_SEVERITY[outcome["decision"]] > _DECISION_SEVERITY[worst_decision]:
            worst_decision = outcome["decision"]

    return {"decision": worst_decision, "party_results": party_results}


def persist_decision(transaction_id: str, aggregate: dict, raw_request: dict) -> ScreeningDecision:
    """Writes a ScreeningDecision + one ScreeningMatch per considered
    candidate (ranked), giving the review UI and any audit the full
    reasoning path, not just the final verdict."""
    decision_row = ScreeningDecision(
        transaction_id=transaction_id,
        decision=aggregate["decision"],
        transfer_action_sent=aggregate["decision"],
        webhook_request_raw=raw_request,
    )
    db.session.add(decision_row)
    db.session.flush()

    for party_result in aggregate["party_results"]:
        candidates = party_result.get("candidates") or []
        for rank, candidate in enumerate(candidates, start=1):
            is_top = rank == 1
            db.session.add(ScreeningMatch(
                screening_decision_id=decision_row.id,
                party_role=party_result["party"].get("role", "unknown"),
                sanctioned_entity_id=candidate["entity_id"],
                matched_name_variant=candidate["sanctioned_name"],
                name_score=candidate["name_score"],
                corroborating_fields_matched=party_result["corroborating"] if is_top else {},
                rule_branch=party_result["rule_branch"] if is_top else "candidate_not_selected",
                composite_score=candidate["name_score"],
                rank=rank,
            ))

    db.session.commit()
    return decision_row


def screen_and_persist(transaction_id: str, parties: list, raw_request: dict, config) -> str:
    """Convenience entry point for the webhook route: screens, persists,
    and returns just the transfer_action string to send back to Envoy."""
    aggregate = screen_parties(parties, config)
    persist_decision(transaction_id, aggregate, raw_request)
    return aggregate["decision"]
