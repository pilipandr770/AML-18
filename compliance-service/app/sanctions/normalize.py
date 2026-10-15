"""Turns a NormalizedRecord's names into the set of EntityNameIndex rows to
store: the primary name, each alias, and -- for any of those containing
Cyrillic characters -- their Latin transliteration variants, each with a
precomputed phonetic blocking key.
"""

import jellyfish

from app.screening.transliterate import transliterate_variants


# Bump when the blocking logic changes: it is mixed into each list's content
# hash (see ingest.py) so every list is re-indexed on its next refresh.
INDEX_VERSION = "3"

# Legal-form and generic corporate tokens that must not decide blocking:
# "Coral Energy PTE Ltd" has to be found from "Coral Energy".
_LEGAL_SUFFIXES = {
    "ltd", "limited", "llc", "l.l.c", "inc", "incorporated", "corp", "corporation", "co", "company", "plc",
    "pte", "pvt", "gmbh", "ag", "sa", "sarl", "srl", "spa", "bv", "nv", "ab", "as", "oy", "kg", "ug", "se",
    "jsc", "ojsc", "pjsc", "cjsc", "oao", "zao", "ooo", "llp", "lp", "fze", "fzco", "fzc", "dmcc", "sdn", "bhd",
    "ltda", "sas", "eurl", "jv", "pty", "the", "of", "and", "al", "el", "bin", "ibn", "abu", "de", "van", "von",
    # generic business words: "Acme Trading Ltd" must not match every "... Trading" entry
    "trading", "trade", "group", "holding", "holdings", "international", "intl", "general", "global", "services",
    "service", "industries", "industrial", "enterprises", "enterprise", "commercial", "investment", "investments",
    "technology", "technologies", "consulting", "solutions", "import", "export", "imp", "exp", "bank",
}


def significant_tokens(name: str) -> list:
    raw = "".join(c if c.isalnum() else " " for c in (name or "").lower()).split()
    return [t for t in raw if len(t) > 1 and t not in _LEGAL_SUFFIXES] or raw


def phonetic_keys(name: str) -> set:
    """NYSIIS keys of the first and last significant tokens. Last token is
    the surname in "forename surname" order; first token covers surname-first
    lists and reversed input ("Hussein Saddam"). Legal-form suffixes and
    particles are ignored so company names block on their distinctive words."""
    tokens = significant_tokens(name)
    keys = set()
    for t in {tokens[0], tokens[-1]} if tokens else set():
        try:
            k = jellyfish.nysiis(t)
        except Exception:
            k = ""
        if k:
            keys.add(k)
    return keys


def _phonetic_key(name: str) -> str:  # kept for callers that need a single deterministic key
    keys = sorted(phonetic_keys(name))
    return keys[-1] if keys else ""


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
        for pk in sorted(phonetic_keys(name)) or [""]:
            variants.append({"name_text": name, "name_type": name_type, "phonetic_key": pk})

        for translit in transliterate_variants(name):
            tkey = (translit.lower(), "transliteration")
            if tkey in seen:
                continue
            seen.add(tkey)
            for pk in sorted(phonetic_keys(translit)) or [""]:
                variants.append({"name_text": translit, "name_type": "transliteration", "phonetic_key": pk})

    add(record.primary_name, "primary")
    for alias in record.aliases:
        add(alias, "aka")

    return variants
