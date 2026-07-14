"""Turns a NormalizedRecord's names into the set of EntityNameIndex rows to
store: the primary name, each alias, and -- for any of those containing
Cyrillic characters -- their Latin transliteration variants, each with a
precomputed phonetic blocking key.
"""

import jellyfish

from app.screening.transliterate import transliterate_variants


def _phonetic_key(name: str) -> str:
    # NYSIIS is designed for single surnames. IVMS101/sanctions names arrive
    # as "forename surname" (or a bare legal entity name); using the last
    # token as the blocking key mirrors how surname-based AML screening
    # conventionally blocks (given name is a corroborating signal during
    # scoring, not part of the blocking key).
    tokens = name.split()
    surname_token = tokens[-1] if tokens else name
    try:
        return jellyfish.nysiis(surname_token) or ""
    except Exception:
        return ""


def name_variants(record) -> list:
    """Returns a de-duplicated list of
    {"name_text", "name_type", "phonetic_key"} dicts for a NormalizedRecord,
    ready to become EntityNameIndex rows."""
    seen = set()
    variants = []

    def add(name: str, name_type: str):
        name = (name or "").strip()
        if not name:
            return
        key = (name.lower(), name_type)
        if key in seen:
            return
        seen.add(key)
        variants.append({
            "name_text": name,
            "name_type": name_type,
            "phonetic_key": _phonetic_key(name),
        })

        for translit in transliterate_variants(name):
            tkey = (translit.lower(), "transliteration")
            if tkey in seen:
                continue
            seen.add(tkey)
            variants.append({
                "name_text": translit,
                "name_type": "transliteration",
                "phonetic_key": _phonetic_key(translit),
            })

    add(record.primary_name, "primary")
    for alias in record.aliases:
        add(alias, "aka")

    return variants
