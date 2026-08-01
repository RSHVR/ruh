"""Product-identity guard.

An analysis must be verifiably about the product the user requested. When the
scrape/fallback chain drifts to a different page (bot-block redirects, wrong
web_fetch target), the extracted "product" can be something else entirely —
worse than no result, because it is confidently wrong. The guard compares the
analyzed product name/brand against the identity tokens embedded in the
product URL's slug and rejects on confirmed mismatch, so the route can fail
the request (extension shows retry) instead of storing and rendering it.

Deliberately conservative: it only rejects when the URL carries enough
identity signal (>= 2 meaningful slug tokens) AND none of them appear in the
analyzed name/brand. Wording differences ("60-count" vs "60ct") never trip it
because ANY single-token overlap passes.
"""

import re
from urllib.parse import urlparse
from typing import Optional, Set

# Generic words that appear in slugs but carry no product identity.
_STOPWORDS = {
    "the", "and", "with", "for", "from", "pack", "count", "pcs", "piece",
    "pieces", "set", "size", "new", "one", "all", "in", "of", "by", "per",
    "kit", "bundle", "value", "mega", "jumbo", "large", "small", "extra",
    "product", "item", "official", "original", "assorted",
}

_MIN_TOKEN_LEN = 3
_MIN_SLUG_SIGNAL = 2  # need at least this many meaningful tokens to reject

_UNIDENTIFIED_NAMES = {"", "unknown", "n/a", "none", "unnamed product"}


def slug_tokens(url: str) -> Set[str]:
    """Meaningful identity tokens from the URL path's product slug segments.

    Splits every path segment on non-alphanumerics, keeps alphabetic tokens of
    length >= 3 that aren't generic stopwords. Numeric ids, locale segments
    ("en", "fr", "ip"), and short glue words drop out naturally.
    """
    try:
        path = urlparse(url).path
    except (ValueError, AttributeError):
        return set()

    tokens: Set[str] = set()
    for raw in re.split(r"[^a-zA-Z0-9]+", path):
        token = raw.lower()
        if len(token) < _MIN_TOKEN_LEN:
            continue
        if not token.isalpha():
            continue
        if token in _STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def product_identity_ok(
    url: str,
    product_name: Optional[str],
    brand: Optional[str] = None,
) -> bool:
    """True when the analyzed product is plausibly the one the URL points to.

    Rejects when (a) the analysis has no usable product name at all, or
    (b) the URL slug carries clear identity (>= 2 meaningful tokens) and the
    analyzed name+brand share none of them.
    """
    name = (product_name or "").strip().lower()
    if name in _UNIDENTIFIED_NAMES:
        return False

    slug = slug_tokens(url)
    if len(slug) < _MIN_SLUG_SIGNAL:
        # Not enough URL signal to dispute the analysis (e.g. Amazon /dp/ ids).
        return True

    haystack = f"{name} {(brand or '').lower()}"
    analyzed_tokens = {
        t for t in re.split(r"[^a-z0-9]+", haystack) if len(t) >= _MIN_TOKEN_LEN
    }
    return bool(slug & analyzed_tokens)
