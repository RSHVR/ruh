"""Tests for the per-retailer review-parser layer.

Review-DOM dialect belongs WITH the retailer (SOLID / open-closed), not baked into
the vector service. Each parser turns a retailer's review shape into a uniform
list of dicts with the keys ReviewVectorService.store_reviews consumes:
``review_text``, ``review_rating`` (int|None), ``reviewer_name``, ``review_date``,
``verified_purchase`` (bool), ``helpful_votes`` (int). Parsers must degrade to an
empty list on malformed input (INV-3 — never raise).
"""

import pytest

from src.infrastructure.scrapers.review_parsers import (
    AmazonReviewParser,
    JsonLdReviewParser,
    WalmartReviewParser,
    UniqloReviewParser,
)
from src.infrastructure.review_vector_service import review_vector_service


# --------------------------------------------------------------------------- #
# Amazon — NEW data-hooks (verified live 2026-08-01) + OLD hooks (back-compat)
# --------------------------------------------------------------------------- #
AMAZON_NEW_HTML = """
<div data-hook="review">
  <div data-hook="genome-widget"><span class="a-profile-name">Jane D.</span></div>
  <div>
    <i data-hook="review-star-rating"><span class="a-icon-alt">5 out of 5 stars</span></i>
    <h5 data-hook="reviewTitle"><span>Absolutely love it</span></h5>
  </div>
  <div data-hook="review-by-line">
    <span data-hook="review-date">Reviewed in Canada on March 3, 2026</span>
  </div>
  <div data-hook="product-variation-attributes">
    <a data-hook="format-strip">Color: Blue</a>
    <div data-hook="review-badges"><span data-hook="avp-badge">Verified Purchase</span></div>
  </div>
  <div data-hook="reviewTextContainer">
    <div data-hook="reviewText"><span><div>This cream cleared my skin.</div><div>No irritation at all.</div></span></div>
  </div>
  <span data-hook="helpful-vote-statement">12 people found this helpful</span>
</div>
"""

AMAZON_OLD_HTML = """
<div data-hook="review">
  <div data-hook="genome-widget"><span class="a-profile-name">Old Bob</span></div>
  <i data-hook="review-star-rating"><span class="a-icon-alt">4.0 out of 5 stars</span></i>
  <a data-hook="review-title"><span>Pretty good</span></a>
  <span data-hook="review-date">Reviewed on January 1, 2024</span>
  <span data-hook="avp-badge">Verified Purchase</span>
  <span data-hook="review-body">Old style body text here.</span>
  <span data-hook="helpful-vote-statement">One person found this helpful</span>
</div>
"""


def test_amazon_parser_new_hooks():
    reviews = AmazonReviewParser().parse(AMAZON_NEW_HTML)
    assert len(reviews) == 1
    r = reviews[0]
    assert "cleared my skin" in r["review_text"]
    assert "No irritation at all" in r["review_text"]
    assert r["review_rating"] == 5
    assert r["reviewer_name"] == "Jane D."
    assert "March 3, 2026" in r["review_date"]
    assert r["verified_purchase"] is True
    assert r["helpful_votes"] == 12
    assert r.get("review_title") == "Absolutely love it"


def test_amazon_parser_old_hooks_still_parse():
    reviews = AmazonReviewParser().parse(AMAZON_OLD_HTML)
    assert len(reviews) == 1
    r = reviews[0]
    assert r["review_text"] == "Old style body text here."
    assert r["review_rating"] == 4
    assert r["reviewer_name"] == "Old Bob"
    assert r["verified_purchase"] is True
    assert r["helpful_votes"] == 1  # "One person found this helpful"


def test_amazon_parser_mixed_old_and_new_regions():
    reviews = AmazonReviewParser().parse(AMAZON_NEW_HTML + AMAZON_OLD_HTML)
    assert len(reviews) == 2


def test_amazon_parser_skips_reviews_without_text():
    html = '<div data-hook="review"><span class="a-profile-name">No Body</span></div>'
    assert AmazonReviewParser().parse(html) == []


