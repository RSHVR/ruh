"""Section-based parser for pre-extracted Amazon product text.

AmazonScraper.process_client_html() outputs plain text with === section ===
markers. Trafilatura expects raw HTML and fails on this format, causing an
unnecessary $0.01 Claude Query fallback every time. This parser handles the
pre-extracted format directly.

Section names come from AmazonScraper.PRODUCT_SECTION_SELECTORS:
  title, brand, price, availability, product_attributes, feature_bullets,
  about_item, product_description, aplus_content, detail_bullets, product_info
"""

import re
import logging
from typing import Dict, List, Tuple

from .trafilatura_extractor import ExtractionResult, _parse_ingredients_text

logger = logging.getLogger(__name__)

# Regex to split on === section_name ===
_SECTION_RE = re.compile(r"^===\s*(\w+)\s*===$", re.MULTILINE)

# Warning keywords to scan across all sections
_WARNING_KEYWORDS = re.compile(
    r"warning|caution|keep out of reach|for external use only|"
    r"do not ingest|may cause|known to cause|prop(?:osition)?\s*65",
    re.IGNORECASE,
)

# Material keywords to scan in product_attributes and description sections
_MATERIAL_KEYWORDS = re.compile(
    r"material[s]?\s*[:]\s*(.+?)(?:\n|$)|"
    r"made (?:of|from|with)\s+(.+?)(?:\.|,|\n|$)|"
    r"(?:fabric|shell|lining)\s*[:]\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)


def _split_sections(text: str) -> Dict[str, str]:
    """Split === name === delimited text into {name: content} dict."""
    sections: Dict[str, str] = {}
    parts = _SECTION_RE.split(text)

    # parts alternates: [pre-header junk, name1, content1, name2, content2, ...]
    i = 1  # skip any text before the first header
    while i + 1 < len(parts):
        name = parts[i].strip().lower()
        content = parts[i + 1].strip()
        if content:
            sections[name] = content
        i += 2

    return sections


def _clean_brand(raw: str) -> str:
    """Strip 'Visit the X Store' / 'Brand: X' wrappers."""
    cleaned = re.sub(r"^(Visit the|Brand:?)\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*Store$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _extract_ingredients_and_materials(
    sections: Dict[str, str],
) -> Tuple[List[str], List[str]]:
    """Pull ingredients and materials from product_attributes and other sections."""
    ingredients: List[str] = []
    materials: List[str] = []

    # product_attributes is key-value formatted ("Ingredients: ...", "Material: ...")
    attrs = sections.get("product_attributes", "")
    if attrs:
        for line in attrs.split("\n"):
            key_val = line.split(":", 1)
            if len(key_val) != 2:
                continue
            key, val = key_val[0].strip().lower(), key_val[1].strip()
            if not val:
                continue
            if "ingredient" in key:
                ingredients.extend(_parse_ingredients_text(val))
            elif key in ("material", "fabric type", "outer material", "shell"):
                materials.append(val)

    # Also scan description-like sections for ingredients if none found yet
    if not ingredients:
        for section_name in ("product_description", "aplus_content", "detail_bullets"):
            text = sections.get(section_name, "")
            if text:
                found = _parse_ingredients_text(text)
                if found:
                    ingredients.extend(found)
                    break

    # Scan for materials in description sections
    for section_name in ("product_description", "aplus_content", "feature_bullets", "about_item"):
        text = sections.get(section_name, "")
        for match in _MATERIAL_KEYWORDS.finditer(text):
            # match groups are alternatives; take the first non-None
            material = next((g for g in match.groups() if g), None)
            if material:
                materials.append(material.strip())

    # Deduplicate
    ingredients = _dedupe(ingredients)
    materials = _dedupe(materials)

    return ingredients, materials


def _extract_features(sections: Dict[str, str]) -> List[str]:
    """Collect features from bullet-point sections."""
    features: List[str] = []
    for section_name in ("feature_bullets", "about_item"):
        text = sections.get(section_name, "")
        if not text:
            continue
        # Bullets are often separated by newlines or bullet chars
        for line in re.split(r"[\n•·]", text):
            line = line.strip()
            if line and len(line) > 5:
                features.append(line)
    return features[:15]  # cap


def _extract_warnings(sections: Dict[str, str]) -> List[str]:
    """Scan all sections for warning text."""
    warnings: List[str] = []
    full_text = "\n".join(sections.values())
    for match in _WARNING_KEYWORDS.finditer(full_text):
        # Grab surrounding context (up to 200 chars after keyword)
        start = match.start()
        snippet = full_text[start : start + 200].strip()
        # Trim at sentence boundary
        sentence_end = re.search(r"[.\n]", snippet[10:])
        if sentence_end:
            snippet = snippet[: 10 + sentence_end.start() + 1]
        if snippet and len(snippet) > 10:
            warnings.append(snippet)
    return _dedupe(warnings)[:5]


def _build_description(sections: Dict[str, str]) -> str:
    """Combine description-like sections into one block."""
    parts: List[str] = []
    for section_name in ("product_description", "aplus_content"):
        text = sections.get(section_name, "")
        if text:
            parts.append(text)
    return "\n\n".join(parts)[:1000]


def _dedupe(items: List[str]) -> List[str]:
    """Deduplicate strings while preserving order."""
    seen: set = set()
    result: List[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen and len(item) > 1:
            seen.add(key)
            result.append(item.strip())
    return result


def parse_sections(text: str, url: str) -> Tuple[ExtractionResult, bool]:
    """Parse === section === formatted text into an ExtractionResult.

    Same return signature as trafilatura_extractor.extract_product_data()
    so it can be used as a drop-in replacement when content is pre-extracted.

    Args:
        text: Pre-extracted text with === section === markers
        url: Product URL (for logging)

    Returns:
        Tuple of (ExtractionResult, needs_llm_fallback)
    """
    sections = _split_sections(text)

    if not sections:
        logger.warning("Section parser: no sections found in text")
        return ExtractionResult(confidence=0.0, extraction_method="section_parser"), True

    result = ExtractionResult(extraction_method="section_parser")

    # Map sections → ExtractionResult fields
    result.product_name = sections.get("title", "")
    result.brand = _clean_brand(sections.get("brand", ""))
    result.ingredients, result.materials = _extract_ingredients_and_materials(sections)
    result.features = _extract_features(sections)
    result.warnings = _extract_warnings(sections)
    result.description = _build_description(sections)

    # Confidence scoring (same weights as trafilatura_extractor)
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

    needs_fallback = result.confidence < 0.5

    logger.info(
        f"Section parser: {result.product_name[:50]}... "
        f"({len(result.ingredients)} ingredients, {len(result.materials)} materials, "
        f"{result.confidence:.0%} confidence)"
    )

    return result, needs_fallback
