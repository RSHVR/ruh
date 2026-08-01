"""Referral program API endpoints.

Users invite friends by email and earn credits once an invited email signs up
and completes their first analysis (credited server-side via the
``process_referral_conversion`` RPC fired from the analyze path — not here).
All endpoints require JWT auth (legacy API-key callers get 401), mirroring the
feature-board and credit routes.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth import get_auth_context, AuthContext
from ...infrastructure import referral_service
from ...infrastructure.referral_service import ReferralSummary

router = APIRouter()

# Per-module limiter, matching the pattern in features.py / analyze.py.
limiter = Limiter(key_func=get_remote_address)

# Max invites accepted in a single POST call.
MAX_EMAILS_PER_CALL = 20

# Max referrals a single referrer can be credited for (mirrors the SQL cap in
# process_referral_conversion). Surfaced so the client can show progress.
CREDITED_CAP = 5


class AddReferralsRequest(BaseModel):
    emails: List[str] = Field(..., min_length=1, max_length=MAX_EMAILS_PER_CALL)


class ReferralItemResponse(BaseModel):
    invited_email: str
    status: str
    created_at: str


class ReferralSummaryResponse(BaseModel):
    invited: int
    signed_up: int
    credited: int
    credited_cap: int = CREDITED_CAP


class AddReferralsResponse(BaseModel):
    added: int
    skipped: int
    summary: ReferralSummaryResponse


class ListReferralsResponse(BaseModel):
    referrals: List[ReferralItemResponse]
    summary: ReferralSummaryResponse


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


def _summary_response(summary: ReferralSummary) -> ReferralSummaryResponse:
    return ReferralSummaryResponse(
        invited=summary.invited,
        signed_up=summary.signed_up,
        credited=summary.credited,
    )


@router.get("/referrals", response_model=ListReferralsResponse)
@limiter.limit("20/minute")
async def list_referrals(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    """List the caller's invites (newest first) with per-status counts."""
    auth = _require_jwt_user(auth)
    listing = referral_service.list_referrals(auth.user_id)
    return ListReferralsResponse(
        referrals=[
            ReferralItemResponse(
                invited_email=i.invited_email,
                status=i.status,
                created_at=i.created_at,
            )
            for i in listing.referrals
        ],
        summary=_summary_response(listing.summary),
    )


@router.post("/referrals", response_model=AddReferralsResponse)
@limiter.limit("20/minute")
async def create_referrals(
    request: Request,
    body: AddReferralsRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    """Record 1-20 email invites, returning added/skipped counts + current summary.

    Invalid addresses, intra-batch duplicates, the caller's own email, and
    already-invited addresses are skipped rather than rejecting the whole call.
    """
    auth = _require_jwt_user(auth)
    result = referral_service.add_referrals(auth.user_id, body.emails)
    listing = referral_service.list_referrals(auth.user_id)
    return AddReferralsResponse(
        added=result["added"],
        skipped=result["skipped"],
        summary=_summary_response(listing.summary),
    )
