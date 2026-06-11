"""Unit tests for HarmScoreCalculator.

Scoring model (tuned 2026-06-11 against the benchmark ground-truth bands):
- Allergens: SEVERITY_POINTS (low=8, moderate=18, high=35, severe=50) x confidence.
- PFAS: PFAS_POINTS (45) x confidence.
- Other concerns: CATEGORY_POINTS x CONCERN_SEVERITY_FACTORS (low=0.4,
  moderate=0.7, high=1.0, severe=1.2; absent severity -> 1.0) x confidence.
- Product-category multiplier applied per finding (pesticide=1.4, bleach=1.3...).
- Findings combine as a risk union: 100 * (1 - prod(1 - c_i/100)) — the worst
  finding dominates, stacking is sub-linear, saturation is asymptotic.
- Global confidence < 0.7 adds a caution bonus of (0.7 - conf) * 20.
- No unconditional floor: low-grade findings may score below 25.
- Clamped to [0, 100], int.
"""

import pytest
from src.domain.harm_calculator import HarmScoreCalculator


def calc(**kwargs):
    return HarmScoreCalculator.calculate(kwargs)


class TestBaseline:
    """Characterization: empty/clean analyses are unchanged."""

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

    def test_empty_with_low_confidence_adds_caution_only(self):
        """No findings + global confidence 0.5 -> just the caution bonus (4)."""
        assert calc(confidence=0.5) == 4

    def test_returns_int_in_bounds(self):
        score = calc(
            allergens_detected=[{"severity": "severe", "confidence": 1.0}],
            pfas_detected=[{"name": "PFOA", "confidence": 1.0}],
        )
        assert isinstance(score, int)
        assert 0 <= score <= 100


class TestSingleFindingSemantics:
    """Characterization: a single finding scores exactly its weighted points."""

    def test_allergen_high_severity(self):
        data = {"allergens_detected": [{"severity": "high", "confidence": 1.0}]}
        assert HarmScoreCalculator.calculate(data) == 35

    def test_allergen_severe_severity(self):
        data = {"allergens_detected": [{"severity": "severe", "confidence": 1.0}]}
        assert HarmScoreCalculator.calculate(data) == 50

    def test_allergen_confidence_weighting(self):
        """severe (50) * confidence 0.5 = 25 points."""
        data = {"allergens_detected": [{"severity": "severe", "confidence": 0.5}]}
        assert HarmScoreCalculator.calculate(data) == 25

    def test_concern_carcinogen_no_severity_field(self):
        """carcinogen without a severity field keeps full category points (40)."""
        data = {"other_concerns": [{"category": "carcinogen", "confidence": 1.0}]}
        assert HarmScoreCalculator.calculate(data) == 40

    def test_concern_unknown_category_severity_fallback(self):
        """Unknown category falls back to severity-based scoring."""
        data = {
            "other_concerns": [
                {"category": "xyz_unknown", "severity": "high", "confidence": 1.0}
            ]
        }
        assert HarmScoreCalculator.calculate(data) == 35  # high=35


class TestNoUnconditionalFloor:
    """New behavior: low-grade findings score their own (low) points — the
    min-25 floor is gone, so the clean-control band [0, 20] is reachable."""

    def test_allergen_low_severity_scores_below_25(self):
        data = {"allergens_detected": [{"severity": "low", "confidence": 1.0}]}
        assert HarmScoreCalculator.calculate(data) == 8

    def test_allergen_moderate_severity(self):
        data = {"allergens_detected": [{"severity": "moderate", "confidence": 1.0}]}
        assert HarmScoreCalculator.calculate(data) == 18

    def test_allergen_unknown_severity_defaults_to_8(self):
        data = {"allergens_detected": [{"severity": "xyz_unknown", "confidence": 1.0}]}
        assert HarmScoreCalculator.calculate(data) == 8

    def test_low_confidence_low_severity_scores_low(self):
        data = {"allergens_detected": [{"severity": "low", "confidence": 0.3}]}
        assert HarmScoreCalculator.calculate(data) == 2  # 8 * 0.3 = 2.4 -> 2

    def test_under_investigation_scores_its_capped_points(self):
        data = {"other_concerns": [{"category": "under_investigation", "confidence": 1.0}]}
        assert HarmScoreCalculator.calculate(data) == 5

    def test_clean_control_archetype_fits_safe_band(self):
        """le_creuset archetype: one trace heavy-metal note (low severity,
        conf 0.55) must stay inside the clean ground-truth band [0, 20]."""
        data = {
            "other_concerns": [
                {"category": "heavy_metal", "severity": "low", "confidence": 0.55}
            ],
            "confidence": 0.88,
            "product_name": "Enameled Cast Iron Skillet",
        }
        score = HarmScoreCalculator.calculate(data)
        assert 0 < score <= 20  # 25 * 0.4 * 0.55 = 5.5 -> 5


