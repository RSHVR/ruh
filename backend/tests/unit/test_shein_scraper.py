"""Tests for SheinScraper (config-only scraper; LORE.md ADR-001/ADR-004).

SHEIN heavily bot-walls servers, so the client-HTML path (INV-1) is the only
real integration surface — these tests exercise ``process_client_html`` against
a synthetic SHEIN-like DOM (JSON-LD Product + visible fabric composition).
No network, no Playwright.
"""

import pytest

from src.infrastructure.scrapers.shein import SheinScraper

# Synthetic SHEIN-like product HTML: JSON-LD Product, visible material, and an
# excluded "you may also like" recommendation rail that must be stripped.
SHEIN_HTML = """
<html><body>
  <header>SITE HEADER JUNK</header>
  <nav>NAV JUNK SHOULD BE REMOVED</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Women's Ruffle Trim Floral Dress",
    "brand": {"@type": "Brand", "name": "SHEIN"},
    "sku": "12345678",
    "material": "95% Polyester, 5% Spandex",
    "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.3", "reviewCount": "210"}
  }
  </script>
  <h1>Women's Ruffle Trim Floral Dress</h1>
  <div class="product-intro__material">Composition: 95% Polyester, 5% Spandex</div>
  <div class="product-intro__description">Lightweight woven dress with ruffle trim.</div>
  <div class="product-description">Machine wash cold. Imported.</div>
  <div class="you-may-also-like">RECOMMENDED JUNK SHOULD BE REMOVED</div>
  <div class="recommend-list">MORE RECOMMENDED JUNK</div>
  <footer>SITE FOOTER JUNK</footer>
</body></html>
"""


@pytest.fixture
def scraper():
    return SheinScraper()


@pytest.mark.asyncio
async def test_can_scrape_shein_domains(scraper):
    assert await scraper.can_scrape("https://www.shein.com/some-name-p-12345678.html") is True
    assert await scraper.can_scrape("https://us.shein.com/some-name-p-12345678.html") is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://us.shein.com/some-name-p-12345678.html",
        product_html=SHEIN_HTML,
    )
    assert result.retailer == "SHEIN"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert result.url == "https://us.shein.com/some-name-p-12345678.html"


def test_process_client_html_extracts_json_ld_and_material(scraper):
    text = scraper.process_client_html(
        url="https://us.shein.com/some-name-p-12345678.html",
        product_html=SHEIN_HTML,
    ).raw_html_product

    # JSON-LD section present with product name (ADR-004 backbone).
    assert "=== structured_data ===" in text
    assert "Women's Ruffle Trim Floral Dress" in text
    # Title (h1) extracted.
    assert "=== title ===" in text
    # Fabric composition (safety-critical for fast-fashion) present.
    assert "=== materials ===" in text
    assert "95% Polyester, 5% Spandex" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://us.shein.com/some-name-p-12345678.html",
        product_html=SHEIN_HTML,
    ).raw_html_product

    assert "NAV JUNK" not in text
    assert "RECOMMENDED JUNK" not in text
    assert "HEADER JUNK" not in text
    assert "FOOTER JUNK" not in text
