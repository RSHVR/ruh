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


def match_ingredients_to_databases(
    ingredients: List[str],
    materials: List[str],
    allergen_database: List[Dict[str, Any]],
    pfas_database: List[Dict[str, Any]],
    similarity_threshold: float = 0.75
) -> Dict[str, Any]:
    """
    Match product ingredients against allergen and PFAS databases.

    Args:
        ingredients: List of ingredient names from product
        materials: List of material names from product
        allergen_database: List of allergen records from database
        pfas_database: List of PFAS compound records from database
        similarity_threshold: Minimum similarity score for matching (0.0-1.0)

    Returns:
        Dictionary with detected allergens, PFAS, and confidence score
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
                    "severity": allergen.get('severity', 'moderate'),
                    "health_effects": allergen.get('health_effects', 'Potential allergic reactions'),
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
                    "severity": allergen.get('severity', 'moderate'),
                    "health_effects": allergen.get('health_effects', 'Potential allergic reactions'),
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

    # Remove duplicates (same allergen found in multiple ingredients)
    allergens_detected = _deduplicate_detections(allergens_detected, 'name')
    pfas_detected = _deduplicate_detections(pfas_detected, 'name')

    # Calculate overall confidence
    if allergens_detected or pfas_detected:
        all_confidences = [a['confidence'] for a in allergens_detected] + [p['confidence'] for p in pfas_detected]
        overall_confidence = sum(all_confidences) / len(all_confidences)
    else:
        # No matches found - confidence depends on whether we had ingredients to check
        overall_confidence = 0.7 if all_components else 0.3

    logger.info(f"Database matching complete: {len(allergens_detected)} allergens, {len(pfas_detected)} PFAS detected")

    return {
        "allergens_detected": allergens_detected,
        "pfas_detected": pfas_detected,
        "other_concerns": [],  # Database doesn't have "other concerns" yet
        "confidence": overall_confidence,
        "method": "database_matching"  # Indicate this was direct matching, not AI analysis
    }


def _deduplicate_detections(detections: List[Dict], key: str) -> List[Dict]:
    """Remove duplicate detections, keeping the one with highest confidence"""
    seen = {}
    for detection in detections:
        name = detection.get(key)
        if name not in seen or detection.get('confidence', 0) > seen[name].get('confidence', 0):
            seen[name] = detection
    return list(seen.values())
