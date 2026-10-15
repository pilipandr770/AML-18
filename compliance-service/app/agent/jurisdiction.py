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
    return {"required": required, "missing": missing, "stale": stale, "ok": not missing and not stale}
