"""Harm score calculation logic."""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class HarmScoreCalculator:
    """Calculate harm score (0-100) based on detected substances.

    Score breakdown:
    - 0-30: Safe
    - 31-60: Moderate risk
    - 61-80: High risk
    - 81-100: Dangerous

    Optimized formula philosophy:
    - Be aggressive with scoring dangerous products (database-validated)
    - Each severe toxin should significantly impact score
    - Product categories (pesticides, cleaners) get multipliers
    - "under_investigation" substances get capped low scores (max 5 points)
    - Confidence weighting to prevent false positives from inflating scores
    """

    # Base points per concern severity
    SEVERITY_POINTS = {
        "low": 8,
        "moderate": 18,
        "high": 35,
        "severe": 50,
    }

    # Category-specific scoring for other_concerns
    CATEGORY_POINTS = {
        "under_investigation": 5,  # Capped: substances not in database
        "carcinogen": 40,          # IARC-classified carcinogens
        "regulatory_action": 30,   # FDA recall, EPA warning, lawsuits
        "heavy_metal": 25,         # Heavy metals (lead, mercury, etc.)
        "endocrine_disruptor": 25, # Hormone disruptors
        "other": 15,               # Other credible concerns
    }

    # Product category multipliers
    CATEGORY_MULTIPLIERS = {
        "pesticide": 1.4,
        "insecticide": 1.4,
        "herbicide": 1.4,
        "household_cleaner": 1.2,
        "disinfectant": 1.2,
        "chemical_product": 1.15,
    }

    @staticmethod
    def calculate(analysis_data: Dict[str, Any]) -> int:
        """Calculate harm score from analysis data.

        Optimized formula:
        1. Start with base score of 0
        2. Add points for allergens (severity-based, confidence-weighted)
        3. Add points for PFAS (fixed 40 points each, confidence-weighted)
        4. Add points for other_concerns (category-based scoring)
        5. Apply product category multiplier
        6. Apply confidence adjustment
        7. Cap at 100

        Args:
            analysis_data: Dict with 'allergens_detected', 'pfas_detected', 'other_concerns',
                          'confidence', 'product_name', 'category'

        Returns:
            Harm score (0-100)
        """
        base_score = 0.0
        breakdown = {
            "allergens": 0.0,
            "pfas": 0.0,
            "other_concerns": 0.0,
            "category_multiplier": 1.0,
            "confidence_penalty": 0.0
        }

        # Add points for allergens (severity-based)
        allergens = analysis_data.get("allergens_detected", [])
        for allergen in allergens:
            severity = allergen.get("severity", "low")
            points = HarmScoreCalculator.SEVERITY_POINTS.get(severity, 8)
            confidence = allergen.get("confidence", 1.0)
            contribution = points * confidence
            breakdown["allergens"] += contribution
            base_score += contribution

        # Add points for PFAS (each PFAS is inherently high risk)
        pfas_compounds = analysis_data.get("pfas_detected", [])
        for pfas in pfas_compounds:
            confidence = pfas.get("confidence", 1.0)
            # PFAS are forever chemicals - high base score
            contribution = 40 * confidence
            breakdown["pfas"] += contribution
            base_score += contribution

        # Add points for other_concerns (category-based scoring)
        other_concerns = analysis_data.get("other_concerns", [])
        for concern in other_concerns:
            category = concern.get("category", "other")
            confidence = concern.get("confidence", 1.0)

            # Use category-specific points (with "under_investigation" capped at 5)
            if category in HarmScoreCalculator.CATEGORY_POINTS:
                points = HarmScoreCalculator.CATEGORY_POINTS[category]
            else:
                # Fallback to severity-based if category not recognized
                severity = concern.get("severity", "low")
                points = HarmScoreCalculator.SEVERITY_POINTS.get(severity, 8)

            contribution = points * confidence
            breakdown["other_concerns"] += contribution
            base_score += contribution

        # Apply category multiplier for high-risk product types
        category_multiplier = HarmScoreCalculator._get_category_multiplier(
            analysis_data.get("product_name", ""),
            analysis_data.get("category", "")
        )
        breakdown["category_multiplier"] = category_multiplier
        base_score *= category_multiplier

        # Apply confidence adjustment (low confidence = add caution points)
        confidence = analysis_data.get("confidence", 1.0)
        if confidence < 0.7:
            # Low confidence means uncertain - add precautionary points
            caution_bonus = (0.7 - confidence) * 20
            breakdown["confidence_penalty"] = caution_bonus
            base_score += caution_bonus

        # Ensure minimum score if any concerns detected
        if (allergens or pfas_compounds or other_concerns) and base_score < 25:
            base_score = 25

        final_score = min(100, int(base_score))

        # Log scoring breakdown for debugging
        logger.debug(
            f"Harm score calculation: "
            f"Allergens={breakdown['allergens']:.1f}, "
            f"PFAS={breakdown['pfas']:.1f}, "
            f"Other={breakdown['other_concerns']:.1f}, "
            f"Multiplier={breakdown['category_multiplier']:.2f}, "
            f"Confidence penalty={breakdown['confidence_penalty']:.1f}, "
            f"Final={final_score}"
        )

        return final_score

    @staticmethod
    def _get_category_multiplier(product_name: str, category: str) -> float:
        """Determine if product is in a high-risk category.

        Args:
            product_name: Product name
            category: Product category

        Returns:
            Multiplier (1.0 = no boost, >1.0 = higher risk)
        """
        product_lower = product_name.lower()
        category_lower = category.lower()

        for keyword, multiplier in HarmScoreCalculator.CATEGORY_MULTIPLIERS.items():
            if keyword in product_lower or keyword in category_lower:
                return multiplier

        # Check for specific keywords
        high_risk_keywords = [
            "killer", "spray", "poison", "toxic", "bleach",
            "acid", "lye", "caustic", "corrosive"
        ]
        for keyword in high_risk_keywords:
            if keyword in product_lower:
                return 1.3

        return 1.0

    @staticmethod
    def get_risk_level(harm_score: int) -> str:
        """Convert harm score to human-readable risk level.

        Args:
            harm_score: Harm score (0-100)

        Returns:
            Risk level string
        """
        if harm_score <= 30:
            return "Safe"
        elif harm_score <= 60:
            return "Moderate Risk"
        elif harm_score <= 80:
            return "High Risk"
        else:
            return "Dangerous"
