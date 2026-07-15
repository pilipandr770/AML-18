from app.audit.models import AuditLog
from app.screening.models import ScreeningDecision, ScreeningMatch


def _make_decision(decision="review", transaction_id="txn-abc"):
    row = ScreeningDecision(
        transaction_id=transaction_id,
        decision=decision,
        transfer_action_sent=decision,
    )
    from app.extensions import db
    db.session.add(row)
    db.session.flush()

    db.session.add(ScreeningMatch(
        screening_decision_id=row.id,
        party_role="originator",
        matched_name_variant="Ivan Ivanov",
        name_score=95.0,
        corroborating_fields_matched={"country": "RU"},
        rule_branch="high_score_corroborated_default_review",
        composite_score=95.0,
        rank=1,
    ))
    db.session.commit()
    return row


def test_list_decisions_empty(client):
    resp = client.get("/review/")
    assert resp.status_code == 200
    assert b"Noch keine Screening-Entscheidungen" in resp.data


def test_list_decisions_shows_created_row(client, app):
    with app.app_context():
        _make_decision()

    resp = client.get("/review/")
    assert resp.status_code == 200
    assert b"txn-abc" in resp.data or b"txn-abc"[:8] in resp.data


def test_list_decisions_filter_by_decision(client, app):
    with app.app_context():
        _make_decision(decision="review", transaction_id="txn-review")
        _make_decision(decision="accepted", transaction_id="txn-accepted")

    resp = client.get("/review/?decision=rejected")
    assert resp.status_code == 200
    assert b"Noch keine Screening-Entscheidungen" in resp.data

    resp = client.get("/review/?decision=review")
    assert resp.status_code == 200
    assert b"Noch keine Screening-Entscheidungen" not in resp.data


def test_decision_detail_shows_matches(client, app):
    with app.app_context():
        row = _make_decision()
        decision_id = row.id

    resp = client.get(f"/review/{decision_id}")
    assert resp.status_code == 200
    assert b"Ivan Ivanov" in resp.data
    assert "Auftraggeber".encode() in resp.data
    assert b"high_score_corroborated_default_review" in resp.data


def test_decision_detail_404_for_unknown_id(client):
    resp = client.get("/review/999999")
    assert resp.status_code == 404


def test_override_decision_persists_and_logs_audit(client, app):
    with app.app_context():
        row = _make_decision()
        decision_id = row.id

    resp = client.post(f"/review/{decision_id}/override", data={
        "override_by": "Compliance Officer",
        "override_decision": "accepted",
        "reason": "Manually verified this is a different Ivan Ivanov, not a match.",
    })
    assert resp.status_code == 302

    with app.app_context():
        from app.extensions import db
        updated = db.session.get(ScreeningDecision, decision_id)
        assert updated.human_override is True
        assert updated.human_override_by == "Compliance Officer"
        assert updated.human_override_decision == "accepted"

        audit_rows = AuditLog.query.filter_by(target_id=str(decision_id)).all()
        assert len(audit_rows) == 1
        assert audit_rows[0].action == "screening_decision_override"


def test_override_decision_requires_all_fields(client, app):
    with app.app_context():
        row = _make_decision()
        decision_id = row.id

    resp = client.post(f"/review/{decision_id}/override", data={
        "override_by": "",
        "override_decision": "accepted",
        "reason": "missing name",
    })
    assert resp.status_code == 400
