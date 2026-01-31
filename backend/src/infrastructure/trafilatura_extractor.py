"""Trafilatura-based product data extraction - replaces Claude Query for common cases.

This module extracts product information using:
1. CSS selectors for known e-commerce site structures (Amazon, etc.)
2. Trafilatura for generic content extraction from manufacturer sites
3. LLM fallback only when structured extraction fails

Cost savings: Eliminates 1 Claude call (~$0.01 per analysis)
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of product data extraction."""
    product_name: str = ""
    brand: str = ""
    ingredients: List[str] = None
    materials: List[str] = None
    features: List[str] = None
    warnings: List[str] = None
    description: str = ""
    confidence: float = 0.0
    extraction_method: str = ""  # "selectors", "trafilatura", "llm_fallback"

    def __post_init__(self):
        self.ingredients = self.ingredients or []
        self.materials = self.materials or []
        self.features = self.features or []
        self.warnings = self.warnings or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_name": self.product_name,
            "brand": self.brand,
            "ingredients": self.ingredients,
            "materials": self.materials,
            "features": self.features,
            "warnings": self.warnings,
            "description": self.description,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
        }


# =============================================================================
# AMAZON SELECTORS - Known structure, no LLM needed
# =============================================================================

AMAZON_SELECTORS = {
    "product_name": [
        "#productTitle",
        "h1.product-title-word-break",
        "span#productTitle",
    ],
    "brand": [
        "#bylineInfo",
        "a#bylineInfo",
        ".po-brand .a-size-base",
    ],
    "ingredients_section": [
        "#important-information .content",
        "#importantInformation",
        "[data-cel-widget='ppd-ingredients']",
        "#productDescription",
    ],
    "features": [
        "#featureBullets_feature_div li",
        ".a-unordered-list.a-vertical li span.a-list-item",
        "#feature-bullets li span",
    ],
}

# Patterns to find ingredient lists in text
INGREDIENT_PATTERNS = [
    r"(?:ingredients?|contains?)[\s:]+(.+?)(?:\.|$)",
    r"active\s+ingredients?[\s:]+(.+?)(?:inactive|$)",
    r"inactive\s+ingredients?[\s:]+(.+?)(?:\.|$)",
]

# Common ingredient delimiters
INGREDIENT_DELIMITERS = [", ", "; ", " - ", "\n", "•", "·"]


def extract_from_amazon(html: str, url: str) -> ExtractionResult:
    """Extract product data from Amazon HTML using CSS selectors.

    This is 100% deterministic and costs $0 in LLM tokens.

    Args:
        html: Raw HTML content
        url: Product URL

    Returns:
        ExtractionResult with extracted data
    """
    soup = BeautifulSoup(html, "lxml")
    result = ExtractionResult(extraction_method="selectors")

    # Extract product name
    for selector in AMAZON_SELECTORS["product_name"]:
        elem = soup.select_one(selector)
        if elem and elem.get_text(strip=True):
            result.product_name = elem.get_text(strip=True)
            break

    # Extract brand
    for selector in AMAZON_SELECTORS["brand"]:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            # Clean up "Visit the X Store" or "Brand: X"
            text = re.sub(r"^(Visit the|Brand:?)\s*", "", text, flags=re.I)
            text = re.sub(r"\s*Store$", "", text, flags=re.I)
            if text:
                result.brand = text
                break

    # Extract features
    for selector in AMAZON_SELECTORS["features"]:
        elements = soup.select(selector)
        for elem in elements[:10]:  # Limit to 10 features
            text = elem.get_text(strip=True)
            if text and len(text) > 5:
                result.features.append(text)
        if result.features:
            break

    # Extract ingredients from various sections
    result.ingredients = _extract_ingredients_from_html(soup)

    # Extract warnings
    result.warnings = _extract_warnings_from_html(soup)

    # Calculate confidence based on what we found
    confidence = 0.0
    if result.product_name:
        confidence += 0.3
    if result.brand:
        confidence += 0.2
    if result.ingredients:
        confidence += 0.4
    elif result.features:
        confidence += 0.1

    result.confidence = min(confidence, 1.0)

    logger.info(
        f"Amazon selector extraction: {result.product_name[:50]}... "
        f"({len(result.ingredients)} ingredients, {result.confidence:.0%} confidence)"
    )

    return result


