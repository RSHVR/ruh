"""Costco product scraper — configuration only (no DOM-specific overrides).

Costco sells both groceries (ingredients/nutrition matter) and general goods
(specifications matter), so the config carries both an ``ingredients`` and a
``specifications`` visible selector on top of the universal JSON-LD backbone
(LORE.md ADR-004) and an ``h1`` title. Costco usually embeds a
``<script type="application/ld+json">`` Product schema. All mechanics are
inherited from ``BaseScraper`` (LORE.md ADR-001); nothing about Costco's DOM
requires a method override. Unvalidated (gated at recon — see LORE.md).
"""

from .base import BaseScraper


class CostcoScraper(BaseScraper):
    """Costco-specific product scraper (config-only)."""

    RETAILER_NAME = "Costco"
    SCRAPE_METHOD = "costco_raw_html"

    DOMAIN_PATTERNS = [
        r"costco\.com",
    ]

    # JSON-LD first (universal backbone), then title, then visible site-specific
    # detail/spec/ingredient sections. No meta[...] selectors (LORE.md ADR-004).
    # Costco spans groceries + goods → both ingredients AND specs matter.
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {"name": "product_details", "selector": "#product-details-tabs, .product-info-description, [class*='product-info' i]"},
        {"name": "specifications", "selector": "[class*='spec' i], #product-tab2"},
        {"name": "ingredients", "selector": "[class*='ingredient' i]"},
    ]

    # Costco has no usable client-session reviews endpoint; reviews (where present)
    # arrive via JSON-LD aggregateRating in structured_data.
    REVIEWS_SECTION_SELECTORS = []

    EXCLUDE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "[class*='recommend' i]",
        "[class*='carousel' i]",
        "[class*='you-may' i]",
    ]
