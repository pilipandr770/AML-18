from pathlib import Path

import pytest

from app.extensions import db
from app.sanctions import ingest as ingest_module
from app.sanctions.ingest import ingest_all, ingest_source
from app.sanctions.models import ListSnapshot, SanctionedEntity, EntityNameIndex
from app.sanctions.sources.ofac_sdn import OFACSDNSource

FIXTURES = Path(__file__).parent / "fixtures"


class _FixtureOFACSource(OFACSDNSource):
    """Same parser, but fetch() returns the local fixture instead of hitting
    the network -- keeps ingestion tests offline and deterministic."""

    def fetch(self) -> bytes:
        return (FIXTURES / "sample_sdn.xml").read_bytes()


class _UnreachableSource(OFACSDNSource):
    name = "TEST_UNREACHABLE"

    def fetch(self) -> bytes:
        raise ConnectionError("simulated network failure")


def test_ingest_source_creates_snapshot_and_entities(app):
    snapshot = ingest_source(_FixtureOFACSource())

    assert snapshot.status == "active"
    assert snapshot.record_count == 2
    assert snapshot.source == "OFAC_SDN"

    entities = SanctionedEntity.query.filter_by(list_snapshot_id=snapshot.id).all()
    assert len(entities) == 2
    assert all(e.is_active for e in entities)

    ivan = next(e for e in entities if e.source_entity_id == "10001")
    names = EntityNameIndex.query.filter_by(entity_id=ivan.id).all()
    name_texts = {n.name_text for n in names}
    assert "Ivan Ivanov" in name_texts
    assert "Ivan Ivanoff" in name_texts


def test_ingest_source_is_idempotent_on_unchanged_content(app):
    first = ingest_source(_FixtureOFACSource())
    second = ingest_source(_FixtureOFACSource())

    assert first.id == second.id
    assert SanctionedEntity.query.count() == 2  # not duplicated


def test_ingest_source_supersedes_previous_snapshot_on_change(app):
    first = ingest_source(_FixtureOFACSource())

    class _ChangedSource(_FixtureOFACSource):
        def fetch(self) -> bytes:
            raw = (FIXTURES / "sample_sdn.xml").read_bytes()
            return raw + b"<!-- force a different content hash -->"

    second = ingest_source(_ChangedSource())

    assert second.id != first.id

    db.session.refresh(first)
    assert first.status == "superseded"
    assert second.status == "active"

    old_entities = SanctionedEntity.query.filter_by(list_snapshot_id=first.id).all()
    assert old_entities
    assert all(not e.is_active for e in old_entities)


def test_ingest_source_records_failed_snapshot_on_fetch_error(app):
    with pytest.raises(ConnectionError):
        ingest_source(_UnreachableSource())

    snapshot = ListSnapshot.query.filter_by(source="TEST_UNREACHABLE").one()
    assert snapshot.status == "failed"
    assert "simulated network failure" in snapshot.error_detail
    assert snapshot.content_hash == ""


def test_ingest_all_continues_past_an_unreachable_source(app, monkeypatch):
    monkeypatch.setattr(
        ingest_module, "REGISTERED_SOURCES", [_UnreachableSource, _FixtureOFACSource]
    )

    results = ingest_all()

    assert len(results) == 1
    assert results[0].source == "OFAC_SDN"
    assert results[0].status == "active"

    failed = ListSnapshot.query.filter_by(source="TEST_UNREACHABLE").one()
    assert failed.status == "failed"
