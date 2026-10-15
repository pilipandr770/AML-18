from pathlib import Path

import pytest

from app.sanctions.addresses import addresses_from_national_ids, match_address, normalize_address
from app.sanctions.ingest import ingest_source
from app.sanctions.models import SanctionedAddress
from app.sanctions.sources.ofac_sdn import OFACSDNSource

FIXTURES = Path(__file__).parent / "fixtures"


class _CryptoFixtureSource(OFACSDNSource):
    def fetch(self) -> bytes:
        return (FIXTURES / "sample_sdn_crypto.xml").read_bytes()


@pytest.fixture
def seeded(app):
    ingest_source(_CryptoFixtureSource())
    return app


def test_extracts_addresses_from_ofac_id_types():
    ids = [{"type": "Digital Currency Address - XBT", "value": " bc1qabc "}, {"type": "Passport", "value": "123"},
           {"type": "digital currency address - usdt", "value": "TXyz"}]
    assert addresses_from_national_ids(ids) == [
        {"currency": "XBT", "address": "bc1qabc"}, {"currency": "USDT", "address": "TXyz"}]


def test_evm_addresses_are_case_insensitive_others_are_not():
    mixed = "0xAbCdEf0123456789aBcDeF0123456789AbCdEf01"
    assert normalize_address(mixed) == mixed.lower()
    assert normalize_address("  TTestFixtureTronAddressxxxxxxxxxxxxx ") == "TTestFixtureTronAddressxxxxxxxxxxxxx"
    assert normalize_address("TTESTFIXTURETRONADDRESSXXXXXXXXXXXXX") != "TTestFixtureTronAddressxxxxxxxxxxxxx"


def test_ingest_stores_addresses(seeded):
    assert SanctionedAddress.query.count() == 3


def test_exact_match_each_chain(seeded):
    hit = match_address("bc1qtestfixtureaddressxxxxxxxxxxxxxxxxxx0")
    assert hit[0]["sanctioned_name"] == "Testcoin Mixer Ltd" and hit[0]["currency"] == "XBT"
    assert match_address("0xabcdef0123456789abcdef0123456789abcdef01")[0]["currency"] == "ETH"  # different casing
    assert match_address("TTestFixtureTronAddressxxxxxxxxxxxxx")[0]["source"] == "OFAC_SDN"


def test_near_miss_and_unknown_do_not_match(seeded):
    assert match_address("bc1qtestfixtureaddressxxxxxxxxxxxxxxxxxx1") == []
    assert match_address("") == []
    assert match_address("0x0000000000000000000000000000000000000000") == []


def test_superseded_snapshot_addresses_are_not_matched(seeded):
    # a new snapshot without the entity's addresses should drop them from matching
    class _Empty(OFACSDNSource):
        def fetch(self):
            return (FIXTURES / "sample_sdn.xml").read_bytes()

    ingest_source(_Empty())
    assert match_address("bc1qtestfixtureaddressxxxxxxxxxxxxxxxxxx0") == []


def test_check_address_endpoint(seeded, client, auth_headers):
    r = client.post("/screening/check-address", json={"address": "0xABCDEF0123456789ABCDEF0123456789ABCDEF01"}, headers=auth_headers)
    body = r.get_json()
    assert r.status_code == 200 and body["listed"] is True and body["decision"] == "rejected"
    assert body["matches"][0]["sanctioned_name"] == "Testcoin Mixer Ltd"
    clean = client.post("/screening/check-address", json={"address": "0x1111111111111111111111111111111111111111"}, headers=auth_headers)
    assert clean.get_json() == {"listed": False, "decision": "accepted", "matches": []}


def test_check_address_requires_key_and_valid_body(client, auth_headers):
    assert client.post("/screening/check-address", json={"address": "x"}).status_code == 401
    assert client.post("/screening/check-address", json={}, headers=auth_headers).status_code == 400