class TestConcernSeverityScaling:
    """New behavior: category points are scaled by the concern's own severity."""

    def test_heavy_metal_low_below_high(self):
        low = calc(other_concerns=[
            {"category": "heavy_metal", "severity": "low", "confidence": 1.0}])
        high = calc(other_concerns=[
            {"category": "heavy_metal", "severity": "high", "confidence": 1.0}])
        assert low == 10   # 25 * 0.4
        assert high == 25  # 25 * 1.0

    def test_severity_ordering_within_category(self):
        scores = [
            calc(other_concerns=[
                {"category": "regulatory_action", "severity": s, "confidence": 1.0}])
            for s in ("low", "moderate", "high", "severe")
        ]
        assert scores == sorted(scores)
        assert scores[0] < scores[-1]

    def test_severe_concern_exceeds_base_category_points(self):
        """severe factor (1.2) pushes above the category base."""
        severe = calc(other_concerns=[
            {"category": "carcinogen", "severity": "severe", "confidence": 1.0}])
        assert severe == 48  # 40 * 1.2


class TestPfasScoring:
    """PFAS keep dominance; multi-PFAS stays Dangerous without pinning at 100."""

    def test_pfas_single_compound(self):
        data = {"pfas_detected": [{"name": "PFOA", "confidence": 1.0}]}
        assert HarmScoreCalculator.calculate(data) == 45

    def test_pfas_single_compound_at_least_40(self):
        """Characterization: a confirmed PFAS alone is at least moderate-high."""
        assert calc(pfas_detected=[{"name": "PTFE", "confidence": 1.0}]) >= 40

    def test_pfas_three_compounds_dangerous_with_headroom(self):
        """3 PFAS = risk union 1 - 0.55^3 -> 83: Dangerous (>80) but not pinned at 100."""
        data = {
            "pfas_detected": [
                {"name": "PFOA", "confidence": 1.0},
                {"name": "PFOS", "confidence": 1.0},
                {"name": "PTFE", "confidence": 1.0},
            ]
        }
        score = HarmScoreCalculator.calculate(data)
        assert score == 83
        assert 80 < score < 100

    def test_pfas_product_scores_higher_than_without(self):
        base = {
            "allergens_detected": [{"severity": "moderate", "confidence": 1.0}],
            "other_concerns": [{"category": "other", "severity": "moderate", "confidence": 0.8}],
        }
        with_pfas = dict(base, pfas_detected=[{"name": "PTFE", "confidence": 1.0}])
        assert (HarmScoreCalculator.calculate(with_pfas)
                > HarmScoreCalculator.calculate(base))


