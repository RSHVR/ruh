"""Inconclusive-analysis detection (free-unlock rule).

Born from a real prod complaint (2026-08-01): a user paid 1 credit to unlock
a detail view containing zero ingredients and zero findings at confidence 30.
"""

from src.domain.quality import is_inconclusive_analysis, should_rescan


def _row(**overrides):
    base = {
        "ingredients": ["Aqua", "Glycerin"],
        "allergens_detected": [],
        "pfas_detected": [],
        "other_concerns": [{"name": "Fragrance"}],
        "confidence": 85,
    }
    base.update(overrides)
    return base


class TestInconclusive:
    def test_the_real_prod_case_is_inconclusive(self):
        # Identified product, but nothing extracted at all
        assert is_inconclusive_analysis(
            _row(ingredients=[], allergens_detected=[], pfas_detected=[],
                 other_concerns=[], confidence=30)
        )

    def test_low_confidence_is_inconclusive_even_with_content(self):
        assert is_inconclusive_analysis(_row(confidence=10))
        assert is_inconclusive_analysis(_row(confidence=0.1))  # 0-1 scale

    def test_clean_product_with_ingredients_is_conclusive(self):
        # "No concerns found" over a real ingredient list is a real answer
        assert not is_inconclusive_analysis(
            _row(allergens_detected=[], pfas_detected=[], other_concerns=[])
        )

    def test_findings_without_ingredient_list_are_conclusive(self):
        # e.g. materials-based products where concerns come from research
        assert not is_inconclusive_analysis(
            _row(ingredients=[], other_concerns=[{"name": "PFOA"}], confidence=70)
        )

    def test_confidence_at_floor_is_conclusive(self):
        assert not is_inconclusive_analysis(_row(confidence=30))
        assert not is_inconclusive_analysis(_row(confidence=0.3))

    def test_json_string_fields_are_parsed(self):
        assert is_inconclusive_analysis(
            _row(ingredients="[]", allergens_detected="[]",
                 pfas_detected="[]", other_concerns="[]", confidence=90)
        )
        assert not is_inconclusive_analysis(
            _row(ingredients='["Aqua"]', confidence=90)
        )

    def test_missing_row_is_inconclusive(self):
        assert is_inconclusive_analysis(None)
        assert is_inconclusive_analysis({})

    def test_absent_confidence_with_content_is_conclusive(self):
        assert not is_inconclusive_analysis(_row(confidence=None))


class TestShouldRescan:
    def test_inconclusive_cache_is_rescanned(self):
        assert should_rescan(
            _row(ingredients=[], allergens_detected=[], pfas_detected=[],
                 other_concerns=[], confidence=30)
        )

    def test_conclusive_cache_is_served(self):
        assert not should_rescan(_row())

    def test_rescan_cap(self):
        bad = _row(ingredients=[], allergens_detected=[], pfas_detected=[],
                   other_concerns=[], confidence=10)
        assert should_rescan({**bad, "rescan_count": 2})
        assert not should_rescan({**bad, "rescan_count": 3})
        assert not should_rescan({**bad, "rescan_count": 7})

    def test_missing_row_is_not_a_rescan(self):
        assert not should_rescan(None)
        assert not should_rescan({})  # empty dict == falsy -> fresh path anyway


class TestGarbageIngredients:
    GARBAGE = [
        "Product Description Clean People Laundry Detergent Sheets - Recyclable Packaging",
        "Customer Reviews 4.4 out of 5 stars 31,933",
        "Simpler Ingredients ✓ ✓ ✓ ✓ ✓ Great for Sensitive Skin ✓ ✓ ✓ ✓ ✓",
        "Price $39.99 $ 39 . 99",
    ]

    def test_mostly_garbage_ingredients_are_inconclusive(self):
        # The real prod row: comparison-table furniture stored as ingredients
        assert is_inconclusive_analysis(_row(ingredients=self.GARBAGE + ["Aqua"], confidence=70))

    def test_minor_garbage_with_real_list_is_conclusive(self):
        real = ["Aqua", "Sodium Carbonate", "Sodium Percarbonate", "Citric Acid",
                "Sodium Silicate", "Subtilisin", "Amylase"]
        assert not is_inconclusive_analysis(_row(ingredients=real + [self.GARBAGE[0]], confidence=70))

    def test_long_but_real_inci_names_are_not_garbage(self):
        real = ["Amides, C16-18 and C18-unsatd., N,N-bis(hydroxyethyl)",
                "Viscose 75% (Shell)", "Polyamide 25% (Shell)"]
        assert not is_inconclusive_analysis(_row(ingredients=real, confidence=70))
