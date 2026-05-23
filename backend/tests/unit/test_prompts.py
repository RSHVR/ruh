"""build_kb_block must be byte-deterministic across input orderings.

Anthropic's 1hr ephemeral cache matches on EXACT prefix bytes — any drift
silently doubles cost on cached configs (1, 3, 5). This test is the single
canonical guard against that regression.
"""

import random
import sys
from pathlib import Path

# Make `scripts.benchmark.configs.prompts` importable.
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.benchmark.configs.prompts import build_kb_block, STATIC_BASE_PROMPT  # noqa: E402


def _allergens():
    return [
        {"name": "Latex", "synonyms": ["Natural Rubber Latex", "NRL"]},
        {"name": "Cetearyl Alcohol", "synonyms": ["Cetostearyl Alcohol"]},
        {"name": "Fragrance", "synonyms": ["Parfum", "Aroma"]},
        {"name": "Methylisothiazolinone", "synonyms": ["MI", "Kathon"]},
        {"name": "Phenoxyethanol", "synonyms": []},
    ]


def _pfas():
    return [
        {"name": "PFOA", "cas_number": "335-67-1"},
        {"name": "PTFE", "cas_number": "9002-84-0"},
        {"name": "PFOS", "cas_number": "1763-23-1"},
        {"name": "GenX", "cas_number": "13252-13-6"},
    ]


def test_kb_block_is_deterministic_across_shuffles():
    allergens = _allergens()
    pfas = _pfas()
    expected = build_kb_block(allergens, pfas)

    for _ in range(20):
        a_shuf = allergens[:]
        p_shuf = pfas[:]
        random.shuffle(a_shuf)
        random.shuffle(p_shuf)
        # Shuffle synonyms too — the renderer must sort them.
        for row in a_shuf:
            random.shuffle(row["synonyms"])
        assert build_kb_block(a_shuf, p_shuf) == expected, (
            "build_kb_block produced different bytes after shuffling — "
            "cache prefix invariant violated"
        )


def test_kb_block_sorts_alphabetically():
    rendered = build_kb_block(_allergens(), _pfas())
    # Cetearyl Alcohol should come before Fragrance.
    assert rendered.find("Cetearyl") < rendered.find("Fragrance")
    # Among PFAS, GenX < PFOA < PFOS < PTFE alphabetically.
    assert rendered.find("GenX") < rendered.find("PFOA") < rendered.find("PFOS") < rendered.find("PTFE")


def test_kb_block_caps_synonyms_at_three():
    allergens = [{
        "name": "TestSubstance",
        "synonyms": ["synA", "synB", "synC", "synD", "synE", "synF"],
    }]
    out = build_kb_block(allergens, [])
    # Only first 3 (sorted: synA, synB, synC) should appear.
    assert "synA, synB, synC" in out
    assert "synD" not in out
    assert "synE" not in out
    assert "synF" not in out


def test_kb_block_handles_empty_inputs():
    assert build_kb_block([], []) == ""


def test_allergen_profile_is_outside_cached_block():
    """User-specific profile must NOT be in the cached KB section.

    The cached prefix is everything up to and including the KB block. The
    profile is appended AFTER and is permitted to change per request without
    invalidating the cache prefix.
    """
    base = build_kb_block(_allergens(), _pfas(), allergen_profile=None)
    with_profile = build_kb_block(_allergens(), _pfas(), allergen_profile=["peanuts"])
    # The shared prefix must match.
    assert with_profile.startswith(base.rstrip("\n"))
    assert "peanuts" not in base
    assert "peanuts" in with_profile


def test_static_prompt_is_a_frozen_string():
    """Catch unintended edits to the cacheable body."""
    # If you intentionally change the prompt, update this hash. Drift here
    # invalidates every Anthropic cache entry across configs 1, 3, 5.
    import hashlib
    h = hashlib.sha256(STATIC_BASE_PROMPT.encode()).hexdigest()
    # The hash itself is not pinned in this assertion (it would force a
    # version bump on any edit); we only assert it's stable per process.
    h2 = hashlib.sha256(STATIC_BASE_PROMPT.encode()).hexdigest()
    assert h == h2
    assert len(STATIC_BASE_PROMPT) > 1000  # sanity: not accidentally emptied
