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


# --- costco.ca + new React-app URL scheme + new DOM ids (2026-08-01 recon) ---

@pytest.mark.asyncio
async def test_can_scrape_costco_ca_both_url_schemes(scraper):
    # Legacy scheme and the new /p/-/<slug>/<id> scheme, on both TLDs.
    assert await scraper.can_scrape(
        "https://www.costco.ca/oxiclean.product.100334757.html"
    ) is True
    assert await scraper.can_scrape(
        "https://www.costco.ca/p/-/oxiclean-versatile-stain-remover/100334757?langId=-24"
    ) is True
    assert await scraper.can_scrape(
        "https://www.costco.com/p/-/some-item/100334757"
    ) is True


# Synthetic Costco React-app DOM using the verified live ids, plus a Bazaarvoice
# reviews script (schema.org Review objects) and its aggregate summary.
COSTCO_NEW_HTML = """
<html><body>
  <h1>OxiClean Versatile Stain Remover 5.25 kg</h1>
  <div id="productDescriptionDesktop">Removes tough stains from laundry and more.</div>
  <div id="product-details-summary">Powder stain remover, chlorine-free.</div>
  <div id="ProductSpecifications">
    <table>
      <tr><th>Brand</th><td>OxiClean</td></tr>
      <tr><th>Container Size</th><td>5.25 kg</td></tr>
    </table>
  </div>
  <script id="bv-jsonld-bvloader-summary" type="application/ld+json">
  {"@type":"AggregateRating","ratingValue":"4.6","reviewCount":"8"}
  </script>
  <script id="bv-jsonld-reviews-data" type="application/ld+json">
  [
    {"@type":"Review","headline":"Works great","reviewBody":"Got rid of set-in stains, no strong chemical smell.",
     "reviewRating":{"ratingValue":"5","bestRating":"5"},"author":{"@type":"Person","name":"CleanFreak"},"dateCreated":"2026-06-01"},
    {"@type":"Review","headline":"Skin reaction","reviewBody":"Left my hands itchy and irritated after use.",
     "reviewRating":{"ratingValue":2,"bestRating":5},"author":"Anon","datePublished":"2026-06-10"}
  ]
  </script>
</body></html>
"""


def test_new_dom_ids_extracted(scraper):
    text = scraper.process_client_html(
        url="https://www.costco.ca/p/-/oxiclean/100334757",
        product_html=COSTCO_NEW_HTML,
    ).raw_html_product
    assert "Removes tough stains" in text          # #productDescriptionDesktop
    assert "chlorine-free" in text                  # #product-details-summary
    assert "OxiClean" in text                       # #ProductSpecifications table
    assert "5.25 kg" in text


def test_bazaarvoice_reviews_parsed_via_review_parser(scraper):
    reviews = scraper.parse_reviews(COSTCO_NEW_HTML)
    assert len(reviews) == 2
    assert reviews[0]["review_rating"] == 5
    assert reviews[0]["reviewer_name"] == "CleanFreak"
    assert "no strong chemical smell" in reviews[0]["review_text"]
    assert reviews[1]["review_rating"] == 2
    assert "itchy and irritated" in reviews[1]["review_text"]


def test_bazaarvoice_reviews_captured_in_review_text(scraper):
    result = scraper.process_client_html(
        url="https://www.costco.ca/p/-/oxiclean/100334757",
        product_html=COSTCO_NEW_HTML,
    )
    assert result.has_reviews is True
    assert "chemical smell" in result.raw_html_reviews
