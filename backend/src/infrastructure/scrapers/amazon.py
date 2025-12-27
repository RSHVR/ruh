"""Amazon product scraper using Playwright for JavaScript rendering."""

import re
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import List, Dict, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from playwright.async_api import Browser

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
    # Updated based on actual Amazon HTML structure analysis (Dec 2025)
    REVIEWS_SECTION_SELECTORS = [
        # Main reviews container with histogram and top reviews
        {"name": "reviews_medley", "selector": "#reviewsMedley"},
        # Rating histogram widget
        {"name": "ratings_histogram", "selector": ".cr-widget-TitleRatingsHistogram"},
        # Top reviews section (usually 8-15 reviews)
        {"name": "focal_reviews", "selector": ".cr-widget-FocalReviews"},
        # Individual review items (processed specially)
        {"name": "review_items", "selector": "[data-hook='review']"},
        # Q&A section
        {"name": "questions_answers", "selector": "#ask-btf, #askATFLink"},
    ]

    # Data hooks for extracting individual review details
    REVIEW_DATA_HOOKS = {
        "star_rating": "[data-hook='review-star-rating'] .a-icon-alt",
        "title": "[data-hook='review-title']",
        "date": "[data-hook='review-date']",
        "body": "[data-hook='review-collapsed'], [data-hook='review-body']",
        "verified": "[data-hook='avp-badge'], [data-hook='avp-badge-linkless']",
        "helpful_votes": "[data-hook='helpful-vote-statement']",
        "reviewer_name": ".a-profile-name",
        "format_strip": "[data-hook='format-strip-linkless']",
    }

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

    async def _fetch_with_playwright(self, url: str, timeout: int = 30000) -> Optional[str]:
        """Fetch page HTML using Playwright headless browser.

        Uses Chromium to bypass bot detection and execute JavaScript.

        Args:
            url: URL to fetch
            timeout: Page load timeout in milliseconds

        Returns:
            HTML content or None if failed
        """
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Navigate and wait for DOM
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

                # Wait for JavaScript to render content
                await asyncio.sleep(1.5)

                # Scroll to trigger lazy-loaded content (reviews, etc.)
                await page.evaluate("""
                    async () => {
                        await new Promise((resolve) => {
                            let totalHeight = 0;
                            const distance = 300;
                            const timer = setInterval(() => {
                                window.scrollBy(0, distance);
                                totalHeight += distance;
                                if (totalHeight >= document.body.scrollHeight) {
                                    clearInterval(timer);
                                    resolve();
                                }
                            }, 100);
                        });
                    }
                """)

                # Wait for lazy content to load
                await asyncio.sleep(0.5)

                # Get full rendered HTML
                html = await page.content()
                await browser.close()

                logger.info(f"✅ Playwright fetched {len(html)} bytes from {url}")
                return html

        except Exception as e:
            logger.error(f"❌ Playwright fetch failed: {e}")
            return None

    def process_client_html(
        self,
        url: str,
        product_html: str,
        reviews_html: str = ""
    ) -> ScrapedProduct:
        """Process client-provided HTML using the same extraction logic.

        This applies selector-based extraction to reduce ~2MB raw HTML to ~20KB
        clean text that Claude can process efficiently.

        Args:
            url: Product URL
            product_html: Raw HTML from client (full DOM)
            reviews_html: Raw reviews HTML from client (optional)

        Returns:
            ScrapedProduct with extracted text content
        """
        logger.info(f"📦 Processing client HTML: {len(product_html) / 1024:.1f}KB product, {len(reviews_html) / 1024:.1f}KB reviews")

        # Parse product HTML
        soup = BeautifulSoup(product_html, "html.parser")

        # Remove excluded sections (ads, nav, sidebar)
        self._remove_excluded_sections(soup)

        # Extract only relevant product sections as plain text
        extracted_product = self._extract_sections(soup, self.PRODUCT_SECTION_SELECTORS)

        # Process reviews HTML if provided
        extracted_reviews = ""
        if reviews_html:
            reviews_soup = BeautifulSoup(reviews_html, "html.parser")
            extracted_reviews = self._extract_reviews_structured(reviews_soup)

        # Log compression ratio
        original_size = len(product_html) + len(reviews_html)
        extracted_size = len(extracted_product) + len(extracted_reviews)
        compression_ratio = (1 - extracted_size / original_size) * 100 if original_size > 0 else 0

        logger.info(f"✅ Extracted: {len(extracted_product) / 1024:.1f}KB product, {len(extracted_reviews) / 1024:.1f}KB reviews")
        logger.info(f"📉 Compression: {original_size / 1024:.1f}KB → {extracted_size / 1024:.1f}KB ({compression_ratio:.1f}% reduction)")

        return ScrapedProduct(
            url=url,
            retailer=self._extract_retailer(url),
            raw_html_product=extracted_product,
            raw_html_reviews=extracted_reviews,
            raw_html_snippet=extracted_product[:1000],
            confidence=0.95,  # High confidence since it's from user's session
            scrape_method="client",
            scraped_at=datetime.now(timezone.utc),
            has_reviews=len(extracted_reviews) > 100,
        )

    async def scrape(self, url: str, include_reviews: bool = False) -> ScrapedProduct:
        """Scrape Amazon product page using Playwright.

        Uses headless Chromium to bypass bot detection and render JavaScript.

        Args:
            url: Product URL
            include_reviews: If True, also scrape reviews/Q&A sections

        Returns:
            ScrapedProduct with raw HTML sections
        """
        try:
            logger.info(f"🕷️  Fetching Amazon product with Playwright: {url} (reviews={include_reviews})")

            # Fetch HTML using Playwright
            html = await self._fetch_with_playwright(url)

            if not html:
                logger.error("❌ Playwright returned empty HTML")
                return self._create_error_result(url, "Failed to fetch page")

            soup = BeautifulSoup(html, "html.parser")

            # Remove excluded sections first
            self._remove_excluded_sections(soup)

            # Extract product sections (always)
            product_html = self._extract_sections(soup, self.PRODUCT_SECTION_SELECTORS)

            # Extract reviews sections (optional) - uses enhanced structured extraction
            reviews_html = ""
            if include_reviews:
                reviews_html = self._extract_reviews_structured(soup)

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
                scraped_at=datetime.now(timezone.utc),
                has_reviews=include_reviews and len(reviews_html) > 100,
            )

        except asyncio.TimeoutError as e:
            logger.error(f"❌ Timeout while scraping {url}: {e}")
            return self._create_error_result(url, f"Request timeout: {str(e)}")

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

    def _extract_reviews_structured(self, soup: BeautifulSoup) -> str:
        """Extract reviews in a structured, Claude-friendly format.

        This method extracts reviews with clear labels for each component,
        making it easier for Claude to parse and analyze health concerns.

        Args:
            soup: BeautifulSoup object

        Returns:
            Structured text with reviews data
        """
        sections = []

        # 1. Extract overall rating summary
        rating_summary = self._extract_rating_summary(soup)
        if rating_summary:
            sections.append("=== rating_summary ===")
            sections.append(rating_summary)
            sections.append("")

        # 2. Extract rating histogram
        histogram = self._extract_rating_histogram(soup)
        if histogram:
            sections.append("=== rating_histogram ===")
            sections.append(histogram)
            sections.append("")

        # 3. Extract individual reviews with structured data
        reviews = self._extract_individual_reviews(soup)
        if reviews:
            sections.append("=== reviews ===")
            sections.append(reviews)
            sections.append("")

        # 4. Extract Q&A section
        qa_section = soup.select_one("#ask-btf, #askATFLink, #ask-lazy-load-feature")
        if qa_section:
            qa_text = qa_section.get_text(separator=" ", strip=True)
            if qa_text and len(qa_text) > 50:
                sections.append("=== questions_and_answers ===")
                # Clean up excessive whitespace
                qa_text = re.sub(r'\s+', ' ', qa_text)
                sections.append(qa_text[:5000])  # Limit Q&A to 5KB
                sections.append("")

        return "\n".join(sections)

    def _extract_rating_summary(self, soup: BeautifulSoup) -> str:
        """Extract overall rating summary (average rating, total count).

        Args:
            soup: BeautifulSoup object

        Returns:
            Formatted rating summary string
        """
        summary_parts = []

        # Overall rating (e.g., "4.6 out of 5 stars")
        rating_el = soup.select_one("#acrPopover")
        if rating_el:
            rating = rating_el.get("title", "")
            if rating:
                summary_parts.append(f"Average Rating: {rating}")

        # Total ratings count (e.g., "6,011 global ratings")
        total_el = soup.select_one("[data-hook='total-review-count']")
        if total_el:
            total = total_el.get_text(strip=True)
            summary_parts.append(f"Total Ratings: {total}")

        # Total reviews text
        reviews_count_el = soup.select_one("#acrCustomerReviewText")
        if reviews_count_el:
            count = reviews_count_el.get_text(strip=True)
            summary_parts.append(f"Reviews Count: {count}")

        return "\n".join(summary_parts)

    def _extract_rating_histogram(self, soup: BeautifulSoup) -> str:
        """Extract rating distribution histogram.

        Args:
            soup: BeautifulSoup object

        Returns:
            Formatted histogram string (e.g., "5 star: 74%")
        """
        histogram_lines = []

        # Find histogram links with aria-labels like "74 percent of reviews have 5 stars"
        histogram_links = soup.select("a[aria-label*='percent of reviews']")

        for link in histogram_links:
            aria_label = link.get("aria-label", "")
            if aria_label:
                # Parse "74 percent of reviews have 5 stars" -> "5 star: 74%"
                match = re.search(r'(\d+)\s*percent.*?(\d+)\s*star', aria_label, re.IGNORECASE)
                if match:
                    percent, stars = match.groups()
                    histogram_lines.append(f"{stars} star: {percent}%")

        # Deduplicate while preserving order (5, 4, 3, 2, 1)
        seen = set()
        unique_lines = []
        for line in histogram_lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)

        return "\n".join(unique_lines)

    def _extract_individual_reviews(self, soup: BeautifulSoup) -> str:
        """Extract individual reviews with structured formatting.

        Args:
            soup: BeautifulSoup object

        Returns:
            Formatted reviews text with clear labels
        """
        review_elements = soup.select("[data-hook='review']")
        reviews_text = []

        for i, review_el in enumerate(review_elements, 1):
            review_parts = [f"--- Review #{i} ---"]

            # Star rating
            star_el = review_el.select_one("[data-hook='review-star-rating'] .a-icon-alt")
            if star_el:
                review_parts.append(f"Rating: {star_el.get_text(strip=True)}")

            # Reviewer name
            name_el = review_el.select_one(".a-profile-name")
            if name_el:
                review_parts.append(f"Reviewer: {name_el.get_text(strip=True)}")

            # Review date
            date_el = review_el.select_one("[data-hook='review-date']")
            if date_el:
                review_parts.append(f"Date: {date_el.get_text(strip=True)}")

            # Verified purchase
            verified_el = review_el.select_one("[data-hook='avp-badge'], [data-hook='avp-badge-linkless']")
            if verified_el:
                review_parts.append("Verified Purchase: Yes")
            else:
                review_parts.append("Verified Purchase: No")

            # Product variant (color, size, etc.)
            format_el = review_el.select_one("[data-hook='format-strip-linkless']")
            if format_el:
                review_parts.append(f"Variant: {format_el.get_text(strip=True)}")

            # Review title
            title_el = review_el.select_one("[data-hook='review-title']")
            if title_el:
                # Clean the title - remove the star rating text that's often included
                title_text = title_el.get_text(strip=True)
                # Remove patterns like "5.0 out of 5 stars" from the beginning
                title_text = re.sub(r'^[\d.]+\s+out\s+of\s+\d+\s+stars?\s*', '', title_text)
                if title_text:
                    review_parts.append(f"Title: {title_text}")

            # Review body - try collapsed first (actual content), then full body
            body_el = review_el.select_one("[data-hook='review-collapsed']")
            if not body_el:
                body_el = review_el.select_one("[data-hook='review-body']")

            if body_el:
                body_text = body_el.get_text(separator=" ", strip=True)
                # Remove JavaScript artifacts
                body_text = re.sub(r'\(function\(\).*?\}\)\(\);?', '', body_text, flags=re.DOTALL)
                body_text = re.sub(r'\.review-text.*?\}', '', body_text, flags=re.DOTALL)
                body_text = re.sub(r'Read more\s*$', '', body_text)
                body_text = re.sub(r'\s+', ' ', body_text).strip()

                if body_text and len(body_text) > 10:
                    review_parts.append(f"Review: {body_text}")

            # Helpful votes
            helpful_el = review_el.select_one("[data-hook='helpful-vote-statement']")
            if helpful_el:
                review_parts.append(f"Helpful: {helpful_el.get_text(strip=True)}")

            reviews_text.append("\n".join(review_parts))

        return "\n\n".join(reviews_text)

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
            scraped_at=datetime.now(timezone.utc),
            has_reviews=False,
            error_message=error_message,
        )
