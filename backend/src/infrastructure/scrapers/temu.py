"""Temu product scraper — configuration only (no DOM-specific overrides).

Temu embeds a ``<script type="application/ld+json">`` Product schema, so the
universal JSON-LD backbone (LORE.md ADR-004) plus a few visible goods-description /
material / specification selectors covers it. All mechanics are inherited from
``BaseScraper`` (LORE.md ADR-001); nothing about Temu's DOM requires a method
override.

Temu heavily bot-walls automated server requests (LORE.md recon notes), so the
client-HTML path (INV-1) is the only real integration surface — the same DOM the
logged-in user's browser organically loads. JSON-LD may be partial; the config is
flagged unvalidated and is refined later against real sessions.
"""

from .base import BaseScraper


class TemuScraper(BaseScraper):
    """Temu-specific product scraper (config-only)."""

    RETAILER_NAME = "Temu"
    SCRAPE_METHOD = "temu_raw_html"

    DOMAIN_PATTERNS = [
        r"temu\.com",
    ]

    # JSON-LD first (universal backbone), then title, then visible site-specific
    # goods-description / material / specification sections. No meta[...] selectors
    # (LORE.md ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {"name": "product_details", "selector": "[class*='goods-desc' i], [class*='detail' i], [class*='description' i]"},
        {"name": "materials", "selector": "[class*='material' i]"},
        {"name": "specifications", "selector": "[class*='spec' i]"},
    ]

    # Temu has no usable client-session reviews endpoint; reviews (where present)
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
