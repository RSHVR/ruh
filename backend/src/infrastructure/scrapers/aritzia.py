"""Aritzia product scraper — configuration only (no DOM-specific overrides).

All mechanics are inherited from ``BaseScraper`` (LORE.md ADR-001); nothing about
Aritzia's DOM requires a method override.

Recon note (2026-06-03, live): product pages reachable (partial). Unlike most retailers,
Aritzia does **not** expose JSON-LD Product on the initial DOM, and materials/care load
lazily behind accordions. The visible description uses the ``ch-`` class prefix
(``.ch-description``), added below. Because the safety-critical composition is lazy, the
client-HTML path (INV-1) only captures it if the user expanded the section — best-effort.
"""

from .base import BaseScraper


class AritziaScraper(BaseScraper):
    """Aritzia-specific product scraper (config-only)."""

    RETAILER_NAME = "Aritzia"
    SCRAPE_METHOD = "aritzia_raw_html"

    DOMAIN_PATTERNS = [
        r"aritzia\.com",
    ]

    # JSON-LD first (universal backbone), then title, then visible site-specific
    # fabric/material, detail, and care sections. Apparel → fabric composition
    # matters. No meta[...] selectors (LORE.md ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {"name": "materials", "selector": "[class*='materials' i], [class*='fabric' i], [class*='composition' i], [class*='ch-material' i]"},
        {"name": "product_details", "selector": "[class*='ch-description' i], [class*='ch-pdp' i], [data-testid*='detail' i], [class*='description' i], [class*='product-detail' i]"},
        {"name": "care", "selector": "[class*='care' i], [class*='ch-care' i]"},
    ]

    # Aritzia has no usable client-session reviews endpoint; reviews (where
    # present) arrive via JSON-LD aggregateRating in structured_data.
    REVIEWS_SECTION_SELECTORS = []

    EXCLUDE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "[class*='recommend' i]",
        "[class*='carousel' i]",
        "[class*='you-may' i]",
    ]