class TestStackingSubLinearity:
    """New behavior: findings combine as a risk union (sub-linear, monotonic)."""

    def test_two_severe_allergens_sublinear(self):
        """50 + 50 linear would clamp at 100; risk union gives 75."""
        data = {
            "allergens_detected": [
                {"severity": "severe", "confidence": 1.0},
                {"severity": "severe", "confidence": 1.0},
            ]
        }
        assert HarmScoreCalculator.calculate(data) == 75

    def test_combined_below_sum_above_max(self):
        a = {"allergens_detected": [{"severity": "high", "confidence": 1.0}]}
        b = {"other_concerns": [{"category": "regulatory_action", "severity": "moderate",
                                 "confidence": 0.8}]}
        both = {
            "allergens_detected": a["allergens_detected"],
            "other_concerns": b["other_concerns"],
        }
        sa = HarmScoreCalculator.calculate(a)
        sb = HarmScoreCalculator.calculate(b)
        sab = HarmScoreCalculator.calculate(both)
        assert sab < sa + sb
        assert sab >= max(sa, sb)

    def test_adding_a_finding_never_lowers_score(self):
        base = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "other_concerns": [{"category": "regulatory_action", "severity": "moderate",
                                "confidence": 0.8}],
        }
        more = {
            "allergens_detected": base["allergens_detected"]
            + [{"severity": "moderate", "confidence": 0.85}],
            "other_concerns": base["other_concerns"],
        }
        assert (HarmScoreCalculator.calculate(more)
                >= HarmScoreCalculator.calculate(base))

    def test_raising_severity_never_lowers_score(self):
        lo = calc(allergens_detected=[{"severity": "moderate", "confidence": 1.0}],
                  other_concerns=[{"category": "heavy_metal", "severity": "low",
                                   "confidence": 0.9}])
        hi = calc(allergens_detected=[{"severity": "severe", "confidence": 1.0}],
                  other_concerns=[{"category": "heavy_metal", "severity": "high",
                                   "confidence": 0.9}])
        assert hi >= lo

    def test_saturation_headroom_severe_plus_moderates(self):
        """skippy archetype: severe allergen + moderate allergen + 2 concerns
        no longer lands 85-100 (risk union -> 65)."""
        data = {
            "allergens_detected": [
                {"severity": "severe", "confidence": 1.0},
                {"severity": "moderate", "confidence": 0.85},
            ],
            "other_concerns": [
                {"category": "regulatory_action", "severity": "moderate", "confidence": 0.8},
                {"category": "under_investigation", "severity": "low", "confidence": 0.5},
            ],
            "confidence": 0.88,
            "product_name": "Creamy Peanut Butter",
        }
        score = HarmScoreCalculator.calculate(data)
        assert 50 <= score < 85
        assert score == 65

    def test_extreme_stacking_stays_high_without_pinning(self):
        """Extreme input still reads near-maximal (>= 95) — real signal not crushed."""
        data = {
            "allergens_detected": [
                {"severity": "severe", "confidence": 1.0},
                {"severity": "severe", "confidence": 1.0},
            ],
            "pfas_detected": [
                {"name": "PFOA", "confidence": 1.0},
                {"name": "PFOS", "confidence": 1.0},
            ],
            "other_concerns": [{"category": "carcinogen", "confidence": 1.0}],
            "product_name": "Toxic Pesticide",
            "category": "pesticide",
        }
        score = HarmScoreCalculator.calculate(data)
        assert 95 <= score <= 100

    def test_true_hazard_product_stays_high(self):
        """tfal archetype: PFAS + metal allergens + a concern stays >= 40."""
        data = {
            "allergens_detected": [
                {"severity": "low", "confidence": 0.75},
                {"severity": "low", "confidence": 0.75},
            ],
            "pfas_detected": [{"name": "PTFE", "confidence": 1.0}],
            "other_concerns": [{"category": "other", "severity": "moderate",
                                "confidence": 0.9}],
            "confidence": 0.9,
            "product_name": "Nonstick Skillet",
        }
        assert HarmScoreCalculator.calculate(data) >= 40

    def test_fuzz_adding_findings_is_monotonic(self):
        """Seeded fuzz: appending any finding to any analysis never lowers
        the score, and scores stay int within [0, 100]."""
        import random

        rng = random.Random(20260611)
        severities = ["low", "moderate", "high", "severe"]
        categories = ["under_investigation", "carcinogen", "regulatory_action",
                      "heavy_metal", "endocrine_disruptor", "other", "weird_cat"]

        def random_finding():
            kind = rng.choice(["allergen", "pfas", "concern"])
            conf = round(rng.uniform(0.1, 1.0), 2)
            if kind == "allergen":
                return kind, {"severity": rng.choice(severities), "confidence": conf}
            if kind == "pfas":
                return kind, {"name": "PFX", "confidence": conf}
            return kind, {"category": rng.choice(categories),
                          "severity": rng.choice(severities), "confidence": conf}

        key = {"allergen": "allergens_detected", "pfas": "pfas_detected",
               "concern": "other_concerns"}
        for _ in range(200):
            data = {
                "allergens_detected": [], "pfas_detected": [], "other_concerns": [],
                "confidence": round(rng.uniform(0.3, 1.0), 2),
                "product_name": rng.choice(["Soap", "Pesticide Spray", "Skillet"]),
            }
            prev = HarmScoreCalculator.calculate(data)
            for _ in range(rng.randint(1, 6)):
                kind, finding = random_finding()
                data[key[kind]].append(finding)
                score = HarmScoreCalculator.calculate(data)
                assert isinstance(score, int)
                assert 0 <= score <= 100
                assert score >= prev, f"monotonicity violated: {prev} -> {score} on {data}"
                prev = score


