"""Tests for CostcoScraper (config-only, JSON-LD backbone — LORE.md ADR-004).

Costco sells both groceries (ingredients/nutrition matter for allergens/PFAS) and
general goods (specifications matter), so these tests exercise the primary
client-HTML path (INV-1) against a synthetic Costco-like DOM that includes a JSON-LD
Product block, a visible specifications block, AND a visible ingredients block, and
assert that the excluded recommendation/carousel chrome is stripped.
"""

import pytest

from src.infrastructure.scrapers.costco import CostcoScraper

# Synthetic Costco-like product HTML: JSON-LD Product + visible specifications +
# visible ingredients, plus excluded header/nav/recommendation/carousel chrome.
COSTCO_HTML = """
<html><body>
  <header>SITE HEADER NAV JUNK</header>
  <nav>BREADCRUMB NAV JUNK</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Kirkland Signature Organic Peanut Butter 28oz",
    "brand": {"@type": "Brand", "name": "Kirkland Signature"},
    "sku": "100334757"
  }
  </script>
  <h1>Kirkland Signature Organic Peanut Butter 28oz</h1>
  <div id="product-details-tabs" class="product-info-description">
    Creamy organic peanut butter made from dry roasted peanuts.
  </div>
  <div id="product-tab2" class="specifications-table">
    Net Weight: 28 oz. Country of Origin: USA. Storage: Refrigerate after opening.
  </div>
  <div class="product-ingredients-list">
    Ingredients: Organic Peanuts, Sea Salt. Contains: Peanuts. May contain Tree Nuts.
  </div>
  <section class="you-may-also-like">RECOMMENDED JUNK SHOULD BE REMOVED</section>
  <div class="product-carousel">CAROUSEL JUNK SHOULD BE REMOVED</div>
</body></html>
"""


@pytest.fixture
def scraper():
    return CostcoScraper()


@pytest.mark.asyncio
async def test_can_scrape_costco_domain(scraper):
    assert (
        await scraper.can_scrape(
            "https://www.costco.com/some-item.product.100334757.html"
        )
        is True
    )


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://www.costco.com/some-item.product.100334757.html",
        product_html=COSTCO_HTML,
    )
    assert result.retailer == "Costco"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert result.url == "https://www.costco.com/some-item.product.100334757.html"


def test_process_client_html_extracts_jsonld_and_visible_sections(scraper):
    text = scraper.process_client_html(
        url="https://www.costco.com/some-item.product.100334757.html",
        product_html=COSTCO_HTML,
    ).raw_html_product

    # JSON-LD backbone present (name from the Product schema)
    assert "=== structured_data ===" in text
    assert "Kirkland Signature Organic Peanut Butter 28oz" in text

    # Title section present
    assert "=== title ===" in text

    # Goods path: a visible specification string extracted
    assert "=== specifications ===" in text
    assert "Net Weight: 28 oz" in text

    # Grocery path: a visible ingredient string extracted (allergen present)
    assert "=== ingredients ===" in text
    assert "Organic Peanuts" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://www.costco.com/some-item.product.100334757.html",
        product_html=COSTCO_HTML,
    ).raw_html_product
    assert "RECOMMENDED JUNK" not in text
    assert "CAROUSEL JUNK" not in text
    assert "NAV JUNK" not in text
