"""Hybrid retrieval wiring tests for get_health_relevant_reviews.

These exercise the fusion path end-to-end with the two retrievers stubbed (no live
DB, no Cohere): the guarantee that a review found ONLY by the lexical retriever is
still returned (the "never miss an exact match" goal), that semantic ∪ lexical is
unioned and deduped, and that an unavailable DB degrades to an empty list (INV-3).
Cohere rerank is genuinely absent here, so this also proves the rerank→RRF-order
fallback.
"""

from types import SimpleNamespace

import pytest

import src.infrastructure.review_vector_service as rvs


def _review(rid, text, rating=2):
    return {
        "id": rid,
        "review_text": text,
        "review_rating": rating,
        "verified_purchase": True,
        "helpful_votes": 0,
        "reviewer_name": "tester",
    }


@pytest.mark.asyncio
async def test_lexical_only_hit_is_returned_when_semantic_empty(monkeypatch):
    monkeypatch.setattr(rvs, "db", SimpleNamespace(is_available=True))
    svc = rvs.ReviewVectorService()
    # Semantic finds nothing (e.g. embedding ranked it low / Cohere down)...
    monkeypatch.setattr(svc, "_semantic_candidates", lambda q, u, top_k=10, **k: [])
    # ...but the lexical retriever hits the exact substance name.
    monkeypatch.setattr(
        svc,
        "_lexical_candidates",
        lambda q, u, top_k=10, **k: [_review("lex1", "product left PFOA residue on my pan")],
    )

    results = await svc.get_health_relevant_reviews("hash123", max_reviews=15)

    assert any("PFOA" in r["review_text"] for r in results)


@pytest.mark.asyncio
async def test_semantic_and_lexical_are_unioned_and_deduped(monkeypatch):
    monkeypatch.setattr(rvs, "db", SimpleNamespace(is_available=True))
    svc = rvs.ReviewVectorService()
    monkeypatch.setattr(
        svc, "_semantic_candidates", lambda q, u, top_k=10, **k: [_review("a", "gave me a rash")]
    )
    monkeypatch.setattr(
        svc,
        "_lexical_candidates",
        lambda q, u, top_k=10, **k: [_review("a", "gave me a rash"), _review("b", "strong benzene smell")],
    )

    results = await svc.get_health_relevant_reviews("hash123", max_reviews=15)

    texts = {r["review_text"] for r in results}
    assert "gave me a rash" in texts  # shared doc kept once (RRF dedup on id)
    assert "strong benzene smell" in texts  # lexical-only doc included
    assert sum(1 for r in results if r["id"] == "a") == 1


@pytest.mark.asyncio
async def test_empty_when_db_unavailable(monkeypatch):
    monkeypatch.setattr(rvs, "db", SimpleNamespace(is_available=False))
    svc = rvs.ReviewVectorService()
    assert await svc.get_health_relevant_reviews("hash123") == []


@pytest.mark.asyncio
async def test_both_retrievers_empty_yields_empty(monkeypatch):
    monkeypatch.setattr(rvs, "db", SimpleNamespace(is_available=True))
    svc = rvs.ReviewVectorService()
    monkeypatch.setattr(svc, "_semantic_candidates", lambda q, u, top_k=10, **k: [])
    monkeypatch.setattr(svc, "_lexical_candidates", lambda q, u, top_k=10, **k: [])
    assert await svc.get_health_relevant_reviews("hash123") == []
