import pytest
from sqlalchemy import text

from app.agent import journal
from app.agent.models import AgentAuditEntry
from app.extensions import db


def _seed(app, n=3, project_id=1):
    for i in range(n):
        journal.append(project_id, "agent", "case_screened", {"i": i, "note": "ünïcode"}, case_public_id="c1")


def test_chain_links_and_verifies(app):
    _seed(app)
    rows = AgentAuditEntry.query.order_by(AgentAuditEntry.seq).all()
    assert [r.seq for r in rows] == [1, 2, 3]
    assert rows[0].prev_hash == journal.GENESIS_HASH
    assert rows[1].prev_hash == rows[0].entry_hash
    assert journal.verify_chain(1) == (True, None)


def test_chains_are_per_project(app):
    _seed(app, 2, project_id=1)
    _seed(app, 2, project_id=2)
    assert journal.verify_chain(1) == (True, None)
    assert journal.verify_chain(2) == (True, None)
    assert AgentAuditEntry.query.filter_by(developer_project_id=2).first().prev_hash == journal.GENESIS_HASH


def test_orm_refuses_update_and_delete(app):
    _seed(app, 1)
    row = AgentAuditEntry.query.first()
    row.actor = "someone_else"
    with pytest.raises(journal.JournalTamperError):
        db.session.commit()
    db.session.rollback()
    row = AgentAuditEntry.query.first()
    db.session.delete(row)
    with pytest.raises(journal.JournalTamperError):
        db.session.commit()
    db.session.rollback()


def test_tampering_with_content_is_detected(app):
    _seed(app)
    # bypass the ORM guard, as an attacker with DB access would
    db.session.execute(text("UPDATE agent_audit_entries SET actor='mallory' WHERE seq=2"))
    db.session.commit()
    assert journal.verify_chain(1) == (False, 2)


def test_deleting_an_entry_is_detected(app):
    _seed(app)
    db.session.execute(text("DELETE FROM agent_audit_entries WHERE seq=2"))
    db.session.commit()
    ok, bad_seq = journal.verify_chain(1)
    assert ok is False and bad_seq == 3


def test_rewriting_a_hash_still_breaks_the_next_link(app):
    _seed(app)
    db.session.execute(text("UPDATE agent_audit_entries SET entry_hash='%s' WHERE seq=1" % ("a" * 64)))
    db.session.commit()
    assert journal.verify_chain(1)[0] is False
