"""Sephora product scraper — configuration only (no DOM-specific overrides).

Sephora is a beauty retailer where the **ingredients** list is the most important
safety signal (allergens such as Limonene/Linalool, PFAS, etc.), so the ingredients
selector is given prominence right after the universal JSON-LD backbone + title
(LORE.md ADR-004). Sephora normally embeds a ``<script type="application/ld+json">``
Product schema; all mechanics are inherited from ``BaseScraper`` (LORE.md ADR-001),
and nothing about Sephora's DOM requires a method override.

Recon note (2026-06-03, live): product pages ARE reachable. JSON-LD Product confirmed
(name/description/brand/aggregateRating/reviews — no ingredients). Stable hooks are the
``data-at`` attributes (``data-at="ingredients"``, ``data-at="about_the_product_title"``);
CSS classes are hashed (e.g. ``css-148av0y``) and unreliable. Ingredients sit behind an
accordion, so the raw INCI list is present in the client DOM only if expanded — the
client-HTML path (INV-1) captures whatever the user's session rendered.
"""

from .base import BaseScraper


class SephoraScraper(BaseScraper):
    """Sephora-specific product scraper (config-only)."""

    RETAILER_NAME = "Sephora"
    SCRAPE_METHOD = "sephora_raw_html"

    DOMAIN_PATTERNS = [
        r"sephora\.com",
    ]

    # JSON-LD first (universal backbone), then title, then the safety-critical
    # ingredients block (prominent for a beauty retailer), then product details and
    # how-to-use. No meta[...] selectors (LORE.md ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {
            "name": "ingredients",
            "selector": "[class*='Ingredient' i], #ingredients, [data-comp*='Ingredient' i], [data-at*='ingredient' i]",
        },
        {
            "name": "product_details",
            "selector": "[data-at*='about_the_product' i], [data-at*='product_detail' i], [data-comp*='ProductInformation' i], #tabpanel-details",
        },
        {
            "name": "how_to_use",
            "selector": "[data-comp*='HowToUse' i], [class*='HowToUse' i]",
        },
    ]

    # Sephora has no usable client-session reviews endpoint; reviews (where present)
    # arrive via JSON-LD aggregateRating in structured_data.
    REVIEWS_SECTION_SELECTORS = []

    EXCLUDE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "[class*='recommend' i]",
        "[data-comp*='Carousel' i]",
        "[class*='you-may' i]",
    ]
