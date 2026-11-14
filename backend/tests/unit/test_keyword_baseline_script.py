from scripts.keyword_baseline import (
    RESULT_WINDOW,
    BaselineQuestion,
    parse_questions,
    rank_of_expected,
)

BASE = "https://github.com/acme/widgets/blob/HEAD/"
SAMPLE = f"""# Baseline

URL base: `{BASE}`

| # | Question | Expected artifact (path after URL base) |
|---|---|---|
| Q1 | How are citations checked? | `backend/src/services/answer_svc.py` |
| Q2 | Why Groq? | `docs/decisions/ADR-002-groq-llm-provider.md` |
"""


def test_parses_questions_and_builds_expected_urls():
    assert parse_questions(SAMPLE) == [
        BaselineQuestion(
            "Q1", "How are citations checked?", BASE + "backend/src/services/answer_svc.py"
        ),
        BaselineQuestion(
            "Q2", "Why Groq?", BASE + "docs/decisions/ADR-002-groq-llm-provider.md"
        ),
    ]


def test_header_and_separator_rows_are_not_questions():
    assert [q.label for q in parse_questions(SAMPLE)] == ["Q1", "Q2"]


def test_rank_ignores_the_line_anchor_on_chunk_urls():
    expected = BASE + "app.py"

    assert rank_of_expected(expected, [BASE + "other.py", BASE + "app.py#L10-L30"]) == 2


def test_rank_is_none_when_expected_is_missing_or_outside_the_window():
    expected = BASE + "app.py"
    far = [BASE + f"f{i}.py" for i in range(RESULT_WINDOW)] + [expected]

    assert rank_of_expected(expected, [BASE + "other.py"]) is None
    assert rank_of_expected(expected, far) is None
