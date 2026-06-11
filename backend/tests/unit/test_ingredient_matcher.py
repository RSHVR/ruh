"""Unit tests for ingredient_matcher.

Tests match_ingredients_to_databases() and _deduplicate_detections().
Fixtures use real Supabase field shapes from the allergens, pfas_compounds,
and toxic_substances tables.
"""

import pytest
from src.domain.ingredient_matcher import (
    match_ingredients_to_databases,
    _deduplicate_detections,
    _map_severity_int_to_label,
    similar,
)


# ── Fixtures: Real DB field shapes ──────────────────────────


ALLERGEN_PEANUTS = {
    "name": "Peanuts",
    "severity_default": 10,
    "severity_range": "potentially_life_threatening",
    "allergen_type": "food",
    "synonyms": ["groundnut", "Arachis hypogaea", "monkey nuts"],
}

ALLERGEN_FRAGRANCE = {
    "name": "Fragrance Mix I",
    "severity_default": 5,
    "severity_range": "mild_to_moderate",
    "allergen_type": "fragrance",
    "synonyms": [
        "cinnamal", "cinnamyl alcohol", "eugenol", "isoeugenol",
        "geraniol", "hydroxycitronellal", "oak moss absolute",
    ],
}

ALLERGEN_LATEX = {
    "name": "Latex",
    "severity_default": 8,
    "severity_range": "potentially_life_threatening",
    "allergen_type": "latex",
    "synonyms": ["natural rubber latex", "rubber", "Hevea brasiliensis"],
}

ALLERGEN_NO_NAME = {
    "severity_default": 5,
    "allergen_type": "unknown",
}

PFAS_PFOA = {
    "name": "PFOA",
    "cas_number": "335-67-1",
    "health_impacts": ["liver damage", "thyroid disease", "cancer"],
    "body_effects": "Liver damage, thyroid disease, increased cancer risk",
    "synonyms": ["perfluorooctanoic acid", "C8"],
}

PFAS_PFOS = {
    "name": "PFOS",
    "cas_number": "1763-23-1",
    "health_impacts": ["liver damage", "immune effects", "cancer"],
    "body_effects": "Liver damage, immune suppression, developmental effects",
    "synonyms": ["perfluorooctane sulfonate"],
}

PFAS_PTFE = {
    "name": "PTFE",
    "cas_number": "9002-84-0",
    "health_impacts": ["polymer fume fever", "respiratory effects"],
    "body_effects": "Polymer fume fever when overheated, respiratory irritation",
    "synonyms": ["polytetrafluoroethylene", "Teflon", "fluoropolymer"],
}

TOXIC_DEHP = {
    "name": "DEHP",
    "cas_number": "117-81-7",
    "substance_category": "phthalate",
    "health_impacts": ["testicular toxicity", "reduced sperm count", "liver toxicity"],
    "body_effects": "Reproductive toxicity (anti-androgenic), liver damage",
    "concentration_limits": {"toys": "0.1%", "cosmetics_EU": "0%"},
    "synonyms": ["di(2-ethylhexyl) phthalate"],
}

TOXIC_BPA = {
    "name": "BPA",
    "cas_number": "80-05-7",
    "substance_category": "bisphenol",
    "health_impacts": ["endocrine disruption", "reproductive effects"],
    "body_effects": "Endocrine disruption, estrogenic activity",
    "concentration_limits": {"food_contact_EU": "0.04 mg/kg"},
    "synonyms": ["bisphenol A", "4,4'-isopropylidenediphenol"],
}

TOXIC_LEAD = {
    "name": "Lead",
    "cas_number": "7439-92-1",
    "substance_category": "heavy_metal",
    "health_impacts": ["neurotoxicity", "developmental effects", "kidney damage"],
    "body_effects": "Neurotoxicity, developmental delays in children, kidney damage",
    "concentration_limits": {"cosmetics_FDA": "10 ppm", "drinking_water_EPA": "15 ppb"},
    "synonyms": ["Pb", "plumbum"],
}

ALL_ALLERGENS = [ALLERGEN_PEANUTS, ALLERGEN_FRAGRANCE, ALLERGEN_LATEX]
ALL_PFAS = [PFAS_PFOA, PFAS_PFOS, PFAS_PTFE]
ALL_TOXIC = [TOXIC_DEHP, TOXIC_BPA, TOXIC_LEAD]


