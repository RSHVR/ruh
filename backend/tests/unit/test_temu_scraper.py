"""Tests for TemuScraper (config-only, JSON-LD backbone — LORE.md ADR-004).

Mirrors test_amazon_scraper.py / test_ikea_scraper.py: a synthetic Temu-like DOM
(no network, no Playwright) exercising the client-HTML path, which is the primary
data source (LORE.md INV-1; Temu heavily bot-walls servers so the server-side
Playwright path is not viable). Asserts domain matching, client metadata, JSON-LD +
visible detail/material extraction, and exclude-section removal.
"""

import pytest

from src.infrastructure.scrapers.temu import TemuScraper

# Synthetic Temu-like product HTML: a JSON-LD Product block (name/brand/material/
# sku), an h1 title, visible goods-description / material sections, plus header/
# footer/recommendation blocks that must be excluded.
TEMU_HTML = """
<html><body>
  <header>HEADER JUNK SHOULD BE REMOVED</header>
  <nav>NAV JUNK SHOULD BE REMOVED</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Stainless Steel Insulated Water Bottle 32oz",
    "brand": {"@type": "Brand", "name": "Temu"},
    "description": "A leak-proof double-wall vacuum insulated bottle.",
    "material": "304 Stainless Steel",
    "sku": "601099512345678"
  }
  </script>
  <h1>Stainless Steel Insulated Water Bottle 32oz</h1>
  <div class="goods-desc-content">Keeps drinks cold for 24 hours and hot for 12 hours.</div>
  <div class="product-detail-section">Capacity 32oz; BPA-free lid.</div>
  <div class="material-info">Material: 304 Stainless Steel, Food-grade silicone seal</div>
  <div class="goods-spec-table">Specifications: Height 27cm, Diameter 8cm</div>
  <div class="recommend-rail">YOU MAY ALSO LIKE THIS REMOVED</div>
  <div class="goods-carousel">CAROUSEL JUNK REMOVED</div>
  <footer>FOOTER JUNK SHOULD BE REMOVED</footer>
</body></html>
"""


@pytest.fixture
def scraper():
    return TemuScraper()


@pytest.mark.asyncio
async def test_can_scrape_temu_domain(scraper):
    assert await scraper.can_scrape(
        "https://www.temu.com/stainless-steel-water-bottle-g-601099512345678.html"
    ) is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False
    assert await scraper.can_scrape("https://www.walmart.com/ip/123") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://www.temu.com/stainless-steel-water-bottle-g-601099512345678.html",
        product_html=TEMU_HTML,
    )
    assert result.retailer == "Temu"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert (
        result.url
        == "https://www.temu.com/stainless-steel-water-bottle-g-601099512345678.html"
    )


def test_process_client_html_extracts_jsonld_and_details(scraper):
    text = scraper.process_client_html(
        url="https://www.temu.com/stainless-steel-water-bottle-g-601099512345678.html",
        product_html=TEMU_HTML,
    ).raw_html_product

    # Section markers present
    assert "=== structured_data ===" in text
    assert "=== title ===" in text
    assert "=== product_details ===" in text
    assert "=== materials ===" in text

    # JSON-LD product name + material come through (Claude parses the raw JSON)
    assert "Stainless Steel Insulated Water Bottle 32oz" in text
    assert "304 Stainless Steel" in text

    # Visible detail / material section text extracted
    assert "Keeps drinks cold for 24 hours" in text
    assert "Food-grade silicone seal" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://www.temu.com/stainless-steel-water-bottle-g-601099512345678.html",
        product_html=TEMU_HTML,
    ).raw_html_product
    assert "HEADER JUNK" not in text
    assert "FOOTER JUNK" not in text
    assert "NAV JUNK" not in text
    assert "YOU MAY ALSO LIKE" not in text
    assert "CAROUSEL JUNK" not in text
