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

    Formula philosophy (tuned 2026-06-11 against benchmark ground-truth bands):
    - Each finding contributes points (severity/category based, confidence
      weighted); the product-category multiplier is applied per finding.
    - Findings combine as a *risk union* — 100 * (1 - prod(1 - c_i/100)) —
      so the worst finding dominates, stacked findings add with diminishing
      returns, and the score approaches 100 asymptotically instead of
      truncating (a true multi-hazard product still reads near-maximal).
    - other_concerns category points are scaled by the concern's own severity
      (a trace/low finding in a category scores well below a confirmed
      high-severity one); "under_investigation" stays capped low.
    - No unconditional score floor: genuinely hazardous findings (high or
      severe severity, PFAS, carcinogens) clear 25 on their own points, so
      low-grade trace findings may legitimately score in the 0-20 safe band.
    - Low global confidence adds precautionary points.
    """

    # Base points per concern severity
    SEVERITY_POINTS = {
        "low": 8,
        "moderate": 18,
        "high": 35,
        "severe": 50,
    }

    # Points per detected PFAS compound. PFAS are persistent "forever
    # chemicals": one confirmed compound alone reads moderate-high (45), and
    # three at full confidence still reach the Dangerous band (>80) under the
    # risk-union combination.
    PFAS_POINTS = 45

    # Category-specific scoring for other_concerns
    CATEGORY_POINTS = {
        "under_investigation": 5,  # Capped: substances not in database
        "carcinogen": 40,          # IARC-classified carcinogens
        "regulatory_action": 30,   # FDA recall, EPA warning, lawsuits
        "heavy_metal": 25,         # Heavy metals (lead, mercury, etc.)
        "endocrine_disruptor": 25, # Hormone disruptors
        "other": 15,               # Other credible concerns
    }

    # Scales CATEGORY_POINTS by the concern's own reported severity, so a
    # trace ("low") finding in a category does not score like a confirmed
    # high-severity one. Missing/unknown severity keeps the full category
    # points (conservative).
    CONCERN_SEVERITY_FACTORS = {
        "low": 0.4,
        "moderate": 0.7,
        "high": 1.0,
        "severe": 1.2,
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

        Formula:
        1. Compute per-finding contributions:
           - allergens: severity points x confidence
           - PFAS: PFAS_POINTS x confidence
           - other_concerns: category points x severity factor x confidence
             (falls back to severity points for unknown categories)
        2. Apply the product category multiplier to each contribution.
        3. Combine contributions as a risk union:
           100 * (1 - prod(1 - c_i / 100))
        4. Add precautionary points when global confidence < 0.7.
        5. Clamp to [0, 100].

        Args:
            analysis_data: Dict with 'allergens_detected', 'pfas_detected', 'other_concerns',
                          'confidence', 'product_name', 'category'

        Returns:
            Harm score (0-100)
        """
        contributions = []
        breakdown = {
            "allergens": 0.0,
            "pfas": 0.0,
            "other_concerns": 0.0,
            "category_multiplier": 1.0,
            "confidence_penalty": 0.0
        }

        # Points for allergens (severity-based)
        allergens = analysis_data.get("allergens_detected", [])
        for allergen in allergens:
            severity = allergen.get("severity", "low")
            points = HarmScoreCalculator.SEVERITY_POINTS.get(severity, 8)
            confidence = allergen.get("confidence", 1.0)
            contribution = points * confidence
            breakdown["allergens"] += contribution
            contributions.append(contribution)

        # Points for PFAS (each PFAS is inherently high risk)
        pfas_compounds = analysis_data.get("pfas_detected", [])
        for pfas in pfas_compounds:
            confidence = pfas.get("confidence", 1.0)
            contribution = HarmScoreCalculator.PFAS_POINTS * confidence
            breakdown["pfas"] += contribution
            contributions.append(contribution)

        # Points for other_concerns (category-based, scaled by the concern's
        # own severity)
        other_concerns = analysis_data.get("other_concerns", [])
        for concern in other_concerns:
            category = concern.get("category", "other")
            confidence = concern.get("confidence", 1.0)

            if category in HarmScoreCalculator.CATEGORY_POINTS:
                severity_factor = HarmScoreCalculator.CONCERN_SEVERITY_FACTORS.get(
                    concern.get("severity"), 1.0
                )
                points = HarmScoreCalculator.CATEGORY_POINTS[category] * severity_factor
            else:
                # Fallback to severity-based if category not recognized
                severity = concern.get("severity", "low")
                points = HarmScoreCalculator.SEVERITY_POINTS.get(severity, 8)

            contribution = points * confidence
            breakdown["other_concerns"] += contribution
            contributions.append(contribution)

        # Apply category multiplier for high-risk product types (per finding,
        # which preserves single-finding semantics under the risk union).
        category_multiplier = HarmScoreCalculator._get_category_multiplier(
            analysis_data.get("product_name", ""),
            analysis_data.get("category", "")
        )
        breakdown["category_multiplier"] = category_multiplier

        # Combine findings as a risk union: each contribution is an
        # independent share of harm, so stacking is sub-linear (the worst
        # finding dominates) and saturation at 100 is asymptotic.
        survival = 1.0
        for contribution in contributions:
            boosted = min(contribution * category_multiplier, 100.0)
            survival *= 1.0 - boosted / 100.0
        base_score = 100.0 * (1.0 - survival)

        # Apply confidence adjustment (low confidence = add caution points)
        confidence = analysis_data.get("confidence", 1.0)
        if confidence < 0.7:
            # Low confidence means uncertain - add precautionary points
            caution_bonus = (0.7 - confidence) * 20
            breakdown["confidence_penalty"] = caution_bonus
            base_score += caution_bonus

        # Round away float epsilon from the survival product before the
        # truncating int() (e.g. 8.0 computing as 7.99999999999):
        final_score = max(0, min(100, int(round(base_score, 6))))

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
