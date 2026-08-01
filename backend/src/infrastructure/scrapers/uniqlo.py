"""Uniqlo product scraper — configuration only (no DOM-specific overrides).

Uniqlo product pages normally embed a ``<script type="application/ld+json">``
Product schema (name, brand, description, sku), so the universal JSON-LD backbone
(LORE.md ADR-004) plus a few visible apparel selectors (fabric composition, product
details, care) fully covers it. All mechanics are inherited from ``BaseScraper``
(LORE.md ADR-001); nothing about Uniqlo's DOM requires a method override.

Apparel → fabric composition matters, so ``materials``/``composition`` selectors are
included after the JSON-LD + title backbone.

Recon note (2026-06-03, live): product pages reachable; **VALIDATED**. The JSON-LD Product
is rich and includes ``material`` AND ``description`` (like IKEA), so ``structured_data``
alone captures the composition. The visible PDP container uses the ``fr-ec-template-pdp``
class prefix (added below as a robust fallback).
"""

from .base import BaseScraper
from .review_parsers import UniqloReviewParser


class UniqloScraper(BaseScraper):
    """Uniqlo-specific product scraper (config-only)."""

    RETAILER_NAME = "Uniqlo"
    SCRAPE_METHOD = "uniqlo_raw_html"

    #: Uniqlo renders reviews in a DOM container (#productReviews-container);
    #: parsed best-effort into structured dicts for the vector store.
    REVIEW_PARSER = UniqloReviewParser

    DOMAIN_PATTERNS = [
        r"uniqlo\.com",
    ]

    # JSON-LD first (universal backbone), then title, then visible site-specific
    # apparel sections (composition/details/care). No meta[...] selectors (ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {"name": "materials", "selector": "[class*='material' i], [class*='composition' i]"},
        {"name": "product_details", "selector": "[class*='fr-ec-template-pdp' i], .product-description, [class*='description' i], [class*='product-detail' i]"},
        {"name": "care", "selector": "[class*='care' i]"},
    ]

    # Uniqlo has no usable client-session reviews endpoint; reviews (where present)
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
