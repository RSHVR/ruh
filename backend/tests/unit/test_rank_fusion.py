"""Tests for Reciprocal Rank Fusion (RRF) — the hybrid-retrieval fusion primitive.

RRF fuses several independently-ranked candidate lists (here: semantic/pgvector
hits ∪ lexical/full-text hits) into one order without needing comparable scores:
``score(d) = Σ_lists 1/(k + rank_d)``, k=60 standard. A doc surfaced by BOTH
retrievers outranks one surfaced by a single retriever — which is exactly how a
hard lexical match ("PFOA", "benzene") is guaranteed a seat at the table even if
its embedding ranked it low. Pure function → tested directly, no DB/Cohere.
"""

import pytest

from src.infrastructure.rank_fusion import reciprocal_rank_fusion


def test_doc_in_both_lists_outranks_single_list_docs():
    semantic = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    lexical = [{"id": "b"}, {"id": "d"}]
    fused = reciprocal_rank_fusion([semantic, lexical], k=60)
    ids = [r["id"] for r in fused]
    assert ids[0] == "b"  # appears in both → highest fused score
    assert sorted(ids) == ["a", "b", "c", "d"]  # union, deduped


def test_rrf_score_math_and_ordering():
    l1 = [{"id": "x"}, {"id": "y"}]
    l2 = [{"id": "y"}]
    fused = reciprocal_rank_fusion([l1, l2], k=60)
    by_id = {r["id"]: r["rrf_score"] for r in fused}
    assert by_id["x"] == pytest.approx(1 / 61)
    assert by_id["y"] == pytest.approx(1 / 62 + 1 / 61)
    assert [r["id"] for r in fused][0] == "y"


def test_one_source_empty_returns_other_in_order():
    l1 = [{"id": "a"}, {"id": "b"}]
    assert [r["id"] for r in reciprocal_rank_fusion([l1, []], k=60)] == ["a", "b"]
    assert [r["id"] for r in reciprocal_rank_fusion([[], l1], k=60)] == ["a", "b"]


def test_both_empty_and_no_lists_return_empty():
    assert reciprocal_rank_fusion([[], []]) == []
    assert reciprocal_rank_fusion([]) == []


def test_dedup_keeps_first_seen_payload_and_sums_score():
    l1 = [{"id": "a", "review_text": "from semantic", "similarity": 0.9}]
    l2 = [{"id": "a", "review_text": "from lexical", "lexical_rank": 0.5}]
    fused = reciprocal_rank_fusion([l1, l2])
    assert len(fused) == 1
    assert fused[0]["review_text"] == "from semantic"  # first-seen payload wins
    assert fused[0]["rrf_score"] == pytest.approx(1 / 61 + 1 / 61)


def test_falls_back_to_review_text_when_id_missing():
    l1 = [{"review_text": "PFOA detected in coating"}]
    l2 = [{"review_text": "PFOA detected in coating"}]
    fused = reciprocal_rank_fusion([l1, l2], id_key="id")
    assert len(fused) == 1  # deduped on review_text since no id


def test_custom_k_changes_scores():
    fused = reciprocal_rank_fusion([[{"id": "a"}]], k=1)
    assert fused[0]["rrf_score"] == pytest.approx(1 / 2)


def test_deterministic_tie_break_is_first_seen():
    # a and b each rank 1 in their own list → equal fused score; first-seen wins.
    fused = reciprocal_rank_fusion([[{"id": "a"}], [{"id": "b"}]], k=60)
    assert [r["id"] for r in fused] == ["a", "b"]


def test_input_items_are_not_mutated():
    item = {"id": "a"}
    reciprocal_rank_fusion([[item]])
    assert "rrf_score" not in item  # returns enriched copies, never mutates inputs


def test_items_without_id_or_text_are_skipped():
    fused = reciprocal_rank_fusion([[{"foo": "bar"}, {"id": "a"}]])
    assert [r["id"] for r in fused] == ["a"]
