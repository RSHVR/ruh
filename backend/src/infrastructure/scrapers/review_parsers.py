"""Per-retailer review parsers → uniform structured review dicts.

The review-DOM dialect of a site belongs WITH that retailer, not baked into the
vector service (SOLID / single-responsibility). Each parser converts a retailer's
review shape (Amazon's ``data-hook`` DOM, generic schema.org JSON-LD, Walmart's
``__NEXT_DATA__`` JSON, Uniqlo's review container) into the contract the
``ReviewVectorService.store_reviews`` pipeline consumes:

    {
        "review_text": str,          # required, non-empty
        "review_rating": int | None, # 1-5 where known
        "reviewer_name": str | None,
        "review_date": str | None,
        "verified_purchase": bool,
        "helpful_votes": int,
        "review_title": str | None,  # optional, ignored by storage
    }

Resolution is per retailer via ``BaseScraper.REVIEW_PARSER`` (open/closed — adding
a retailer stays configuration, INV-2). Every parser degrades to ``[]`` on
malformed input and never raises (INV-3).
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Normalise review text before storage/embedding (whitespace, punctuation)."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([.!?,])\1+", r"\1", text)
    text = re.sub(r"\s+[^\w\s]\s+", " ", text)
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\u00a0", " ")
    return text.strip()


class ReviewParser:
    """Base review parser: HTML/JSON text → list of uniform review dicts."""

    def parse(self, html: str) -> List[Dict[str, Any]]:  # pragma: no cover - abstract
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Amazon — data-hook DOM (accepts BOTH renamed 2026 hooks and legacy hooks)
# --------------------------------------------------------------------------- #
class AmazonReviewParser(ReviewParser):
    """Amazon review DOM parser.

    Accepts the renamed 2026 hooks (``div[data-hook="reviewText"]`` inside
    ``reviewTextContainer``; ``h5[data-hook="reviewTitle"]``) AND the legacy hooks
    (``span[data-hook="review-body"]``, ``a[data-hook="review-title"]``) so old
    saved fixtures and any old-DOM regions stay parseable.
    """

    def parse(self, html: str) -> List[Dict[str, Any]]:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Amazon review parse: soup failed: {e}")
            return []

        reviews: List[Dict[str, Any]] = []
        for div in soup.find_all("div", {"data-hook": "review"}):
            try:
                parsed = self._parse_one(div)
            except Exception as e:
                logger.warning(f"Failed to parse Amazon review: {e}")
                continue
            if parsed:
                reviews.append(parsed)
        return reviews

    def _parse_one(self, div) -> Optional[Dict[str, Any]]:
        body_el = (
            div.find(attrs={"data-hook": "reviewText"})           # new
            or div.find(attrs={"data-hook": "review-collapsed"})  # legacy (expanded)
            or div.find(attrs={"data-hook": "review-body"})       # legacy
        )
        if not body_el:
            return None
        text = self._clean_body(body_el.get_text(separator=" ", strip=True))
        if not text:
            return None

        review: Dict[str, Any] = {
            "review_text": text,
            "review_rating": self._rating(div),
            "reviewer_name": self._first_text(div, "span", class_="a-profile-name"),
            "review_date": self._first_text(div, attrs={"data-hook": "review-date"}),
            "verified_purchase": bool(
                div.find(attrs={"data-hook": "avp-badge"})
                or div.find(attrs={"data-hook": "avp-badge-linkless"})
            ),
            "helpful_votes": self._helpful_votes(div),
            "review_title": self._title(div),
        }
        return review

    @staticmethod
    def _clean_body(text: str) -> str:
        text = re.sub(r"\(function\(\).*?\}\)\(\);?", "", text, flags=re.DOTALL)
        text = re.sub(r"\.review-text.*?\}", "", text, flags=re.DOTALL)
        text = re.sub(r"Read more\s*$", "", text)
        return clean_text(text)

    @staticmethod
    def _first_text(div, name=None, class_=None, attrs=None) -> Optional[str]:
        el = div.find(name, class_=class_) if class_ else div.find(name, attrs=attrs or {})
        return el.get_text(strip=True) if el else None

    @staticmethod
    def _rating(div) -> Optional[int]:
        el = div.find("i", {"data-hook": "review-star-rating"}) or div.find(
            "i", {"data-hook": "cmps-review-star-rating"}
        )
        if not el:
            return None
        m = re.search(r"(\d+(?:\.\d+)?)", el.get_text())
        return int(float(m.group(1))) if m else None

    @staticmethod
    def _helpful_votes(div) -> int:
        el = div.find("span", {"data-hook": "helpful-vote-statement"})
        if not el:
            return 0
        text = el.get_text()
        m = re.search(r"(\d+)", text)
        if m:
            return int(m.group(1))
        return 1 if "one person" in text.lower() else 0

    @staticmethod
    def _title(div) -> Optional[str]:
        el = div.find("h5", {"data-hook": "reviewTitle"}) or div.find(
            attrs={"data-hook": "review-title"}
        )
        if not el:
            return None
        title = re.sub(
            r"^[\d.]+\s+out\s+of\s+\d+\s+stars?\s*", "", el.get_text(separator=" ", strip=True)
        ).strip()
        return title or None


# --------------------------------------------------------------------------- #
# Generic schema.org JSON-LD — Costco/Bazaarvoice, H&M, Sephora, and any future
# site that ships Review objects in ld+json (or Bazaarvoice's review script).
# --------------------------------------------------------------------------- #
class JsonLdReviewParser(ReviewParser):
    """Parse schema.org ``Review`` objects out of JSON-LD script tags.

    Walks every ``script[type="application/ld+json"]`` plus Bazaarvoice's
    ``script#bv-jsonld-reviews-data`` and recursively collects Review objects,
    covering top-level review arrays, ``Product.review[]``,
    ``ProductGroup.review[]`` and nested ``ProductGroup.hasVariant[].review[]``.
    """

    def parse(self, html: str) -> List[Dict[str, Any]]:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"JSON-LD review parse: soup failed: {e}")
            return []

        reviews: List[Dict[str, Any]] = []
        seen_scripts: set = set()
        for script in soup.select(
            'script[type="application/ld+json"], script#bv-jsonld-reviews-data'
        ):
            if id(script) in seen_scripts:
                continue
            seen_scripts.add(id(script))
            raw = script.string or script.get_text()
            if not raw or not raw.strip():
                continue
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            collected: List[Dict[str, Any]] = []
            _collect_review_nodes(data, collected)
            for node in collected:
                review = _review_from_jsonld(node)
                if review:
                    reviews.append(review)
        return reviews


def _collect_review_nodes(node: Any, out: List[Dict[str, Any]]) -> None:
    """Recursively collect schema.org Review dicts anywhere in the structure."""
    if isinstance(node, list):
        for item in node:
            _collect_review_nodes(item, out)
    elif isinstance(node, dict):
        if _is_review(node):
            out.append(node)
        for value in node.values():
            _collect_review_nodes(value, out)


def _is_review(node: Dict[str, Any]) -> bool:
    type_field = node.get("@type")
    types = type_field if isinstance(type_field, list) else [type_field]
    if any(isinstance(t, str) and "review" in t.lower() for t in types):
        return True
    # Untyped but clearly a review (has a review body).
    return "reviewBody" in node


def _review_from_jsonld(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    body = node.get("reviewBody") or node.get("description") or ""
    if isinstance(body, list):
        body = " ".join(str(b) for b in body)
    text = clean_text(str(body))
    if not text:
        return None
    return {
        "review_text": text,
        "review_rating": _rating_value(node.get("reviewRating")),
        "reviewer_name": _author_name(node.get("author")),
        "review_date": node.get("dateCreated") or node.get("datePublished"),
        "verified_purchase": False,
        "helpful_votes": 0,
        "review_title": node.get("headline") or node.get("name") or None,
    }


def _rating_value(rating: Any) -> Optional[int]:
    value = rating.get("ratingValue") if isinstance(rating, dict) else rating
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _author_name(author: Any) -> Optional[str]:
    if isinstance(author, str):
        return author.strip() or None
    if isinstance(author, dict):
        name = author.get("name")
        return name.strip() if isinstance(name, str) and name.strip() else None
    if isinstance(author, list) and author:
        return _author_name(author[0])
    return None


# --------------------------------------------------------------------------- #
# Walmart — Next.js __NEXT_DATA__ customerReviews
# --------------------------------------------------------------------------- #
def parse_next_data_json(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """Return the parsed ``__NEXT_DATA__`` JSON blob, or None if absent/invalid."""
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        return None
    raw = script.string or script.get_text()
    if not raw or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


class WalmartReviewParser(ReviewParser):
    """Parse Walmart reviews from ``__NEXT_DATA__``'s ``customerReviews`` array."""

    def parse(self, html: str) -> List[Dict[str, Any]]:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Walmart review parse: soup failed: {e}")
            return []

        data = parse_next_data_json(soup)
        if not data:
            return []
        customer_reviews = _dig(
            data, "props", "pageProps", "initialData", "data", "reviews", "customerReviews"
        )
        return self.from_customer_reviews(customer_reviews)

    @staticmethod
    def from_customer_reviews(customer_reviews: Any) -> List[Dict[str, Any]]:
        """Map a Walmart ``customerReviews`` list to uniform review dicts.

        Shared by the WalmartScraper's Claude-text path so the field mapping lives
        in one place.
        """
        if not isinstance(customer_reviews, list):
            return []
        reviews: List[Dict[str, Any]] = []
        for cr in customer_reviews:
            if not isinstance(cr, dict):
                continue
            text = clean_text(str(cr.get("reviewText") or ""))
            if not text:
                continue
            reviews.append(
                {
                    "review_text": text,
                    "review_rating": _as_int(cr.get("rating")),
                    "reviewer_name": cr.get("userNickname"),
                    "review_date": cr.get("reviewSubmissionTime"),
                    "verified_purchase": False,
                    "helpful_votes": _as_int(cr.get("positiveFeedback")) or 0,
                    "review_title": cr.get("reviewTitle"),
                }
            )
        return reviews