def _extract_ingredients_from_html(soup: BeautifulSoup) -> List[str]:
    """Extract ingredient list from HTML using heuristics.

    Looks for common patterns like "Ingredients:", "Contains:", etc.
    """
    ingredients = []

    # Search in specific sections first
    for selector in AMAZON_SELECTORS["ingredients_section"]:
        sections = soup.select(selector)
        for section in sections:
            text = section.get_text(" ", strip=True)
            found = _parse_ingredients_text(text)
            if found:
                ingredients.extend(found)
                break
        if ingredients:
            break

    # If not found, search the entire page for ingredient patterns
    if not ingredients:
        full_text = soup.get_text(" ", strip=True)
        for pattern in INGREDIENT_PATTERNS:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for match in matches:
                found = _parse_ingredients_text(match)
                if found:
                    ingredients.extend(found)

    # Deduplicate while preserving order
    seen = set()
    unique_ingredients = []
    for ing in ingredients:
        ing_lower = ing.lower().strip()
        if ing_lower and ing_lower not in seen and len(ing) > 1:
            seen.add(ing_lower)
            unique_ingredients.append(ing.strip())

    return unique_ingredients[:50]  # Limit to 50 ingredients


def _parse_ingredients_text(text: str) -> List[str]:
    """Parse ingredient text into individual ingredients."""
    if not text:
        return []

    # Strip common prefixes like "Ingredients:", "Contains:", etc.
    text = re.sub(r'^(ingredients?|contains?|active\s+ingredients?|inactive\s+ingredients?)\s*[:\-]\s*', '', text, flags=re.IGNORECASE)

    # Try each delimiter
    for delim in INGREDIENT_DELIMITERS:
        parts = text.split(delim)
        if len(parts) > 3:  # Likely a valid list
            # Clean each part - remove any remaining label prefixes
            cleaned = []
            for p in parts:
                p = p.strip()
                # Skip if it's just a label
                if p.lower() in ('ingredients', 'contains', 'active ingredients', 'inactive ingredients'):
                    continue
                if p:
                    cleaned.append(p)
            return cleaned

    return []


def _extract_warnings_from_html(soup: BeautifulSoup) -> List[str]:
    """Extract warning text from HTML."""
    warnings = []

    # Common warning patterns
    warning_patterns = [
        r"warning[\s:]+(.+?)(?:\.|$)",
        r"caution[\s:]+(.+?)(?:\.|$)",
        r"keep out of reach",
        r"for external use only",
    ]

    full_text = soup.get_text(" ", strip=True).lower()

    for pattern in warning_patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, str) and len(match) > 10:
                warnings.append(match[:200])  # Limit length

    return warnings[:5]  # Limit to 5 warnings


# =============================================================================
# TRAFILATURA - For generic sites (manufacturer pages, etc.)
# =============================================================================

def extract_with_trafilatura(html: str, url: str) -> ExtractionResult:
    """Extract product data from generic HTML using Trafilatura.

    Trafilatura excels at extracting main content from web pages,
    filtering out navigation, ads, and boilerplate.

    Args:
        html: Raw HTML content
        url: Product URL

    Returns:
        ExtractionResult with extracted data
    """
    result = ExtractionResult(extraction_method="trafilatura")

    # Extract main content with Trafilatura
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        include_images=False,
        include_links=False,
        deduplicate=True,
        favor_precision=True,  # Prefer quality over quantity
    )

    if not extracted:
        logger.warning("Trafilatura returned no content")
        result.confidence = 0.0
        return result

    # Try to parse structure from extracted text
    lines = extracted.split("\n")

    # First non-empty line is often the title
    for line in lines:
        line = line.strip()
        if line and len(line) > 5:
            result.product_name = line[:200]
            break

    # Look for ingredient patterns in extracted text
    result.ingredients = _parse_ingredients_text(extracted)[:30]

    # Look for warning patterns
    warning_match = re.search(r"warning[:\s]+(.+?)(?:\n|$)", extracted, re.IGNORECASE)
    if warning_match:
        result.warnings.append(warning_match.group(1)[:200])

    # Store remaining as description
    result.description = extracted[:1000]

    # Calculate confidence
    confidence = 0.2  # Base confidence for any extraction
    if result.product_name:
        confidence += 0.2
    if result.ingredients:
        confidence += 0.4
    if result.description:
        confidence += 0.1

    result.confidence = min(confidence, 1.0)

    logger.info(
        f"Trafilatura extraction: {result.product_name[:50]}... "
        f"({len(result.ingredients)} ingredients, {result.confidence:.0%} confidence)"
    )

    return result


