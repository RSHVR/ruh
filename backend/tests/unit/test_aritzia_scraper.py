"""Tests for AritziaScraper (config-only, JSON-LD backbone — LORE.md ADR-004).

Mirrors test_amazon_scraper.py / test_ikea_scraper.py: a synthetic Aritzia-like
DOM (no network, no Playwright) exercising the client-HTML path, which is the
primary data source (LORE.md INV-1). Asserts domain matching, client metadata,
JSON-LD + visible fabric-composition extraction, and exclude-section removal.
"""

import pytest

from src.infrastructure.scrapers.aritzia import AritziaScraper

# Synthetic Aritzia-like product HTML: a JSON-LD Product block (name/brand/sku),
# an h1 title, a visible fabric composition / materials section, plus
# header/footer/recommendations that must be excluded.
ARITZIA_HTML = """
<html><body>
  <header>HEADER JUNK SHOULD BE REMOVED</header>
  <nav>NAV JUNK SHOULD BE REMOVED</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Effortless Pant",
    "brand": {"@type": "Brand", "name": "Wilfred"},
    "description": "A high-waisted tailored trouser.",
    "sku": "12345"
  }
  </script>
  <h1>Effortless Pant</h1>
  <div class="product-materials">Fabric: 64% Polyester, 33% Viscose, 3% Elastane</div>
  <div class="product-description">A relaxed high-waisted trouser with a fluid drape.</div>
  <div class="product-care">Dry clean only.</div>
  <div class="you-may-also-like">YOU MAY ALSO LIKE THIS REMOVED</div>
  <footer>FOOTER JUNK SHOULD BE REMOVED</footer>
</body></html>
"""


@pytest.fixture
def scraper():
    return AritziaScraper()


@pytest.mark.asyncio
async def test_can_scrape_aritzia_domain(scraper):
    assert await scraper.can_scrape(
        "https://www.aritzia.com/us/en/product/effortless-pant/12345.html"
    ) is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False
    assert await scraper.can_scrape("https://www.walmart.com/ip/123") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://www.aritzia.com/us/en/product/effortless-pant/12345.html",
        product_html=ARITZIA_HTML,
    )
    assert result.retailer == "Aritzia"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert (
        result.url
        == "https://www.aritzia.com/us/en/product/effortless-pant/12345.html"
    )


def test_process_client_html_extracts_jsonld_and_composition(scraper):
    text = scraper.process_client_html(
        url="https://www.aritzia.com/us/en/product/effortless-pant/12345.html",
        product_html=ARITZIA_HTML,
    ).raw_html_product

    # Section markers present
    assert "=== structured_data ===" in text
    assert "=== title ===" in text
    assert "=== materials ===" in text

    # JSON-LD product name comes through (Claude parses the raw JSON)
    assert "Effortless Pant" in text

    # Visible fabric composition extracted (apparel → composition matters)
    assert "64% Polyester" in text
    assert "Elastane" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://www.aritzia.com/us/en/product/effortless-pant/12345.html",
        product_html=ARITZIA_HTML,
    ).raw_html_product
    assert "HEADER JUNK" not in text
    assert "FOOTER JUNK" not in text
    assert "NAV JUNK" not in text
    assert "YOU MAY ALSO LIKE" not in text