class TestIngredientMatcher:
    """Tests for match_ingredients_to_databases()."""

    # ── Exact substring matching ────────────────────────────

    def test_exact_match_allergen(self):
        """Direct name match → confidence 0.9."""
        result = match_ingredients_to_databases(
            ingredients=["Fragrance Mix I", "Water"],
            materials=[],
            allergen_database=ALL_ALLERGENS,
            pfas_database=[],
        )
        assert len(result["allergens_detected"]) == 1
        assert result["allergens_detected"][0]["name"] == "Fragrance Mix I"
        assert result["allergens_detected"][0]["confidence"] == 0.9

    def test_exact_match_component_in_allergen_name(self):
        """Component 'Latex' is substring of allergen name 'Latex'."""
        result = match_ingredients_to_databases(
            ingredients=["Latex gloves"],
            materials=[],
            allergen_database=[ALLERGEN_LATEX],
            pfas_database=[],
        )
        assert len(result["allergens_detected"]) == 1
        assert result["allergens_detected"][0]["name"] == "Latex"

    def test_exact_match_pfas(self):
        """PFAS name in component → confidence 0.9."""
        result = match_ingredients_to_databases(
            ingredients=["PTFE coating"],
            materials=[],
            allergen_database=[],
            pfas_database=ALL_PFAS,
        )
        assert len(result["pfas_detected"]) == 1
        assert result["pfas_detected"][0]["name"] == "PTFE"
        assert result["pfas_detected"][0]["confidence"] == 0.9

    def test_case_insensitive_matching(self):
        """Matching is case-insensitive."""
        result = match_ingredients_to_databases(
            ingredients=["FRAGRANCE MIX I"],
            materials=[],
            allergen_database=ALL_ALLERGENS,
            pfas_database=[],
        )
        assert len(result["allergens_detected"]) == 1
        assert result["allergens_detected"][0]["name"] == "Fragrance Mix I"

    # ── CAS number matching ─────────────────────────────────

    def test_cas_number_match_pfoa(self):
        """CAS number in component text → confidence 0.95."""
        result = match_ingredients_to_databases(
            ingredients=["PFOA (335-67-1)"],
            materials=[],
            allergen_database=[],
            pfas_database=ALL_PFAS,
        )
        # Should match by name substring first (0.9), not CAS
        # since "PFOA" is in "PFOA (335-67-1)"
        detected = result["pfas_detected"]
        assert len(detected) == 1
        assert detected[0]["name"] == "PFOA"

    def test_cas_number_match_pfos(self):
        """CAS number match when name doesn't substring-match."""
        result = match_ingredients_to_databases(
            ingredients=["Chemical compound 1763-23-1"],
            materials=[],
            allergen_database=[],
            pfas_database=ALL_PFAS,
        )
        detected = result["pfas_detected"]
        assert len(detected) == 1
        assert detected[0]["name"] == "PFOS"
        assert detected[0]["confidence"] == 0.95

    # ── Fuzzy matching ──────────────────────────────────────

    def test_fuzzy_match_above_threshold(self):
        """Slight typo still matches above default 0.75 threshold."""
        result = match_ingredients_to_databases(
            ingredients=["Fragrancee Mix I"],  # typo: double 'e'
            materials=[],
            allergen_database=ALL_ALLERGENS,
            pfas_database=[],
        )
        # "Fragrancee Mix I" vs "Fragrance Mix I" → substring match
        # because "Fragrance Mix I".lower() in "Fragrancee Mix I".lower() is False
        # but "fragrancee mix i" does not contain "fragrance mix i" exactly
        # So this goes to fuzzy. similarity("Fragrancee Mix I", "Fragrance Mix I") ≈ 0.93
        detected = result["allergens_detected"]
        assert len(detected) >= 1

    def test_fuzzy_match_below_threshold_no_match(self):
        """'Water' vs 'Fragrance Mix I' → too different, no match."""
        result = match_ingredients_to_databases(
            ingredients=["Water"],
            materials=[],
            allergen_database=[ALLERGEN_FRAGRANCE],
            pfas_database=[],
        )
        assert len(result["allergens_detected"]) == 0

    def test_custom_similarity_threshold(self):
        """Higher threshold rejects matches that default would accept."""
        result = match_ingredients_to_databases(
            ingredients=["Fragrancee Mix I"],
            materials=[],
            allergen_database=[ALLERGEN_FRAGRANCE],
            pfas_database=[],
            similarity_threshold=0.99,
        )
        assert len(result["allergens_detected"]) == 0

    # ── Edge cases ──────────────────────────────────────────

    def test_empty_inputs_confidence_0_3(self):
        """No ingredients + no materials → confidence 0.3."""
        result = match_ingredients_to_databases(
            ingredients=[],
            materials=[],
            allergen_database=ALL_ALLERGENS,
            pfas_database=ALL_PFAS,
        )
        assert result["allergens_detected"] == []
        assert result["pfas_detected"] == []
        assert result["confidence"] == 0.3

    def test_short_component_skipped(self):
        """Components shorter than 2 chars are skipped."""
        result = match_ingredients_to_databases(
            ingredients=["A"],
            materials=[],
            allergen_database=ALL_ALLERGENS,
            pfas_database=ALL_PFAS,
        )
        assert result["allergens_detected"] == []
        assert result["pfas_detected"] == []

    def test_missing_name_field_skipped(self):
        """Allergen records without 'name' are skipped."""
        result = match_ingredients_to_databases(
            ingredients=["Peanuts"],
            materials=[],
            allergen_database=[ALLERGEN_NO_NAME],
            pfas_database=[],
        )
        assert len(result["allergens_detected"]) == 0

    def test_no_matches_with_ingredients_conf_0_7(self):
        """Ingredients provided but no matches → confidence 0.7."""
        result = match_ingredients_to_databases(
            ingredients=["Water", "Glycerin"],
            materials=[],
            allergen_database=[],
            pfas_database=[],
        )
        assert result["confidence"] == 0.7

    # ── Deduplication ───────────────────────────────────────

    def test_duplicate_detection_keeps_highest_conf(self):
        """Same allergen found in two ingredients → highest confidence kept."""
        result = match_ingredients_to_databases(
            ingredients=["Peanuts", "Peanut butter"],
            materials=[],
            allergen_database=[ALLERGEN_PEANUTS],
            pfas_database=[],
        )
        # Both will match "Peanuts" but dedup keeps only one
        assert len(result["allergens_detected"]) == 1

    # ── Combined ────────────────────────────────────────────

    def test_materials_checked_for_pfas(self):
        """Materials list is also checked (not just ingredients)."""
        result = match_ingredients_to_databases(
            ingredients=[],
            materials=["PTFE non-stick coating"],
            allergen_database=[],
            pfas_database=ALL_PFAS,
        )
        assert len(result["pfas_detected"]) == 1
        assert result["pfas_detected"][0]["name"] == "PTFE"

    def test_output_structure_has_all_keys(self):
        """Verify output dict has all expected keys."""
        result = match_ingredients_to_databases(
            ingredients=["Water"],
            materials=[],
            allergen_database=[],
            pfas_database=[],
        )
        assert "allergens_detected" in result
        assert "pfas_detected" in result
        assert "other_concerns" in result
        assert "confidence" in result
        assert "method" in result
        assert result["method"] == "database_matching"

    # ── Severity mapping (fixed) ───────────────────────────

    def test_severity_mapped_from_severity_default(self):
        """severity_default int is mapped to frontend label string."""
        result = match_ingredients_to_databases(
            ingredients=["Peanuts"],
            materials=[],
            allergen_database=[ALLERGEN_PEANUTS],  # severity_default=10
            pfas_database=[],
        )
        detected = result["allergens_detected"]
        assert len(detected) == 1
        assert detected[0]["severity"] == "severe"  # 10 → severe

    def test_severity_mapping_moderate(self):
        """severity_default=5 → moderate."""
        result = match_ingredients_to_databases(
            ingredients=["Fragrance Mix I"],
            materials=[],
            allergen_database=[ALLERGEN_FRAGRANCE],  # severity_default=5
            pfas_database=[],
        )
        detected = result["allergens_detected"]
        assert len(detected) == 1
        assert detected[0]["severity"] == "moderate"

    def test_severity_mapping_high(self):
        """severity_default=8 → high."""
        result = match_ingredients_to_databases(
            ingredients=["Latex"],
            materials=[],
            allergen_database=[ALLERGEN_LATEX],  # severity_default=8
            pfas_database=[],
        )
        detected = result["allergens_detected"]
        assert len(detected) == 1
        assert detected[0]["severity"] == "high"


