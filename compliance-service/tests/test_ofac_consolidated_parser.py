from pathlib import Path
from unittest.mock import patch

from app.sanctions.sources.ofac_consolidated import OFACConsolidatedSource

FIXTURES = Path(__file__).parent / "fixtures"


def _records():
    raw = (FIXTURES / "sample_ofac_consolidated.xml").read_bytes()
    return list(OFACConsolidatedSource().parse(raw))


def test_skips_nameless_entry():
    records = _records()
    assert [r.source_entity_id for r in records] == ["900001", "900002"]


def test_person_fields():
    p = _records()[0]
    assert p.source == "OFAC_CONSOLIDATED"
    assert p.entity_type == "person"
    assert p.primary_name == "Anna TESTOVA"
    assert "Anya TESTOVA-X" in p.aliases
    assert p.date_of_birth == "1960"
    assert p.place_of_birth == "Fictoria"
    assert p.programs == ["NS-TEST"]
    assert p.addresses == [{"city": "Faketown", "country": "Fictoria"}]


def test_entity_fields():
    e = _records()[1]
    assert e.entity_type == "legal_entity"
    assert e.primary_name == "FAKE HOLDINGS JSC"
    assert {"type": "Registration ID", "value": "REG-0001"} in e.national_ids


def test_parse_does_not_fetch():
    with patch("requests.get") as get:
        _records()
    get.assert_not_called()
    assert OFACConsolidatedSource.name == "OFAC_CONSOLIDATED"
    assert OFACConsolidatedSource.source_url.endswith("/consolidated.xml")
