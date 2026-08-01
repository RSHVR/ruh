"""Credit management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..auth import get_auth_context, AuthContext
from ...domain.quality import is_inconclusive_analysis
from ...infrastructure import credit_service
from ...infrastructure.database import db

router = APIRouter()


class CreditBalanceResponse(BaseModel):
    tier: str
    credits_remaining: int  # -1 for unlimited
    monthly_credits: int
    total_used_this_cycle: int
    cycle_end: Optional[str] = None


class DeductRequest(BaseModel):
    url_hash: str


class DeductResponse(BaseModel):
    success: bool
    credits_remaining: int
    already_unlocked: bool
    is_unlimited: bool
    # False when the unlock was free because the analysis was inconclusive —
    # charging for an empty detail view is a trust-destroying trade.
    charged: bool = True
    free_reason: Optional[str] = None


class CheckUnlockResponse(BaseModel):
    unlocked: bool
    tier: str
    credits_remaining: int


def _require_jwt_user(auth: AuthContext) -> AuthContext:
    """Raise 401 if the caller is using a legacy API key (no user identity)."""
    if auth.is_api_key:
        raise HTTPException(
            status_code=401,
            detail="This endpoint requires user authentication (JWT)",
        )
    if not auth.user_id:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )
    return auth


@router.get("/credits/me", response_model=CreditBalanceResponse)
async def get_my_credits(
    auth: AuthContext = Depends(get_auth_context),
):
    """Get current user's credit balance and tier info."""
    auth = _require_jwt_user(auth)

    info = credit_service.get_user_credits(auth.user_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Credit info not found")

    return CreditBalanceResponse(
        tier=info.tier,
        credits_remaining=info.credits_remaining,
        monthly_credits=info.monthly_credits,
        total_used_this_cycle=info.total_used_this_cycle,
        cycle_end=info.cycle_end,
    )


@router.post("/credits/deduct", response_model=DeductResponse)
async def deduct_credit(
    body: DeductRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    """Spend 1 credit to unlock a product's detailed analysis.

    Idempotent: if the product is already unlocked, no credit is deducted.
    """
    auth = _require_jwt_user(auth)

    # Inconclusive analyses unlock for free — the detail view has nothing
    # worth paying for (no ingredients, no findings, or rock-bottom
    # confidence). Failure to load the row falls through to normal charging.
    try:
        stored = await db.get_cached_analysis(body.url_hash)
    except Exception:
        stored = None
    if stored is not None and is_inconclusive_analysis(stored):
        already = credit_service.is_analysis_unlocked(auth.user_id, body.url_hash)
        if not already:
            credit_service.free_unlock(auth.user_id, body.url_hash)
        return DeductResponse(
            success=True,
            credits_remaining=auth.credits_remaining,
            already_unlocked=already,
            is_unlimited=auth.tier == "unlimited",
            charged=False,
            free_reason="inconclusive",
        )

    result = credit_service.deduct_credit(auth.user_id, body.url_hash)

    if not result.success and not result.already_unlocked and not result.is_unlimited:
        raise HTTPException(
            status_code=402,
            detail="No credits remaining",
        )

    return DeductResponse(
        success=result.success,
        credits_remaining=result.credits_remaining,
        already_unlocked=result.already_unlocked,
        is_unlimited=result.is_unlimited,
    )


@router.get("/credits/check/{url_hash}", response_model=CheckUnlockResponse)
async def check_unlock(
    url_hash: str,
    auth: AuthContext = Depends(get_auth_context),
):
    """Check if a product is already unlocked and return credit balance."""
    auth = _require_jwt_user(auth)

    unlocked = (
        auth.tier == "unlimited"
        or credit_service.is_analysis_unlocked(auth.user_id, url_hash)
    )

    return CheckUnlockResponse(
        unlocked=unlocked,
        tier=auth.tier,
        credits_remaining=auth.credits_remaining,
    )
