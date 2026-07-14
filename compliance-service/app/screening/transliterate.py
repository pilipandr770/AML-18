"""Cyrillic -> Latin transliteration variant generation for name screening.

Not a formal linguistic implementation -- a pragmatic set of heuristics
covering the Russian Cyrillic alphabet, aimed at generating the handful of
spellings a real transliterated name is actually likely to appear as. Ukrainian
and Belarusian-specific letters are out of scope for v1.

Deliberately NOT using Beider-Morse Phonetic Matching (BMPM): its only mature
Python implementation (`abydos`) is GPLv3+, which conflicts with this
project's "any small CASP can self-host this for free" goal the same way
OpenSanctions' NC license does. Instead, this module generates a handful of
explicit candidate spellings, and phonetic blocking (see matcher.py, using
the MIT-licensed `jellyfish`) runs on each of those -- it only needs to
absorb ordinary spelling noise within one transliteration, not the
Cyrillic-to-Latin variance itself.
"""

import re

_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")

# ICAO Doc 9303 (the standard used on modern Russian international
# passports / MRZ lines).
_ICAO_9303 = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "ie", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}

# GOST 7.79 System B (older Russian standard) -- differs from ICAO on
# several letters, giving a genuinely distinct second candidate spelling
# rather than a near-duplicate of the ICAO one.
_GOST_7_79B = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "c", "ч": "ch", "ш": "sh", "щ": "shh",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "ju", "я": "ja",
}


def is_cyrillic(text: str) -> bool:
    return bool(text) and bool(_CYRILLIC_RE.search(text))


def _apply_map(text: str, mapping: dict) -> str:
    return "".join(mapping.get(ch.lower(), ch) for ch in text)


def _informal_variants(base: str) -> set:
    """Common anglicized renderings that neither formal standard captures:
    emigre-style '-ov'/'-ova' -> '-off'/'-eva' surname endings, and 'kh' often
    simplified to a bare 'h' (e.g. "Khodorkovsky" vs "Hodorkovsky")."""
    variants = set()

    if base.endswith("ov"):
        variants.add(base[:-2] + "off")
    elif base.endswith("ova"):
        variants.add(base[:-3] + "ova")
        variants.add(base[:-3] + "offa")

    if "kh" in base:
        variants.add(base.replace("kh", "h"))

    return variants


def transliterate_variants(text: str) -> list:
    """Returns a de-duplicated list of plausible Latin transliterations for
    a Cyrillic name. Returns an empty list if the input has no Cyrillic
    characters (nothing to transliterate)."""
    if not is_cyrillic(text):
        return []

    icao = _apply_map(text, _ICAO_9303)
    gost = _apply_map(text, _GOST_7_79B)

    variants = {icao, gost}
    variants |= _informal_variants(icao)
    variants |= _informal_variants(gost)

    return sorted(variants)
