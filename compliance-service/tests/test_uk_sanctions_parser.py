from pathlib import Path
from unittest.mock import patch

import pytest

from app.sanctions.sources.uk_sanctions import UKSanctionsListSource

FIXTURES = Path(__file__).parent / "fixtures"


def _records():
    source = UKSanctionsListSource()
    raw = (FIXTURES / "sample_uk_sanctions.xml").read_bytes()
    with patch("requests.get", side_effect=AssertionError("network must not be used")):
        return list(source.parse(raw))


def _by_id(records, entity_id):
    return next(r for r in records if r.source_entity_id == entity_id)


def test_source_metadata():
    assert UKSanctionsListSource.name == "UK_SANCTIONS_LIST"
    assert "sanctionslist.fcdo.gov.uk" in UKSanctionsListSource.source_url


def test_dedup_and_nameless_skipped():
    records = _records()
    # 5 designations: TST0005 has no name, TST0004 duplicates group 90002
    assert sorted(r.source_entity_id for r in records) == ["90001", "90002", "TST0003"]


def test_person_fields():
    p = _by_id(_records(), "90001")
    assert p.source == "UK_SANCTIONS_LIST"
    assert p.entity_type == "person"
    assert p.primary_name == "Petr Ivanovich SIDOROV"
    assert "Petr Sidoroff" in p.aliases
    assert "SIDOROV Petr" in p.aliases
    assert "Пётр Сидоров" in p.aliases
    assert p.primary_name not in p.aliases
    assert p.date_of_birth == "1980-03-12"
    assert p.nationality == "Testland"
    assert p.place_of_birth == "Testgrad, Testland"
    assert p.country_of_residence == "Testland"
    assert p.addresses == [{"city": "Testgrad", "country": "Testland"}]
    assert p.national_ids.count({"type": "Passport", "value": "TP1234567"}) == 1
    assert {"type": "National ID", "value": "NID-555"} in p.national_ids
    assert p.programs == ["The Testland (Sanctions) Regulations 2020"]
    assert p.crypto_addresses == []


def test_entity_merged_across_regimes_with_crypto():
    e = _by_id(_records(), "90002")
    assert e.entity_type == "legal_entity"
    assert e.primary_name == "Testinvest Group SA"
    assert {"TIG Holdings", "Testinvest Holdings"} <= set(e.aliases)
    assert len(e.programs) == 2
    assert {"type": "Business Registration Number", "value": "REG 998877 (Testland)"} in e.national_ids
    assert {"currency": "ETH", "address": "0x" + "1" * 40} in e.crypto_addresses
    assert {"currency": "XBT", "address": "1FictionalBtcAddressForTestsOnly1234"} in e.crypto_addresses


def test_ship_is_legal_entity_with_imo():
    s = _by_id(_records(), "TST0003")
    assert s.entity_type == "legal_entity"
    assert s.primary_name == "Fictional Star"
    assert {"type": "IMO Number", "value": "IMO0000001"} in s.national_ids


def test_rejects_xml_entity_expansion():
    evil = b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "x">]><Designations>&a;</Designations>'
    with pytest.raises(Exception):
        list(UKSanctionsListSource().parse(evil))
