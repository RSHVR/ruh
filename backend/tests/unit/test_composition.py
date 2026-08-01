"""Tests for normalize_composition (deterministic textile-composition splitter).

Veer wants each fibre in an apparel composition to be its own ingredient while
keeping the percentages (which he likes) and the garment part, e.g.
``["Shell: Viscose 75%, Polyamide 25%", "Lining: Cotton 100%"]`` should become
``["Viscose 75% (Shell)", "Polyamide 25% (Shell)", "Cotton 100% (Lining)"]``.

Critically, non-composition strings (regular cosmetics ingredient lists, plain
materials) MUST pass through verbatim — the splitter is pattern-based and
deterministic, not an LLM call.
"""

from src.domain.composition import normalize_composition


def test_splits_multi_part_composition_keeping_percent_and_part():
    result = normalize_composition(
        ["Shell: Viscose 75%, Polyamide 25%", "Lining: Cotton 100%"]
    )
    assert result == [
        "Viscose 75% (Shell)",
        "Polyamide 25% (Shell)",
        "Cotton 100% (Lining)",
    ]


def test_single_fibre_part_keeps_percent():
    assert normalize_composition(["Body: Cotton 100%"]) == ["Cotton 100% (Body)"]


def test_multi_word_part_label_preserved():
    assert normalize_composition(["Outer fabric: Polyester 60%, Elastane 40%"]) == [
        "Polyester 60% (Outer fabric)",
        "Elastane 40% (Outer fabric)",
    ]


def test_multiple_parts_in_one_string_switch_part_mid_stream():
    # Some sites emit all parts as one string; the splitter must track part switches.
    result = normalize_composition(
        ["Shell: Viscose 75%, Polyamide 25%, Lining: Cotton 100%"]
    )
    assert result == [
        "Viscose 75% (Shell)",
        "Polyamide 25% (Shell)",
        "Cotton 100% (Lining)",
    ]


def test_regular_cosmetics_ingredient_list_passes_through_untouched():
    # A normal cosmetics list (no part label, no percentages) must be UNTOUCHED.
    cosmetics = [
        "Water",
        "Glycerin",
        "Sodium Laureth Sulfate",
        "Cocamidopropyl Betaine",
        "Fragrance",
    ]
    assert normalize_composition(cosmetics) == cosmetics


def test_single_comma_joined_cosmetics_string_passes_through():
    single = ["Water, Glycerin, Sodium Chloride, Citric Acid, Fragrance"]
    assert normalize_composition(single) == single


def test_labelled_string_without_percentage_passes_through():
    # "Ingredients: ..." has a label but no percentage → NOT a fibre composition.
    item = ["Ingredients: Water, Glycerin, Fragrance"]
    assert normalize_composition(item) == item


def test_plain_material_without_part_passes_through():
    assert normalize_composition(["100% Cotton"]) == ["100% Cotton"]
    assert normalize_composition(["Cotton 80%, Polyester 20%"]) == [
        "Cotton 80%, Polyester 20%"
    ]


def test_empty_and_non_string_are_safe():
    assert normalize_composition([]) == []
    assert normalize_composition(None) is None
    # Non-string entries pass through unchanged (defensive; never raise).
    assert normalize_composition([123, "Shell: Cotton 100%"]) == [
        123,
        "Cotton 100% (Shell)",
    ]


def test_percentage_before_fibre_name():
    assert normalize_composition(["Shell: 100% Cotton"]) == ["100% Cotton (Shell)"]
