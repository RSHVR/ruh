"""Amazon product scraper."""

import re
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import logging

from .base import BaseScraper
from ...domain.models import ScrapedProduct

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    """Amazon-specific product scraper.

    Extracts product data from Amazon product pages in two modes:
    1. Product sections: Title through Product Information (for analysis)
    2. Reviews sections: Customer reviews and Q&A (for consumer insights)
    """

    DOMAIN_PATTERNS = [
        r"amazon\.(com|ca|co\.uk|de|fr|it|es|com\.au|co\.jp)",
    ]

    # User agent to avoid bot detection
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # MAIN PRODUCT SECTIONS (for ingredient/material analysis)
    PRODUCT_SECTION_SELECTORS = [
        {"name": "title", "selector": "#productTitle"},
        {"name": "brand", "selector": "#bylineInfo"},
        {"name": "price", "selector": ".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice"},
        {"name": "availability", "selector": "#availability"},
        {"name": "product_attributes", "selector": ".a-section.a-spacing-small.a-spacing-top-small"},  # Ingredients, skin type, material features
        {"name": "feature_bullets", "selector": "#feature-bullets-btf"},
        {"name": "about_item", "selector": "#featurebullets_feature_div"},
        {"name": "product_description", "selector": "#productDescription"},
        {"name": "aplus_content", "selector": "#aplus, #aplus_feature_div"},
        # Removed tech_details - redundant with detail_bullets and product_info, contains useless forms
        {"name": "detail_bullets", "selector": "#detailBullets_feature_div"},
        {"name": "product_info", "selector": "#productDetails_techSpec_section_1, #productDetails_detailBullets_sections1"},
    ]

    # REVIEWS & Q&A SECTIONS (for consumer insights)
    REVIEWS_SECTION_SELECTORS = [
        {"name": "reviews_summary", "selector": "#reviewsMedley"},
        {"name": "customer_reviews", "selector": "#customer-reviews"},
        {"name": "critical_reviews", "selector": ".cr-widget-FocalReviews"},
        {"name": "reviews_list", "selector": "[data-hook='review']"},
        {"name": "questions_answers", "selector": "#ask-btf, #customer-questions"},
    ]

    # Always exclude these (recommended products, ads)
    EXCLUDE_SELECTORS = [
        "#similarities_feature_div",
        "#purchase-sims-feature",
        ".similarities-widget",
        "[data-component-type='sp-sponsored-products']",
        "#nav-subnav",
        "#navbar",
        "#rhf",
    ]

    async def can_scrape(self, url: str) -> bool:
        """Check if this scraper can handle the URL.

        Args:
            url: Product URL to check

        Returns:
            True if URL is an Amazon domain
        """
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.DOMAIN_PATTERNS)

    async def scrape(self, url: str, include_reviews: bool = False) -> ScrapedProduct:
        """Scrape Amazon product page.

        Args:
            url: Product URL
            include_reviews: If True, also scrape reviews/Q&A sections

        Returns:
            ScrapedProduct with raw HTML sections
        """
        try:
            logger.info(f"🕷️  Fetching Amazon product: {url} (reviews={include_reviews})")

            # Fetch HTML
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": self.USER_AGENT,
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                    follow_redirects=True
                )
                response.raise_for_status()
                html = response.text

            soup = BeautifulSoup(html, "lxml")

            # Remove excluded sections first
            self._remove_excluded_sections(soup)

            # Extract product sections (always)
            product_html = self._extract_sections(soup, self.PRODUCT_SECTION_SELECTORS)

            # Extract reviews sections (optional)
            reviews_html = ""
            if include_reviews:
                reviews_html = self._extract_sections(soup, self.REVIEWS_SECTION_SELECTORS)

            # Measure sizes
            product_size_kb = len(product_html) / 1024
            reviews_size_kb = len(reviews_html) / 1024

            logger.info(f"✅ Extracted product HTML: {product_size_kb:.1f}KB")
            if include_reviews:
                logger.info(f"✅ Extracted reviews HTML: {reviews_size_kb:.1f}KB")

            return ScrapedProduct(
                url=url,
                retailer=self._extract_retailer(url),
                raw_html_product=product_html,
                raw_html_reviews=reviews_html,
                raw_html_snippet=product_html[:1000],
                confidence=self._calculate_confidence(product_size_kb, reviews_size_kb),
                scrape_method="amazon_raw_html",
                scraped_at=datetime.utcnow(),
                has_reviews=include_reviews and len(reviews_html) > 100,
            )

        except httpx.TimeoutException as e:
            logger.error(f"❌ Timeout while scraping {url}: {e}")
            return self._create_error_result(url, f"Request timeout: {str(e)}")

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error {e.response.status_code} for {url}")
            return self._create_error_result(url, f"HTTP {e.response.status_code}: {str(e)}")

        except Exception as e:
            logger.error(f"❌ Scraping failed for {url}: {e}", exc_info=True)
            return self._create_error_result(url, str(e))

    def _remove_excluded_sections(self, soup: BeautifulSoup) -> None:
        """Remove excluded sections from soup in-place.

        Args:
            soup: BeautifulSoup object to modify
        """
        for selector in self.EXCLUDE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

    def _extract_sections(self, soup: BeautifulSoup, selectors: List[Dict]) -> str:
        """Extract TEXT content from sections (no HTML markup).

        Args:
            soup: BeautifulSoup object
            selectors: List of selector definitions

        Returns:
            Combined text string with section markers (no HTML tags)
        """
        import re
        extracted_text = []

        for section_def in selectors:
            elements = soup.select(section_def["selector"])
            if elements:
                # Special handling for price: only take first element to avoid duplicates
                if section_def["name"] == "price":
                    section_text = elements[0].get_text(separator=" ", strip=True)
                # Special handling for product_attributes: format as key-value pairs
                elif section_def["name"] == "product_attributes":
                    section_text = self._extract_product_attributes(elements)
                    # Don't collapse whitespace for attributes - already formatted
                else:
                    # Extract text from all matching elements
                    texts = []
                    for el in elements:
                        # Remove forms (price comparison, feedback forms, etc.)
                        for form in el.select('form'):
                            form.decompose()
                        texts.append(el.get_text(separator=" ", strip=True))
                    section_text = "\n".join(texts)
                    # Clean up excessive whitespace and newlines
                    section_text = re.sub(r'\s+', ' ', section_text)  # Collapse multiple spaces

                section_text = section_text.strip()

                if section_text:  # Only add if there's actual content
                    extracted_text.append(f"=== {section_def['name']} ===")
                    extracted_text.append(section_text)
                    extracted_text.append("")  # Blank line between sections

        return "\n".join(extracted_text)

    def _extract_product_attributes(self, elements: List) -> str:
        """Extract product attributes table with clean key-value formatting.

        Args:
            elements: List of BeautifulSoup elements containing attributes

        Returns:
            Formatted string with key: value pairs
        """
        attributes = []

        for element in elements:
            # Find table rows
            rows = element.select('tr')
            if not rows:
                continue

            for row in rows:
                # Get label and value columns
                label_cell = row.select_one('.a-span3, .a-span4')
                value_cell = row.select_one('.a-span9, .a-span8')

                if label_cell and value_cell:
                    label = label_cell.get_text(strip=True)
                    value = value_cell.get_text(strip=True)

                    # Clean up "See more" buttons
                    value = value.replace('See more', '').strip()

                    if label and value:
                        attributes.append(f"{label}: {value}")

        return "\n".join(attributes)

    def _extract_retailer(self, url: str) -> str:
        """Extract retailer name from URL.

        Args:
            url: Product URL

        Returns:
            Retailer name (e.g., "Amazon.ca")
        """
        if "amazon.ca" in url:
            return "Amazon.ca"
        elif "amazon.com" in url:
            return "Amazon.com"
        elif "amazon.co.uk" in url:
            return "Amazon.co.uk"
        elif "amazon.de" in url:
            return "Amazon.de"
        elif "amazon.fr" in url:
            return "Amazon.fr"
        elif "amazon.it" in url:
            return "Amazon.it"
        elif "amazon.es" in url:
            return "Amazon.es"
        elif "amazon.com.au" in url:
            return "Amazon.com.au"
        elif "amazon.co.jp" in url:
            return "Amazon.co.jp"
        return "Amazon"

    def _calculate_confidence(self, product_size_kb: float, reviews_size_kb: float) -> float:
        """Calculate confidence score based on extracted HTML size.

        Args:
            product_size_kb: Size of product HTML in KB
            reviews_size_kb: Size of reviews HTML in KB

        Returns:
            Confidence score (0.0-1.0)
        """
        if product_size_kb > 2:
            return 0.9
        elif product_size_kb > 1:
            return 0.7
        elif product_size_kb > 0.5:
            return 0.5
        else:
            return 0.2

    def _create_error_result(self, url: str, error_message: str) -> ScrapedProduct:
        """Create a ScrapedProduct for error cases.

        Args:
            url: Product URL
            error_message: Error description

        Returns:
            ScrapedProduct with error information
        """
        return ScrapedProduct(
            url=url,
            retailer=self._extract_retailer(url),
            raw_html_product="",
            raw_html_reviews="",
            raw_html_snippet="",
            confidence=0.0,
            scrape_method="failed",
            scraped_at=datetime.utcnow(),
            has_reviews=False,
            error_message=error_message,
        )
