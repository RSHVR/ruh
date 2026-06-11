"""Tests for WalmartScraper (config-driven, client-HTML primary path).

Walmart blocks server-side automation (PerimeterX/HUMAN), so the client-HTML
path is the ONLY real integration surface (LORE.md INV-1 + recon notes). These
tests use a synthetic Walmart-like DOM (no network, no Playwright) and exercise
``process_client_html``, mirroring test_amazon_scraper.py.
"""

import pytest

from src.infrastructure.scrapers.walmart import WalmartScraper

# Synthetic Walmart-like product HTML: JSON-LD Product schema + visible
# ingredients/specs + an excluded recommendation carousel.
WALMART_HTML = """
<html><body>
  <header>HEADER JUNK SHOULD BE REMOVED</header>
  <nav>NAV JUNK SHOULD BE REMOVED</nav>
  <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product",
     "name":"Great Value Organic Honey 12oz",
     "brand":{"@type":"Brand","name":"Great Value"},
     "description":"Pure organic honey."}
  </script>
  <h1>Great Value Organic Honey 12oz</h1>
  <div data-testid="product-description-content">A pure organic honey sourced responsibly.</div>
  <div id="product-overview">12 oz squeeze bottle.</div>
  <div data-testid="specifications-table">Net Weight: 12 oz</div>
  <div class="ingredients-list">Ingredients: Organic Honey</div>
  <div data-testid="carousel-recommendations">CAROUSEL JUNK SHOULD BE REMOVED</div>
  <div class="you-may-also-like">RECOMMEND JUNK SHOULD BE REMOVED</div>
  <footer>FOOTER JUNK SHOULD BE REMOVED</footer>
</body></html>
"""


@pytest.fixture
def scraper():
    return WalmartScraper()


@pytest.mark.asyncio
async def test_can_scrape_walmart_domain(scraper):
    assert await scraper.can_scrape("https://www.walmart.com/ip/Product/1971741696") is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://www.walmart.com/ip/Great-Value-Honey/1971741696",
        product_html=WALMART_HTML,
    )
    assert result.retailer == "Walmart"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert result.url == "https://www.walmart.com/ip/Great-Value-Honey/1971741696"


def test_process_client_html_extracts_sections(scraper):
    text = scraper.process_client_html(
        url="https://www.walmart.com/ip/Great-Value-Honey/1971741696",
        product_html=WALMART_HTML,
    ).raw_html_product

    # JSON-LD structured data feeds the product name to Claude
    assert "=== structured_data ===" in text
    assert "Great Value Organic Honey 12oz" in text
    # Title from h1
    assert "=== title ===" in text
    # Visible ingredients/spec strings
    assert "Organic Honey" in text
    assert "Net Weight: 12 oz" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://www.walmart.com/ip/Great-Value-Honey/1971741696",
        product_html=WALMART_HTML,
    ).raw_html_product
    assert "HEADER JUNK" not in text
    assert "NAV JUNK" not in text
    assert "FOOTER JUNK" not in text
    assert "CAROUSEL JUNK" not in text
    assert "RECOMMEND JUNK" not in text
