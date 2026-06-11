"""IKEA product scraper — config + a hydrate-blob override for safety-critical detail.

IKEA's JSON-LD Product only carries marketing-level ``material`` ("Solid wood"). The
*safety-critical* breakdown — the actual materials per part (e.g. "Inner side panel:
Particleboard", "Main parts: Solid pine, Adhesive, Stain, Clear acrylic lacquer"), care
instructions, safety & compliance warnings, certifications, and "good to know" — is NOT in
the visible initial DOM (it renders into an on-demand ``.pipf-product-details-modal``).

Crucially it IS present, statically, in ``<script type="text/hydrate">`` SSR hydration blobs
(preact island state) at first load — no user interaction or accordion expansion required.
So rather than driving fragile modal/accordion clicks in the extension, ``IkeaScraper``
overrides ``_extract_sections`` to parse those blobs and emit compact, labeled sections
(see LORE.md ADR-005, MEMORY.md 2026-06-03). This is the one IKEA-specific exception to the
config-only rule (ADR-001) and is justified by the safety value of the per-part materials.
"""

import re

from bs4 import BeautifulSoup
from typing import List

from .base import BaseScraper


class IkeaScraper(BaseScraper):
    """IKEA-specific product scraper (config + hydrate-blob override)."""

    RETAILER_NAME = "IKEA"
    SCRAPE_METHOD = "ikea_raw_html"

    DOMAIN_PATTERNS = [
        r"ikea\.com",
    ]

    # JSON-LD first (universal backbone), then title, then visible detail/material
    # blocks and the in-page Q&A + reviews. The per-part materials / care / safety /
    # certifications are added from the hydrate blobs by the override below.
    # No meta[...] selectors (LORE.md ADR-004).
    PRODUCT_SECTION_SELECTORS = [
        {"name": "structured_data", "selector": "script[type='application/ld+json']"},
        {"name": "title", "selector": "h1"},
        {"name": "product_details", "selector": ".pipf-product-details-modal, [class*='product-details' i]"},
        {"name": "description", "selector": "[class*='pip-product-summary'], [class*='product-summary']"},
        {"name": "questions_answers", "selector": ".pipf-questions-and-answers, .pipf-ratings-and-qna"},
        {"name": "reviews", "selector": ".pipf-seo-reviews"},
    ]

    REVIEWS_SECTION_SELECTORS = []

    EXCLUDE_SELECTORS = [
        "header",
        "footer",
        "nav",
        "[class*='recommend' i]",
        "[class*='carousel' i]",
        "[class*='you-might' i]",
    ]

    # ------------------------------------------------------------------ #
    # IKEA-specific: pull safety-critical detail from text/hydrate blobs
    # ------------------------------------------------------------------ #
    def _extract_sections(self, soup: BeautifulSoup, selectors: List[dict]) -> str:
        """Standard selector extraction + compact sections parsed from hydrate blobs."""
        base = super()._extract_sections(soup, selectors)
        hydrate = self._extract_hydrate_detail(soup)
        return f"{base}\n{hydrate}".rstrip() if hydrate else base

    def _extract_hydrate_detail(self, soup: BeautifulSoup) -> str:
        """Parse ``<script type='text/hydrate'>`` SSR blobs for materials/care/safety.

        These blobs hold the full structured product data (per-part materials, care,
        safety & compliance, certifications, good-to-know) even when the visible modal
        is collapsed. We extract only the relevant fields to stay compact (~1KB), never
        dumping the whole ~200KB blob (cf. the Instacart Apollo lesson, MEMORY.md).
        """
        blob = "\n".join(s.get_text() for s in soup.select("script[type='text/hydrate']"))
        if not blob:
            return ""

        out: List[str] = []

        # Per-part materials: {"material":"…","part":"…"} in either field order.
        pairs: List[tuple] = []
        pairs += [(p, m) for m, p in re.findall(
            r'"material"\s*:\s*"([^"]{1,250})"\s*,\s*"part"\s*:\s*"([^"]{1,90})"', blob)]
        pairs += [(p, m) for p, m in re.findall(
            r'"part"\s*:\s*"([^"]{1,90})"\s*,\s*"material"\s*:\s*"([^"]{1,250})"', blob)]
        if pairs:
            lines, seen = [], set()
            for part, material in pairs:
                line = self._clean(f"{part} {material}")
                if line and line not in seen:
                    seen.add(line)
                    lines.append(line)
            if lines:
                out += ["=== materials_breakdown ===", *lines, ""]

        # Care instructions (match by content — field name varies).
        care = [self._clean(c) for c in re.findall(r'"([^"]{0,40}(?:wipe|damp cloth|dust|clean cloth)[^"]{0,200})"', blob, re.I)]
        care = list(dict.fromkeys(c for c in care if c))
        if care:
            out += ["=== care ===", *care[:6], ""]

        # Title-anchored free-text sections.
        for title, label in (
            ("Safety and compliance", "safety_and_compliance"),
            ("Certifications or recognition", "certifications"),
            ("Good to know", "good_to_know"),
        ):
            texts = self._hydrate_section_texts(blob, title)
            if texts:
                out += [f"=== {label} ===", *texts, ""]

        return "\n".join(out)

    def _hydrate_section_texts(self, blob: str, title: str, limit: int = 6, window: int = 4000) -> List[str]:
        """Collect ``"text":"…"`` values that appear just after a section ``title``."""
        seg = blob.split(f'"title":"{title}"', 1)
        if len(seg) < 2:
            return []
        texts, seen = [], set()
        for t in re.findall(r'"text"\s*:\s*"([^"]{8,400})"', seg[1][:window]):
            t = self._clean(t)
            if t and t not in seen:
                seen.add(t)
                texts.append(t)
            if len(texts) >= limit:
                break
        return texts

    @staticmethod
    def _clean(s: str) -> str:
        """Unescape common JSON artifacts and collapse whitespace."""
        s = s.replace("\\u002F", "/").replace("\\/", "/").replace("\\n", " ").replace('\\"', '"')
        return re.sub(r"\s+", " ", s).strip()
