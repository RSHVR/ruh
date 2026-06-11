"""Abstract base class for product scrapers (config-driven template method).

A concrete scraper is mostly *configuration*: declare the class attributes
(``DOMAIN_PATTERNS``, ``RETAILER_NAME``, ``PRODUCT_SECTION_SELECTORS``,
``REVIEWS_SECTION_SELECTORS``, ``EXCLUDE_SELECTORS``) and the shared mechanics here
(Playwright fetch, section text extraction, client-HTML processing, confidence,
error results) are inherited. Override a method **only** when a site's DOM needs it.

See LORE.md ADR-001 for the rationale and INV-1 (client HTML is the primary source).
"""

import re
import asyncio
import logging
from abc import ABC
from datetime import datetime, timezone
from typing import List, Dict, Optional

from bs4 import BeautifulSoup

from ...domain.models import ScrapedProduct

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base scraper providing shared extraction mechanics.

    Subclasses configure the class attributes below. The default methods operate
    polymorphically on that config, so a typical retailer scraper is ~30-60 lines.
    """

    # --- Configuration (override in subclasses) ---
    #: Regex patterns matched against the URL to claim it (case-insensitive).
    DOMAIN_PATTERNS: List[str] = []
    #: Human-readable retailer name (used as default for ``_extract_retailer``).
    RETAILER_NAME: str = "Unknown"
    #: ``scrape_method`` tag recorded on server-side Playwright scrapes.
    SCRAPE_METHOD: str = "raw_html"

    #: Product sections to extract: ``[{"name": str, "selector": str}, ...]``.
    PRODUCT_SECTION_SELECTORS: List[Dict] = []
    #: Review sections to extract (used by the generic ``_extract_reviews_structured``).
    REVIEWS_SECTION_SELECTORS: List[Dict] = []
    #: Selectors removed before extraction (ads, nav, recommendations).
    EXCLUDE_SELECTORS: List[str] = []

    #: User agent for Playwright (avoids trivial bot detection).
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # ------------------------------------------------------------------ #
    # URL matching
    # ------------------------------------------------------------------ #
    async def can_scrape(self, url: str) -> bool:
        """Return True if this scraper claims the URL's domain."""
        return any(
            re.search(pattern, url, re.IGNORECASE) for pattern in self.DOMAIN_PATTERNS
        )

    # ------------------------------------------------------------------ #
    # Fetching (server-side fallback path)
    # ------------------------------------------------------------------ #
    async def _fetch_with_playwright(self, url: str, timeout: int = 30000) -> Optional[str]:
        """Fetch fully-rendered HTML via headless Chromium.

        Playwright is imported lazily so the module loads without it installed
        (the primary path is client-provided HTML; see INV-1).
        """
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(user_agent=self.USER_AGENT)

                await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                await asyncio.sleep(1.5)

                # Scroll to trigger lazy-loaded content (reviews, A+ content, etc.)
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
                await asyncio.sleep(0.5)

                html = await page.content()
                await browser.close()
                logger.info(f"✅ Playwright fetched {len(html)} bytes from {url}")
                return html
        except Exception as e:
            logger.error(f"❌ Playwright fetch failed: {e}")
            return None

    async def scrape(self, url: str, include_reviews: bool = False) -> ScrapedProduct:
        """Scrape a product page server-side via Playwright (fallback path)."""
        try:
            logger.info(
                f"🕷️  Fetching {self.RETAILER_NAME} product with Playwright: {url} "
                f"(reviews={include_reviews})"
            )
            html = await self._fetch_with_playwright(url)
            if not html:
                logger.error("❌ Playwright returned empty HTML")
                return self._create_error_result(url, "Failed to fetch page")

            soup = BeautifulSoup(html, "html.parser")
            self._remove_excluded_sections(soup)

            product_html = self._extract_sections(soup, self.PRODUCT_SECTION_SELECTORS)
            reviews_html = self._extract_reviews_structured(soup) if include_reviews else ""

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
                scrape_method=self.SCRAPE_METHOD,
                scraped_at=datetime.now(timezone.utc),
                has_reviews=include_reviews and len(reviews_html) > 100,
            )
        except asyncio.TimeoutError as e:
            logger.error(f"❌ Timeout while scraping {url}: {e}")
            return self._create_error_result(url, f"Request timeout: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Scraping failed for {url}: {e}", exc_info=True)
            return self._create_error_result(url, str(e))

    # ------------------------------------------------------------------ #
    # Client-HTML processing (primary path — INV-1)
    # ------------------------------------------------------------------ #
    def process_client_html(
        self,
        url: str,
        product_html: str,
        reviews_html: str = "",
    ) -> ScrapedProduct:
        """Process HTML captured from the user's authenticated session.

        Applies selector-based extraction to reduce a large raw DOM (~MBs) to
        compact, Claude-friendly text. High confidence since it's a real session.
        """
        logger.info(
            f"📦 Processing client HTML ({self.RETAILER_NAME}): "
            f"{len(product_html) / 1024:.1f}KB product, {len(reviews_html) / 1024:.1f}KB reviews"
        )

        soup = BeautifulSoup(product_html, "html.parser")
        self._remove_excluded_sections(soup)
        extracted_product = self._extract_sections(soup, self.PRODUCT_SECTION_SELECTORS)

        extracted_reviews = ""
        if reviews_html:
            reviews_soup = BeautifulSoup(reviews_html, "html.parser")
            extracted_reviews = self._extract_reviews_structured(reviews_soup)

        original_size = len(product_html) + len(reviews_html)
        extracted_size = len(extracted_product) + len(extracted_reviews)
        compression_ratio = (1 - extracted_size / original_size) * 100 if original_size > 0 else 0
        logger.info(
            f"✅ Extracted: {len(extracted_product) / 1024:.1f}KB product, "
            f"{len(extracted_reviews) / 1024:.1f}KB reviews "
            f"({compression_ratio:.1f}% reduction)"
        )

        return ScrapedProduct(
            url=url,
            retailer=self._extract_retailer(url),
            raw_html_product=extracted_product,
            raw_html_reviews=extracted_reviews,
            raw_html_snippet=extracted_product[:1000],
            confidence=0.95,  # High: from the user's real session
            scrape_method="client",
            scraped_at=datetime.now(timezone.utc),
            has_reviews=len(extracted_reviews) > 100,
        )

    # ------------------------------------------------------------------ #
    # Extraction mechanics (generic; override only when a DOM needs it)
    # ------------------------------------------------------------------ #
    def _remove_excluded_sections(self, soup: BeautifulSoup) -> None:
        """Remove EXCLUDE_SELECTORS from the soup in place."""
        for selector in self.EXCLUDE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

    def _extract_sections(self, soup: BeautifulSoup, selectors: List[Dict]) -> str:
        """Extract TEXT (no markup) from configured sections with ``=== name ===`` markers."""
        extracted_text: List[str] = []

        for section_def in selectors:
            elements = soup.select(section_def["selector"])
            if not elements:
                continue

            name = section_def["name"]
            if name == "price":
                # Only the first match to avoid duplicate price strings.
                section_text = elements[0].get_text(separator=" ", strip=True)
            elif name == "product_attributes":
                # Key/value attribute table (retailer-specific formatting hook).
                section_text = self._extract_product_attributes(elements)
            else:
                texts = []
                for el in elements:
                    for form in el.select("form"):  # drop noisy embedded forms
                        form.decompose()
                    texts.append(el.get_text(separator=" ", strip=True))
                section_text = "\n".join(texts)
                section_text = re.sub(r"\s+", " ", section_text)

            section_text = section_text.strip()
            if section_text:
                extracted_text.append(f"=== {name} ===")
                extracted_text.append(section_text)
                extracted_text.append("")

        return "\n".join(extracted_text)

    def _extract_product_attributes(self, elements: List) -> str:
        """Generic key/value extraction from table rows (override per retailer).

        Default: for each ``<tr>``, label = first cell, value = last cell.
        """
        attributes: List[str] = []
        for element in elements:
            for row in element.select("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[-1].get_text(strip=True)
                    if label and value:
                        attributes.append(f"{label}: {value}")
        return "\n".join(attributes)

    def _extract_reviews_structured(self, soup: BeautifulSoup) -> str:
        """Generic review extraction: dump configured REVIEWS_SECTION_SELECTORS as text.

        Override for sites with a rich, structured review DOM (e.g. Amazon).
        """
        sections: List[str] = []
        for section_def in self.REVIEWS_SECTION_SELECTORS:
            elements = soup.select(section_def["selector"])
            if not elements:
                continue
            text = "\n".join(el.get_text(separator=" ", strip=True) for el in elements)
            text = re.sub(r"\s+", " ", text).strip()
            if text and len(text) > 30:
                sections.append(f"=== {section_def['name']} ===")
                sections.append(text[:8000])
                sections.append("")
        return "\n".join(sections)

    # ------------------------------------------------------------------ #
    # Metadata helpers
    # ------------------------------------------------------------------ #
    def _extract_retailer(self, url: str) -> str:
        """Return the retailer label for a URL (override for multi-TLD sites)."""
        return self.RETAILER_NAME

    def _calculate_confidence(self, product_size_kb: float, reviews_size_kb: float) -> float:
        """Confidence (0.0-1.0) from extracted product HTML size."""
        if product_size_kb > 2:
            return 0.9
        elif product_size_kb > 1:
            return 0.7
        elif product_size_kb > 0.5:
            return 0.5
        return 0.2

    def _create_error_result(self, url: str, error_message: str) -> ScrapedProduct:
        """Build a zero-confidence ScrapedProduct for failures."""
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
