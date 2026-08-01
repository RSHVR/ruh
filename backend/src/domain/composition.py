"""Deterministic textile-composition splitter (no LLM, pure function).

Apparel retailers (H&M, Uniqlo, Aritzia, …) express fabric composition per
garment part, e.g. ``"Shell: Viscose 75%, Polyamide 25%"``. Stored as-is this is
one opaque "ingredient"; Veer wants each fibre to be its own ingredient while
keeping the percentages (he likes them) and the part it belongs to:

    ["Shell: Viscose 75%, Polyamide 25%", "Lining: Cotton 100%"]
        -> ["Viscose 75% (Shell)", "Polyamide 25% (Shell)", "Cotton 100% (Lining)"]

A string is treated as a composition only when it carries BOTH a ``Part:`` label
(pattern-matched, not a hardcoded part list) AND at least one percentage. Every
other string — regular cosmetics ingredient lists, plain materials — passes
through verbatim. This is wired into the extraction post-processing
(``claude_query.py``); it is pattern-based, so it applies to any textile retailer
automatically. See INDEX.md §2 (extraction) and the H&M recon notes.
"""

import re
from typing import List

# A leading garment-part label: "Shell:", "Lining:", "Outer fabric:", "Body:".
# Pattern-based (letters, spaces, slashes before a colon) rather than a fixed
# list, so new part names work without a code change.
_PART_LABEL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z /]*?)\s*:\s*(.+)$")

# A fibre segment carries an explicit percentage (the signal that a labelled
# string is a fabric composition and not, say, "Ingredients: water, glycerin").
_PERCENT_RE = re.compile(r"\d+\s*%")


def normalize_composition(ingredients: List[str]) -> List[str]:
    """Split ``Part: Fiber N%, Fiber M%`` strings into one fibre per entry.

    Args:
        ingredients: Extracted ingredient/composition strings (may be ``None``).

    Returns:
        A new list where composition strings are expanded to ``"<fibre> (<part>)"``
        entries and every other string is preserved verbatim. ``None`` in →
        ``None`` out (defensive; never raises).
    """
    if not ingredients:
        return ingredients

    result: List[str] = []
    for item in ingredients:
        if not isinstance(item, str):
            result.append(item)
            continue
        result.extend(_split_composition(item))
    return result


def _split_composition(item: str) -> List[str]:
    """Expand a single composition string, or return ``[item]`` unchanged."""
    if not _PART_LABEL_RE.match(item) or not _PERCENT_RE.search(item):
        return [item]

    expanded: List[str] = []
    current_part: str = ""
    for segment in item.split(","):
        segment = segment.strip()
        if not segment:
            continue
        label_match = _PART_LABEL_RE.match(segment)
        if label_match:
            # A "Word...:" prefix (re)sets the part the following fibres belong to.
            current_part = label_match.group(1).strip()
            fibre = label_match.group(2).strip()
        else:
            fibre = segment
        if not fibre:
            continue
        expanded.append(f"{fibre} ({current_part})" if current_part else fibre)

    return expanded or [item]
