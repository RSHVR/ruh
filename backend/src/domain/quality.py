"""Analysis-quality checks.

`is_inconclusive_analysis` decides whether a stored analysis actually contains
something worth paying for. Users spend a credit to unlock the detail view;
charging for an analysis with no ingredients and no findings (or rock-bottom
confidence) is a trust-destroying trade — the deduct route uses this to make
such unlocks free instead.
"""

import json
from typing import Any, Dict, List, Optional

# Below this confidence the UI already warns "results may be incomplete".
# Stored rows use a 0-100 scale; in-memory models use 0.0-1.0 — accept both.
_CONFIDENCE_FLOOR = 30.0


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    if isinstance(value, list):
        return value
    return []


def _normalized_confidence(value: Any) -> Optional[float]:
    """Confidence on the 0-100 scale, or None when absent/unparseable."""
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= conf <= 1.0:
        return conf * 100.0
    return conf


# Page-furniture markers that never belong in a substance name. Seen in prod:
# comparison-table rows, review counts, and prices extracted as "ingredients".
_GARBAGE_MARKERS = (
    "out of 5 stars",
    "customer review",
    "product description",
    "price $",
    "$",
    "✓",
    "add to cart",
)
_MAX_INGREDIENT_LEN = 90  # longest real INCI names run ~60 chars


def _is_garbage_ingredient(entry: Any) -> bool:
    text = str(entry).strip().lower()
    if not text:
        return True
    if len(text) > _MAX_INGREDIENT_LEN:
        return True
    return any(marker in text for marker in _GARBAGE_MARKERS)


def is_inconclusive_analysis(row: Dict[str, Any]) -> bool:
    """True when an analysis has nothing meaningful behind the paywall.

    Inconclusive =
      - no ingredients AND no findings of any kind (empty detail view), OR
      - confidence below the low-confidence floor the UI warns about, OR
      - the ingredient list is mostly page furniture (garbage extraction).

    A clean product WITH an ingredient list is conclusive — "no concerns
    found" is a real, useful answer. Missing/absent rows are treated as
    inconclusive (nothing to show).
    """
    if not row:
        return True

    has_content = any(
        _as_list(row.get(field))
        for field in (
            "ingredients",
            "allergens_detected",
            "pfas_detected",
            "other_concerns",
        )
    )
    if not has_content:
        return True

    conf = _normalized_confidence(row.get("confidence"))
    if conf is not None and conf < _CONFIDENCE_FLOOR:
        return True

    ingredients = _as_list(row.get("ingredients"))
    if ingredients:
        garbage = sum(1 for i in ingredients if _is_garbage_ingredient(i))
        if garbage * 2 >= len(ingredients):  # half or more is junk
            return True

    return False


# Bounded so a permanently-unscrapeable product can't burn analysis spend
# forever. After the cap, the (inconclusive) cache is served — and unlocks
# stay free via is_inconclusive_analysis.
MAX_RESCANS = 3


def should_rescan(row: Optional[Dict[str, Any]]) -> bool:
    """True when a cached analysis should be bypassed and re-run.

    Inconclusive cache entries are treated as stale: the next visit re-analyzes
    instead of serving the empty result, up to MAX_RESCANS attempts.
    """
    if not row:
        return False  # nothing cached — normal fresh-analysis path anyway
    if not is_inconclusive_analysis(row):
        return False
    try:
        rescans = int(row.get("rescan_count") or 0)
    except (TypeError, ValueError):
        rescans = 0
    return rescans < MAX_RESCANS
