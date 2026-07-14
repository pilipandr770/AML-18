from pathlib import Path

from app.extensions import db
from app.sanctions.ingest import ingest_source
from app.sanctions.models import EntityNameIndex, SanctionedEntity
from app.sanctions.sources.ofac_sdn import OFACSDNSource

FIXTURES = Path(__file__).parent / "fixtures"


class _FixtureOFACSource(OFACSDNSource):
    """Same parser, but fetch() returns the local fixture instead of hitting
    the network -- keeps ingestion tests offline and deterministic."""

    def fetch(self) -> bytes:
        return (FIXTURES / "sample_sdn.xml").read_bytes()


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
