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

    # Both TLDs; costco.ca 301s the legacy ``/<slug>.product.<id>.html`` scheme to
    # the new React app scheme ``/p/-/<slug>/<id>`` — domain match claims both.
    DOMAIN_PATTERNS = [
        r"costco\.com",
        r"costco\.ca",
    ]

    # JSON-LD first (universal backbone), then title, then visible site-specific
    # detail/spec/ingredient sections. No meta[...] selectors (LORE.md ADR-004).
    # Costco spans groceries + goods → both ingredients AND specs matter. Both the
    # new React-app ids (verified live 2026-08-01: #productDescriptionDesktop,
    # #product_details, #product-details-summary, #specifications,
    # #ProductSpecifications) AND the legacy selectors are kept (old pages fall back).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {
            "name": "product_details",
            "selector": (
                "#productDescriptionDesktop, #product_details, #product-details-summary, "
                "#product-details-tabs, .product-info-description, [class*='product-info' i]"
            ),
        },
        {
            "name": "specifications",
            "selector": "#specifications, #ProductSpecifications, [class*='spec' i], #product-tab2",
        },
        {"name": "ingredients", "selector": "[class*='ingredient' i]"},
    ]

    # Costco embeds reviews via Bazaarvoice: schema.org Review objects live in
    # ``script#bv-jsonld-reviews-data`` (+ an aggregate summary in
    # ``script#bv-jsonld-bvloader-summary``). Captured here for the Claude review
    # text path; the vector-store dicts come from the inherited JSON-LD REVIEW_PARSER.
    REVIEWS_SECTION_SELECTORS = [
        {"name": "bazaarvoice_reviews", "selector": "script#bv-jsonld-reviews-data"},
        {"name": "bazaarvoice_summary", "selector": "script#bv-jsonld-bvloader-summary"},
    ]

    EXCLUDE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "[class*='recommend' i]",
        "[class*='carousel' i]",
        "[class*='you-may' i]",
    ]
