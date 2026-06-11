"""Tests for GarageScraper (config-driven, mirrors test_amazon_scraper.py).

Garage is config-only over BaseScraper (LORE.md ADR-001). These tests exercise the
client-HTML primary path (INV-1): JSON-LD provides name/brand/description (ADR-004)
and a visible accordion provides fabric composition. A synthetic Garage-like DOM is
used (no network/Playwright) and includes a recommendation carousel that must be
excluded.
"""

import pytest

from src.infrastructure.scrapers.garage import GarageScraper

# Synthetic Garage-like product HTML: JSON-LD Product + visible details/fabric +
# an excluded recommendations carousel.
GARAGE_HTML = """
<html><body>
  <header>SITE HEADER NAV JUNK</header>
  <nav>BREADCRUMB NAV JUNK</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Low Rise Baggy Jeans",
    "brand": {"@type": "Brand", "name": "Garage"},
    "description": "Relaxed low rise baggy fit jeans.",
    "sku": "10010171607H",
    "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.3", "reviewCount": "112"}
  }
  </script>
  <h1>Low Rise Baggy Jeans</h1>
  <div class="product-detail">
    <div class="product-details-accordion">
      <div class="fabric-composition">Fabric: 99% Cotton, 1% Elastane</div>
    </div>
  </div>
  <div class="product-description">Sits low on the waist with a baggy leg.</div>
  <section class="recommendations-carousel">
    <h2>You May Also Like</h2>
    <p>RECOMMENDED PRODUCT JUNK SHOULD BE REMOVED</p>
  </section>
  <footer>SITE FOOTER JUNK</footer>
</body></html>
"""

PRODUCT_URL = "https://www.garageclothing.com/us/p/low-rise-baggy-jeans/10010171607H.html"


@pytest.fixture
def scraper():
    return GarageScraper()


@pytest.mark.asyncio
async def test_can_scrape_garage_domain(scraper):
    assert await scraper.can_scrape(PRODUCT_URL) is True
    assert await scraper.can_scrape("https://garageclothing.com/p/x.html") is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False
    assert await scraper.can_scrape("https://www.walmart.com/ip/123") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(url=PRODUCT_URL, product_html=GARAGE_HTML)
    assert result.retailer == "Garage"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert result.url == PRODUCT_URL
    assert result.has_reviews is False


def test_process_client_html_extracts_json_ld_and_fabric(scraper):
    text = scraper.process_client_html(url=PRODUCT_URL, product_html=GARAGE_HTML).raw_html_product

    # JSON-LD backbone (ADR-004): name fed to Claude via the structured_data section.
    assert "=== structured_data ===" in text
    assert "Low Rise Baggy Jeans" in text
    assert '"sku": "10010171607H"' in text or '"sku":"10010171607H"' in text
    # Visible h1 title.
    assert "=== title ===" in text
    # Visible fabric composition from the product-details accordion.
    assert "99% Cotton, 1% Elastane" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(url=PRODUCT_URL, product_html=GARAGE_HTML).raw_html_product
    assert "RECOMMENDED PRODUCT JUNK" not in text
    assert "SITE HEADER NAV JUNK" not in text
    assert "SITE FOOTER JUNK" not in text
    assert "BREADCRUMB NAV JUNK" not in text
