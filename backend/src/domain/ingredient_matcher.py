"""
Ingredient Matcher - Python-level database comparison

This module provides fallback functionality to match product ingredients
against allergen and PFAS databases without requiring AI or web search.
Used when Claude Agent fails or rate limits are hit.
"""

import logging
from typing import List, Dict, Any
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def similar(a: str, b: str) -> float:
    """Calculate similarity between two strings (0.0 to 1.0)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _map_severity_int_to_label(severity_default: int) -> str:
    """Map DB severity_default (1-10) to frontend severity labels.

    Thresholds align with frontend badge display:
    - 9-10: severe (life-threatening, e.g. peanuts, shellfish)
    - 7-8:  high (serious reactions, e.g. latex, eggs)
    - 4-6:  moderate (contact dermatitis, e.g. fragrance, nickel)
    - 1-3:  low (mild irritation, e.g. celery, mustard)
    """
    if severity_default >= 9:
        return "severe"
    elif severity_default >= 7:
        return "high"
    elif severity_default >= 4:
        return "moderate"
    else:
        return "low"


_SUBSTANCE_CATEGORY_MAP = {
    "phthalate": "endocrine_disruptor",
    "bisphenol": "endocrine_disruptor",
    "heavy_metal": "heavy_metal",
    "preservative": "other",
    "surfactant": "other",
    "solvent": "other",
    "voc": "other",
    "flame_retardant": "other",
    "pesticide": "regulatory_action",
}


def match_ingredients_to_databases(
    ingredients: List[str],
    materials: List[str],
    allergen_database: List[Dict[str, Any]],
    pfas_database: List[Dict[str, Any]],
    toxic_database: List[Dict[str, Any]] = None,
    similarity_threshold: float = 0.75
) -> Dict[str, Any]:
    """
    Match product ingredients against allergen, PFAS, and toxic substance databases.

    Args:
        ingredients: List of ingredient names from product
        materials: List of material names from product
        allergen_database: List of allergen records from database
        pfas_database: List of PFAS compound records from database
        toxic_database: List of toxic substance records (phthalates, BPA, heavy metals, etc.)
        similarity_threshold: Minimum similarity score for matching (0.0-1.0)

    Returns:
        Dictionary with detected allergens, PFAS, other concerns, and confidence score
    """
    logger.info(f"Matching {len(ingredients)} ingredients and {len(materials)} materials against databases")

    # Combine ingredients and materials for comprehensive checking
    all_components = ingredients + materials

    # Initialize results
    allergens_detected = []
    pfas_detected = []

    # Match against allergen database
    for component in all_components:
        if not component or len(component) < 2:
            continue

        for allergen in allergen_database:
            allergen_name = allergen.get('name', '')
            if not allergen_name:
                continue

            # Check for exact substring match (case-insensitive)
            if allergen_name.lower() in component.lower() or component.lower() in allergen_name.lower():
                allergens_detected.append({
                    "name": allergen_name,
                    "severity": _map_severity_int_to_label(allergen.get('severity_default', 5)),
                    "health_effects": allergen.get('health_effects') or 'Potential allergic reactions',
                    "source": f"Found in: {component}",
                    "confidence": 0.9  # High confidence for exact substring match
                })
                logger.info(f"Exact match found: {allergen_name} in {component}")
                continue

            # Check for fuzzy match
            similarity = similar(component, allergen_name)
            if similarity >= similarity_threshold:
                allergens_detected.append({
                    "name": allergen_name,
                    "severity": _map_severity_int_to_label(allergen.get('severity_default', 5)),
                    "health_effects": allergen.get('health_effects') or 'Potential allergic reactions',
                    "source": f"Similar to: {component}",
                    "confidence": similarity
                })
                logger.info(f"Fuzzy match found: {allergen_name} ~ {component} (similarity: {similarity:.2f})")

    # Match against PFAS database
    for component in all_components:
        if not component or len(component) < 2:
            continue

        for pfas in pfas_database:
            pfas_name = pfas.get('name', '')
            cas_number = pfas.get('cas_number', '')

            if not pfas_name:
                continue

            # Check for exact substring match (case-insensitive)
            if pfas_name.lower() in component.lower() or component.lower() in pfas_name.lower():
                pfas_detected.append({
                    "name": pfas_name,
                    "cas_number": cas_number,
                    "health_effects": pfas.get('health_effects', 'Forever chemicals - potential health risks'),
                    "source": f"Found in: {component}",
                    "confidence": 0.9
                })
                logger.info(f"PFAS exact match found: {pfas_name} in {component}")
                continue

            # Check CAS number match if available
            if cas_number and cas_number in component:
                pfas_detected.append({
                    "name": pfas_name,
                    "cas_number": cas_number,
                    "health_effects": pfas.get('health_effects', 'Forever chemicals - potential health risks'),
                    "source": f"CAS match in: {component}",
                    "confidence": 0.95  # Very high confidence for CAS number match
                })
                logger.info(f"PFAS CAS match found: {cas_number} in {component}")
                continue

            # Check for fuzzy match
            similarity = similar(component, pfas_name)
            if similarity >= similarity_threshold:
                pfas_detected.append({
                    "name": pfas_name,
                    "cas_number": cas_number,
                    "health_effects": pfas.get('health_effects', 'Forever chemicals - potential health risks'),
                    "source": f"Similar to: {component}",
                    "confidence": similarity
                })
                logger.info(f"PFAS fuzzy match found: {pfas_name} ~ {component} (similarity: {similarity:.2f})")

    # Match against toxic substances database (phthalates, BPA, heavy metals, etc.)
    other_concerns = []
    for component in all_components:
        if not component or len(component) < 2:
            continue

        for substance in (toxic_database or []):
            substance_name = substance.get('name', '')
            cas_number = substance.get('cas_number', '')

            if not substance_name:
                continue

            # Check for exact substring match (case-insensitive)
            if substance_name.lower() in component.lower() or component.lower() in substance_name.lower():
                category = _SUBSTANCE_CATEGORY_MAP.get(substance.get('substance_category', ''), 'other')
                other_concerns.append({
                    "name": substance_name,
                    "category": category,
                    "description": substance.get('body_effects') or 'Potentially harmful substance',
                    "health_effects": substance.get('health_impacts', []),
                    "concentration_limits": substance.get('concentration_limits'),
                    "cas_number": cas_number,
                    "source": f"Found in: {component}",
                    "confidence": 0.9,
                })
                logger.info(f"Toxic substance exact match found: {substance_name} in {component}")
                continue

            # Check CAS number match
            if cas_number and cas_number in component:
                category = _SUBSTANCE_CATEGORY_MAP.get(substance.get('substance_category', ''), 'other')
                other_concerns.append({
                    "name": substance_name,
                    "category": category,
                    "description": substance.get('body_effects') or 'Potentially harmful substance',
                    "health_effects": substance.get('health_impacts', []),
                    "concentration_limits": substance.get('concentration_limits'),
                    "cas_number": cas_number,
                    "source": f"CAS match in: {component}",
                    "confidence": 0.95,
                })
                logger.info(f"Toxic substance CAS match found: {cas_number} in {component}")
                continue

            # Check for fuzzy match
            similarity = similar(component, substance_name)
            if similarity >= similarity_threshold:
                category = _SUBSTANCE_CATEGORY_MAP.get(substance.get('substance_category', ''), 'other')
                other_concerns.append({
                    "name": substance_name,
                    "category": category,
                    "description": substance.get('body_effects') or 'Potentially harmful substance',
                    "health_effects": substance.get('health_impacts', []),
                    "concentration_limits": substance.get('concentration_limits'),
                    "cas_number": cas_number,
                    "source": f"Similar to: {component}",
                    "confidence": similarity,
                })
                logger.info(f"Toxic substance fuzzy match found: {substance_name} ~ {component} (similarity: {similarity:.2f})")

    # Remove duplicates (same substance found in multiple ingredients)
    allergens_detected = _deduplicate_detections(allergens_detected, 'name')
    pfas_detected = _deduplicate_detections(pfas_detected, 'name')
    other_concerns = _deduplicate_detections(other_concerns, 'name')

    # Calculate overall confidence
    all_detections = allergens_detected + pfas_detected + other_concerns
    if all_detections:
        all_confidences = [d['confidence'] for d in all_detections]
        overall_confidence = sum(all_confidences) / len(all_confidences)
    else:
        # No matches found - confidence depends on whether we had ingredients to check
        overall_confidence = 0.7 if all_components else 0.3

    logger.info(
        f"Database matching complete: {len(allergens_detected)} allergens, "
        f"{len(pfas_detected)} PFAS, {len(other_concerns)} toxic substances detected"
    )

    return {
        "allergens_detected": allergens_detected,
        "pfas_detected": pfas_detected,
        "other_concerns": other_concerns,
        "confidence": overall_confidence,
        "method": "database_matching",
    }


def _deduplicate_detections(detections: List[Dict], key: str) -> List[Dict]:
    """Remove duplicate detections, keeping the one with highest confidence"""
    seen = {}
    for detection in detections:
        name = detection.get(key)
        if name not in seen or detection.get('confidence', 0) > seen[name].get('confidence', 0):
            seen[name] = detection
    return list(seen.values())
