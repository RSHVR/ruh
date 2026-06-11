"""Garage Clothing product scraper — configuration only.

Garage (garageclothing.com) is an apparel retailer whose product pages embed a
JSON-LD ``Product`` schema (name/brand/description/sku/aggregateRating) — the
universal data backbone (LORE.md ADR-004). Fabric composition lives in a visible
product-details accordion, so a few site-specific visible selectors supplement the
JSON-LD. Per ADR-001 this class declares class attributes only; all extraction
mechanics are inherited from ``BaseScraper``.
"""

from .base import BaseScraper


class GarageScraper(BaseScraper):
    """Garage Clothing scraper (JSON-LD + visible apparel selectors)."""

    RETAILER_NAME = "Garage"
    SCRAPE_METHOD = "garage_raw_html"

    DOMAIN_PATTERNS = [
        r"garageclothing\.com",
    ]

    # JSON-LD backbone (ADR-004) + title, then visible apparel-specific selectors.
    # No meta[...] selectors — text extraction returns their content empty (ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {
            "name": "product_details",
            "selector": ".product-detail, [class*='productdetails' i], [class*='product-detail' i]",
        },
        {
            "name": "fabric",
            "selector": "[class*='fabric' i], [class*='composition' i], [class*='material' i]",
        },
        {"name": "description", "selector": "[class*='description' i]"},
    ]

    # No usable client-session reviews endpoint; reviews come via JSON-LD where present.
    REVIEWS_SECTION_SELECTORS = []

    # Drop chrome, nav, and recommendation carousels before extraction.
    EXCLUDE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "[class*='recommend' i]",
        "[class*='you-may' i]",
        "[class*='carousel' i]",
    ]
