"""Analysis-feedback storage service.

Same module-function + global ``db`` singleton style as ``referral_service`` /
``feature_service``. Users rate an analysis (thumbs up / down / bug report) from
the side panel, optionally with reason badges and/or a comment; every submission
is stored. Validation of the rating / reasons / comment rules lives in the
route's request model — this layer just persists what it is handed.
"""

import logging
from typing import List, Optional
from uuid import UUID

from .database import db

logger = logging.getLogger(__name__)


def add_feedback(
    user_id: UUID,
    url_hash: str,
    rating: str,
    reasons: List[str],
    comment: Optional[str],
) -> bool:
    """Store one feedback submission.

    Returns True if the row was written, False if the DB is unavailable or the
    insert failed. Never raises — feedback submission is best-effort.
    """
    if not db.is_available:
        return False

    try:
        resp = db.client.table("analysis_feedback").insert({
            "user_id": str(user_id),
            "url_hash": url_hash,
            "rating": rating,
            "reasons": reasons,
            "comment": comment,
        }).execute()
        return bool(resp.data)
    except Exception as e:
        logger.error("Failed to add feedback: %s", e)
        return False
