"""Unit tests for HarmScoreCalculator.

Tests the scoring algorithm using the exact formulas from harm_calculator.py:
- SEVERITY_POINTS: low=8, moderate=18, high=35, severe=50
- PFAS: 40 points per compound (confidence-weighted)
- CATEGORY_POINTS: under_investigation=5, carcinogen=40, regulatory_action=30, etc.
- CATEGORY_MULTIPLIERS: pesticide=1.4, household_cleaner=1.2, etc.
- High-risk keywords (bleach, poison, etc.) → 1.3x
- Confidence < 0.7 → penalty of (0.7 - conf) * 20
- Floor: 25 if any concerns detected
- Cap: 100
"""

import pytest
from src.domain.harm_calculator import HarmScoreCalculator


class TestHarmScoreCalculator:
    """Tests for HarmScoreCalculator.calculate()."""

    # ── Baseline ────────────────────────────────────────────

    def test_empty_data_returns_zero(self):
        assert HarmScoreCalculator.calculate({}) == 0

    def test_no_concerns_returns_zero(self):
        data = {
            "allergens_detected": [],
            "pfas_detected": [],
            "other_concerns": [],
            "confidence": 1.0,
            "product_name": "Water Bottle",
            "category": "drinkware",
        }
        assert HarmScoreCalculator.calculate(data) == 0

    # ── Allergen severity points ────────────────────────────

    def test_allergen_low_severity(self):
        """low severity = 8 points, but floor at 25."""
        data = {
            "allergens_detected": [{"severity": "low", "confidence": 1.0}],
        }
        assert HarmScoreCalculator.calculate(data) == 25  # floor

    def test_allergen_moderate_severity(self):
        """moderate = 18 points, but floor at 25."""
        data = {
            "allergens_detected": [{"severity": "moderate", "confidence": 1.0}],
        }
        assert HarmScoreCalculator.calculate(data) == 25  # floor

    def test_allergen_high_severity(self):
        """high = 35 points."""
        data = {
            "allergens_detected": [{"severity": "high", "confidence": 1.0}],
        }
        assert HarmScoreCalculator.calculate(data) == 35

    def test_allergen_severe_severity(self):
        """severe = 50 points."""
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
        }
        assert HarmScoreCalculator.calculate(data) == 50

    def test_allergen_unknown_severity_defaults_to_8(self):
        """Unknown severity falls back to 8 points (floor 25)."""
        data = {
            "allergens_detected": [{"severity": "xyz_unknown", "confidence": 1.0}],
        }
        assert HarmScoreCalculator.calculate(data) == 25  # 8 pts → floor 25

    # ── PFAS scoring ────────────────────────────────────────

    def test_pfas_single_compound(self):
        """Each PFAS compound = 40 points."""
        data = {
            "pfas_detected": [{"name": "PFOA", "confidence": 1.0}],
        }
        assert HarmScoreCalculator.calculate(data) == 40

    def test_pfas_multiple_compounds_cap_100(self):
        """3 PFAS = 120 raw → capped at 100."""
        data = {
            "pfas_detected": [
                {"name": "PFOA", "confidence": 1.0},
                {"name": "PFOS", "confidence": 1.0},
                {"name": "PTFE", "confidence": 1.0},
            ],
        }
        assert HarmScoreCalculator.calculate(data) == 100

    # ── Other concerns (category-based) ─────────────────────

    def test_concern_carcinogen(self):
        """carcinogen = 40 points."""
        data = {
            "other_concerns": [{"category": "carcinogen", "confidence": 1.0}],
        }
        assert HarmScoreCalculator.calculate(data) == 40

    def test_concern_under_investigation_capped(self):
        """under_investigation = 5 points → floor 25."""
        data = {
            "other_concerns": [{"category": "under_investigation", "confidence": 1.0}],
        }
        assert HarmScoreCalculator.calculate(data) == 25  # 5 pts → floor 25

    def test_concern_unknown_category_severity_fallback(self):
        """Unknown category falls back to severity-based scoring."""
        data = {
            "other_concerns": [
                {"category": "xyz_unknown", "severity": "high", "confidence": 1.0}
            ],
        }
        assert HarmScoreCalculator.calculate(data) == 35  # high=35

    # ── Confidence weighting ────────────────────────────────

    def test_confidence_weighting_on_allergen(self):
        """severe (50) * confidence 0.5 = 25 points."""
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 0.5}],
        }
        assert HarmScoreCalculator.calculate(data) == 25

    def test_low_confidence_penalty(self):
        """Global confidence 0.5 adds (0.7 - 0.5) * 20 = 4 penalty."""
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "confidence": 0.5,
        }
        # 50 (severe) + 4 (penalty) = 54
        assert HarmScoreCalculator.calculate(data) == 54

    def test_confidence_exactly_0_7_no_penalty(self):
        """Confidence = 0.7 → no penalty added."""
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "confidence": 0.7,
        }
        assert HarmScoreCalculator.calculate(data) == 50

    # ── Category multipliers ────────────────────────────────

    def test_pesticide_multiplier_1_4(self):
        """Product name containing 'pesticide' → 1.4x."""
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "product_name": "Garden Pesticide Spray",
            "category": "",
        }
        # 50 * 1.4 = 70
        assert HarmScoreCalculator.calculate(data) == 70

    def test_bleach_keyword_multiplier_1_3(self):
        """Product name containing 'bleach' → 1.3x (high-risk keyword)."""
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "product_name": "Bleach Cleaner",
            "category": "",
        }
        # 50 * 1.3 = 65
        assert HarmScoreCalculator.calculate(data) == 65

    def test_no_multiplier_normal_product(self):
        """Normal product name → 1.0x (no boost)."""
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "product_name": "Sunscreen SPF 50",
            "category": "skincare",
        }
        assert HarmScoreCalculator.calculate(data) == 50

    # ── Edge cases ──────────────────────────────────────────

    def test_minimum_floor_25_with_any_concern(self):
        """Any concern detected → minimum score of 25."""
        data = {
            "allergens_detected": [{"severity": "low", "confidence": 0.3}],
        }
        # 8 * 0.3 = 2.4 → floor 25
        assert HarmScoreCalculator.calculate(data) == 25

    def test_maximum_cap_100(self):
        """Extreme input capped at 100."""
        data = {
            "allergens_detected": [
                {"severity": "severe", "confidence": 1.0},
                {"severity": "severe", "confidence": 1.0},
            ],
            "pfas_detected": [
                {"name": "PFOA", "confidence": 1.0},
                {"name": "PFOS", "confidence": 1.0},
            ],
            "other_concerns": [
                {"category": "carcinogen", "confidence": 1.0},
            ],
            "product_name": "Toxic Pesticide",
            "category": "pesticide",
        }
        assert HarmScoreCalculator.calculate(data) == 100

    def test_combined_allergens_pfas_multiplier_penalty(self):
        """Combined: allergen + PFAS + multiplier + penalty."""
        data = {
            "allergens_detected": [{"severity": "high", "confidence": 1.0}],  # 35
            "pfas_detected": [{"name": "PFOA", "confidence": 1.0}],  # 40
            "confidence": 0.5,  # penalty: (0.7-0.5)*20 = 4
            "product_name": "Household Cleaner",  # 1.2x
            "category": "household_cleaner",
        }
        # (35 + 40) * 1.2 + 4 = 90 + 4 = 94
        assert HarmScoreCalculator.calculate(data) == 94


class TestGetRiskLevel:
    """Tests for HarmScoreCalculator.get_risk_level()."""

    @pytest.mark.parametrize(
        "score,expected",
        [
            (0, "Safe"),
            (15, "Safe"),
            (30, "Safe"),
            (31, "Moderate Risk"),
            (45, "Moderate Risk"),
            (60, "Moderate Risk"),
            (61, "High Risk"),
            (70, "High Risk"),
            (80, "High Risk"),
            (81, "Dangerous"),
            (90, "Dangerous"),
            (100, "Dangerous"),
        ],
    )
    def test_risk_level_boundaries(self, score, expected):
        assert HarmScoreCalculator.get_risk_level(score) == expected