# --------------------------------------------------------------------------- #
# Generic schema.org JSON-LD — Costco/Bazaarvoice, H&M, Sephora
# --------------------------------------------------------------------------- #
COSTCO_BV_HTML = """
<script id="bv-jsonld-bvloader-summary" type="application/ld+json">
{"@type":"AggregateRating","ratingValue":"4.3","reviewCount":"8"}
</script>
<script id="bv-jsonld-reviews-data" type="application/ld+json">
[
  {"@type":"Review","headline":"Great value","reviewBody":"Cleans well, no strong smell.",
   "reviewRating":{"@type":"Rating","ratingValue":"5","bestRating":"5"},
   "author":{"@type":"Person","name":"CostcoFan"},"dateCreated":"2026-01-15","datePublished":"2026-01-16"},
  {"@type":"Review","headline":"Caused a rash","reviewBody":"Gave me skin irritation on my hands.",
   "reviewRating":{"ratingValue":2,"bestRating":5},"author":"Anon","datePublished":"2026-02-01"}
]
</script>
"""

HM_PRODUCTGROUP_HTML = """
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"ProductGroup","name":"Ribbed Top",
 "review":[
   {"@type":"Review","author":{"@type":"Person","name":"HMShopper"},"datePublished":"2026-03-01",
    "reviewBody":"Soft fabric but the seams feel itchy.","reviewRating":{"ratingValue":"4"}}
 ]}
</script>
"""

SEPHORA_HASVARIANT_HTML = """
<script type="application/ld+json">
{"@type":"ProductGroup","name":"Serum","review":[],
 "hasVariant":[
   {"@type":"Product","sku":"v1","review":[
     {"@type":"Review","author":{"name":"SephoraUser"},"datePublished":"2026-04-01",
      "reviewBody":"Broke me out badly within days.","reviewRating":{"ratingValue":1,"bestRating":5}}
   ]}
 ]}
</script>
"""


def test_jsonld_parser_costco_bazaarvoice_array():
    reviews = JsonLdReviewParser().parse(COSTCO_BV_HTML)
    assert len(reviews) == 2
    first = reviews[0]
    assert first["review_text"] == "Cleans well, no strong smell."
    assert first["review_rating"] == 5
    assert first["reviewer_name"] == "CostcoFan"
    assert first["review_date"] == "2026-01-15"  # dateCreated preferred
    assert first.get("review_title") == "Great value"
    # The aggregate summary script must NOT become a review.
    assert all("skin irritation" in r["review_text"] or "Cleans well" in r["review_text"]
               for r in reviews)
    second = reviews[1]
    assert second["review_rating"] == 2
    assert second["reviewer_name"] == "Anon"  # author as bare string
    assert second["review_date"] == "2026-02-01"  # falls back to datePublished


def test_jsonld_parser_hm_productgroup_review():
    reviews = JsonLdReviewParser().parse(HM_PRODUCTGROUP_HTML)
    assert len(reviews) == 1
    assert reviews[0]["review_rating"] == 4
    assert reviews[0]["reviewer_name"] == "HMShopper"
    assert "itchy" in reviews[0]["review_text"]


def test_jsonld_parser_sephora_hasvariant_nested_review():
    reviews = JsonLdReviewParser().parse(SEPHORA_HASVARIANT_HTML)
    assert len(reviews) == 1
    assert reviews[0]["review_rating"] == 1
    assert reviews[0]["reviewer_name"] == "SephoraUser"
    assert "Broke me out" in reviews[0]["review_text"]


def test_jsonld_parser_ignores_aggregate_rating_and_bad_json():
    html = """
    <script type="application/ld+json">{"@type":"Product","name":"X",
      "aggregateRating":{"@type":"AggregateRating","ratingValue":"4.5","reviewCount":"9"}}</script>
    <script type="application/ld+json">this is not json {{{</script>
    """
    assert JsonLdReviewParser().parse(html) == []


