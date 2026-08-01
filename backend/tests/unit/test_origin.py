"""Unit tests for OriginInfo and the origin / user_region wiring on the models.

Origin is food/grocery-only provenance: where the product is produced/sourced,
region-aware, with an optional active supply-chain safety alert. Non-food ->
origin is null. AnalysisRequest gains a free-form user_region (e.g. "CA-ON").
"""

import pytest
from pydantic import ValidationError

from src.domain.models import OriginInfo, ProductAnalysis, AnalysisRequest


def _min_analysis(**overrides) -> ProductAnalysis:
    base = dict(product_url="https://example.com/p", overall_score=80, confidence=0.8)
    base.update(overrides)
    return ProductAnalysis(**base)


# ---------------------------------------------------------------------------
# OriginInfo
# ---------------------------------------------------------------------------

def test_origin_info_summary_only_defaults_region_and_alert_none():
    o = OriginInfo(summary="Produced in California.")
    assert o.summary == "Produced in California."
    assert o.region is None
    assert o.alert is None


def test_origin_info_holds_region_and_alert():
    o = OriginInfo(
        summary="Pooled Ontario milk.",
        region="CA-ON",
        alert="As of July 2026 CFIA is investigating a listeria recall.",
    )
    assert o.region == "CA-ON"
    assert o.alert.startswith("As of July 2026")


def test_origin_info_requires_summary():
    with pytest.raises(ValidationError):
        OriginInfo(region="CA-ON")  # summary is required


# ---------------------------------------------------------------------------
# ProductAnalysis.origin
# ---------------------------------------------------------------------------

def test_product_analysis_origin_defaults_none():
    assert _min_analysis().origin is None


def test_product_analysis_coerces_origin_dict():
    a = _min_analysis(origin={
        "summary": "US-sourced romaine.", "region": "US-CA",
        "alert": "CDC E. coli investigation, late July 2026.",
    })
    assert isinstance(a.origin, OriginInfo)
    assert a.origin.region == "US-CA"
    assert "E. coli" in a.origin.alert


def test_product_analysis_dump_roundtrips_origin():
    a = _min_analysis(origin={"summary": "s", "region": None, "alert": None})
    assert a.model_dump()["origin"] == {"summary": "s", "region": None, "alert": None}


# ---------------------------------------------------------------------------
# AnalysisRequest.user_region
# ---------------------------------------------------------------------------

def test_analysis_request_user_region_defaults_none():
    assert AnalysisRequest(product_url="https://x/p").user_region is None


def test_analysis_request_accepts_freeform_user_region():
    req = AnalysisRequest(product_url="https://x/p", user_region="CA-ON")
    assert req.user_region == "CA-ON"
