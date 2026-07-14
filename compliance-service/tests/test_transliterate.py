from app.screening.transliterate import is_cyrillic, transliterate_variants


def test_is_cyrillic_detects_cyrillic_text():
    assert is_cyrillic("Иванов")  # Ivanov in Cyrillic
    assert not is_cyrillic("Ivanov")
    assert not is_cyrillic("")
    assert not is_cyrillic(None)


def test_transliterate_variants_empty_for_latin_input():
    assert transliterate_variants("Ivanov") == []


def test_transliterate_variants_generates_ov_off_variant():
    variants = transliterate_variants("Иванов")  # Ivanov
    assert "ivanov" in variants
    assert "ivanoff" in variants


def test_transliterate_variants_generates_kh_h_variant():
    # Khodorkovsky
    name = "Ходорковский"
    variants = transliterate_variants(name)
    assert any(v.startswith("kh") for v in variants)
    assert any(v.startswith("h") and not v.startswith("kh") for v in variants)


def test_transliterate_variants_are_deduplicated_and_sorted():
    variants = transliterate_variants("Иванов")
    assert variants == sorted(set(variants))
