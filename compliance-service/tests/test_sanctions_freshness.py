from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.sanctions.freshness import get_freshness
from app.sanctions.models import ListSnapshot


def _snapshot(source, status, activated_at=None, record_count=10):
    row = ListSnapshot(
        source=source,
        source_url="https://example.test/list.xml",
        content_hash="deadbeef",
        record_count=record_count,
        status=status,
        activated_at=activated_at,
    )
    db.session.add(row)
    db.session.commit()
    return row


def test_get_freshness_empty_when_no_sources_ingested(app):
    with app.app_context():
        assert get_freshness() == []


def test_get_freshness_reports_age_of_active_snapshot(app):
    with app.app_context():
        activated_at = datetime.now(timezone.utc) - timedelta(days=3)
        _snapshot("OFAC_SDN", "active", activated_at=activated_at, record_count=42)

        rows = get_freshness()

    assert len(rows) == 1
    assert rows[0]["source"] == "OFAC_SDN"
    assert rows[0]["age_days"] == 3
    assert rows[0]["record_count"] == 42


def test_get_freshness_ignores_superseded_snapshots(app):
    with app.app_context():
        old = datetime.now(timezone.utc) - timedelta(days=10)
        recent = datetime.now(timezone.utc) - timedelta(days=1)
        _snapshot("OFAC_SDN", "superseded", activated_at=old, record_count=41)
        _snapshot("OFAC_SDN", "active", activated_at=recent, record_count=42)

        rows = get_freshness()

    assert len(rows) == 1
    assert rows[0]["age_days"] == 1
    assert rows[0]["record_count"] == 42


def test_get_freshness_none_for_source_with_no_active_snapshot(app):
    with app.app_context():
        _snapshot("EU_FSF", "staged", activated_at=None, record_count=5)

        rows = get_freshness()

    assert len(rows) == 1
    assert rows[0]["source"] == "EU_FSF"
    assert rows[0]["age_days"] is None
    assert rows[0]["activated_at"] is None


def test_get_freshness_covers_multiple_sources_sorted(app):
    with app.app_context():
        now = datetime.now(timezone.utc)
        _snapshot("OFAC_SDN", "active", activated_at=now, record_count=1)
        _snapshot("EU_FSF", "active", activated_at=now, record_count=2)

        rows = get_freshness()

    assert [r["source"] for r in rows] == ["EU_FSF", "OFAC_SDN"]
