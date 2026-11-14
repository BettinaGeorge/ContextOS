"""FR-014 (specs/003): merging keyword and vector results by rank, not by concatenation."""

from types import SimpleNamespace

from src.services.retrieval_svc import RRF_K, reciprocal_rank_fusion


def _item(name: str) -> SimpleNamespace:
    return SimpleNamespace(id=name)


def _ids(items) -> list[str]:
    return [item.id for item in items]


def test_item_first_in_both_lists_beats_item_first_in_only_one():
    a, b, c = _item("a"), _item("b"), _item("c")

    fused = reciprocal_rank_fusion([a, b], [a, c], limit=10)

    assert _ids(fused)[0] == "a"


def test_item_in_both_lists_beats_items_ranked_higher_in_only_one():
    top_keyword, shared, top_vector = _item("k1"), _item("shared"), _item("v1")

    fused = reciprocal_rank_fusion([top_keyword, shared], [top_vector, shared], limit=10)

    assert _ids(fused)[0] == "shared"


def test_item_in_both_lists_appears_once():
    a, b = _item("a"), _item("b")

    fused = reciprocal_rank_fusion([a, b], [b, a], limit=10)

    assert sorted(_ids(fused)) == ["a", "b"]


def test_result_is_cut_to_the_limit():
    keyword = [_item(f"k{i}") for i in range(5)]
    vector = [_item(f"v{i}") for i in range(5)]

    assert len(reciprocal_rank_fusion(keyword, vector, limit=3)) == 3


def test_ties_keep_input_order():
    first_keyword, first_vector = _item("k1"), _item("v1")

    fused = reciprocal_rank_fusion([first_keyword], [first_vector], limit=10)

    assert _ids(fused) == ["k1", "v1"]


def test_scores_follow_the_reciprocal_rank_formula():
    assert RRF_K == 60
    a, b = _item("a"), _item("b")

    fused = reciprocal_rank_fusion([a, b], [], limit=10)

    assert _ids(fused) == ["a", "b"]


def test_empty_inputs_work():
    a = _item("a")

    assert reciprocal_rank_fusion([], [], limit=10) == []
    assert _ids(reciprocal_rank_fusion([a], [], limit=10)) == ["a"]
    assert _ids(reciprocal_rank_fusion([], [a], limit=10)) == ["a"]