# =============================================================================
# MAIN EXTRACTION FUNCTION
# =============================================================================

def extract_product_data(
    html: str,
    url: str,
    min_confidence: float = 0.5,
) -> Tuple[ExtractionResult, bool]:
    """Extract product data using the best available method.

    Tries extraction in order:
    1. Site-specific CSS selectors (Amazon, etc.)
    2. Trafilatura for generic content
    3. Returns low-confidence result for LLM fallback

    Args:
        html: Raw HTML content
        url: Product URL
        min_confidence: Minimum confidence to accept (default 0.5)

    Returns:
        Tuple of (ExtractionResult, needs_llm_fallback)
    """
    url_lower = url.lower()

    # Try site-specific extraction first
    if "amazon." in url_lower:
        result = extract_from_amazon(html, url)
        if result.confidence >= min_confidence:
            return result, False

    # Try Trafilatura for any site
    result = extract_with_trafilatura(html, url)
    if result.confidence >= min_confidence:
        return result, False

    # Need LLM fallback
    logger.info(
        f"Low confidence extraction ({result.confidence:.0%}), needs LLM fallback"
    )
    return result, True


# =============================================================================
# INGREDIENT LIST PRE-PROCESSING
# =============================================================================

# Well-known safe ingredients that don't need research
KNOWN_SAFE_INGREDIENTS = {
    "water", "aqua", "eau",
    "glycerin", "glycerine",
    "tocopherol", "vitamin e",
    "aloe vera", "aloe barbadensis",
    "citric acid",
    "sodium chloride",
    "xanthan gum",
    "hyaluronic acid",
}

# Ingredients that are known allergens/concerns - flag immediately
KNOWN_CONCERN_INGREDIENTS = {
    "fragrance": ("allergen", "Can contain undisclosed allergens/phthalates"),
    "parfum": ("allergen", "Can contain undisclosed allergens/phthalates"),
    "formaldehyde": ("carcinogen", "IARC Group 1 carcinogen"),
    "oxybenzone": ("endocrine_disruptor", "Hormone disruption, coral reef damage"),
    "triclosan": ("regulatory_action", "FDA ban in consumer antiseptic products"),
    "hydroquinone": ("regulatory_action", "Banned in cosmetics in EU, Japan"),
    "coal tar": ("carcinogen", "IARC Group 1 carcinogen"),
}


def preprocess_ingredients(
    ingredients: List[str],
) -> Tuple[List[str], List[Dict[str, str]], List[str]]:
    """Pre-process ingredient list to reduce LLM research needs.

    Separates ingredients into:
    1. Known safe (skip research)
    2. Known concerns (flag immediately without research)
    3. Unknown (need research)

    Args:
        ingredients: List of ingredient names

    Returns:
        Tuple of (safe_ingredients, known_concerns, needs_research)
    """
    safe = []
    concerns = []
    needs_research = []

    for ingredient in ingredients:
        ing_lower = ingredient.lower().strip()

        if ing_lower in KNOWN_SAFE_INGREDIENTS:
            safe.append(ingredient)
        elif ing_lower in KNOWN_CONCERN_INGREDIENTS:
            category, description = KNOWN_CONCERN_INGREDIENTS[ing_lower]
            concerns.append({
                "name": ingredient,
                "category": category,
                "description": description,
                "source": "Known ingredient database",
            })
        else:
            needs_research.append(ingredient)

    logger.info(
        f"Ingredient preprocessing: {len(safe)} safe, "
        f"{len(concerns)} known concerns, {len(needs_research)} need research"
    )

    return safe, concerns, needs_research
