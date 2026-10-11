"""SHEIN product scraper — configuration only (LORE.md ADR-001/ADR-004).

All mechanics (Playwright fetch, section extraction, client-HTML processing,
confidence, error results) are inherited from ``BaseScraper``. SHEIN heavily
bot-walls servers, so the client-HTML path (INV-1) is the only real one — this
class therefore overrides *nothing* and just declares the selector config.

Following ADR-004, the config leads with JSON-LD structured data then the ``h1``
title, then a small set of **visible** selectors for the data JSON-LD usually
omits. For fast-fashion, fabric/material composition matters for safety, so
material selectors come first among the visible ones.
"""

from .base import BaseScraper


class SheinScraper(BaseScraper):
    """SHEIN product scraper (config-only; bot-walled → client-HTML primary)."""

    RETAILER_NAME = "SHEIN"
    SCRAPE_METHOD = "raw_html"

    DOMAIN_PATTERNS = [
        r"shein\.com",
    ]

    # JSON-LD first (ADR-004), then title, then visible site-specific selectors.
    # Fast-fashion → material/fabric composition is the safety-critical signal.
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {"name": "materials", "selector": "[class*='material' i], [class*='composition' i]"},
        {
            "name": "ingredients",
            # SHEIN beauty ingredients live in product-meta's first block (Veer, 2026-08-03).
            # Robust anchor first (id + semantic section), then the exact verified path.
            # NB: "goods-detail-mian" is SHEIN's own element id (their typo) — keep verbatim.
            "selector": (
                "#goods-detail-mian section.product-meta > div:nth-child(1), "
                "#goods-detail-mian > div.goods-detail.product-intro.shipping-theme-wrapper "
                "> div.atf-container > div.atf-right > section.product-meta "
                "> div:nth-child(1) > div"
            ),
        },
        {
            "name": "product_details",
            "selector": ".product-intro__description, [class*='product-intro' i], [class*='detail' i]",
        },
        {"name": "description", "selector": "[class*='description' i]"},
    ]

    # No usable client-session reviews endpoint; rely on JSON-LD review/rating.
    REVIEWS_SECTION_SELECTORS = []

    # Drop chrome + recommendation/carousel rails (no meta[...] per ADR-004).
    EXCLUDE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "[class*='recommend' i]",
        "[class*='carousel' i]",
        "[class*='you-may' i]",
    ]
