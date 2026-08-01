"""Feature-request board API endpoints.

A lightweight public board where authenticated users submit feature requests and
upvote them. All endpoints require JWT auth (legacy API-key callers get 401),
mirroring the credit routes.
"""

from dataclasses import asdict
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth import get_auth_context, AuthContext
from ...infrastructure import feature_service

router = APIRouter()

# Per-module limiter, matching the pattern in analyze.py.
limiter = Limiter(key_func=get_remote_address)

# Max feature submissions per user per day.
MAX_SUBMISSIONS_PER_DAY = 5


class FeatureResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    status: str
    created_at: str
    vote_count: int
    voted_by_me: bool


class CreateFeatureRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class VoteResponse(BaseModel):
    voted: bool
    vote_count: int


def _require_jwt_user(auth: AuthContext) -> AuthContext:
    """Raise 401 if the caller is using a legacy API key (no user identity)."""
    if auth.is_api_key:
        raise HTTPException(
            status_code=401,
            detail="This endpoint requires user authentication (JWT)",
        )
    if not auth.user_id:
        raise HTTPException(status_code=401, detail="User not found")
    return auth


@router.get("/features", response_model=List[FeatureResponse])
@limiter.limit("30/minute")
async def list_features(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """List non-hidden feature requests, most-voted first (max 50)."""
    auth = _require_jwt_user(auth)
    items = feature_service.list_features(auth.user_id)
    return [FeatureResponse(**asdict(item)) for item in items]


@router.post("/features", response_model=FeatureResponse)
@limiter.limit("30/minute")
async def create_feature(
    request: Request,
    body: CreateFeatureRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    """Submit a feature request (auto-voted by the submitter).

    Enforces a per-user cap of 5 submissions per day (429 when exceeded).
    """
    auth = _require_jwt_user(auth)

    if feature_service.count_user_features_today(auth.user_id) >= MAX_SUBMISSIONS_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail=f"Daily submission limit reached ({MAX_SUBMISSIONS_PER_DAY} per day)",
        )

    item = feature_service.create_feature(auth.user_id, body.title, body.description)
    if item is None:
        raise HTTPException(status_code=503, detail="Could not create feature request")

    return FeatureResponse(**asdict(item))


@router.post("/features/{feature_id}/vote", response_model=VoteResponse)
@limiter.limit("30/minute")
async def vote_feature(
    request: Request,
    feature_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
):
    """Toggle the current user's vote on a feature request."""
    auth = _require_jwt_user(auth)
    result = feature_service.toggle_vote(auth.user_id, feature_id)
    return VoteResponse(voted=result.voted, vote_count=result.vote_count)