class TestToxicSubstanceMatching:
    """Tests for toxic_database matching (other_concerns)."""

    def test_toxic_exact_match_dehp(self):
        """DEHP in ingredients → detected in other_concerns."""
        result = match_ingredients_to_databases(
            ingredients=["DEHP plasticizer"],
            materials=[],
            allergen_database=[],
            pfas_database=[],
            toxic_database=ALL_TOXIC,
        )
        concerns = result["other_concerns"]
        assert len(concerns) == 1
        assert concerns[0]["name"] == "DEHP"
        assert concerns[0]["category"] == "endocrine_disruptor"
        assert concerns[0]["confidence"] == 0.9
        assert concerns[0]["concentration_limits"] is not None

    def test_toxic_cas_number_match(self):
        """CAS number match for BPA."""
        result = match_ingredients_to_databases(
            ingredients=["Compound 80-05-7 residue"],
            materials=[],
            allergen_database=[],
            pfas_database=[],
            toxic_database=[TOXIC_BPA],
        )
        concerns = result["other_concerns"]
        assert len(concerns) == 1
        assert concerns[0]["name"] == "BPA"
        assert concerns[0]["confidence"] == 0.95

    def test_toxic_heavy_metal_category(self):
        """Heavy metals get heavy_metal category."""
        result = match_ingredients_to_databases(
            ingredients=["Lead paint"],
            materials=[],
            allergen_database=[],
            pfas_database=[],
            toxic_database=[TOXIC_LEAD],
        )
        concerns = result["other_concerns"]
        assert len(concerns) == 1
        assert concerns[0]["category"] == "heavy_metal"

    def test_toxic_in_materials(self):
        """Materials list is also checked for toxic substances."""
        result = match_ingredients_to_databases(
            ingredients=[],
            materials=["BPA-free plastic"],  # "BPA" substring matches
            allergen_database=[],
            pfas_database=[],
            toxic_database=[TOXIC_BPA],
        )
        concerns = result["other_concerns"]
        assert len(concerns) == 1
        assert concerns[0]["name"] == "BPA"

    def test_no_toxic_database_backward_compatible(self):
        """Omitting toxic_database still works (backward compatible)."""
        result = match_ingredients_to_databases(
            ingredients=["Water"],
            materials=[],
            allergen_database=[],
            pfas_database=[],
        )
        assert result["other_concerns"] == []

    def test_combined_all_databases(self):
        """Allergens + PFAS + toxic substances all detected together."""
        result = match_ingredients_to_databases(
            ingredients=["Peanuts", "PFOA coating", "DEHP"],
            materials=[],
            allergen_database=ALL_ALLERGENS,
            pfas_database=ALL_PFAS,
            toxic_database=ALL_TOXIC,
        )
        assert len(result["allergens_detected"]) >= 1
        assert len(result["pfas_detected"]) >= 1
        assert len(result["other_concerns"]) >= 1


