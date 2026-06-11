"""Tests for HMScraper (config-only, JSON-LD backbone — LORE.md ADR-004).

Mirrors test_amazon_scraper.py / test_ikea_scraper.py: a synthetic H&M-like DOM
(no network, no Playwright) exercising the client-HTML path, which is the primary
data source (LORE.md INV-1). Asserts domain matching, client metadata, JSON-LD +
visible fabric-composition extraction, and exclude-section removal.

Apparel → fabric composition matters for PFAS/finishes, so the test pins the
visible composition string ("80% cotton, 20% polyester") through extraction.
"""

import pytest

from src.infrastructure.scrapers.hm import HMScraper

# Synthetic H&M-like product HTML: a JSON-LD Product block (name/brand/sku), an h1
# title, a visible materials/composition section, plus header/footer/recommendations
# that must be excluded.
HM_HTML = """
<html><body>
  <header>HEADER JUNK SHOULD BE REMOVED</header>
  <nav>NAV JUNK SHOULD BE REMOVED</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Regular Fit Cotton T-shirt",
    "brand": {"@type": "Brand", "name": "H&M"},
    "description": "A relaxed-fit T-shirt in soft cotton jersey.",
    "sku": "1234567001"
  }
  </script>
  <h1>Regular Fit Cotton T-shirt</h1>
  <div class="ProductDescription">A relaxed-fit T-shirt in soft cotton jersey.</div>
  <div class="product-materials">Composition: Shell: 80% cotton, 20% polyester</div>
  <div id="section-descriptionAccordion">Imported. Machine wash cold.</div>
  <div class="product-care">Machine wash cold, tumble dry low.</div>
  <div class="recommendations-rail">YOU MAY ALSO LIKE THIS REMOVED</div>
  <div class="product-carousel">CAROUSEL JUNK REMOVED</div>
  <footer>FOOTER JUNK SHOULD BE REMOVED</footer>
</body></html>
"""

PRODUCT_URL = "https://www2.hm.com/en_us/productpage.1234567001.html"


@pytest.fixture
def scraper():
    return HMScraper()


@pytest.mark.asyncio
async def test_can_scrape_hm_domains(scraper):
    assert await scraper.can_scrape(PRODUCT_URL) is True
    assert await scraper.can_scrape("https://hm.com/en_us/productpage.1234567001.html") is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False
    assert await scraper.can_scrape("https://www.walmart.com/ip/123") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(url=PRODUCT_URL, product_html=HM_HTML)
    assert result.retailer == "H&M"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert result.url == PRODUCT_URL


def test_process_client_html_extracts_jsonld_and_composition(scraper):
    text = scraper.process_client_html(url=PRODUCT_URL, product_html=HM_HTML).raw_html_product

    # Section markers present
    assert "=== structured_data ===" in text
    assert "=== title ===" in text
    assert "=== materials ===" in text

    # JSON-LD product name comes through (Claude parses the raw JSON)
    assert "Regular Fit Cotton T-shirt" in text

    # Visible fabric composition string extracted (PFAS/finishes signal)
    assert "80% cotton, 20% polyester" in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(url=PRODUCT_URL, product_html=HM_HTML).raw_html_product
    assert "HEADER JUNK" not in text
    assert "FOOTER JUNK" not in text
    assert "NAV JUNK" not in text
    assert "YOU MAY ALSO LIKE" not in text
    assert "CAROUSEL JUNK" not in text
