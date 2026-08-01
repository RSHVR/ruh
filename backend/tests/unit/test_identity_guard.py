"""Product-identity guard: an analysis must be about the product the user asked for.

Born from a real prod failure (2026-08-01): a costco.ca pre-workout URL fell to the
web_fetch fallback (old backend didn't know costco.ca), the fallback analyzed some
other page entirely, and a fabric-softener ingredient list was stored and shown as
"Analysis Complete" for a supplement. The guard rejects analyses whose identity
cannot be tied to the requested URL, so the extension shows retry instead.
"""

from src.domain.identity import product_identity_ok, slug_tokens


class TestSlugTokens:
    def test_extracts_meaningful_tokens_from_costco_slug(self):
        url = (
            "https://www.costco.ca/p/-/dynomight-pre-workout-60-count-variety-pack"
            "/4201011437?storeId=10302"
        )
        tokens = slug_tokens(url)
        assert "dynomight" in tokens
        assert "workout" in tokens
        # numbers and short/stop words are not meaningful identity tokens
        assert "60" not in tokens
        assert "of" not in tokens

    def test_legacy_costco_product_slug(self):
        url = "https://www.costco.ca/oxiclean-max-efficiency-stain-remover-525-kg.product.4000289802.html"
        tokens = slug_tokens(url)
        assert "oxiclean" in tokens
        assert "stain" in tokens

    def test_amazon_dp_url_has_no_slug(self):
        assert slug_tokens("https://www.amazon.ca/dp/B000LN5O8O") == set()

    def test_walmart_ca_slug(self):
        url = "https://www.walmart.ca/en/ip/Britax-One4Life-All-in-One-Car-Seat-Glacier-Graphite/38WYZF7I4FZ6"
        tokens = slug_tokens(url)
        assert "britax" in tokens
        assert "seat" in tokens


class TestProductIdentityOk:
    URL = "https://www.costco.ca/p/-/dynomight-pre-workout-60-count-variety-pack/4201011437"

    def test_rejects_the_real_prod_failure(self):
        # Fabric softener analyzed for a pre-workout URL -> reject
        assert not product_identity_ok(self.URL, "Downy Ultra Fabric Softener", "Downy")

    def test_rejects_unknown_product_name(self):
        assert not product_identity_ok(self.URL, "Unknown", "Unknown")
        assert not product_identity_ok(self.URL, "", None)
        assert not product_identity_ok(self.URL, None, None)

    def test_accepts_matching_product(self):
        assert product_identity_ok(self.URL, "Dynomight Pre-Workout Variety Pack, 60-count", "Dynomight")

    def test_accepts_partial_match_via_brand(self):
        # Only the brand token matches -> still identifiable
        assert product_identity_ok(self.URL, "Pre Workout Supplement 60ct", "Dynomight Labs")

    def test_accepts_single_token_overlap(self):
        # Conservative: ANY meaningful overlap passes (title wording varies wildly)
        assert product_identity_ok(self.URL, "Variety Bundle", None)

    def test_sluggless_url_skips_check_but_still_requires_a_name(self):
        # No slug to compare against (Amazon /dp/) -> cannot verify, allow real names
        assert product_identity_ok("https://www.amazon.ca/dp/B000LN5O8O", "Nikwax Tech Wash 300ml", "Nikwax")
        # ...but a nameless analysis is still rejected
        assert not product_identity_ok("https://www.amazon.ca/dp/B000LN5O8O", "Unknown", None)

    def test_short_slug_skips_mismatch_check(self):
        # Fewer than 2 meaningful slug tokens -> not enough signal to reject on mismatch
        assert product_identity_ok("https://example.com/p/soap/123", "Some Cleaning Bar", "Acme")