# --------------------------------------------------------------------------- #
# Uniqlo — DOM review container (best-effort)
# --------------------------------------------------------------------------- #
class UniqloReviewParser(ReviewParser):
    """Best-effort parse of Uniqlo's ``#productReviews-container`` review blocks."""

    def parse(self, html: str) -> List[Dict[str, Any]]:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Uniqlo review parse: soup failed: {e}")
            return []

        container = soup.select_one("#productReviews-container")
        if not container:
            return []

        reviews: List[Dict[str, Any]] = []
        for info in container.select(".reviewUserInfo"):
            block = info.parent or info
            name_el = info.select_one("[class*='user' i], [class*='name' i]")
            reviewer_name = (
                name_el.get_text(strip=True) if name_el else info.get_text(strip=True)
            ) or None

            text_el = block.select_one(
                "[class*='reviewText' i], [class*='reviewBody' i], [class*='reviewComment' i], p"
            )
            text = clean_text(
                (text_el or block).get_text(separator=" ", strip=True)
            )
            if not text:
                continue
            reviews.append(
                {
                    "review_text": text,
                    "review_rating": _uniqlo_rating(block),
                    "reviewer_name": reviewer_name,
                    "review_date": None,
                    "verified_purchase": False,
                    "helpful_votes": 0,
                }
            )
        return reviews


def _uniqlo_rating(block) -> Optional[int]:
    el = block.select_one("[aria-label*='out of' i], [class*='rating' i], [class*='star' i]")
    if not el:
        return None
    label = el.get("aria-label") or el.get_text(strip=True)
    m = re.search(r"(\d+(?:\.\d+)?)", label or "")
    return int(float(m.group(1))) if m else None


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _dig(data: Any, *keys: str) -> Any:
    """Safely walk nested dict keys, returning None if any hop is missing."""
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
