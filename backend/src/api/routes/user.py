"""User profile API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..auth import get_auth_context, AuthContext

router = APIRouter()


class UserProfileResponse(BaseModel):
    user_id: str
    auth_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    tier: str
    credits_remaining: int


@router.get("/user/me", response_model=UserProfileResponse)
async def get_my_profile(
    auth: AuthContext = Depends(get_auth_context),
):
    """Get current user's profile.

    Auto-creates the user on first JWT request (handled in auth layer).
    Returns 401 for legacy API key callers.
    """
    if auth.is_api_key:
        raise HTTPException(
            status_code=401,
            detail="This endpoint requires user authentication (JWT)",
        )
    if not auth.user_id or not auth.auth_id:
        raise HTTPException(status_code=401, detail="User not found")

    # Fetch profile details from DB
    from ...infrastructure.database import db

    if not db.is_available:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        resp = db.client.table("users").select(
            "email, display_name, avatar_url"
        ).eq("id", str(auth.user_id)).execute()

        profile = resp.data[0] if resp.data else {}

        return UserProfileResponse(
            user_id=str(auth.user_id),
            auth_id=str(auth.auth_id),
            email=profile.get("email"),
            display_name=profile.get("display_name"),
            avatar_url=profile.get("avatar_url"),
            tier=auth.tier,
            credits_remaining=auth.credits_remaining,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch profile")
