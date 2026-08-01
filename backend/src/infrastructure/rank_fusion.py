"""Reciprocal Rank Fusion (RRF) for hybrid review retrieval.

Fuses several independently-ranked candidate lists into one ranking without
requiring their scores to be comparable — the classic problem when combining a
semantic/pgvector ranker (cosine similarity) with a lexical/full-text ranker
(``ts_rank_cd``). For each list a document contributes ``1/(k + rank)`` to its
fused score (rank is 1-based); the constant ``k`` (60 is the standard from the
original Cormack et al. RRF paper) damps the influence of top ranks so no single
list dominates. A document surfaced by BOTH retrievers therefore outranks one
surfaced by only one — which is why an exact lexical hit ("PFOA", "benzene") is
guaranteed into the fused pool even if its embedding ranked it poorly.

Pure and deterministic: dedupes on a stable id (falling back to review text),
never mutates inputs, and breaks ties by first-seen order.
"""

from typing import Any, Dict, List, Optional

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = DEFAULT_RRF_K,
    id_key: str = "id",
) -> List[Dict[str, Any]]:
    """Fuse ranked lists of review dicts via Reciprocal Rank Fusion.

    Args:
        ranked_lists: Each inner list is a retriever's results in rank order
            (best first). Empty lists are ignored, so a failed retriever simply
            drops out and fusion degrades to the remaining source(s).
        k: RRF damping constant (standard 60).
        id_key: Field used to identify/dedupe a document across lists; when
            absent, ``review_text`` is used so text-only rows still fuse.

    Returns:
        A new list of the unique documents ordered by descending fused score,
        each an enriched COPY carrying an added ``rrf_score``. Inputs are never
        mutated. Ties break by first-seen order (deterministic).
    """
    scores: Dict[Any, float] = {}
    items: Dict[Any, Dict[str, Any]] = {}
    first_seen: Dict[Any, int] = {}
    order = 0

    for ranked in ranked_lists:
        if not ranked:
            continue
        for rank, item in enumerate(ranked, start=1):
            key = _fusion_key(item, id_key)
            if key is None:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in items:
                items[key] = item
                first_seen[key] = order
                order += 1

    ordered_keys = sorted(items.keys(), key=lambda key: (-scores[key], first_seen[key]))

    fused: List[Dict[str, Any]] = []
    for key in ordered_keys:
        enriched = dict(items[key])
        enriched["rrf_score"] = scores[key]
        fused.append(enriched)
    return fused


def _fusion_key(item: Dict[str, Any], id_key: str) -> Optional[Any]:
    """Stable identity for a review dict: its id, else its review text."""
    if not isinstance(item, dict):
        return None
    return item.get(id_key) or item.get("review_text")
