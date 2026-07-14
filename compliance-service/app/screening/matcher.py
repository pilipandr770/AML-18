"""rapidfuzz scoring over a phonetic-blocked shortlist.

Two-stage design: (1) blocking -- pull only the candidates sharing a
phonetic key with the query name (or one of its transliteration variants),
keeping the scored set small regardless of list size, both to stay well
inside Envoy's 30s webhook timeout and to control false-positive noise;
(2) scoring -- rapidfuzz over just that shortlist.
"""

import jellyfish
from rapidfuzz import fuzz, utils as rf_utils

from app.sanctions.models import EntityNameIndex, SanctionedEntity
from app.screening.transliterate import transliterate_variants


def _phonetic_key(name: str) -> str:
    tokens = name.split()
    surname_token = tokens[-1] if tokens else name
    try:
        return jellyfish.nysiis(surname_token) or ""
    except Exception:
        return ""


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


def candidate_shortlist(name: str):
    """EntityNameIndex rows (of active entities only) sharing a phonetic key
    with the query name or any of its transliteration variants."""
    phonetic_keys = {_phonetic_key(v) for v in _query_variants(name)}
    phonetic_keys.discard("")
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
            score = fuzz.WRatio(qv, row.name_text, processor=rf_utils.default_process)
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