class TestConfidenceCaution:
    """Characterization: global low confidence adds caution points."""

    def test_low_confidence_penalty(self):
        """Global confidence 0.5 adds (0.7 - 0.5) * 20 = 4."""
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "confidence": 0.5,
        }
        assert HarmScoreCalculator.calculate(data) == 54

    def test_confidence_exactly_0_7_no_penalty(self):
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "confidence": 0.7,
        }
        assert HarmScoreCalculator.calculate(data) == 50

    def test_lower_finding_confidence_never_raises_score(self):
        hi = calc(allergens_detected=[{"severity": "severe", "confidence": 1.0}])
        lo = calc(allergens_detected=[{"severity": "severe", "confidence": 0.6}])
        assert lo <= hi


class TestCategoryMultipliers:
    """Characterization: product-class multipliers preserved (per finding)."""

    def test_pesticide_multiplier_1_4(self):
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "product_name": "Garden Pesticide Spray",
            "category": "",
        }
        assert HarmScoreCalculator.calculate(data) == 70  # 50 * 1.4

    def test_bleach_keyword_multiplier_1_3(self):
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "product_name": "Bleach Cleaner",
            "category": "",
        }
        assert HarmScoreCalculator.calculate(data) == 65  # 50 * 1.3

    def test_no_multiplier_normal_product(self):
        data = {
            "allergens_detected": [{"severity": "severe", "confidence": 1.0}],
            "product_name": "Sunscreen SPF 50",
            "category": "skincare",
        }
        assert HarmScoreCalculator.calculate(data) == 50

    def test_multiplier_never_lowers_score(self):
        plain = calc(allergens_detected=[{"severity": "high", "confidence": 1.0}],
                     pfas_detected=[{"name": "PFOA", "confidence": 1.0}],
                     product_name="Skillet")
        boosted = calc(allergens_detected=[{"severity": "high", "confidence": 1.0}],
                       pfas_detected=[{"name": "PFOA", "confidence": 1.0}],
                       product_name="Household Cleaner",
                       category="household_cleaner")
        assert boosted >= plain

    def test_combined_allergens_pfas_multiplier_penalty(self):
        """high (35*1.2=42) U pfas (45*1.2=54) -> 73.32 + 4 caution = 77."""
        data = {
            "allergens_detected": [{"severity": "high", "confidence": 1.0}],
            "pfas_detected": [{"name": "PFOA", "confidence": 1.0}],
            "confidence": 0.5,
            "product_name": "Household Cleaner",
            "category": "household_cleaner",
        }
        assert HarmScoreCalculator.calculate(data) == 77


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
