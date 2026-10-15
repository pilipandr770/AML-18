from pathlib import Path
from unittest import mock

from app.sanctions.sources.seco import SECOSource

FIXTURES = Path(__file__).parent / "fixtures"


def _records():
    source = SECOSource()
    raw = (FIXTURES / "sample_seco.xml").read_bytes()
    with mock.patch("app.sanctions.sources.seco.requests.get") as get:
        records = list(source.parse(raw))
        get.assert_not_called()
    return records


def _by_id(records, ssid):
    return next(r for r in records if r.source_entity_id == ssid)


def test_source_name():
    assert SECOSource.name == "CH_SECO"


def test_skips_delisted_and_nameless_and_dedupes_versions():
    records = _records()
    assert sorted(r.source_entity_id for r in records) == ["100", "200", "300"]


def test_person_name_assembled_from_parts_and_current_version_used():
    p = _by_id(_records(), "100")
    assert p.entity_type == "person"
    assert p.primary_name == "Anton Petrovich Testov"  # title dropped, family name last
    assert p.source == "CH_SECO"


def test_person_aliases_and_script_variants():
    p = _by_id(_records(), "100")
    assert "Tony Test" in p.aliases
    assert "Antoine Testeau" in p.aliases
    assert "Toni Testoff" in p.aliases  # non-main identity
    assert "Антон Петрович Тестов" in p.aliases  # Cyrillic spelling variants
    assert p.primary_name not in p.aliases


def test_person_details():
    p = _by_id(_records(), "100")
    assert p.date_of_birth == "1970-03-23"
    assert p.raw_record["additional_dates_of_birth"] == ["1971"]
    assert p.place_of_birth == "Faketown, Fake district, Testland"
    assert p.nationality == "Testland"
    assert p.country_of_residence == "Testland"
    assert {"type": "passport", "value": "TP1234567", "issuer": "Testland"} in p.national_ids
    assert p.addresses[0]["city"] == "Capital City"
    assert p.addresses[0]["country"] == "Testland"
    assert set(p.programs) == {"Testland", "Exampleland"}


def test_entity_and_crypto():
    e = _by_id(_records(), "200")
    assert e.entity_type == "legal_entity"
    assert e.primary_name == "Testinvest Holding Ltd"
    assert e.aliases == ["TI Holding"]
    assert e.programs == ["Exampleland"]
    assert e.addresses == [{"city": "Some Region", "country": "Exampleland"}]
    addrs = {(c["currency"], c["address"]) for c in e.crypto_addresses}
    assert ("ETH", "0x1111111111111111111111111111111111111111") in addrs
    assert any(cur == "XBT" for cur, _ in addrs)
    assert ("TRX", "TabcdefghjkmnpqrstuvwxyzABCDEFGHJK") in addrs


def test_vessel_is_legal_entity():
    v = _by_id(_records(), "300")
    assert v.entity_type == "legal_entity"
    assert v.primary_name == "Fictional Star"
    assert v.raw_record["imo"] == "1234567"
    assert v.raw_record["object_type"] == "vessel"
