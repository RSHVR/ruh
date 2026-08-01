"""Feature-request board service.

Single entry point for the feature board's data access. Follows the same
module-function + global ``db`` singleton style as ``credit_service`` so routes
depend on this thin layer rather than the Supabase client directly.

Vote counts are aggregated in Python — cheap at beta scale and keeps the query
surface small (two selects for the list view).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from .database import db

logger = logging.getLogger(__name__)


@dataclass
class FeatureItem:
    """A feature request enriched with vote aggregates for the current user."""
    id: str
    user_id: str
    title: str
    description: Optional[str]
    status: str
    created_at: str
    vote_count: int
    voted_by_me: bool


@dataclass
class VoteResult:
    """Outcome of toggling a vote."""
    voted: bool       # True if the user now has a vote, False if it was removed
    vote_count: int   # Total votes on the feature after the toggle


def list_features(user_id: UUID, limit: int = 50) -> List[FeatureItem]:
    """Return non-hidden feature requests, most-voted first (recency breaks ties).

    ``vote_count`` and ``voted_by_me`` are computed from a single votes read.
    """
    if not db.is_available:
        return []

    try:
        features_resp = db.client.table("feature_requests").select(
            "id, user_id, title, description, status, created_at"
        ).eq("hidden", False).execute()
        features = features_resp.data or []
        if not features:
            return []

        votes_resp = db.client.table("feature_votes").select(
            "feature_id, user_id"
        ).execute()
        votes = votes_resp.data or []

        uid = str(user_id)
        counts: dict[str, int] = {}
        voted: set[str] = set()
        for vote in votes:
            fid = vote["feature_id"]
            counts[fid] = counts.get(fid, 0) + 1
            if vote["user_id"] == uid:
                voted.add(fid)

        items = [
            FeatureItem(
                id=f["id"],
                user_id=f["user_id"],
                title=f["title"],
                description=f.get("description"),
                status=f["status"],
                created_at=f["created_at"],
                vote_count=counts.get(f["id"], 0),
                voted_by_me=f["id"] in voted,
            )
            for f in features
        ]
        # votes desc, then created_at desc — ISO-8601 strings sort chronologically.
        items.sort(key=lambda i: (i.vote_count, i.created_at), reverse=True)
        return items[:limit]
    except Exception as e:
        logger.error("Failed to list features: %s", e)
        return []


def create_feature(
    user_id: UUID,
    title: str,
    description: Optional[str] = None,
) -> Optional[FeatureItem]:
    """Create a feature request and auto-vote it for the submitter."""
    if not db.is_available:
        return None

    try:
        insert_resp = db.client.table("feature_requests").insert({
            "user_id": str(user_id),
            "title": title,
            "description": description,
        }).execute()

        if not insert_resp.data:
            return None
        row = insert_resp.data[0]

        # Submitter auto-votes their own request.
        db.client.table("feature_votes").insert({
            "feature_id": row["id"],
            "user_id": str(user_id),
        }).execute()

        return FeatureItem(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            description=row.get("description"),
            status=row["status"],
            created_at=row["created_at"],
            vote_count=1,
            voted_by_me=True,
        )
    except Exception as e:
        logger.error("Failed to create feature: %s", e)
        return None


def toggle_vote(user_id: UUID, feature_id: UUID) -> VoteResult:
    """Toggle the current user's vote on a feature and return the new tally."""
    if not db.is_available:
        return VoteResult(voted=False, vote_count=0)

    uid = str(user_id)
    fid = str(feature_id)
    try:
        existing = db.client.table("feature_votes").select("id").eq(
            "feature_id", fid
        ).eq("user_id", uid).execute()

        if existing.data:
            db.client.table("feature_votes").delete().eq(
                "feature_id", fid
            ).eq("user_id", uid).execute()
            voted = False
        else:
            db.client.table("feature_votes").insert({
                "feature_id": fid,
                "user_id": uid,
            }).execute()
            voted = True

        count_resp = db.client.table("feature_votes").select("id").eq(
            "feature_id", fid
        ).execute()
        return VoteResult(voted=voted, vote_count=len(count_resp.data or []))
    except Exception as e:
        logger.error("Failed to toggle vote: %s", e)
        return VoteResult(voted=False, vote_count=0)


def count_user_features_today(user_id: UUID) -> int:
    """Count feature requests the user has submitted since 00:00 UTC today."""
    if not db.is_available:
        return 0

    try:
        start_of_day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        resp = db.client.table("feature_requests").select("id").eq(
            "user_id", str(user_id)
        ).gte("created_at", start_of_day.isoformat()).execute()
        return len(resp.data or [])
    except Exception as e:
        logger.error("Failed to count user features today: %s", e)
        return 0
