"""Credit and tier management service.

All credit mutations go through Supabase RPCs to ensure atomicity.
This service is the single entry point for credit-related operations.
"""

import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from .database import db

logger = logging.getLogger(__name__)


@dataclass
class CreditInfo:
    """Snapshot of a user's credit state."""
    tier: str
    credits_remaining: int  # -1 for unlimited
    monthly_credits: int
    total_used_this_cycle: int
    cycle_end: Optional[str] = None


@dataclass
class DeductResult:
    """Result of a credit deduction attempt."""
    success: bool
    credits_remaining: int
    already_unlocked: bool
    is_unlimited: bool


def get_user_credits(user_id: UUID) -> Optional[CreditInfo]:
    """Fetch current credit balance and tier for a user."""
    if not db.is_available:
        return None

    try:
        tier_resp = db.client.table("user_tiers").select(
            "tier, monthly_credits"
        ).eq("user_id", str(user_id)).execute()

        credit_resp = db.client.table("credit_ledger").select(
            "credits_remaining, total_used_this_cycle, cycle_end"
        ).eq("user_id", str(user_id)).execute()

        if not tier_resp.data:
            return None

        tier_row = tier_resp.data[0]
        credit_row = credit_resp.data[0] if credit_resp.data else {}

        tier = tier_row["tier"]
        credits = -1 if tier == "unlimited" else credit_row.get("credits_remaining", 0)

        return CreditInfo(
            tier=tier,
            credits_remaining=credits,
            monthly_credits=tier_row["monthly_credits"],
            total_used_this_cycle=credit_row.get("total_used_this_cycle", 0),
            cycle_end=credit_row.get("cycle_end"),
        )
    except Exception as e:
        logger.error("Failed to get user credits: %s", e)
        return None


def deduct_credit(user_id: UUID, url_hash: str) -> DeductResult:
    """Atomically deduct one credit for viewing a product's details.

    Calls the deduct_credit PostgreSQL RPC which handles:
    - Unlimited tier bypass
    - Already-unlocked check
    - Atomic balance decrement with row lock
    - Transaction + unlock recording
    """
    if not db.is_available:
        return DeductResult(success=False, credits_remaining=0,
                            already_unlocked=False, is_unlimited=False)

    try:
        resp = db.client.rpc("deduct_credit", {
            "p_user_id": str(user_id),
            "p_url_hash": url_hash,
        }).execute()

        if not resp.data:
            return DeductResult(success=False, credits_remaining=0,
                                already_unlocked=False, is_unlimited=False)

        row = resp.data[0]
        return DeductResult(
            success=row["success"],
            credits_remaining=row["credits_remaining"],
            already_unlocked=row["already_unlocked"],
            is_unlimited=row["is_unlimited"],
        )
    except Exception as e:
        logger.error("Failed to deduct credit: %s", e)
        return DeductResult(success=False, credits_remaining=0,
                            already_unlocked=False, is_unlimited=False)


def free_unlock(user_id: UUID, url_hash: str) -> bool:
    """Record an unlock WITHOUT charging a credit.

    Used when the stored analysis is inconclusive (see domain.quality) —
    charging for an empty detail view is a trust-destroying trade. Idempotent
    via the UNIQUE(user_id, url_hash) constraint (conflicts are ignored).
    """
    if not db.is_available:
        return False

    try:
        db.client.table("unlocked_analyses").upsert(
            {"user_id": str(user_id), "url_hash": url_hash},
            on_conflict="user_id,url_hash",
            ignore_duplicates=True,
        ).execute()
        return True
    except Exception as e:
        logger.error("Failed to record free unlock: %s", e)
        return False


def is_analysis_unlocked(user_id: UUID, url_hash: str) -> bool:
    """Check if a user has already unlocked a product's detailed view."""
    if not db.is_available:
        return False

    try:
        resp = db.client.table("unlocked_analyses").select("id").eq(
            "user_id", str(user_id)
        ).eq("url_hash", url_hash).execute()
        return bool(resp.data)
    except Exception as e:
        logger.error("Failed to check unlock status: %s", e)
        return False


def get_or_create_user_from_auth(
    auth_id: str,
    email: str = "",
    display_name: str = "",
    avatar_url: str = "",
    auth_provider: str = "",
) -> Optional[UUID]:
    """Ensure a user row exists for the given Supabase Auth ID.

    Creates user + tier + credit ledger on first login.
    Returns the internal user_id.
    """
    if not db.is_available:
        return None

    try:
        # Check if user exists
        resp = db.client.table("users").select("id").eq(
            "auth_id", auth_id
        ).execute()

        if resp.data:
            return UUID(resp.data[0]["id"])

        # Create new user
        user_data = {
            "auth_id": auth_id,
            "email": email,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "auth_provider": auth_provider,
        }
        insert_resp = db.client.table("users").insert(user_data).execute()
        user_id = UUID(insert_resp.data[0]["id"])

        # Initialize tier and credits via RPC
        db.client.rpc("initialize_user_credits", {
            "p_user_id": str(user_id),
        }).execute()

        logger.info("Created user %s for auth_id %s", user_id, auth_id)
        return user_id

    except Exception as e:
        logger.error("Failed to get/create user from auth: %s", e)
        return None
