"""Harm score calculation logic."""

from typing import Dict, Any


class HarmScoreCalculator:
    """Calculate harm score (0-100) based on detected substances.

    Score breakdown:
    - 0-30: Safe
    - 31-60: Moderate risk
    - 61-80: High risk
    - 81-100: Dangerous

    New formula philosophy:
    - Be aggressive with scoring dangerous products
    - Each severe toxin should significantly impact score
    - Product categories (pesticides, cleaners) get multipliers
    - No artificial dampening/normalization
    """

    # Base points per concern
    SEVERITY_POINTS = {
        "low": 8,
        "moderate": 18,
        "high": 35,
        "severe": 50,
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

        New formula:
        1. Start with base score of 0
        2. Add points for each detected concern (allergen, PFAS, toxin)
        3. Apply category multiplier if product is in high-risk category
        4. Apply confidence adjustment
        5. Cap at 100

        Args:
            analysis_data: Dict with 'allergens', 'pfas_detected', 'other_concerns',
                          'confidence', 'product_name', 'category'

        Returns:
            Harm score (0-100)
        """
        base_score = 0.0

        # Add points for allergens
        allergens = analysis_data.get("allergens_detected", [])
        for allergen in allergens:
            severity = allergen.get("severity", "low")
            points = HarmScoreCalculator.SEVERITY_POINTS.get(severity, 8)
            confidence = allergen.get("confidence", 1.0)
            base_score += points * confidence

        # Add points for PFAS (each PFAS is inherently high risk)
        pfas_compounds = analysis_data.get("pfas_detected", [])
        for pfas in pfas_compounds:
            confidence = pfas.get("confidence", 1.0)
            # PFAS are forever chemicals - high base score
            base_score += 40 * confidence

        # Add points for other toxins/concerns
        toxins = analysis_data.get("other_concerns", [])
        for toxin in toxins:
            severity = toxin.get("severity", "low")
            points = HarmScoreCalculator.SEVERITY_POINTS.get(severity, 8)
            confidence = toxin.get("confidence", 1.0)
            base_score += points * confidence

        # Apply category multiplier for high-risk product types
        category_multiplier = HarmScoreCalculator._get_category_multiplier(
            analysis_data.get("product_name", ""),
            analysis_data.get("category", "")
        )
        base_score *= category_multiplier

        # Apply confidence adjustment (low confidence = add caution points)
        confidence = analysis_data.get("confidence", 1.0)
        if confidence < 0.7:
            # Low confidence means uncertain - add precautionary points
            caution_bonus = (0.7 - confidence) * 20
            base_score += caution_bonus

        # Ensure minimum score if any concerns detected
        if (allergens or pfas_compounds or toxins) and base_score < 25:
            base_score = 25

        final_score = min(100, int(base_score))
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
