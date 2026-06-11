"""Composition test: ScraperFactory routes every retailer URL to its scraper.

Proves the registry (factory.py) and all 12 scraper configs compose correctly and
that domain matching is unambiguous (no URL claimed by the wrong scraper). Guards
LORE.md INV-2 (adding a retailer = registration only) and ADR-002.
"""

import pytest

from src.infrastructure.scrapers.factory import ScraperFactory

# (representative product URL, expected scraper class name)
CASES = [
    ("https://www.amazon.ca/dp/B000123456", "AmazonScraper"),
    ("https://www.walmart.com/ip/Some-Item/123456", "WalmartScraper"),
    ("https://www.costco.com/some-item.product.100334757.html", "CostcoScraper"),
    ("https://www.instacart.com/products/12345-some-item", "InstacartScraper"),
    ("https://www.sephora.com/product/some-serum-P123456", "SephoraScraper"),
    ("https://www2.hm.com/en_us/productpage.1234567001.html", "HMScraper"),
    ("https://www.uniqlo.com/us/en/products/E460318-000", "UniqloScraper"),
    ("https://us.shein.com/some-name-p-12345678.html", "SheinScraper"),
    ("https://www.aritzia.com/us/en/product/effortless-pant/12345.html", "AritziaScraper"),
    ("https://www.garageclothing.com/us/p/low-rise-baggy-jeans/10010171607H.html", "GarageScraper"),
    ("https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-10576191/", "IkeaScraper"),
    ("https://www.temu.com/some-name-g-601099512345678.html", "TemuScraper"),
]


@pytest.fixture
def factory():
    return ScraperFactory()


@pytest.mark.asyncio
@pytest.mark.parametrize("url,expected", CASES)
async def test_factory_routes_to_correct_scraper(factory, url, expected):
    scraper = await factory.get_scraper(url)
    assert scraper is not None, f"no scraper claimed {url}"
    assert scraper.__class__.__name__ == expected


@pytest.mark.asyncio
async def test_factory_returns_none_for_unknown_domain(factory):
    assert await factory.get_scraper("https://www.target.com/p/-/A-123") is None


@pytest.mark.asyncio
async def test_no_url_claimed_by_multiple_scrapers(factory):
    """Each retailer URL must be claimed by exactly one scraper (no ambiguity)."""
    for url, _ in CASES:
        claimers = [
            s.__class__.__name__
            for s in factory.scrapers
            if await s.can_scrape(url)
        ]
        assert len(claimers) == 1, f"{url} claimed by {claimers}"
