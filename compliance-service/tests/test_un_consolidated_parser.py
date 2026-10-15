from pathlib import Path
from unittest.mock import patch

from app.sanctions.sources.un_consolidated import UNConsolidatedSource

FIXTURES = Path(__file__).parent / "fixtures"


def _records():
    raw = (FIXTURES / "sample_un_consolidated.xml").read_bytes()
    return {r.source_entity_id: r for r in UNConsolidatedSource().parse(raw)}


def test_skips_nameless_and_counts():
    assert sorted(_records()) == ["990001", "990002", "990101"]


def test_individual_fields():
    p = _records()["990001"]
    assert p.source == "UN_CONSOLIDATED"
    assert p.entity_type == "person"
    assert p.primary_name == "TESTA EXAMPLOV FICTIVE"
    assert "TESTA EXAMPLOFF" in p.aliases and "T. Examplov" in p.aliases
    assert "ТЕСТА ЭКЗАМПЛОВ" in p.aliases
    assert "" not in p.aliases
    assert p.date_of_birth == "1970-05-17"  # first usable DOB
    assert p.place_of_birth == "Oldtown, Fictoria"
    assert p.nationality == "Fictoria"
    assert p.country_of_residence == "Fictoria"
    assert p.national_ids == [{"type": "Passport", "value": "P1234567"}]
    assert p.addresses == [{"city": "Faketown", "country": "Fictoria"}]
    assert p.programs == ["Testland"]
    assert p.raw_record["reference_number"] == "TLi.001"


def test_between_year_dob():
    assert _records()["990002"].date_of_birth == "1973 to 1974"


def test_entity_fields():
    e = _records()["990101"]
    assert e.entity_type == "legal_entity"
    assert e.primary_name == "Fictional Front Organisation"
    assert e.aliases == ["FFO"]
    assert e.programs == ["Otherland"]
    assert e.country_of_residence == "Fictoria"


def test_parse_does_not_fetch():
    with patch("requests.get") as get:
        _records()
    get.assert_not_called()
