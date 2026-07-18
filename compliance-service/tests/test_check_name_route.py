from pathlib import Path

import pytest

from app.sanctions.ingest import ingest_source
from app.sanctions.models import SanctionedEntity
from app.sanctions.sources.ofac_sdn import OFACSDNSource

FIXTURES = Path(__file__).parent / "fixtures"


class _FixtureOFACSource(OFACSDNSource):
    def fetch(self) -> bytes:
        return (FIXTURES / "sample_sdn.xml").read_bytes()


@pytest.fixture
def seeded(app):
    ingest_source(_FixtureOFACSource())
    return app


def test_check_name_requires_api_key(client):
    resp = client.post("/screening/check-name", json={"name": "Ivan Ivanov"})
    assert resp.status_code == 401


def test_check_name_rejects_bad_body(client, auth_headers):
    resp = client.post("/screening/check-name", json={}, headers=auth_headers)
    assert resp.status_code == 400


def test_check_name_no_match_is_accepted(client, auth_headers, seeded):
    resp = client.post(
        "/screening/check-name",
        json={"name": "Completely Different Person"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["decision"] == "accepted"
    assert data["score"] == 0.0
    assert data["matches"] == []


def test_check_name_strong_match_goes_to_review(client, auth_headers, seeded):
    ivan = SanctionedEntity.query.filter_by(source_entity_id="10001").one()

    resp = client.post(
        "/screening/check-name",
        json={"name": "Ivan Ivanov", "country": ivan.nationality},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["decision"] == "review"
    assert data["score"] >= 95
    assert data["matches"]
    top = data["matches"][0]
    assert top["entity_id"] == ivan.id
    assert top["corroborating_fields"].get("country") == ivan.nationality.upper()


def test_check_name_date_of_birth_counts_as_corroboration(client, auth_headers, seeded):
    ivan = SanctionedEntity.query.filter_by(source_entity_id="10001").one()
    assert ivan.date_of_birth, "fixture must carry a DOB for this test to be meaningful"

    resp = client.post(
        "/screening/check-name",
        json={"name": "Ivan Ivanov", "date_of_birth": ivan.date_of_birth},
        headers=auth_headers,
    )
    data = resp.get_json()
    assert data["matches"][0]["corroborating_fields"].get("date_of_birth") == ivan.date_of_birth
