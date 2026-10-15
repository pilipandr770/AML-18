from pathlib import Path

import pytest

from app.sanctions.sources import canada_sema
from app.sanctions.sources.canada_sema import CanadaSEMASource

FIXTURES = Path(__file__).parent / "fixtures"


def _records():
    raw = (FIXTURES / "sample_canada_sema.xml").read_bytes()
    return {r.source_entity_id: r for r in CanadaSEMASource().parse(raw)}


def test_nameless_record_skipped_and_ids_are_composite():
    records = _records()
    assert len(records) == 4
    assert "Examplestan|1, Part 1|1" in records
    assert "Otherland||2" not in records


def test_person_fields_and_aliases():
    r = _records()["Examplestan|1, Part 1|1"]
    assert r.source == "CA_SEMA"
    assert r.entity_type == "person"
    assert r.primary_name == "Ivan Fictivovich Testov"
    assert r.aliases == ["Ivan Testoff", "Иван Тестов", "Ivan Testov"]
    assert r.date_of_birth == "1970-01-02 or 1971"
    assert r.programs == ["SEMA - Examplestan (Schedule 1, Part 1)"]


def test_entity_alias_keeps_legal_suffix():
    r = _records()["Examplestan|1, Part 2|1"]
    assert r.entity_type == "legal_entity"
    assert r.primary_name == "Fictional Holdings Ltd"
    assert r.aliases == ["Fiktiv Holding, Co., Ltd", "FH Group"]
    assert r.date_of_birth is None


def test_vessel_has_imo_and_no_dob():
    r = _records()["Examplestan|1, Part 2|2"]
    assert r.entity_type == "legal_entity"
    assert {"type": "IMO Number", "value": "9999999"} in r.national_ids
    assert r.date_of_birth is None
    assert r.raw_record["build_date"] == "2001"


def test_non_numeric_imo_field_treated_as_alias():
    r = _records()["Otherland||1"]
    assert r.entity_type == "person"
    assert r.national_ids == []
    assert r.aliases == ["آنا ناموجود"]
    assert r.programs == ["SEMA - Otherland"]


def test_parse_does_not_fetch(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(canada_sema.requests, "get", boom)
    assert list(CanadaSEMASource().parse((FIXTURES / "sample_canada_sema.xml").read_bytes()))


def test_rejects_malicious_entities():
    evil = b'<!DOCTYPE d [<!ENTITY x "boom">]><data-set><record>&x;</record></data-set>'
    with pytest.raises(Exception):
        list(CanadaSEMASource().parse(evil))
