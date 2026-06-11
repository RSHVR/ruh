"""Tests for UniqloScraper (config-only, JSON-LD backbone — LORE.md ADR-004).

Mirrors test_ikea_scraper.py: a synthetic Uniqlo-like DOM (no network, no
Playwright) exercising the client-HTML path, which is the primary data source
(LORE.md INV-1). Asserts domain matching, client metadata, JSON-LD + visible
fabric-composition extraction, and exclude-section removal.
"""

import pytest

from src.infrastructure.scrapers.uniqlo import UniqloScraper

# Synthetic Uniqlo-like product HTML: a JSON-LD Product block (name/brand/sku),
# an h1 title, a visible composition section (apparel fabric matters), plus
# header/footer/nav/recommendations that must be excluded.
UNIQLO_HTML = """
<html><body>
  <header>HEADER JUNK SHOULD BE REMOVED</header>
  <nav>NAV JUNK SHOULD BE REMOVED</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "AIRism Cotton Crew Neck Short-Sleeve T-Shirt",
    "brand": {"@type": "Brand", "name": "Uniqlo"},
    "description": "A breathable everyday t-shirt.",
    "sku": "E460318-000"
  }
  </script>
  <h1>AIRism Cotton Crew Neck Short-Sleeve T-Shirt</h1>
  <div class="product-composition">Material: 53% Cotton, 47% Polyester</div>
  <div class="product-description">Soft, quick-drying fabric for all-day comfort.</div>
  <div class="care-instructions">Machine wash cold, tumble dry low.</div>
  <div class="recommendations-rail">YOU MAY ALSO LIKE THIS REMOVED</div>
  <div class="product-carousel">CAROUSEL JUNK REMOVED</div>
  <footer>FOOTER JUNK SHOULD BE REMOVED</footer>
</body></html>
"""


@pytest.fixture
def scraper():
    return UniqloScraper()


@pytest.mark.asyncio
async def test_can_scrape_uniqlo_domain(scraper):
    assert await scraper.can_scrape(
        "https://www.uniqlo.com/us/en/products/E460318-000"
    ) is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False
    assert await scraper.can_scrape("https://www.walmart.com/ip/123") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://www.uniqlo.com/us/en/products/E460318-000",
        product_html=UNIQLO_HTML,
    )
    assert result.retailer == "Uniqlo"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert result.url == "https://www.uniqlo.com/us/en/products/E460318-000"


def test_process_client_html_extracts_jsonld_and_composition(scraper):
    text = scraper.process_client_html(
        url="https://www.uniqlo.com/us/en/products/E460318-000",
        product_html=UNIQLO_HTML,
    ).raw_html_product

    # Section markers present
    assert "=== structured_data ===" in text
    assert "=== title ===" in text
    assert "=== materials ===" in text

    # JSON-LD product name comes through (Claude parses the raw JSON)
    assert "AIRism Cotton Crew Neck Short-Sleeve T-Shirt" in text

    # Visible fabric composition extracted (apparel → composition matters)
    assert "53% Cotton, 47% Polyester" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://www.uniqlo.com/us/en/products/E460318-000",
        product_html=UNIQLO_HTML,
    ).raw_html_product
    assert "HEADER JUNK" not in text
    assert "FOOTER JUNK" not in text
    assert "NAV JUNK" not in text
    assert "YOU MAY ALSO LIKE" not in text
    assert "CAROUSEL JUNK" not in text
