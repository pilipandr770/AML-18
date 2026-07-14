from pathlib import Path

from app.sanctions.sources.ofac_sdn import OFACSDNSource

FIXTURES = Path(__file__).parent / "fixtures"


def _records():
    source = OFACSDNSource()
    raw = (FIXTURES / "sample_sdn.xml").read_bytes()
    return list(source.parse(raw))


def test_parses_expected_number_of_entries():
    records = _records()
    assert len(records) == 2


def test_parses_individual_entry_fields():
    records = _records()
    ivan = next(r for r in records if r.source_entity_id == "10001")

    assert ivan.entity_type == "person"
    assert ivan.primary_name == "Ivan Ivanov"
    assert "Ivan Ivanoff" in ivan.aliases
    assert ivan.date_of_birth == "15 Jan 1975"
    assert ivan.place_of_birth == "Moscow, Russia"
    assert ivan.nationality == "Russia"
    assert ivan.country_of_residence == "Russia"
    assert "UKRAINE-EO13662" in ivan.programs
    assert {"type": "Passport", "value": "751234567"} in ivan.national_ids
    assert ivan.lei is None
    assert ivan.source == "OFAC_SDN"


def test_parses_entity_entry_and_extracts_lei():
    records = _records()
    corp = next(r for r in records if r.source_entity_id == "10002")

    assert corp.entity_type == "legal_entity"
    assert corp.primary_name == "Testcorp Holdings Ltd"
    assert corp.lei == "549300ABCDEF1234GH56"
    assert "SDGT" in corp.programs
    assert corp.country_of_residence == "United Kingdom"


def test_parser_is_namespace_agnostic():
    # Re-parse with the OLD pre-2024 namespace to prove we don't hardcode
    # the current namespace URI (OFAC has changed it before).
    source = OFACSDNSource()
    raw = (FIXTURES / "sample_sdn.xml").read_text(encoding="utf-8")
    old_ns_raw = raw.replace(
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML",
        "http://tempuri.org/sdnList.xsd",
    ).encode("utf-8")

    records = list(source.parse(old_ns_raw))
    assert len(records) == 2
    assert records[0].primary_name == "Ivan Ivanov"
