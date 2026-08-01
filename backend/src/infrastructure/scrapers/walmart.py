"""Walmart product scraper — config + a ``__NEXT_DATA__`` extraction override.

Walmart pages are a Next.js app: the full product/spec/review payload lives in a
``<script id="__NEXT_DATA__">`` blob (~236KB), NOT in readable DOM sections.
Shipping the whole blob to Claude is wasteful, so this scraper overrides the
generic section/review extraction (the base class explicitly allows per-site
overrides — LORE.md ADR-001) to emit a compact structured block from
``props.pageProps.initialData.data.{product, idml, reviews}``. When ``__NEXT_DATA__``
is missing or unparseable it degrades to the visible DOM selectors (INV-3 — never
500). Walmart bot-walls server automation (PerimeterX), so the client-HTML path is
the real integration surface (INV-1).
"""

import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from .base import BaseScraper
from .review_parsers import WalmartReviewParser, parse_next_data_json


class WalmartScraper(BaseScraper):
    """Walmart-specific product scraper (``__NEXT_DATA__`` first, DOM fallback)."""

    RETAILER_NAME = "Walmart"

    # walmart.com uses numeric ids (/ip/<slug>/<digits>); walmart.ca uses
    # alphanumeric ids (/en/ip/<slug>/38WYZF7I4FZ6). Domain match claims both.
    DOMAIN_PATTERNS = [
        r"walmart\.com",
        r"walmart\.ca",
    ]

    #: Walmart reviews live in __NEXT_DATA__ (customerReviews), not the DOM.
    REVIEW_PARSER = WalmartReviewParser

    # DOM fallback selectors (used only when __NEXT_DATA__ is absent). JSON-LD
    # backbone + title + the verified visible section ids (ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {
            "name": "product_details",
            "selector": (
                "#product-description-section, #about-this-item-section, #item-product-details, "
                "[data-testid*='product-description'], #product-overview, [class*='product-description' i]"
            ),
        },
        {
            "name": "specifications",
            "selector": (
                "#specifications-wrapper, [data-testid*='specification'], [class*='specification' i]"
            ),
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

    # ------------------------------------------------------------------ #
    # __NEXT_DATA__ extraction (preferred), DOM selectors as fallback
    # ------------------------------------------------------------------ #
    def _extract_sections(self, soup: BeautifulSoup, selectors: List[Dict]) -> str:
        """Prefer a compact block built from __NEXT_DATA__; fall back to the DOM."""
        data = self._next_data(soup)
        if data:
            block = self._build_product_block(data)
            if block:
                return block
        return super()._extract_sections(soup, selectors)

    def _extract_reviews_structured(self, soup: BeautifulSoup) -> str:
        """Compact review text from __NEXT_DATA__ customerReviews (DOM fallback)."""
        data = self._next_data(soup)
        if data:
            customer_reviews = (data.get("reviews") or {}).get("customerReviews")
            reviews = WalmartReviewParser.from_customer_reviews(customer_reviews)
            if reviews:
                return self._format_reviews_block(reviews)
        return super()._extract_reviews_structured(soup)

    @staticmethod
    def _next_data(soup: BeautifulSoup) -> Optional[Dict]:
        """Return ``props.pageProps.initialData.data`` from __NEXT_DATA__, or None."""
        raw = parse_next_data_json(soup)
        if not raw:
            return None
        data = (
            ((raw.get("props") or {}).get("pageProps") or {}).get("initialData") or {}
        ).get("data")
        return data if isinstance(data, dict) else None

    def _build_product_block(self, data: Dict) -> str:
        """Build a compact ``=== section ===`` product block from product + idml."""
        product = data.get("product") or {}
        idml = data.get("idml") or {}
        lines: List[str] = []

        header: List[str] = []
        for label, key in (
            ("Product", "name"),
            ("Brand", "brand"),
            ("Seller", "sellerName"),
        ):
            value = product.get(key)
            if value:
                header.append(f"{label}: {self._text(value)}")
        description = product.get("shortDescription") or product.get("longDescription")
        if description:
            header.append(f"Description: {self._text(description)}")
        if header:
            lines += ["=== structured_data ==="] + header + [""]

        specs = idml.get("specifications")
        if isinstance(specs, list):
            spec_lines = [
                f"{s['name']}: {self._text(s['value'])}"
                for s in specs
                if isinstance(s, dict) and s.get("name") and s.get("value")
            ]
            if spec_lines:
                lines += ["=== specifications ==="] + spec_lines + [""]

        ingredients = idml.get("ingredients")
        if ingredients:
            text = (
                self._text(ingredients)
                if isinstance(ingredients, str)
                else self._text(" ".join(map(str, ingredients)))
                if isinstance(ingredients, list)
                else str(ingredients)
            )
            if text:
                lines += ["=== ingredients ===", text, ""]

        return "\n".join(lines).strip()

    @staticmethod
    def _format_reviews_block(reviews: List[Dict]) -> str:
        sections = ["=== reviews ==="]
        for i, r in enumerate(reviews, 1):
            parts = [f"--- Review #{i} ---"]
            if r.get("review_rating") is not None:
                parts.append(f"Rating: {r['review_rating']} out of 5")
            if r.get("reviewer_name"):
                parts.append(f"Reviewer: {r['reviewer_name']}")
            if r.get("review_date"):
                parts.append(f"Date: {r['review_date']}")
            if r.get("review_title"):
                parts.append(f"Title: {r['review_title']}")
            parts.append(f"Review: {r['review_text']}")
            sections.append("\n".join(parts))
        return "\n\n".join(sections)

    @staticmethod
    def _text(value) -> str:
        """Coerce a value to clean text, stripping any embedded HTML."""
        text = str(value)
        if "<" in text and ">" in text:
            text = BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()
