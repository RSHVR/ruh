"""Route tests for the analysis-feedback endpoint.

Mirrors ``test_referrals_routes.py``: the full FastAPI app is imported so
routing/validation/serialization is exercised end to end. ``get_auth_context``
is overridden to inject a JWT user or an API-key caller, and the service layer
is patched so no real Supabase client is touched.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.auth import get_auth_context, AuthContext
from src.infrastructure import feedback_service

client = TestClient(app)

# A body that passes all validation rules (bug report with a >=25 char comment).
VALID_BUG = {
    "url_hash": "abc123",
    "rating": "bug",
    "reasons": [],
    "comment": "the score here is totally wrong",
}


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


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_feedback_rejects_api_key_caller():
    _use_api_key()
    resp = client.post("/api/feedback", json=VALID_BUG)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation -> 422
# ---------------------------------------------------------------------------

def test_feedback_bug_comment_too_short_returns_422():
    _use_jwt()
    resp = client.post("/api/feedback", json={
        "url_hash": "h", "rating": "bug", "reasons": [], "comment": "too short",
    })
    assert resp.status_code == 422


def test_feedback_bad_reason_returns_422():
    _use_jwt()
    resp = client.post("/api/feedback", json={
        "url_hash": "h", "rating": "up", "reasons": ["Not a real reason"],
    })
    assert resp.status_code == 422


def test_feedback_invalid_rating_returns_422():
    _use_jwt()
    resp = client.post("/api/feedback", json={
        "url_hash": "h", "rating": "meh", "reasons": [],
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Success -> {"ok": true}
# ---------------------------------------------------------------------------

def test_feedback_success_returns_ok():
    _use_jwt()
    with patch.object(feedback_service, "add_feedback", return_value=True) as m:
        resp = client.post("/api/feedback", json={
            "url_hash": "h", "rating": "up", "reasons": ["Accurate"],
        })
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    m.assert_called_once()


def test_feedback_bug_success_returns_ok():
    _use_jwt()
    with patch.object(feedback_service, "add_feedback", return_value=True):
        resp = client.post("/api/feedback", json=VALID_BUG)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_feedback_service_failure_returns_503():
    _use_jwt()
    with patch.object(feedback_service, "add_feedback", return_value=False):
        resp = client.post("/api/feedback", json={
            "url_hash": "h", "rating": "down", "reasons": [],
        })
    assert resp.status_code == 503
