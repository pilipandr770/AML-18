from pathlib import Path

from app.sanctions.sources.eu_fsf import EUFSFSource

FIXTURES = Path(__file__).parent / "fixtures"


def _records():
    source = EUFSFSource()
    raw = (FIXTURES / "sample_eu_fsf.xml").read_bytes()
    return list(source.parse(raw))


def test_parses_expected_number_of_entries():
    records = _records()
    assert len(records) == 2


def test_parses_person_entry_fields():
    records = _records()
    petr = next(r for r in records if r.source_entity_id == "EU-1001")

    assert petr.entity_type == "person"
    assert petr.primary_name == "Petr Sidorov"
    assert "Petr Sidoroff" in petr.aliases
    assert petr.date_of_birth == "1980-03-12"
    assert petr.nationality == "Russia"
    assert petr.country_of_residence == "Russia"
    assert "RUS" in petr.programs
    assert {"type": "Passport", "value": "70 1234567"} in petr.national_ids
    assert petr.lei is None
    assert petr.source == "EU_FSF"


def test_parses_legal_entity_and_extracts_lei():
    records = _records()
    corp = next(r for r in records if r.source_entity_id == "EU-1002")

    assert corp.entity_type == "legal_entity"
    assert corp.primary_name == "Testinvest Group SA"
    assert corp.lei == "213800XYZLEITESTABC1"
    assert "SDGT" in corp.programs
    assert corp.country_of_residence == "Luxembourg"