def test_jsonld_parser_graph_wrapped_product_review():
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
      {"@type":"Product","name":"X","review":[
        {"@type":"Review","reviewBody":"Works great","reviewRating":{"ratingValue":5},"author":{"name":"G"}}
      ]}
    ]}
    </script>
    """
    reviews = JsonLdReviewParser().parse(html)
    assert len(reviews) == 1
    assert reviews[0]["review_text"] == "Works great"


# --------------------------------------------------------------------------- #
# Walmart — __NEXT_DATA__ customerReviews
# --------------------------------------------------------------------------- #
WALMART_NEXT_DATA_HTML = """
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"initialData":{"data":{
  "product":{"name":"Britax Car Seat","brand":"Britax"},
  "idml":{"specifications":[{"name":"Brand","value":"Britax"}]},
  "reviews":{"customerReviews":[
    {"reviewId":"1","rating":5,"reviewText":"Very safe and comfy.","reviewTitle":"Love it",
     "reviewSubmissionTime":"2026-05-01","userNickname":"ParentX","positiveFeedback":3,"negativeFeedback":0},
    {"reviewId":"2","rating":2,"reviewText":"Straps gave my baby a rash.","reviewTitle":"Careful",
     "reviewSubmissionTime":"2026-05-05","userNickname":"ParentY","positiveFeedback":1,"negativeFeedback":2}
  ]}
}}}}}
</script>
"""


def test_walmart_parser_next_data():
    reviews = WalmartReviewParser().parse(WALMART_NEXT_DATA_HTML)
    assert len(reviews) == 2
    first = reviews[0]
    assert first["review_text"] == "Very safe and comfy."
    assert first["review_rating"] == 5
    assert first["reviewer_name"] == "ParentX"
    assert first["review_date"] == "2026-05-01"
    assert first["helpful_votes"] == 3
    assert first.get("review_title") == "Love it"
    assert reviews[1]["review_rating"] == 2
    assert "rash" in reviews[1]["review_text"]


def test_walmart_parser_no_next_data_is_empty():
    assert WalmartReviewParser().parse("<html><body>no next data</body></html>") == []
    assert WalmartReviewParser().parse('<script id="__NEXT_DATA__">{bad json</script>') == []


# --------------------------------------------------------------------------- #
# Uniqlo — DOM #productReviews-container (.reviewUserInfo blocks), best-effort
# --------------------------------------------------------------------------- #
UNIQLO_HTML = """
<div id="productReviews-container">
  <div class="review">
    <div class="reviewUserInfo"><span class="userName">UniqloFan</span>
      <span class="rating" aria-label="4 out of 5 stars">★★★★</span></div>
    <p class="reviewText">Comfortable but it shrank after one wash.</p>
  </div>
  <div class="review">
    <div class="reviewUserInfo"><span class="userName">Buyer2</span></div>
    <p class="reviewText">Nice material, no complaints.</p>
  </div>
</div>
"""


def test_uniqlo_parser_dom_reviews():
    reviews = UniqloReviewParser().parse(UNIQLO_HTML)
    assert len(reviews) == 2
    assert reviews[0]["reviewer_name"] == "UniqloFan"
    assert "shrank" in reviews[0]["review_text"]
    assert reviews[0]["review_rating"] == 4
    assert reviews[1]["reviewer_name"] == "Buyer2"
    assert reviews[1]["review_rating"] is None


def test_uniqlo_parser_missing_container_is_empty():
    assert UniqloReviewParser().parse("<html><body>no reviews</body></html>") == []


# --------------------------------------------------------------------------- #
# Per-retailer routing through the vector service seam (no DB required)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_routing_amazon_url_uses_amazon_parser():
    reviews = await review_vector_service.parse_reviews_for_url(
        "https://www.amazon.ca/dp/B000123456", AMAZON_NEW_HTML
    )
    assert len(reviews) == 1
    assert reviews[0]["review_rating"] == 5


@pytest.mark.asyncio
async def test_routing_costco_url_uses_jsonld_parser():
    reviews = await review_vector_service.parse_reviews_for_url(
        "https://www.costco.ca/p/-/soap/100334757", COSTCO_BV_HTML
    )
    assert len(reviews) == 2


@pytest.mark.asyncio
async def test_routing_walmart_url_uses_next_data_parser():
    reviews = await review_vector_service.parse_reviews_for_url(
        "https://www.walmart.ca/en/ip/car-seat/38WYZF7I4FZ6", WALMART_NEXT_DATA_HTML
    )
    assert len(reviews) == 2
    assert reviews[0]["reviewer_name"] == "ParentX"


@pytest.mark.asyncio
async def test_routing_unknown_url_falls_back_to_generic_jsonld():
    reviews = await review_vector_service.parse_reviews_for_url(
        "https://www.some-unknown-shop.example/product/123", HM_PRODUCTGROUP_HTML
    )
    assert len(reviews) == 1
    assert reviews[0]["reviewer_name"] == "HMShopper"
