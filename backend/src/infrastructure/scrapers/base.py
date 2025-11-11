"""Abstract base class for product scrapers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.models import ScrapedProduct


class BaseScraper(ABC):
    """Abstract base class for product scrapers.

    Each scraper implementation should handle a specific e-commerce site
    (e.g., Amazon, Walmart) and extract relevant HTML sections.
    """

    @abstractmethod
    async def can_scrape(self, url: str) -> bool:
        """Check if this scraper can handle the given URL.

        Args:
            url: Product URL to check

        Returns:
            True if this scraper supports the URL's domain
        """
        pass

    @abstractmethod
    async def scrape(self, url: str, include_reviews: bool = False) -> "ScrapedProduct":
        """Scrape product data from URL.

        Args:
            url: Product URL to scrape
            include_reviews: If True, also scrape reviews and Q&A sections

        Returns:
            ScrapedProduct with raw HTML sections
        """
        pass
