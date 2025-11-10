"""Harm score calculation logic."""

from typing import Dict, Any


class HarmScoreCalculator:
    """Calculate harm score (0-100) based on detected substances.

    Score breakdown:
    - 0-20: Safe
    - 21-40: Low risk
    - 41-60: Moderate risk
    - 61-80: High risk
    - 81-100: Dangerous
    """

    # Severity weights for allergens
    SEVERITY_WEIGHTS = {
        "low": 1,
        "moderate": 3,
        "high": 6,
        "severe": 10,
    }

    @staticmethod
    def calculate(analysis_data: Dict[str, Any]) -> int:
        """Calculate harm score from analysis data.

        Formula:
        - Allergen score: 40% weight
        - PFAS score: 40% weight
        - Other toxins: 20% weight
        - Confidence penalty: Lower confidence = higher reported risk

        Args:
            analysis_data: Dict with 'allergens', 'pfas_detected', 'other_concerns', 'confidence'

        Returns:
            Harm score (0-100)
        """
        allergen_score = HarmScoreCalculator._calculate_allergen_score(
            analysis_data.get("allergens_detected", [])
        )
        pfas_score = HarmScoreCalculator._calculate_pfas_score(
            analysis_data.get("pfas_detected", [])
        )
        toxin_score = HarmScoreCalculator._calculate_toxin_score(
            analysis_data.get("other_concerns", [])
        )

        # Weighted combination (allergens 40%, PFAS 40%, toxins 20%)
        raw_score = (allergen_score * 0.4) + (pfas_score * 0.4) + (toxin_score * 0.2)

        # Apply confidence penalty (low confidence = report higher risk to be safe)
        confidence = analysis_data.get("confidence", 1.0)
        confidence_penalty = (1.0 - confidence) * 10  # Up to 10 points penalty

        final_score = min(100, int(raw_score + confidence_penalty))
        return final_score

    @staticmethod
    def _calculate_allergen_score(allergens: list) -> float:
        """Calculate allergen component of harm score.

        Args:
            allergens: List of allergen detections with 'severity' field

        Returns:
            Allergen score (0-100)
        """
        if not allergens:
            return 0.0

        total_severity = 0.0
        for allergen in allergens:
            severity = allergen.get("severity", "low")
            weight = HarmScoreCalculator.SEVERITY_WEIGHTS.get(severity, 1)
            confidence = allergen.get("confidence", 1.0)
            total_severity += weight * confidence

        # Normalize to 0-100 scale (assume max 10 severe allergens = 100)
        max_severity = 10 * HarmScoreCalculator.SEVERITY_WEIGHTS["severe"]
        score = min(100, (total_severity / max_severity) * 100)
        return score

    @staticmethod
    def _calculate_pfas_score(pfas_compounds: list) -> float:
        """Calculate PFAS component of harm score.

        Args:
            pfas_compounds: List of PFAS detections

        Returns:
            PFAS score (0-100)
        """
        if not pfas_compounds:
            return 0.0

        # Each PFAS compound adds 15 points (weighted by confidence)
        total_score = 0.0
        for compound in pfas_compounds:
            confidence = compound.get("confidence", 1.0)
            total_score += 15 * confidence

        return min(100, total_score)

    @staticmethod
    def _calculate_toxin_score(toxins: list) -> float:
        """Calculate other toxins component of harm score.

        Args:
            toxins: List of other toxin concerns with 'severity' field

        Returns:
            Toxin score (0-100)
        """
        if not toxins:
            return 0.0

        total_severity = 0.0
        for toxin in toxins:
            severity = toxin.get("severity", "low")
            weight = HarmScoreCalculator.SEVERITY_WEIGHTS.get(severity, 1)
            confidence = toxin.get("confidence", 1.0)
            total_severity += weight * confidence

        # Each toxin adds ~5 points (normalized)
        score = min(100, (total_severity / 20) * 100)
        return score

    @staticmethod
    def get_risk_level(harm_score: int) -> str:
        """Convert harm score to human-readable risk level.

        Args:
            harm_score: Harm score (0-100)

        Returns:
            Risk level string
        """
        if harm_score <= 20:
            return "Safe"
        elif harm_score <= 40:
            return "Low Risk"
        elif harm_score <= 60:
            return "Moderate Risk"
        elif harm_score <= 80:
            return "High Risk"
        else:
            return "Dangerous"
