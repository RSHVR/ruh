"""Service for scraping product data with intelligent fallback."""

from typing import Optional
import logging

from .scrapers.factory import ScraperFactory
from ..domain.models import ScrapedProduct

logger = logging.getLogger(__name__)


class ProductScraperService:
    """Service for scraping product data with intelligent fallback.

    Attempts to scrape product data using site-specific scrapers.
    Returns None if scraping fails or no scraper is available,
    indicating that the caller should fallback to Claude's web_fetch.
    """

    def __init__(self):
        """Initialize scraper service."""
        self.factory = ScraperFactory()

    async def try_scrape(
        self,
        url: str,
        include_reviews: bool = False
    ) -> Optional[ScrapedProduct]:
        """Attempt to scrape product data.

        Args:
            url: Product URL
            include_reviews: If True, also scrape reviews/Q&A sections

        Returns:
            ScrapedProduct if successful (confidence >= 0.3)
            None if should fallback to Claude web_fetch
        """
        logger.info(f"🕷️  SCRAPER START: Attempting to scrape {url}")

        # Get appropriate scraper
        scraper = await self.factory.get_scraper(url)

        if scraper is None:
            logger.info(f"🔄 SCRAPER SKIP: No scraper available for {url}, will use Claude web_fetch fallback")
            return None

        # Attempt scraping
        logger.info(f"🕷️  SCRAPER RUNNING: Fetching HTML from {url}")
        result = await scraper.scrape(url, include_reviews=include_reviews)

        logger.info(f"🕷️  SCRAPER COMPLETE: HTML size = {len(result.raw_html_product)} chars, confidence = {result.confidence:.2f}")

        # Check confidence threshold
        if result.confidence < 0.3:
            logger.warning(
                f"⚠️  SCRAPER FAILED: Scraping confidence too low ({result.confidence:.2f}), "
                f"will fallback to Claude web_fetch"
            )
            if result.error_message:
                logger.warning(f"   Error: {result.error_message}")
            return None

        logger.info(f"✅ SCRAPER SUCCESS: Scraped {len(result.raw_html_product)} chars with confidence {result.confidence:.2f}")
        return result
