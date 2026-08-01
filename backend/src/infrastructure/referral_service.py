"""Referral program service.

Single entry point for the referral feature's data access. Follows the same
module-function + global ``db`` singleton style as ``feature_service`` /
``credit_service`` so routes depend on this thin layer rather than the Supabase
client directly.

Users invite friends by email (unlimited invites, stored). A referrer earns
credits only once an invited email both signs up AND completes their first
analysis — that crediting is done server-side and atomically by the
``process_referral_conversion`` Postgres RPC (migration 016), fired from the
analyze path via :func:`process_conversion`. This module never grants credit
itself; it only records invites and reads state.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from .database import db

logger = logging.getLogger(__name__)

# Rudimentary email shape check — a full RFC 5322 validation is overkill here;
# invites that slip through simply never match a real signup.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class ReferralItem:
    """One invite row, as surfaced to the referrer."""
    invited_email: str
    status: str        # 'invited' | 'signed_up' | 'credited'
    created_at: str


@dataclass
class ReferralSummary:
    """Per-referrer counts by status."""
    invited: int
    signed_up: int
    credited: int


@dataclass
class ReferralListing:
    """A referrer's invites plus aggregate counts."""
    referrals: List[ReferralItem]
    summary: ReferralSummary


def _empty_summary() -> ReferralSummary:
    return ReferralSummary(invited=0, signed_up=0, credited=0)


def _own_email(user_id: str) -> Optional[str]:
    """Return the caller's own email (normalized) to prevent self-referral."""
    try:
        resp = db.client.table("users").select("email").eq("id", user_id).execute()
        if resp.data and resp.data[0].get("email"):
            return resp.data[0]["email"].strip().lower()
    except Exception as e:
        logger.warning("Failed to look up own email for self-referral guard: %s", e)
    return None


def add_referrals(user_id: UUID, emails: List[str]) -> dict:
    """Record invites for ``emails``, returning ``{"added", "skipped"}``.

    Emails are normalized (strip + lowercase) and validated with a rudimentary
    regex. Intra-batch duplicates, invalid addresses, and the caller's own
    email are dropped (counted as skipped). The remaining unique addresses are
    upserted ignoring conflicts, so a friend already invited by this referrer is
    silently skipped rather than duplicated. ``added`` counts only newly stored
    invites.
    """
    if not db.is_available:
        return {"added": 0, "skipped": len(emails)}

    uid = str(user_id)
    own = _own_email(uid)

    seen: set[str] = set()
    valid: List[str] = []
    skipped = 0
    for raw in emails:
        email = (raw or "").strip().lower()
        if not _EMAIL_RE.match(email):
            skipped += 1
            continue
        if own is not None and email == own:  # no self-referral
            skipped += 1
            continue
        if email in seen:  # intra-batch duplicate
            skipped += 1
            continue
        seen.add(email)
        valid.append(email)

    if not valid:
        return {"added": 0, "skipped": skipped}

    try:
        rows = [{"referrer_user_id": uid, "invited_email": e} for e in valid]
        resp = db.client.table("referrals").upsert(
            rows,
            on_conflict="referrer_user_id,invited_email",
            ignore_duplicates=True,
        ).execute()

        # TODO(resend-invites): a later version sends an invite email here (via
        # Resend) for each newly-inserted address in ``resp.data``. Kept out of
        # this version deliberately — invites are stored but not delivered.

        added = len(resp.data or [])
        # Valid addresses that conflicted with an existing invite were ignored.
        skipped += len(valid) - added
        return {"added": added, "skipped": skipped}
    except Exception as e:
        logger.error("Failed to add referrals: %s", e)
        return {"added": 0, "skipped": len(emails)}


def list_referrals(user_id: UUID) -> ReferralListing:
    """Return the referrer's invites (newest first) with per-status counts."""
    if not db.is_available:
        return ReferralListing(referrals=[], summary=_empty_summary())

    try:
        resp = db.client.table("referrals").select(
            "invited_email, status, created_at"
        ).eq("referrer_user_id", str(user_id)).order(
            "created_at", desc=True
        ).execute()
        rows = resp.data or []

        items = [
            ReferralItem(
                invited_email=r["invited_email"],
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
        summary = ReferralSummary(
            invited=sum(1 for r in rows if r["status"] == "invited"),
            signed_up=sum(1 for r in rows if r["status"] == "signed_up"),
            credited=sum(1 for r in rows if r["status"] == "credited"),
        )
        return ReferralListing(referrals=items, summary=summary)
    except Exception as e:
        logger.error("Failed to list referrals: %s", e)
        return ReferralListing(referrals=[], summary=_empty_summary())


def process_conversion(user_id: UUID) -> int:
    """Credit a referrer if ``user_id`` just completed a qualifying first analysis.

    Delegates to the ``process_referral_conversion`` RPC, which is idempotent
    (returns 0 and changes nothing when there is no outstanding invite for this
    user's email). Runs inside the analyze path, so it never raises — any error
    is logged and swallowed. Returns 1 if a referral was credited, else 0.
    """
    if not db.is_available:
        return 0

    try:
        resp = db.client.rpc(
            "process_referral_conversion", {"p_user_id": str(user_id)}
        ).execute()
        return _coerce_rpc_int(resp.data)
    except Exception as e:
        logger.error("Referral conversion failed (non-fatal): %s", e)
        return 0


def _coerce_rpc_int(data) -> int:
    """Normalize a scalar-returning RPC result to an int (0 on anything odd)."""
    try:
        if data is None:
            return 0
        if isinstance(data, bool):
            return int(data)
        if isinstance(data, int):
            return data
        if isinstance(data, list):
            if not data:
                return 0
            first = data[0]
            if isinstance(first, dict):
                return int(next(iter(first.values())))
            return int(first)
        return int(data)
    except (TypeError, ValueError, StopIteration):
        return 0
