"""Score-band decision logic: maps a name match score + corroborating fields
to accept/review/reject, with an explicit rule_branch on every decision --
the actual BaFin-auditable "why," not a bare score.

Deliberately conservative: a name-only match, however strong, is never
sufficient to auto-reject on its own -- common-surname clustering (especially
for Slavic names) makes name-only auto-reject a real false-positive risk.
Auto-reject requires an explicit opt-in, at least two corroborating fields,
and a hit against the entity's primary/canonical name (not an aka-only hit).
"""


def corroborating_fields(party: dict, entity) -> dict:
    """Returns {field_name: matched_value} for every field shared between
    the incoming party and a candidate sanctioned entity."""
    matched = {}

    party_country = (party.get("country") or "").strip().upper()
    entity_countries = {
        (entity.nationality or "").strip().upper(),
        (entity.country_of_residence or "").strip().upper(),
    }
    entity_countries.discard("")
    if party_country and party_country in entity_countries:
        matched["country"] = party_country

    party_id_values = {nid.get("value") for nid in (party.get("national_ids") or []) if nid.get("value")}
    entity_id_values = {nid.get("value") for nid in (entity.national_ids or []) if nid.get("value")}
    overlap = party_id_values & entity_id_values
    if overlap:
        matched["national_id"] = sorted(overlap)[0]

    party_lei = party.get("lei")
    if party_lei and entity.lei and party_lei == entity.lei:
        matched["lei"] = party_lei

    party_dob = (party.get("date_of_birth") or "").strip()
    entity_dob = (getattr(entity, "date_of_birth", None) or "").strip()
    if party_dob and entity_dob and party_dob == entity_dob:
        matched["date_of_birth"] = party_dob

    return matched


def decide(name_score: float, corroborating: dict, name_type: str, config) -> dict:
    """Returns {"decision": "accepted"|"review"|"rejected", "rule_branch": str}."""
    review_threshold = config["SCREENING_REVIEW_THRESHOLD"]
    reject_threshold = config["SCREENING_REJECT_THRESHOLD"]
    auto_reject_enabled = config["SCREENING_AUTO_REJECT_EXACT_MATCH"]

    is_corroborated = len(corroborating) >= 1
    is_strongly_corroborated = len(corroborating) >= 2
    is_primary_entry = name_type == "primary"

    if name_score < review_threshold:
        return {"decision": "accepted", "rule_branch": "below_review_threshold"}

    if name_score < reject_threshold:
        if is_corroborated:
            return {"decision": "review", "rule_branch": "mid_band_corroborated"}
        return {"decision": "accepted", "rule_branch": "mid_band_uncorroborated_sampled"}

    # name_score >= reject_threshold
    if not is_corroborated:
        return {"decision": "review", "rule_branch": "high_score_uncorroborated"}

    if auto_reject_enabled and is_strongly_corroborated and is_primary_entry:
        return {"decision": "rejected", "rule_branch": "auto_reject_exact_match"}

    return {"decision": "review", "rule_branch": "high_score_corroborated_default_review"}
