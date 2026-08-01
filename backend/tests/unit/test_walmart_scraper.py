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


# --- walmart.ca + __NEXT_DATA__ extraction (2026-08-01 recon) ---

@pytest.mark.asyncio
async def test_can_scrape_walmart_ca_alphanumeric_id(scraper):
    # walmart.ca ids are alphanumeric, not numeric like walmart.com.
    assert await scraper.can_scrape(
        "https://www.walmart.ca/en/ip/britax-car-seat/38WYZF7I4FZ6"
    ) is True
    assert await scraper.can_scrape(
        "https://www.walmart.ca/fr/ip/siege-auto/38WYZF7I4FZ6"
    ) is True


# Synthetic Walmart Next.js page: the payload lives in __NEXT_DATA__, NOT the DOM.
WALMART_NEXT_HTML = """
<html><body>
  <h1>ignored dom title</h1>
  <script id="__NEXT_DATA__" type="application/json">
  {"props":{"pageProps":{"initialData":{"data":{
    "product":{"name":"Britax Boulevard Car Seat","brand":"Britax","sellerName":"Walmart",
               "shortDescription":"<p>ClickTight installation.</p>"},
    "idml":{"specifications":[{"name":"Brand","value":"Britax"},{"name":"Material","value":"Polyester"}],
            "ingredients":null},
    "reviews":{"customerReviews":[
      {"reviewId":"1","rating":5,"reviewText":"Feels very safe and easy to install.","reviewTitle":"Great seat",
       "reviewSubmissionTime":"2026-07-01","userNickname":"ParentA","positiveFeedback":4},
      {"reviewId":"2","rating":2,"reviewText":"The fabric gave my baby a rash.","reviewTitle":"Watch out",
       "reviewSubmissionTime":"2026-07-05","userNickname":"ParentB","positiveFeedback":1}
    ]}
  }}}}}
  </script>
</body></html>
"""


def test_next_data_product_block_extracted(scraper):
    text = scraper.process_client_html(
        url="https://www.walmart.ca/en/ip/britax/38WYZF7I4FZ6",
        product_html=WALMART_NEXT_HTML,
    ).raw_html_product
    # Compact block built from __NEXT_DATA__, not the 236KB blob or the DOM h1.
    assert "Britax Boulevard Car Seat" in text
    assert "Brand: Britax" in text
    assert "Material: Polyester" in text
    # HTML in shortDescription is stripped to text.
    assert "ClickTight installation." in text
    assert "<p>" not in text
    # The raw giant blob / dom h1 must NOT be shipped verbatim.
    assert "ignored dom title" not in text
    assert "__NEXT_DATA__" not in text


def test_next_data_reviews_extracted_as_text(scraper):
    result = scraper.process_client_html(
        url="https://www.walmart.ca/en/ip/britax/38WYZF7I4FZ6",
        product_html=WALMART_NEXT_HTML,
    )
    assert result.has_reviews is True
    assert "easy to install" in result.raw_html_reviews
    assert "gave my baby a rash" in result.raw_html_reviews


def test_next_data_reviews_parsed_via_review_parser(scraper):
    reviews = scraper.parse_reviews(WALMART_NEXT_HTML)
    assert len(reviews) == 2
    assert reviews[0]["review_rating"] == 5
    assert reviews[0]["reviewer_name"] == "ParentA"
    assert reviews[0]["review_date"] == "2026-07-01"
    assert reviews[0]["helpful_votes"] == 4
    assert reviews[1]["review_rating"] == 2
    assert "rash" in reviews[1]["review_text"]


def test_dom_fallback_when_no_next_data(scraper):
    # The original DOM-only fixture (no __NEXT_DATA__) must still extract via DOM.
    text = scraper.process_client_html(
        url="https://www.walmart.com/ip/Great-Value-Honey/1971741696",
        product_html=WALMART_HTML,
    ).raw_html_product
    assert "Great Value Organic Honey 12oz" in text
    assert "Organic Honey" in text
