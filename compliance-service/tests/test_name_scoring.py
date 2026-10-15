from app.sanctions.normalize import phonetic_keys, significant_tokens
from app.screening.matcher import name_score


def test_legal_suffixes_and_generic_words_are_ignored():
    assert significant_tokens("Coral Energy PTE Ltd") == ["coral", "energy"]
    assert significant_tokens("ACS Trading LLC") == ["acs"]
    assert significant_tokens("Ltd") == ["ltd"]  # never reduced to nothing


def test_company_found_with_or_without_suffix():
    assert name_score("Coral Energy", "Coral Energy PTE Ltd") == 100
    assert name_score("Coral Energy PTE Ltd", "Coral Energy DMCC") == 100


def test_blocking_keys_cover_first_and_last_token_and_ignore_suffix():
    assert phonetic_keys("Coral Energy") == phonetic_keys("Coral Energy PTE Ltd")
    assert phonetic_keys("Saddam Hussein") == phonetic_keys("Hussein Saddam")


def test_word_order_does_not_matter():
    assert name_score("Hussein Saddam", "Saddam HUSSEIN") == 100
    assert name_score("MOHAMMED, Ali", "Mohammed Ali") == 100


def test_one_word_alias_does_not_match_a_full_name():
    # the regression that flooded reviewers: alias "John" scored 90 against every "John ..."
    assert name_score("John Smith", "John") < 70
    assert name_score("Maria Rossi", "MARIA") < 70


def test_two_shared_tokens_count_as_subset_match_at_reduced_weight():
    assert 85 <= name_score("Saddam Hussein", "Saddam Hussein Al-Tikriti") < 100


def test_unrelated_and_generic_only_overlap_stay_low():
    assert name_score("Acme Trading Ltd", "ACS Trading LLC") < 70
    assert name_score("Anna Schmidt", "Vladimir Putin") < 40


def test_small_spelling_variation_still_matches():
    assert name_score("Ivan Ivanof", "Ivan Ivanoff") >= 90
