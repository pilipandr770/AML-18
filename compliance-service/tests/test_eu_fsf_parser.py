from pathlib import Path

from app.sanctions.sources.eu_fsf import EUFSFSource, _is_lei

FIXTURES = Path(__file__).parent / "fixtures"


def _records():
    source = EUFSFSource()
    raw = (FIXTURES / "sample_eu_fsf.xml").read_bytes()
    return list(source.parse(raw))


def test_parses_expected_number_of_entries():
    assert len(_records()) == 2


def test_parses_person_entry_fields():
    petr = next(r for r in _records() if r.source_entity_id == "9001")

    assert petr.entity_type == "person"
    assert petr.primary_name == "Petr Sidorov"
    # distinct names only; wholeName empty -> built from first/middle/last;
    # case-insensitive duplicate of the primary dropped
    assert petr.aliases == ["Petr Sidoroff", "Pyotr Ivanovich Sidorov"]
    assert petr.date_of_birth == "1980-03-12"  # full date preferred over the earlier year-only one
    assert [b["date"] for b in petr.raw_record["birthdates"]] == ["1980", "1980-03-12"]
    assert petr.place_of_birth == "Springfield, RUSSIAN FEDERATION"
    assert petr.nationality == "RUSSIAN FEDERATION"
    assert petr.raw_record["nationalities"] == ["RUSSIAN FEDERATION", "BELARUS"]
    assert petr.country_of_residence == "RUSSIAN FEDERATION"
    assert petr.programs == ["TST", "998/2026 (OJ L2)"]  # empty programme falls back to numberTitle
    assert {"type": "National passport", "value": "70 1234567", "country": "RUSSIAN FEDERATION"} in petr.national_ids
    assert petr.addresses[0]["street"] == "1 Fictional Street"
    assert petr.addresses[0]["city"] == "Moscow"
    assert petr.lei is None
    assert petr.source == "EU_FSF"


def test_parses_enterprise_and_detects_lei_by_checksum():
    corp = next(r for r in _records() if r.source_entity_id == "9002")

    assert corp.entity_type == "legal_entity"
    assert corp.primary_name == "Testinvest Group SA"
    assert corp.lei == "5299000TESTFIX000116"
    assert len(corp.national_ids) == 2  # the LEI is also kept as an identification
    assert corp.programs == ["TST2"]
    assert corp.country_of_residence == "LUXEMBOURG"


def test_is_lei_rejects_bad_checksum_and_shape():
    assert _is_lei("5299000TESTFIX000116")
    assert not _is_lei("5299000TESTFIX000117")
    assert not _is_lei("B123456")


def test_download_uses_public_token_and_override():
    assert EUFSFSource().source_url.endswith("?token=dG9rZW4tMjAxNw")
    assert EUFSFSource(token="abc").source_url.endswith("?token=abc")
