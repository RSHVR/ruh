"""Route tests for /api/credits/deduct — the unlock path.

Born from a prod outage (2026-08-01): the free-unlock check called the ASYNC
``db.get_cached_analysis`` without await, so every unlock 500ed while the
suite stayed green (no deduct route test existed). These tests exercise the
real route with an async-mocked cache read, so an unawaited coroutine can
never ship silently again.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.auth import get_auth_context, AuthContext
from src.infrastructure import credit_service
from src.infrastructure.credit_service import DeductResult

client = TestClient(app)

CONCLUSIVE_ROW = {
    "ingredients": ["Aqua", "Glycerin"],
    "allergens_detected": [],
    "pfas_detected": [],
    "other_concerns": [{"name": "Fragrance"}],
    "confidence": 85,
}

INCONCLUSIVE_ROW = {
    "ingredients": [],
    "allergens_detected": [],
    "pfas_detected": [],
    "other_concerns": [],
    "confidence": 30,
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


def _deduct(url_hash: str = "hash123"):
    return client.post("/api/credits/deduct", json={"url_hash": url_hash})


def test_conclusive_analysis_charges_normally():
    with patch("src.api.routes.credits.db") as mock_db, \
         patch.object(credit_service, "deduct_credit") as mock_deduct:
        mock_db.get_cached_analysis = AsyncMock(return_value=CONCLUSIVE_ROW)
        mock_deduct.return_value = DeductResult(
            success=True, credits_remaining=14,
            already_unlocked=False, is_unlimited=False,
        )
        resp = _deduct()
    assert resp.status_code == 200
    body = resp.json()
    assert body["charged"] is True
    assert body["credits_remaining"] == 14
    mock_deduct.assert_called_once()


def test_inconclusive_analysis_unlocks_free():
    with patch("src.api.routes.credits.db") as mock_db, \
         patch.object(credit_service, "deduct_credit") as mock_deduct, \
         patch.object(credit_service, "is_analysis_unlocked", return_value=False), \
         patch.object(credit_service, "free_unlock", return_value=True) as mock_free:
        mock_db.get_cached_analysis = AsyncMock(return_value=INCONCLUSIVE_ROW)
        resp = _deduct()
    assert resp.status_code == 200
    body = resp.json()
    assert body["charged"] is False
    assert body["free_reason"] == "inconclusive"
    mock_deduct.assert_not_called()
    mock_free.assert_called_once()


def test_missing_cache_row_falls_through_to_normal_charge():
    with patch("src.api.routes.credits.db") as mock_db, \
         patch.object(credit_service, "deduct_credit") as mock_deduct:
        mock_db.get_cached_analysis = AsyncMock(return_value=None)
        mock_deduct.return_value = DeductResult(
            success=True, credits_remaining=13,
            already_unlocked=False, is_unlimited=False,
        )
        resp = _deduct()
    assert resp.status_code == 200
    assert resp.json()["charged"] is True


def test_no_credits_still_402s():
    with patch("src.api.routes.credits.db") as mock_db, \
         patch.object(credit_service, "deduct_credit") as mock_deduct:
        mock_db.get_cached_analysis = AsyncMock(return_value=CONCLUSIVE_ROW)
        mock_deduct.return_value = DeductResult(
            success=False, credits_remaining=0,
            already_unlocked=False, is_unlimited=False,
        )
        resp = _deduct()
    assert resp.status_code == 402
