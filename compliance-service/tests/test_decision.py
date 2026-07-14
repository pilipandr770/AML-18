import pytest

from app.screening.decision import corroborating_fields, decide


class _FakeEntity:
    def __init__(self, nationality=None, country_of_residence=None, national_ids=None, lei=None):
        self.nationality = nationality
        self.country_of_residence = country_of_residence
        self.national_ids = national_ids or []
        self.lei = lei


CONFIG = {
    "SCREENING_REVIEW_THRESHOLD": 70,
    "SCREENING_REJECT_THRESHOLD": 85,
    "SCREENING_AUTO_REJECT_EXACT_MATCH": False,
}


def _config(**overrides):
    return {**CONFIG, **overrides}


# --- corroborating_fields ---------------------------------------------


def test_corroborating_fields_matches_country():
    party = {"country": "ru", "national_ids": [], "lei": None}
    entity = _FakeEntity(nationality="RU")
    assert corroborating_fields(party, entity) == {"country": "RU"}


def test_corroborating_fields_matches_national_id():
    party = {"country": None, "national_ids": [{"type": "Passport", "value": "12345"}], "lei": None}
    entity = _FakeEntity(national_ids=[{"type": "Passport", "value": "12345"}])
    assert corroborating_fields(party, entity)["national_id"] == "12345"


def test_corroborating_fields_matches_lei():
    party = {"country": None, "national_ids": [], "lei": "ABC123"}
    entity = _FakeEntity(lei="ABC123")
    assert corroborating_fields(party, entity) == {"lei": "ABC123"}


def test_corroborating_fields_empty_when_nothing_matches():
    party = {"country": "US", "national_ids": [{"type": "SSN", "value": "1"}], "lei": None}
    entity = _FakeEntity(nationality="RU", national_ids=[{"type": "Passport", "value": "2"}])
    assert corroborating_fields(party, entity) == {}


# --- decide: the full band table ---------------------------------------


def test_below_review_threshold_always_accepted():
    result = decide(name_score=50, corroborating={"country": "RU"}, name_type="primary", config=_config())
    assert result == {"decision": "accepted", "rule_branch": "below_review_threshold"}


def test_mid_band_uncorroborated_is_accepted_and_sampled():
    result = decide(name_score=75, corroborating={}, name_type="primary", config=_config())
    assert result["decision"] == "accepted"
    assert result["rule_branch"] == "mid_band_uncorroborated_sampled"


def test_mid_band_corroborated_goes_to_review():
    result = decide(name_score=75, corroborating={"country": "RU"}, name_type="primary", config=_config())
    assert result["decision"] == "review"
    assert result["rule_branch"] == "mid_band_corroborated"


def test_high_score_uncorroborated_goes_to_review_not_reject():
    # Deliberately conservative: name alone, however strong, never auto-rejects.
    result = decide(name_score=99, corroborating={}, name_type="primary", config=_config())
    assert result["decision"] == "review"
    assert result["rule_branch"] == "high_score_uncorroborated"


def test_high_score_single_corroboration_defaults_to_review():
    result = decide(
        name_score=95, corroborating={"country": "RU"}, name_type="primary", config=_config()
    )
    assert result["decision"] == "review"
    assert result["rule_branch"] == "high_score_corroborated_default_review"


def test_auto_reject_disabled_by_default_even_with_strong_corroboration():
    result = decide(
        name_score=95,
        corroborating={"country": "RU", "national_id": "123"},
        name_type="primary",
        config=_config(),  # auto-reject off by default
    )
    assert result["decision"] == "review"


def test_auto_reject_requires_opt_in_and_two_fields_and_primary_entry():
    config = _config(SCREENING_AUTO_REJECT_EXACT_MATCH=True)

    # All conditions met -> rejected.
    result = decide(
        name_score=95,
        corroborating={"country": "RU", "national_id": "123"},
        name_type="primary",
        config=config,
    )
    assert result == {"decision": "rejected", "rule_branch": "auto_reject_exact_match"}

    # Opted in but only one corroborating field -> still review.
    result = decide(
        name_score=95, corroborating={"country": "RU"}, name_type="primary", config=config
    )
    assert result["decision"] == "review"

    # Opted in, two fields, but only an aka/transliteration match -> still review.
    result = decide(
        name_score=95,
        corroborating={"country": "RU", "national_id": "123"},
        name_type="aka",
        config=config,
    )
    assert result["decision"] == "review"
