"""Product scrapers for extracting HTML from e-commerce sites."""

from .base import BaseScraper
from .amazon import AmazonScraper
from .factory import ScraperFactory

__all__ = ["BaseScraper", "AmazonScraper", "ScraperFactory"]
