"""FR-011 (specs/003): turning a free-text question into safe keyword search terms."""

from src.repositories.artifact_repository import MAX_KEYWORD_TOKENS, keyword_tokens


def test_lower_cases_and_splits_on_anything_that_is_not_a_letter_or_digit():
    assert keyword_tokens("How does Login-Retry_work?") == [
        "how",
        "does",
        "login",
        "retry",
        "work",
    ]


def test_keeps_digits():
    assert keyword_tokens("HTTP 401 error") == ["http", "401", "error"]


def test_drops_single_character_tokens():
    assert keyword_tokens("a b cd e fg") == ["cd", "fg"]


def test_removes_duplicates_keeping_first_position():
    assert keyword_tokens("login Login LOGIN retry login") == ["login", "retry"]


def test_caps_the_number_of_tokens():
    question = " ".join(f"word{i}" for i in range(MAX_KEYWORD_TOKENS + 8))

    tokens = keyword_tokens(question)

    assert len(tokens) == MAX_KEYWORD_TOKENS
    assert tokens[0] == "word0"


def test_search_syntax_characters_never_survive():
    assert keyword_tokens('login & (retry) | "x" -y :z') == ["login", "retry"]


def test_question_of_only_punctuation_or_syntax_has_no_tokens():
    assert keyword_tokens('"-&():|') == []
    assert keyword_tokens("?!...") == []


def test_empty_string_has_no_tokens():
    assert keyword_tokens("") == []
