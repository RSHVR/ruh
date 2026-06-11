"""Tests for InstacartScraper (JSON-LD backbone + content-pattern override — ADR-004/005).

Instacart is login-gated and archetype-D: nutrition facts (and sometimes ingredients) are
lazily rendered into hashed-class DOM with no state blob. ``InstacartScraper`` extracts the
nutrition panel by a content keyword-cluster and the ingredient list by an explicit
``Ingredients:`` label (never by guessing food words — that catches recommended products).

The synthetic DOM below mirrors that: a real-shaped Nutrition Facts panel (hashed classes),
a labeled ingredient list with a "Soy" allergen, and a recommended-product carousel whose
food words must NOT be mistaken for the ingredient list.
"""

import pytest

from src.infrastructure.scrapers.instacart import InstacartScraper

INSTACART_HTML = """
<html><body>
  <header>SITE HEADER JUNK SHOULD BE REMOVED</header>
  <nav>NAV JUNK SHOULD BE REMOVED</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Organic Soy Sauce 10oz",
    "brand": {"@type": "Brand", "name": "Kikkoman"},
    "description": "Naturally brewed organic soy sauce."
  }
  </script>
  <h1>Organic Soy Sauce 10oz</h1>
  <div class="e-abc123">
    Nutrition Facts Serving size 1 tbsp Calories 10
    Total Fat 0g 0% daily value Sodium 920mg 40% daily value
    Total Carbohydrate 1g 0% daily value Protein 2g
  </div>
  <div class="e-def456">Ingredients: Water, Soybeans (Soy), Wheat, Salt.</div>
  <div class="recommended-carousel">YOU MIGHT ALSO LIKE: Creamy Peanut Butter, Honey, Jam</div>
</body></html>
"""


@pytest.fixture
def scraper():
    return InstacartScraper()


@pytest.mark.asyncio
async def test_can_scrape_instacart_domain(scraper):
    assert await scraper.can_scrape("https://www.instacart.com/products/12345-organic-soy-sauce") is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://www.instacart.com/products/12345-organic-soy-sauce",
        product_html=INSTACART_HTML,
    )
    assert result.retailer == "Instacart"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95


def test_extracts_jsonld_and_title(scraper):
    text = scraper.process_client_html(
        url="https://www.instacart.com/products/12345-organic-soy-sauce",
        product_html=INSTACART_HTML,
    ).raw_html_product
    assert "=== structured_data ===" in text
    assert "Organic Soy Sauce 10oz" in text


def test_nutrition_facts_extracted_by_content_pattern(scraper):
    """Nutrition panel found via keyword-cluster despite hashed classes (ADR-005)."""
    text = scraper.process_client_html(
        url="https://www.instacart.com/products/12345-organic-soy-sauce",
        product_html=INSTACART_HTML,
    ).raw_html_product
    assert "=== nutrition_facts ===" in text
    assert "Sodium 920mg" in text
    assert "Total Carbohydrate 1g" in text
    assert "Protein 2g" in text


def test_ingredients_extracted_from_label_with_allergen(scraper):
    text = scraper.process_client_html(
        url="https://www.instacart.com/products/12345-organic-soy-sauce",
        product_html=INSTACART_HTML,
    ).raw_html_product
    assert "=== ingredients ===" in text
    assert "Water, Soybeans (Soy), Wheat, Salt" in text  # incl. the Soy allergen


def test_recommended_products_not_mistaken_for_ingredients(scraper):
    """Food words in a recommendations carousel must NOT surface as ingredients (MEMORY.md)."""
    text = scraper.process_client_html(
        url="https://www.instacart.com/products/12345-organic-soy-sauce",
        product_html=INSTACART_HTML,
    ).raw_html_product
    assert "Peanut Butter" not in text  # excluded carousel + label-gated ingredients


def test_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://www.instacart.com/products/12345-organic-soy-sauce",
        product_html=INSTACART_HTML,
    ).raw_html_product
    assert "SITE HEADER JUNK" not in text
    assert "NAV JUNK" not in text
