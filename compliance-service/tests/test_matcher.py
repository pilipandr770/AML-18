from pathlib import Path

import pytest

from app.sanctions.ingest import ingest_source
from app.sanctions.models import SanctionedEntity
from app.sanctions.sources.ofac_sdn import OFACSDNSource
from app.screening.matcher import match_name

FIXTURES = Path(__file__).parent / "fixtures"


class _FixtureOFACSource(OFACSDNSource):
    def fetch(self) -> bytes:
        return (FIXTURES / "sample_sdn.xml").read_bytes()


@pytest.fixture
def seeded(app):
    ingest_source(_FixtureOFACSource())
    return app


def test_exact_name_match_scores_high(seeded):
    results = match_name("Ivan Ivanov")
    assert results
    top = results[0]
    ivan = SanctionedEntity.query.filter_by(source_entity_id="10001").one()
    assert top["entity_id"] == ivan.id
    assert top["name_score"] >= 95


def test_informal_alias_spelling_still_matches(seeded):
    # "Ivanoff" is the aka we ingested for the same person.
    results = match_name("Ivan Ivanoff")
    assert results
    ivan = SanctionedEntity.query.filter_by(source_entity_id="10001").one()
    assert results[0]["entity_id"] == ivan.id
    assert results[0]["name_score"] >= 95


def test_matching_is_case_insensitive(seeded):
    # rapidfuzz does NOT normalize case by default -- "ivan ivanov" vs
    # "Ivan Ivanov" scores ~55 without an explicit processor, not the ~100
    # an analyst would expect for the same name. Regression test for that.
    results = match_name("ivan ivanov")
    assert results
    ivan = SanctionedEntity.query.filter_by(source_entity_id="10001").one()
    assert results[0]["entity_id"] == ivan.id
    assert results[0]["name_score"] >= 95


def test_cyrillic_input_matches_via_transliteration(seeded):
    # Ivan Ivanov, written in Cyrillic, should still surface the same entity
    # via transliteration + phonetic blocking.
    results = match_name("Иван Иванов")
    assert results
    ivan = SanctionedEntity.query.filter_by(source_entity_id="10001").one()
    matched_ids = {r["entity_id"] for r in results}
    assert ivan.id in matched_ids


def test_unrelated_name_does_not_match(seeded):
    results = match_name("Completely Different Person")
    ivan = SanctionedEntity.query.filter_by(source_entity_id="10001").one()
    matched_ids = {r["entity_id"] for r in results}
    assert ivan.id not in matched_ids


def test_empty_name_returns_no_matches(seeded):
    assert match_name("") == []
    assert match_name(None) == []
