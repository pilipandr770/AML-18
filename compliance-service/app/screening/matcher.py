"""rapidfuzz scoring over a phonetic-blocked shortlist.

Two-stage design: (1) blocking -- pull only the candidates sharing a
phonetic key with the query name (or one of its transliteration variants),
keeping the scored set small regardless of list size, both to stay well
inside Envoy's 30s webhook timeout and to control false-positive noise;
(2) scoring -- rapidfuzz over just that shortlist.
"""

from rapidfuzz import fuzz, utils as rf_utils

from app.sanctions.models import EntityNameIndex, SanctionedEntity
from app.sanctions.normalize import phonetic_keys as name_phonetic_keys, significant_tokens
from app.screening.transliterate import transliterate_variants


def _query_variants(name: str) -> list:
    variants = [name] + transliterate_variants(name)
    # De-duplicate while preserving order.
    seen = set()
    out = []
    for v in variants:
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out


def name_score(query: str, candidate: str) -> float:
    """Similarity of two names (0-100) over their significant tokens
    (legal-form suffixes and particles dropped, order-insensitive).

    Deliberately NOT rapidfuzz's WRatio: its partial-match mode scores any
    name that merely contains a short string highly, so a one-word alias
    like "John" or "MARIA" matched every "John ..." / "Maria ..." at 90 and
    flooded reviewers. Here a subset of tokens only counts (at 90% weight)
    when at least two tokens are shared, so "Saddam Hussein" still finds
    "Saddam Hussein Al-Tikriti" but "John Smith" does not find "John"."""
    qt = significant_tokens(query)
    ct = significant_tokens(candidate)
    if not qt or not ct:
        return 0.0
    q, c = " ".join(qt), " ".join(ct)
    score = fuzz.token_sort_ratio(q, c, processor=rf_utils.default_process)
    if min(len(set(qt)), len(set(ct))) >= 2:
        score = max(score, 0.9 * fuzz.token_set_ratio(q, c, processor=rf_utils.default_process))
    return float(score)


def candidate_shortlist(name: str):
    """EntityNameIndex rows (of active entities only) sharing a phonetic key
    with the query name or any of its transliteration variants."""
    phonetic_keys = set()
    for v in _query_variants(name):
        phonetic_keys |= name_phonetic_keys(v)
    if not phonetic_keys:
        return []

    return (
        EntityNameIndex.query
        .join(SanctionedEntity, EntityNameIndex.entity_id == SanctionedEntity.id)
        .filter(EntityNameIndex.phonetic_key.in_(phonetic_keys))
        .filter(SanctionedEntity.is_active.is_(True))
        .all()
    )


def match_name(name: str, top_n: int = 5) -> list:
    """Returns up to top_n best-scoring candidates for a query name, one
    entry per distinct entity (its single best-scoring name variant), sorted
    by score descending: [{"entity_id", "sanctioned_name", "query_variant",
    "name_score", "name_type"}]. `name_type` ("primary"/"aka"/
    "transliteration") reflects which name row produced the winning score --
    the decision engine treats a hit against the canonical name differently
    from a hit against an obscure alias."""
    name = (name or "").strip()
    if not name:
        return []

    query_variants = _query_variants(name)
    shortlist = candidate_shortlist(name)

    best_per_entity = {}
    for row in shortlist:
        best_score = 0.0
        best_variant = None
        for qv in query_variants:
            # rapidfuzz does NOT normalize case/punctuation by default --
            # "Abu Abbas" vs "Abu ABBAS" scores ~55 without this, not the
            # ~100 an analyst would expect for what is obviously the same
            # name. `default_process` (lowercase + strip non-alphanumeric +
            # collapse whitespace) is rapidfuzz's own recommended fix.
            score = name_score(qv, row.name_text)
            if score > best_score:
                best_score = score
                best_variant = qv

        existing = best_per_entity.get(row.entity_id)
        if existing is None or best_score > existing["name_score"]:
            best_per_entity[row.entity_id] = {
                "entity_id": row.entity_id,
                "sanctioned_name": row.name_text,
                "query_variant": best_variant,
                "name_score": best_score,
                "name_type": row.name_type,
            }

    ranked = sorted(best_per_entity.values(), key=lambda r: r["name_score"], reverse=True)
    return ranked[:top_n]
