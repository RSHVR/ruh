"""Tests for IkeaScraper (JSON-LD backbone + text/hydrate override — LORE.md ADR-004/005).

Mirrors test_amazon_scraper.py: a synthetic IKEA-like DOM (no network, no Playwright)
exercising the client-HTML path, which is the primary data source (LORE.md INV-1).

Key behavior under test: IKEA's safety-critical per-part materials / care / safety &
compliance / certifications are NOT in the visible initial DOM — they live in
``<script type="text/hydrate">`` SSR blobs. ``IkeaScraper`` parses those into compact
``materials_breakdown`` / ``care`` / ``safety_and_compliance`` / ``certifications``
sections (LORE.md ADR-005). The synthetic ``text/hydrate`` blob below mirrors the real
field structure observed during live recon (2026-06-03).
"""

import pytest

from src.infrastructure.scrapers.ikea import IkeaScraper

# Synthetic IKEA-like product HTML: JSON-LD Product (marketing-level material only) + h1
# title + a text/hydrate blob carrying the real per-part materials / care / safety /
# certifications structure, plus header/footer/recommendations that must be excluded.
IKEA_HTML = """
<html><body>
  <header>HEADER JUNK SHOULD BE REMOVED</header>
  <nav>NAV JUNK SHOULD BE REMOVED</nav>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "HEMNES 8-drawer dresser, white stain",
    "brand": {"@type": "Brand", "name": "IKEA"},
    "description": "A solid wood dresser with a timeless design.",
    "material": "Solid wood",
    "color": "White stain",
    "sku": "10576191"
  }
  </script>
  <h1>HEMNES 8-drawer dresser, white stain</h1>
  <div class="pip-product-summary">A solid wood dresser with a timeless design.</div>
  <div class="recommendations-rail">YOU MIGHT ALSO LIKE THIS REMOVED</div>
  <script type="text/hydrate">
  {"id":"materials-and-care","title":"Materials and care","contentProps":{"materials":[{"materials":[
    {"material":"Solid pine, Adhesive, Stain, Clear acrylic lacquer","part":"Main parts:"},
    {"material":"Particleboard","part":"Inner side panel:"},
    {"material":"Fiberboard, Acrylic paint","part":"Drawer bottom:"}],
    "careInstructions":[{"text":"Wipe clean with a damp cloth."},{"text":"Wipe dry with a clean cloth."}]}},
   "extra":[{"title":"Safety and compliance","content":[{"text":"WARNING! Tipping hazard - this product must be securely anchored."}]},
            {"title":"Certifications or recognition","content":[{"text":"Designed to meet the US Federal Stability Standard."}]}]}
  </script>
  <footer>FOOTER JUNK SHOULD BE REMOVED</footer>
</body></html>
"""


@pytest.fixture
def scraper():
    return IkeaScraper()


@pytest.mark.asyncio
async def test_can_scrape_ikea_domain(scraper):
    assert await scraper.can_scrape(
        "https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/"
    ) is True


@pytest.mark.asyncio
async def test_can_scrape_rejects_other_domains(scraper):
    assert await scraper.can_scrape("https://www.amazon.com/dp/B000123456") is False
    assert await scraper.can_scrape("https://www.walmart.com/ip/123") is False


def test_process_client_html_metadata(scraper):
    result = scraper.process_client_html(
        url="https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/",
        product_html=IKEA_HTML,
    )
    assert result.retailer == "IKEA"
    assert result.scrape_method == "client"
    assert result.confidence == 0.95
    assert (
        result.url
        == "https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/"
    )


def test_process_client_html_extracts_jsonld_and_title(scraper):
    text = scraper.process_client_html(
        url="https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/",
        product_html=IKEA_HTML,
    ).raw_html_product

    assert "=== structured_data ===" in text
    assert "=== title ===" in text
    # JSON-LD product name comes through (Claude parses the raw JSON)
    assert "HEMNES 8-drawer dresser, white stain" in text


def test_hydrate_materials_breakdown_extracted(scraper):
    """The safety-critical per-part materials come from the text/hydrate blob (ADR-005)."""
    text = scraper.process_client_html(
        url="https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/",
        product_html=IKEA_HTML,
    ).raw_html_product

    assert "=== materials_breakdown ===" in text
    # Per-part composition — the real safety signal (adhesives, lacquer, particleboard)
    assert "Main parts: Solid pine, Adhesive, Stain, Clear acrylic lacquer" in text
    assert "Inner side panel: Particleboard" in text
    assert "Drawer bottom: Fiberboard, Acrylic paint" in text


def test_hydrate_care_safety_certifications_extracted(scraper):
    text = scraper.process_client_html(
        url="https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/",
        product_html=IKEA_HTML,
    ).raw_html_product

    assert "=== care ===" in text
    assert "Wipe clean with a damp cloth." in text
    assert "=== safety_and_compliance ===" in text
    assert "Tipping hazard" in text
    assert "=== certifications ===" in text
    assert "US Federal Stability Standard" in text


def test_hydrate_extraction_stays_compact(scraper):
    """The override must extract only relevant fields, never the whole hydrate blob."""
    text = scraper.process_client_html(
        url="https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/",
        product_html=IKEA_HTML,
    ).raw_html_product
    # No raw JSON field names leak from the hydrate parse
    assert '"contentProps"' not in text
    assert '"careInstructions"' not in text


def test_process_client_html_removes_excluded(scraper):
    text = scraper.process_client_html(
        url="https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/",
        product_html=IKEA_HTML,
    ).raw_html_product
    assert "HEADER JUNK" not in text
    assert "FOOTER JUNK" not in text
    assert "NAV JUNK" not in text
