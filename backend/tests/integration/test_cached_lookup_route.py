"""Route tests for GET /api/analyze/cached — the payload-free cache probe.

The extension calls this BEFORE capturing the page DOM; only a 404 triggers
the full multi-MB capture + POST flow. A hit must serve the same response
shape as the POST route's cached branch (shared helper).
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.auth import get_auth_context, AuthContext

client = TestClient(app)

CACHED_ROW = {
    "product_url": "https://www2.hm.com/en_ca/productpage.1321040003.html",
    "product_name": "Aviator Sunglasses",
    "brand": "H&M",
    "retailer": "H&M Canada",
    "ingredients": ["Polycarbonate", "Metal"],
    "overall_score": 58,
    "allergens_detected": [],
    "pfas_detected": [],
    "other_concerns": [{"name": "UV coating", "category": "other",
                        "severity": "low", "description": "x", "confidence": 0.5}],
    "confidence": 85,
    "analyzed_at": "2026-08-01T16:25:54+00:00",
    "rescan_count": 0,
}

INCONCLUSIVE_ROW = {
    **CACHED_ROW,
    "ingredients": [],
    "other_concerns": [],
    "confidence": 20,
}


def _jwt_ctx() -> AuthContext:
    return AuthContext(
        user_id=uuid4(), auth_id=uuid4(), tier="free",
        credits_remaining=15, is_api_key=False,
    )


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[get_auth_context] = _jwt_ctx
    yield
    app.dependency_overrides.clear()


def _probe(url: str = CACHED_ROW["product_url"]):
    return client.get("/api/analyze/cached", params={"product_url": url})


def _mock_db(row):
    m = patch("src.api.routes.analyze.db")
    mock = m.start()
    mock.is_available = True
    mock.generate_url_hash.return_value = "hash123"
    mock.get_cached_analysis = AsyncMock(return_value=row)
    mock.get_cached_reviews = AsyncMock(return_value=None)
    mock.get_or_create_anonymous_user = AsyncMock(return_value=uuid4())
    mock.log_search = AsyncMock(return_value=True)
    return m


def test_hit_returns_cached_analysis():
    m = _mock_db(CACHED_ROW)
    try:
        resp = _probe()
    finally:
        m.stop()
    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is True
    assert body["analysis"]["product_name"] == "Aviator Sunglasses"
    assert body["url_hash"] == "hash123"


def test_miss_returns_404():
    m = _mock_db(None)
    try:
        resp = _probe()
    finally:
        m.stop()
    assert resp.status_code == 404


def test_rescannable_inconclusive_row_is_a_miss():
    # The probe must NOT serve a rescan-eligible inconclusive row — a 404 makes
    # the client do the full capture, which gives the rescan real page HTML.
    m = _mock_db(INCONCLUSIVE_ROW)
    try:
        resp = _probe()
    finally:
        m.stop()
    assert resp.status_code == 404
