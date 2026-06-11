"""Factory for selecting appropriate scraper based on URL."""

from typing import Optional
import logging

from .base import BaseScraper
from .amazon import AmazonScraper
from .walmart import WalmartScraper
from .costco import CostcoScraper
from .instacart import InstacartScraper
from .sephora import SephoraScraper
from .hm import HMScraper
from .uniqlo import UniqloScraper
from .shein import SheinScraper
from .aritzia import AritziaScraper
from .garage import GarageScraper
from .ikea import IkeaScraper
from .temu import TemuScraper

logger = logging.getLogger(__name__)


class ScraperFactory:
    """Factory to select appropriate scraper for URL.

    Returns None if no scraper can handle the URL (fallback to Claude web_fetch).
    Registering a retailer here is the only control-flow change adding a site
    requires (LORE.md INV-2 / ADR-002).
    """

    def __init__(self):
        """Initialize factory with available scrapers."""
        self.scrapers = [
            AmazonScraper(),
            WalmartScraper(),
            CostcoScraper(),
            InstacartScraper(),
            SephoraScraper(),
            HMScraper(),
            UniqloScraper(),
            SheinScraper(),
            AritziaScraper(),
            GarageScraper(),
            IkeaScraper(),
            TemuScraper(),
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
