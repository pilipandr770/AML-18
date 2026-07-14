from pathlib import Path

import pytest

from app.sanctions.ingest import ingest_source
from app.sanctions.sources.ofac_sdn import OFACSDNSource
from app.screening.engine import persist_decision, screen_and_persist, screen_parties
from app.screening.models import ScreeningDecision, ScreeningMatch

FIXTURES = Path(__file__).parent / "fixtures"

CONFIG = {
    "SCREENING_REVIEW_THRESHOLD": 70,
    "SCREENING_REJECT_THRESHOLD": 85,
    "SCREENING_AUTO_REJECT_EXACT_MATCH": False,
}


class _FixtureOFACSource(OFACSDNSource):
    def fetch(self) -> bytes:
        return (FIXTURES / "sample_sdn.xml").read_bytes()


@pytest.fixture
def seeded(app):
    ingest_source(_FixtureOFACSource())
    return app


def test_clean_party_is_accepted(seeded):
    parties = [{"role": "originator", "name": "Completely Different Person", "country": "DE", "national_ids": [], "lei": None}]
    aggregate = screen_parties(parties, CONFIG)
    assert aggregate["decision"] == "accepted"
    assert aggregate["party_results"][0]["rule_branch"] == "no_candidates"


def test_uncorroborated_strong_match_goes_to_review_not_reject(seeded):
    # Name matches the sanctioned "Ivan Ivanov" exactly, but country/ID don't
    # corroborate -- must land in review, never auto-reject on name alone.
    parties = [{"role": "originator", "name": "Ivan Ivanov", "country": "DE", "national_ids": [], "lei": None}]
    aggregate = screen_parties(parties, CONFIG)
    assert aggregate["decision"] == "review"


def test_corroborated_strong_match_still_reviews_by_default(seeded):
    parties = [{
        "role": "originator",
        "name": "Ivan Ivanov",
        "country": "Russia",
        "national_ids": [{"type": "Passport", "value": "751234567"}],
        "lei": None,
    }]
    aggregate = screen_parties(parties, CONFIG)
    assert aggregate["decision"] == "review"
    result = aggregate["party_results"][0]
    assert "country" in result["corroborating"] or "national_id" in result["corroborating"]


def test_worst_case_wins_across_multiple_parties(seeded):
    parties = [
        {"role": "originator", "name": "Nobody Special", "country": "DE", "national_ids": [], "lei": None},
        {"role": "beneficiary", "name": "Ivan Ivanov", "country": "DE", "national_ids": [], "lei": None},
    ]
    aggregate = screen_parties(parties, CONFIG)
    assert aggregate["decision"] == "review"  # beneficiary hit outweighs originator's clean result


def test_persist_decision_writes_screening_decision_and_matches(seeded):
    parties = [{"role": "originator", "name": "Ivan Ivanov", "country": "Russia", "national_ids": [], "lei": None}]
    aggregate = screen_parties(parties, CONFIG)
    row = persist_decision("txn-123", aggregate, raw_request={"transaction_id": "txn-123"})

    assert row.id is not None
    assert row.transaction_id == "txn-123"
    assert row.decision == "review"

    matches = ScreeningMatch.query.filter_by(screening_decision_id=row.id).all()
    assert matches
    assert matches[0].party_role == "originator"
    assert matches[0].rule_branch != "candidate_not_selected"


def test_screen_and_persist_returns_transfer_action_and_persists(seeded):
    parties = [{"role": "originator", "name": "Completely Different Person", "country": "DE", "national_ids": [], "lei": None}]
    action = screen_and_persist("txn-456", parties, raw_request={}, config=CONFIG)

    assert action == "accepted"
    assert ScreeningDecision.query.filter_by(transaction_id="txn-456").count() == 1
