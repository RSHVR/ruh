"""Amazon product scraper — configuration + Amazon-specific DOM overrides.

Generic mechanics (Playwright fetch, section extraction, client-HTML processing,
confidence, error results) live in ``BaseScraper`` (LORE.md ADR-001). This class
declares Amazon's selector config and overrides only the three methods whose DOM is
Amazon-specific: retailer-name mapping, the a-span attribute table, and the rich
structured-review extraction.
"""

import re
from bs4 import BeautifulSoup
from typing import List

from .base import BaseScraper
from .review_parsers import AmazonReviewParser


class AmazonScraper(BaseScraper):
    """Amazon-specific product scraper (reference implementation)."""

    RETAILER_NAME = "Amazon"
    SCRAPE_METHOD = "amazon_raw_html"

    #: Amazon ships reviews as a ``data-hook`` DOM (structured dicts for the
    #: vector store come from the dedicated Amazon parser, which accepts both the
    #: renamed 2026 hooks and the legacy ones).
    REVIEW_PARSER = AmazonReviewParser

    DOMAIN_PATTERNS = [
        r"amazon\.(com|ca|co\.uk|de|fr|it|es|com\.au|co\.jp)",
    ]

    # MAIN PRODUCT SECTIONS (for ingredient/material analysis)
    PRODUCT_SECTION_SELECTORS = [
        {"name": "title", "selector": "#productTitle"},
        {"name": "brand", "selector": "#bylineInfo"},
        {"name": "price", "selector": ".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice"},
        {"name": "availability", "selector": "#availability"},
        {"name": "product_attributes", "selector": ".a-section.a-spacing-small.a-spacing-top-small"},
        {"name": "feature_bullets", "selector": "#feature-bullets-btf"},
        {"name": "about_item", "selector": "#featurebullets_feature_div"},
        {"name": "product_description", "selector": "#productDescription"},
        {"name": "aplus_content", "selector": "#aplus, #aplus_feature_div"},
        {"name": "detail_bullets", "selector": "#detailBullets_feature_div"},
        {"name": "product_info", "selector": "#productDetails_techSpec_section_1, #productDetails_detailBullets_sections1"},
    ]

    # REVIEWS & Q&A SECTIONS (for consumer insights)
    REVIEWS_SECTION_SELECTORS = [
        {"name": "reviews_medley", "selector": "#reviewsMedley"},
        {"name": "ratings_histogram", "selector": ".cr-widget-TitleRatingsHistogram"},
        {"name": "focal_reviews", "selector": ".cr-widget-FocalReviews"},
        {"name": "review_items", "selector": "[data-hook='review']"},
        {"name": "questions_answers", "selector": "#ask-btf, #askATFLink"},
    ]

    # Always exclude these (recommended products, ads, nav)
    EXCLUDE_SELECTORS = [
        "#similarities_feature_div",
        "#purchase-sims-feature",
        ".similarities-widget",
        "[data-component-type='sp-sponsored-products']",
        "#nav-subnav",
        "#navbar",
        "#rhf",
        # A+ cross-product comparison modules: rows like "Simpler Ingredients
        # ✓✓✓" over OTHER products' names/prices/ratings poisoned ingredient
        # extraction (live prod failure 2026-08-01, dishwasher pods).
        ".apm-tablemodule",
        ".aplus-comparison-table",
        "#aplus table[class*='comparison']",
    ]

    def _extract_retailer(self, url: str) -> str:
        """Map URL to the specific Amazon TLD label."""
        for tld, name in (
            ("amazon.ca", "Amazon.ca"),
            ("amazon.com.au", "Amazon.com.au"),
            ("amazon.com", "Amazon.com"),
            ("amazon.co.uk", "Amazon.co.uk"),
            ("amazon.co.jp", "Amazon.co.jp"),
            ("amazon.de", "Amazon.de"),
            ("amazon.fr", "Amazon.fr"),
            ("amazon.it", "Amazon.it"),
            ("amazon.es", "Amazon.es"),
        ):
            if tld in url:
                return name
        return "Amazon"

    def _extract_product_attributes(self, elements: List) -> str:
        """Amazon attribute table: label in ``.a-span3/4``, value in ``.a-span9/8``."""
        attributes: List[str] = []
        for element in elements:
            rows = element.select("tr")
            if not rows:
                continue
            for row in rows:
                label_cell = row.select_one(".a-span3, .a-span4")
                value_cell = row.select_one(".a-span9, .a-span8")
                if label_cell and value_cell:
                    label = label_cell.get_text(strip=True)
                    value = value_cell.get_text(strip=True).replace("See more", "").strip()
                    if label and value:
                        attributes.append(f"{label}: {value}")
        return "\n".join(attributes)

    def _extract_reviews_structured(self, soup: BeautifulSoup) -> str:
        """Rich, Claude-friendly review extraction with labeled components."""
        sections: List[str] = []

        rating_summary = self._extract_rating_summary(soup)
        if rating_summary:
            sections += ["=== rating_summary ===", rating_summary, ""]

        histogram = self._extract_rating_histogram(soup)
        if histogram:
            sections += ["=== rating_histogram ===", histogram, ""]

        reviews = self._extract_individual_reviews(soup)
        if reviews:
            sections += ["=== reviews ===", reviews, ""]

        qa_section = soup.select_one("#ask-btf, #askATFLink, #ask-lazy-load-feature")
        if qa_section:
            qa_text = qa_section.get_text(separator=" ", strip=True)
            if qa_text and len(qa_text) > 50:
                sections += ["=== questions_and_answers ===", re.sub(r"\s+", " ", qa_text)[:5000], ""]

        return "\n".join(sections)

    def _extract_rating_summary(self, soup: BeautifulSoup) -> str:
        parts: List[str] = []
        rating_el = soup.select_one("#acrPopover")
        if rating_el and rating_el.get("title"):
            parts.append(f"Average Rating: {rating_el.get('title')}")
        total_el = soup.select_one("[data-hook='total-review-count']")
        if total_el:
            parts.append(f"Total Ratings: {total_el.get_text(strip=True)}")
        reviews_count_el = soup.select_one("#acrCustomerReviewText")
        if reviews_count_el:
            parts.append(f"Reviews Count: {reviews_count_el.get_text(strip=True)}")
        return "\n".join(parts)

    def _extract_rating_histogram(self, soup: BeautifulSoup) -> str:
        lines: List[str] = []
        for link in soup.select("a[aria-label*='percent of reviews']"):
            aria_label = link.get("aria-label", "")
            match = re.search(r"(\d+)\s*percent.*?(\d+)\s*star", aria_label, re.IGNORECASE)
            if match:
                percent, stars = match.groups()
                lines.append(f"{stars} star: {percent}%")
        seen = set()
        unique = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique.append(line)
        return "\n".join(unique)

    def _extract_individual_reviews(self, soup: BeautifulSoup) -> str:
        reviews_text: List[str] = []
        for i, review_el in enumerate(soup.select("[data-hook='review']"), 1):
            parts = [f"--- Review #{i} ---"]

            star_el = review_el.select_one("[data-hook='review-star-rating'] .a-icon-alt")
            if star_el:
                parts.append(f"Rating: {star_el.get_text(strip=True)}")

            name_el = review_el.select_one(".a-profile-name")
            if name_el:
                parts.append(f"Reviewer: {name_el.get_text(strip=True)}")

            date_el = review_el.select_one("[data-hook='review-date']")
            if date_el:
                parts.append(f"Date: {date_el.get_text(strip=True)}")

            verified_el = review_el.select_one("[data-hook='avp-badge'], [data-hook='avp-badge-linkless']")
            parts.append(f"Verified Purchase: {'Yes' if verified_el else 'No'}")

            format_el = review_el.select_one("[data-hook='format-strip-linkless']")
            if format_el:
                parts.append(f"Variant: {format_el.get_text(strip=True)}")

            # Title: renamed 2026 hook (h5[reviewTitle]) first, legacy hook as fallback.
            title_el = review_el.select_one(
                "h5[data-hook='reviewTitle'], [data-hook='review-title']"
            )
            if title_el:
                title_text = re.sub(
                    r"^[\d.]+\s+out\s+of\s+\d+\s+stars?\s*", "", title_el.get_text(strip=True)
                )
                if title_text:
                    parts.append(f"Title: {title_text}")

            # Body: renamed 2026 hook (div[reviewText]) first, legacy hooks as fallback.
            body_el = (
                review_el.select_one("[data-hook='reviewText']")
                or review_el.select_one("[data-hook='review-collapsed']")
                or review_el.select_one("[data-hook='review-body']")
            )
            if body_el:
                body_text = body_el.get_text(separator=" ", strip=True)
                body_text = re.sub(r"\(function\(\).*?\}\)\(\);?", "", body_text, flags=re.DOTALL)
                body_text = re.sub(r"\.review-text.*?\}", "", body_text, flags=re.DOTALL)
                body_text = re.sub(r"Read more\s*$", "", body_text)
                body_text = re.sub(r"\s+", " ", body_text).strip()
                if body_text and len(body_text) > 10:
                    parts.append(f"Review: {body_text}")

            helpful_el = review_el.select_one("[data-hook='helpful-vote-statement']")
            if helpful_el:
                parts.append(f"Helpful: {helpful_el.get_text(strip=True)}")

            reviews_text.append("\n".join(parts))

        return "\n\n".join(reviews_text)
