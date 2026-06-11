"""Integration tests for factory-driven client-HTML routing (LORE.md ADR-002).

Guards against the MEMORY.md regression where every site's HTML was parsed with
Amazon selectors. The service must pick the scraper by URL and degrade gracefully
(return None -> Claude fallback) when no scraper claims the URL.
"""

import pytest

from src.infrastructure.product_scraper import ProductScraperService

PRODUCT_HTML = '<html><body><span id="productTitle">A Product</span></body></html>'


@pytest.fixture
def service():
    return ProductScraperService()


@pytest.mark.asyncio
async def test_amazon_url_routes_to_amazon_scraper(service):
    result = await service.process_client_html(
        url="https://www.amazon.ca/dp/B000123456",
        product_html=PRODUCT_HTML,
    )
    assert result is not None
    assert result.retailer.startswith("Amazon")
    assert result.scrape_method == "client"


@pytest.mark.asyncio
async def test_unknown_url_returns_none_for_graceful_fallback(service):
    result = await service.process_client_html(
        url="https://www.some-unconfigured-shop.example/p/123",
        product_html=PRODUCT_HTML,
    )
    assert result is None  # -> caller falls back to Claude web_fetch (INV-3)
