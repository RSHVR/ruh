"""Walmart product scraper — configuration only (no overrides).

Generic mechanics (Playwright fetch, section extraction, client-HTML processing,
confidence, error results) live in ``BaseScraper`` (LORE.md ADR-001). This class
declares Walmart's selector config and nothing else.

Walmart bot-walls server-side automation (PerimeterX/HUMAN), so the client-HTML
path is the only real integration surface — fine per INV-1, since the extension
ships the real user's logged-in DOM. JSON-LD Product schema is the data backbone
(ADR-004), supplemented by visible description/specification/ingredient selectors.
Selectors are unvalidated (recon was bot-walled); refined later against real sessions.
"""

from .base import BaseScraper


class WalmartScraper(BaseScraper):
    """Walmart-specific product scraper (config-driven; overrides nothing)."""

    RETAILER_NAME = "Walmart"

    DOMAIN_PATTERNS = [
        r"walmart\.com",
    ]

    # JSON-LD backbone + title, then visible site-specific selectors (ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {
            "name": "product_details",
            "selector": "[data-testid*='product-description'], #product-overview, [class*='product-description' i]",
        },
        {
            "name": "specifications",
            "selector": "[data-testid*='specification'], [class*='specification' i]",
        },
        {
            "name": "ingredients",
            "selector": "[class*='ingredient' i], .dangerous-html",
        },
    ]

    EXCLUDE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "[class*='recommend' i]",
        "[data-testid*='carousel' i]",
        "[class*='you-may' i]",
    ]
