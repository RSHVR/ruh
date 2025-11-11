"""Factory for selecting appropriate scraper based on URL."""

from typing import Optional
import logging

from .base import BaseScraper
from .amazon import AmazonScraper

logger = logging.getLogger(__name__)


class ScraperFactory:
    """Factory to select appropriate scraper for URL.

    Returns None if no scraper can handle the URL (fallback to Claude web_fetch).
    """

    def __init__(self):
        """Initialize factory with available scrapers."""
        self.scrapers = [
            AmazonScraper(),
            # Future: WalmartScraper(), TargetScraper(), etc.
        ]

    async def get_scraper(self, url: str) -> Optional[BaseScraper]:
        """Get appropriate scraper for URL, or None if no match.

        Args:
            url: Product URL

        Returns:
            BaseScraper instance if a scraper supports the URL, None otherwise
        """
        for scraper in self.scrapers:
            if await scraper.can_scrape(url):
                logger.debug(f"Selected {scraper.__class__.__name__} for {url}")
                return scraper

        logger.info(f"No scraper available for {url}, will use Claude web_fetch fallback")
        return None
