"""H&M product scraper — configuration only (no DOM-specific overrides).

H&M normally embeds a ``<script type="application/ld+json">`` Product schema
(name, brand, description, sku), so the universal JSON-LD backbone (LORE.md
ADR-004) plus a few visible apparel selectors (materials/composition, product
details, care) fully covers it. Fabric composition is the key signal for apparel
(PFAS/finishes). All mechanics are inherited from ``BaseScraper`` (LORE.md
ADR-001); nothing about H&M's DOM requires a method override.

Recon was bot-walled (LORE.md), so the visible selectors are **unvalidated** and
will be refined against a real session; the JSON-LD baseline still works.
"""

from .base import BaseScraper


class HMScraper(BaseScraper):
    """H&M-specific product scraper (config-only)."""

    RETAILER_NAME = "H&M"
    SCRAPE_METHOD = "hm_raw_html"

    DOMAIN_PATTERNS = [
        r"(www2\.)?hm\.com",
    ]

    # JSON-LD first (universal backbone), then title, then visible apparel-specific
    # composition/details/care sections. No meta[...] selectors (LORE.md ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {"name": "materials", "selector": "[class*='materials' i], [class*='composition' i]"},
        {"name": "product_details", "selector": "#section-descriptionAccordion, [class*='ProductDescription' i], [class*='details' i]"},
        {"name": "care", "selector": "[class*='care' i]"},
    ]

    # H&M has no usable client-session reviews endpoint; reviews (where present)
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
