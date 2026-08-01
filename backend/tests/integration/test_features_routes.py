"""Route tests for the feature-request board.

The full FastAPI app is imported so routing/serialization is exercised end to
end. ``get_auth_context`` is overridden to inject a JWT user or an API-key
caller, and the service layer is patched so no real Supabase client is touched.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.auth import get_auth_context, AuthContext
from src.infrastructure import feature_service
from src.infrastructure.feature_service import FeatureItem, VoteResult

client = TestClient(app)


def _jwt_ctx() -> AuthContext:
    return AuthContext(
        user_id=uuid4(), auth_id=uuid4(), tier="free",
        credits_remaining=15, is_api_key=False,
    )


def _api_key_ctx() -> AuthContext:
    return AuthContext(is_api_key=True)


def _use_jwt():
    app.dependency_overrides[get_auth_context] = _jwt_ctx


def _use_api_key():
    app.dependency_overrides[get_auth_context] = _api_key_ctx


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _sample_item(**overrides) -> FeatureItem:
    base = dict(
        id=str(uuid4()), user_id=str(uuid4()), title="Dark mode",
        description="please add it", status="open",
        created_at="2026-07-20T00:00:00+00:00", vote_count=3, voted_by_me=True,
    )
    base.update(overrides)
    return FeatureItem(**base)


# ---------------------------------------------------------------------------
# GET /api/features
# ---------------------------------------------------------------------------

def test_list_features_rejects_api_key_caller():
    _use_api_key()
    resp = client.get("/api/features")
    assert resp.status_code == 401


def test_list_features_returns_items_for_jwt_user():
    _use_jwt()
    with patch.object(feature_service, "list_features", return_value=[_sample_item()]):
        resp = client.get("/api/features")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "Dark mode"
    assert body[0]["vote_count"] == 3
    assert body[0]["voted_by_me"] is True


# ---------------------------------------------------------------------------
# POST /api/features
# ---------------------------------------------------------------------------

def test_create_feature_rejects_api_key_caller():
    _use_api_key()
    resp = client.post("/api/features", json={"title": "New idea"})
    assert resp.status_code == 401


def test_create_feature_success():
    _use_jwt()
    created = _sample_item(title="Bulk export", vote_count=1, voted_by_me=True)
    with patch.object(feature_service, "count_user_features_today", return_value=0), \
         patch.object(feature_service, "create_feature", return_value=created):
        resp = client.post("/api/features", json={"title": "Bulk export"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Bulk export"
    assert body["vote_count"] == 1
    assert body["voted_by_me"] is True


def test_create_feature_rejects_short_title():
    _use_jwt()
    resp = client.post("/api/features", json={"title": "ab"})
    assert resp.status_code == 422


def test_create_feature_rejects_overlong_description():
    _use_jwt()
    resp = client.post(
        "/api/features",
        json={"title": "Valid title", "description": "x" * 501},
    )
    assert resp.status_code == 422


def test_create_feature_enforces_daily_limit():
    _use_jwt()
    with patch.object(feature_service, "count_user_features_today", return_value=5), \
         patch.object(feature_service, "create_feature") as create_mock:
        resp = client.post("/api/features", json={"title": "One too many"})
    assert resp.status_code == 429
    create_mock.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/features/{feature_id}/vote
# ---------------------------------------------------------------------------

def test_vote_rejects_api_key_caller():
    _use_api_key()
    resp = client.post(f"/api/features/{uuid4()}/vote")
    assert resp.status_code == 401


def test_vote_toggles_on():
    _use_jwt()
    with patch.object(feature_service, "toggle_vote",
                      return_value=VoteResult(voted=True, vote_count=1)):
        resp = client.post(f"/api/features/{uuid4()}/vote")
    assert resp.status_code == 200
    assert resp.json() == {"voted": True, "vote_count": 1}


def test_vote_toggles_off():
    _use_jwt()
    with patch.object(feature_service, "toggle_vote",
                      return_value=VoteResult(voted=False, vote_count=0)):
        resp = client.post(f"/api/features/{uuid4()}/vote")
    assert resp.status_code == 200
    assert resp.json() == {"voted": False, "vote_count": 0}


def test_vote_rejects_malformed_feature_id():
    _use_jwt()
    resp = client.post("/api/features/not-a-uuid/vote")
    assert resp.status_code == 422