class TestDeduplicateDetections:
    """Tests for _deduplicate_detections()."""

    def test_keeps_highest_confidence(self):
        detections = [
            {"name": "PFOA", "confidence": 0.7},
            {"name": "PFOA", "confidence": 0.95},
            {"name": "PFOA", "confidence": 0.8},
        ]
        result = _deduplicate_detections(detections, "name")
        assert len(result) == 1
        assert result[0]["confidence"] == 0.95

    def test_no_duplicates_returns_all(self):
        detections = [
            {"name": "PFOA", "confidence": 0.9},
            {"name": "PFOS", "confidence": 0.85},
            {"name": "PTFE", "confidence": 0.8},
        ]
        result = _deduplicate_detections(detections, "name")
        assert len(result) == 3

    def test_empty_list(self):
        result = _deduplicate_detections([], "name")
        assert result == []


class TestMapSeverityIntToLabel:
    """Tests for _map_severity_int_to_label()."""

    @pytest.mark.parametrize(
        "severity_default,expected",
        [
            (10, "severe"),   # Peanuts
            (9, "severe"),    # Shellfish, Fish, Tree Nuts
            (8, "high"),      # Milk, Eggs, Latex
            (7, "high"),
            (6, "moderate"),
            (5, "moderate"),  # Fragrance Mix I
            (4, "moderate"),
            (3, "low"),       # Celery
            (2, "low"),
            (1, "low"),
        ],
    )
    def test_severity_boundaries(self, severity_default, expected):
        assert _map_severity_int_to_label(severity_default) == expected


class TestSimilarFunction:
    """Tests for the similar() string comparison helper."""

    def test_identical_strings(self):
        assert similar("Peanuts", "Peanuts") == 1.0

    def test_case_insensitive(self):
        assert similar("PEANUTS", "peanuts") == 1.0

    def test_completely_different(self):
        assert similar("Water", "Xylenol") < 0.5
