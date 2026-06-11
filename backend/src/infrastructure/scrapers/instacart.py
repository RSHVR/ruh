"""Instacart product scraper — configuration only (no DOM-specific overrides).

Instacart is login-gated, so the client-HTML path from the user's authenticated
session is the real integration surface (LORE.md INV-1); ``scrape()`` (server-side
Playwright) cannot reach the page. The universal JSON-LD backbone (LORE.md ADR-004)
plus a few visible grocery selectors covers it: for groceries, INGREDIENTS and
NUTRITION are the key safety data (allergens). All mechanics are inherited from
``BaseScraper`` (LORE.md ADR-001); nothing about Instacart's DOM requires an override.

Recon note (2026-06-03, live, logged-in session): product pages reachable at
``/products/<id>-<slug>?retailerSlug=<store>``. JSON-LD Product **validated** (name,
brand, description, category, size, offers — no ingredients). The Nutrition / Details /
Directions sections ARE present in the client DOM (collapsed behind "Show more"; the
nutrition-facts + ingredient text is in the markup, not lazy-fetched), but Instacart uses
hashed Emotion class names (e.g. ``e-1qm1lh``) with no stable ``data-testid``/``id`` on
those sections, so they are not cleanly targetable by a small CSS selector. The full
structured item data (incl. nutrition + ingredients) lives in a stable
``<script id="node-apollo-state" type="application/json">`` blob — but it's ~435KB, so
capturing it wholesale would defeat the selector compression (INV-1 keeps payloads ~20KB)
and spike token cost. Decision: rely on JSON-LD (small, reliable) + Claude enrichment;
the visible ingredient/nutrition selectors below remain best-effort fallbacks. A future
enhancement could add a method override that extracts only the item's node from
``#node-apollo-state`` (see MEMORY.md 2026-06-03).
"""

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import BaseScraper


class InstacartScraper(BaseScraper):
    """Instacart scraper — config + content-pattern override for nutrition/ingredients.

    Instacart is archetype-D (LORE.md ADR-005): the grocery safety data (nutrition facts,
    ingredients) is **lazily rendered on scroll** into DOM elements with hashed Emotion
    classes (e.g. ``e-1qm1lh``) — there is NO stable hook and NO usable state blob
    (``#node-apollo-state`` does not hold the rendered nutrition/ingredient text). So the
    override below locates the nutrition facts by a **content keyword-cluster** (Total Fat /
    Sodium / Carbohydrate / Protein / …) and the ingredient list by an explicit
    ``Ingredients:`` label — both robust to class churn.

    Two-sided requirement: the extension must SCROLL the page before capturing
    (``instacartAdapter.prepareForCapture``) or the lazy content is absent from the DOM.
    Ingredient lists are often not exposed even after scroll (retailer-dependent), so that
    part is best-effort; nutrition facts are reliable (see AUDIT.md).
    """

    RETAILER_NAME = "Instacart"
    SCRAPE_METHOD = "instacart_raw_html"

    DOMAIN_PATTERNS = [
        r"instacart\.com",
    ]

    # JSON-LD backbone + title + a visible description. Nutrition/ingredients are added by
    # the content-pattern override (their DOM has no stable selector). No meta[...] (ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {"name": "product_details", "selector": "[data-testid*='item-details' i], [class*='item-details' i]"},
    ]

    # Keywords that, in a cluster, identify a Nutrition Facts panel.
    _NUTRITION_TOKENS = re.compile(
        r"total fat|saturated|trans fat|cholesterol|sodium|carbohydrate|dietary fiber|"
        r"total sugars|added sugars|protein|serving size|calories|daily value",
        re.I,
    )

    # Instacart has no usable client-session reviews endpoint; ratings, where present,
    # arrive via JSON-LD aggregateRating in structured_data.
    REVIEWS_SECTION_SELECTORS = []

    EXCLUDE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "[class*='recommend' i]",
        "[class*='carousel' i]",
        "[class*='related' i]",
    ]

    # ------------------------------------------------------------------ #
    # Content-pattern extraction (no stable selectors on Instacart's DOM)
    # ------------------------------------------------------------------ #
    def _extract_sections(self, soup: BeautifulSoup, selectors: List[dict]) -> str:
        """Standard selector extraction + content-pattern nutrition/ingredients."""
        base = super()._extract_sections(soup, selectors)
        extra: List[str] = []

        nutrition = self._find_nutrition_facts(soup)
        if nutrition:
            extra += ["=== nutrition_facts ===", nutrition, ""]

        ingredients = self._find_ingredients(soup)
        if ingredients:
            extra += ["=== ingredients ===", ingredients, ""]

        return f"{base}\n" + "\n".join(extra) if extra else base

    def _find_nutrition_facts(self, soup: BeautifulSoup, max_len: int = 1100) -> Optional[str]:
        """Smallest element holding a cluster (>=4 distinct) of nutrition-fact tokens."""
        best: Optional[str] = None
        for el in soup.find_all(["div", "ul", "section", "dl", "table"]):
            text = el.get_text(" ", strip=True)
            if len(text) > 2500:
                continue
            distinct = len({m.lower() for m in self._NUTRITION_TOKENS.findall(text)})
            if distinct >= 4 and (best is None or len(text) < len(best)):
                best = text
        if not best:
            return None
        # Collapse the duplicated a11y labels ("... 9% daily value Total Fat Saturated ...").
        cleaned = re.sub(r"\s+", " ", best).strip()
        cleaned = re.sub(r"(\d+% daily value)\s+Total Fat", r"\1", cleaned)
        return cleaned[:max_len]

    def _find_ingredients(self, soup: BeautifulSoup, max_len: int = 700) -> Optional[str]:
        """Ingredient list from an explicit ``Ingredients:`` label (best-effort).

        Returns None when Instacart doesn't expose a clean labeled list (common) — we do
        NOT guess from food words, which catches recommended-product titles (MEMORY.md).
        """
        for el in soup.find_all(["div", "p", "span", "dd", "section", "li"]):
            text = el.get_text(" ", strip=True)
            m = re.search(
                r"\bIngredients\b[:\s]+(.{20,600}?)(?:Nutrition|Directions|Warnings?|Allergen|$)",
                text,
                re.I,
            )
            if m and m.group(1).count(",") >= 2:
                return re.sub(r"\s+", " ", m.group(1)).strip()[:max_len]
        return None
