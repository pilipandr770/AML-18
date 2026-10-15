"""Jurisdiction profiles (project.jurisdiction = US | EU). They decide which
sanctions sources must be loaded and fresh for a "clear" to be trustworthy,
and carry the legal-notice texts shown to owners.

Nothing here is a legal conclusion. Every text is configuration, marked
REQUIRES COUNSEL REVIEW, and thresholds/reporting duties are deliberately
NOT encoded: they are for the operator and their counsel to define."""

REVIEW_MARKER = "REQUIRES COUNSEL REVIEW"

PROFILES = {
    "US": {
        "label": "United States profile",
        "required_sources": ["OFAC_SDN"],
        # Screened when loaded and shown in reports, but a clear does not depend on them.
        "recommended_sources": ["OFAC_CONSOLIDATED", "UN_CONSOLIDATED", "UK_SANCTIONS_LIST"],
        "notes": [
            "Primary list: OFAC Specially Designated Nationals (SDN). Screening against it does not by itself "
            "discharge any legal obligation of the operator. " + REVIEW_MARKER + ".",
            "Reporting and recordkeeping duties (for example suspicious-activity reporting and thresholds) are "
            "not implemented or decided by this system. " + REVIEW_MARKER + ".",
        ],
    },
    "EU": {
        "label": "European Union profile",
        "required_sources": ["EU_FSF", "OFAC_SDN"],
        "recommended_sources": ["UN_CONSOLIDATED", "UK_SANCTIONS_LIST", "CH_SECO", "OFAC_CONSOLIDATED"],
        "notes": [
            "Lists: EU consolidated financial sanctions (FSF) and OFAC SDN. " + REVIEW_MARKER + ".",
            "Travel Rule and wallet-ownership obligations are handled by separate modules, not by the agent. "
            + REVIEW_MARKER + ".",
        ],
    },
}


def profile_for(jurisdiction: str | None) -> dict:
    return PROFILES.get((jurisdiction or "EU").upper(), PROFILES["EU"])


def coverage(jurisdiction: str | None, freshness: dict, max_age_days: int) -> dict:
    """Deterministic list-coverage check: required sources must exist, have
    an active snapshot, and not be older than max_age_days."""
    required = profile_for(jurisdiction)["required_sources"]
    by_source = {s["source"]: s for s in freshness.get("sources", [])}
    missing, stale = [], []
    for src in required:
        s = by_source.get(src)
        if s is None or s["age_days"] is None:
            missing.append(src)
        elif s["age_days"] > max_age_days:
            stale.append(src)
    recommended = profile_for(jurisdiction).get("recommended_sources", [])
    loaded = [s for s in by_source if by_source[s]["age_days"] is not None]
    return {
        "required": required, "missing": missing, "stale": stale, "ok": not missing and not stale,
        "loaded_sources": sorted(loaded),
        "recommended_missing": [s for s in recommended if s not in loaded],
    }
