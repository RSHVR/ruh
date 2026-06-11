"""Tests for SephoraScraper (config-only, JSON-LD backbone — LORE.md ADR-004).

Sephora is a beauty retailer where the **ingredients** list is the most important
safety data (allergens like Limonene, PFAS). These tests exercise the primary
client-HTML path (INV-1) against a synthetic Sephora-like DOM that includes both a
JSON-LD Product block and a visible ingredients block, and assert that the excluded
recommendation/carousel chrome is stripped.
"""

import pytest

from src.infrastructure.scrapers.sephora import SephoraScraper

# Synthetic Sephora-like product HTML: JSON-LD Product + visible ingredients block,
# plus an excluded "you-may-also-like" recommendations carousel.
SEPHORA_HTML = """
<html><body>
  <header>SITE HEADER NAV JUNK</header>
  <nav>BREADCRUMB NAV JUNK</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Glow Revival Vitamin C Serum",
    "brand": {"@type": "Brand", "name": "Luminous Labs"},
    "sku": "P123456"
  }
  </script>
  <h1>Glow Revival Vitamin C Serum</h1>
  <div data-comp="IngredientsTab" class="Ingredients-section">
    Water, Glycerin, Ascorbic Acid, Limonene, Linalool, Fragrance.
  </div>
  <div data-comp="ProductInformation">A brightening daily vitamin C serum.</div>
  <div data-comp="HowToUse">Apply 2-3 drops to clean skin each morning.</div>
  <section class="you-may-also-like">RECOMMENDED JUNK SHOULD BE REMOVED</section>
  <div data-comp="ProductCarousel">CAROUSEL JUNK SHOULD BE REMOVED</div>
</body></html>
"""


@pytest.fixture
def scraper():
    return SephoraScraper()


@pytest.mark.asyncio
async def test_can_scrape_sephora_domain(scraper):
    assert await scraper.can_scrape("https://www.sephora.com/product/some-serum-P123456") is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://www.sephora.com/product/some-serum-P123456",
        product_html=SEPHORA_HTML,
    )
    assert result.retailer == "Sephora"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert result.url == "https://www.sephora.com/product/some-serum-P123456"


def test_process_client_html_extracts_jsonld_and_ingredients(scraper):
    text = scraper.process_client_html(
        url="https://www.sephora.com/product/some-serum-P123456",
        product_html=SEPHORA_HTML,
    ).raw_html_product

    # JSON-LD backbone present (name from the Product schema)
    assert "=== structured_data ===" in text
    assert "Glow Revival Vitamin C Serum" in text

    # Title section present
    assert "=== title ===" in text

    # Safety-critical ingredients block extracted, including an allergen
    assert "=== ingredients ===" in text
    assert "Limonene" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://www.sephora.com/product/some-serum-P123456",
        product_html=SEPHORA_HTML,
    ).raw_html_product
    assert "RECOMMENDED JUNK" not in text
    assert "CAROUSEL JUNK" not in text
    assert "NAV JUNK" not in text
