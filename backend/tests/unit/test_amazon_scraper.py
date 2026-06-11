"""Characterization tests for AmazonScraper.

These lock the *current* extraction behavior so the SOLID refactor that lifts
generic logic into BaseScraper cannot silently change Amazon's output (LORE.md INV-4).
They use a synthetic Amazon-like DOM (no network, no Playwright) and exercise the
client-HTML path, which is the primary data source (LORE.md INV-1).
"""

import pytest

from src.infrastructure.scrapers.amazon import AmazonScraper

# Synthetic Amazon-like product HTML exercising the real selectors + an excluded nav.
AMAZON_HTML = """
<html><body>
  <div id="navbar">NAV JUNK SHOULD BE REMOVED</div>
  <span id="productTitle">CeraVe Moisturizing Cream 19oz</span>
  <a id="bylineInfo">Brand: CeraVe</a>
  <div class="a-price"><span class="a-offscreen">$18.99</span></div>
  <div class="a-price"><span class="a-offscreen">$99.99 DUPLICATE</span></div>
  <div id="availability">In Stock</div>
  <div id="feature-bullets-btf">Fragrance free. Developed with dermatologists.</div>
  <div id="featurebullets_feature_div">Ceramides 1, 3, 6-II. Hyaluronic acid.</div>
  <div id="productDescription">A rich moisturizing cream.</div>
  <table class="a-section a-spacing-small a-spacing-top-small">
    <tr><td class="a-span3">Ingredients</td><td class="a-span9">Glycerin, Cetyl Alcohol See more</td></tr>
    <tr><td class="a-span3">Skin Type</td><td class="a-span9">Dry</td></tr>
  </table>
</body></html>
"""


@pytest.fixture
def scraper():
    return AmazonScraper()


@pytest.mark.asyncio
async def test_can_scrape_amazon_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is True
    assert await scraper.can_scrape("https://www.amazon.ca/dp/B000123456") is True
    assert await scraper.can_scrape("https://www.amazon.co.uk/dp/X") is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.walmart.com/ip/123") is False
    assert await scraper.can_scrape("https://www.costco.com/p/123") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://www.amazon.ca/dp/B000123456",
        product_html=AMAZON_HTML,
    )
    assert result.retailer == "Amazon.ca"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert result.url == "https://www.amazon.ca/dp/B000123456"
    assert result.has_reviews is False


def test_process_client_html_extracts_sections(scraper):
    text = scraper.process_client_html(
        url="https://www.amazon.com/dp/B000123456",
        product_html=AMAZON_HTML,
    ).raw_html_product

    # Section markers present
    assert "=== title ===" in text
    assert "CeraVe Moisturizing Cream 19oz" in text
    assert "Brand: CeraVe" in text
    # Ingredients/attributes formatted as key: value
    assert "Ingredients: Glycerin, Cetyl Alcohol" in text
    assert "Skin Type: Dry" in text
    # "See more" stripped from attribute values
    assert "See more" not in text
    # Feature bullets extracted
    assert "Fragrance free" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://www.amazon.com/dp/B000123456",
        product_html=AMAZON_HTML,
    ).raw_html_product
    assert "NAV JUNK" not in text


def test_process_client_html_price_deduplicated(scraper):
    text = scraper.process_client_html(
        url="https://www.amazon.com/dp/B000123456",
        product_html=AMAZON_HTML,
    ).raw_html_product
    # price special-case takes only the first matching element
    assert "$18.99" in text
    assert "DUPLICATE" not in text
