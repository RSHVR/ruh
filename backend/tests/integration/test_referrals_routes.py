"""Route tests for the referral program.

Mirrors ``test_features_routes.py``: the full FastAPI app is imported so
routing/serialization is exercised end to end. ``get_auth_context`` is
overridden to inject a JWT user or an API-key caller, and the service layer is
patched so no real Supabase client is touched.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.auth import get_auth_context, AuthContext
from src.infrastructure import referral_service
from src.infrastructure.referral_service import (
    ReferralItem,
    ReferralListing,
    ReferralSummary,
)

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


def _listing(**overrides) -> ReferralListing:
    summary = ReferralSummary(
        invited=overrides.get("invited", 2),
        signed_up=overrides.get("signed_up", 1),
        credited=overrides.get("credited", 1),
    )
    referrals = overrides.get("referrals", [
        ReferralItem(invited_email="a@x.com", status="invited",
                     created_at="2026-07-01T00:00:00+00:00"),
    ])
    return ReferralListing(referrals=referrals, summary=summary)


# ---------------------------------------------------------------------------
# GET /api/referrals
# ---------------------------------------------------------------------------

def test_list_referrals_rejects_api_key_caller():
    _use_api_key()
    resp = client.get("/api/referrals")
    assert resp.status_code == 401


def test_list_referrals_returns_summary_shape():
    _use_jwt()
    with patch.object(referral_service, "list_referrals", return_value=_listing()):
        resp = client.get("/api/referrals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["referrals"][0]["invited_email"] == "a@x.com"
    assert body["summary"] == {
        "invited": 2, "signed_up": 1, "credited": 1, "credited_cap": 5,
    }


# ---------------------------------------------------------------------------
# POST /api/referrals
# ---------------------------------------------------------------------------

def test_add_referrals_rejects_api_key_caller():
    _use_api_key()
    resp = client.post("/api/referrals", json={"emails": ["a@x.com"]})
    assert resp.status_code == 401


def test_add_referrals_success():
    _use_jwt()
    with patch.object(referral_service, "add_referrals",
                      return_value={"added": 2, "skipped": 1}), \
         patch.object(referral_service, "list_referrals", return_value=_listing()):
        resp = client.post(
            "/api/referrals",
            json={"emails": ["a@x.com", "b@x.com", "a@x.com"]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["added"] == 2
    assert body["skipped"] == 1
    assert body["summary"]["invited"] == 2
    assert body["summary"]["credited_cap"] == 5


def test_add_referrals_rejects_empty_email_list():
    _use_jwt()
    resp = client.post("/api/referrals", json={"emails": []})
    assert resp.status_code == 422


def test_add_referrals_rejects_too_many_emails():
    _use_jwt()
    resp = client.post(
        "/api/referrals",
        json={"emails": [f"user{i}@x.com" for i in range(21)]},
    )
    assert resp.status_code == 422
