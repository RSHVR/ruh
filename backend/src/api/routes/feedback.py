"""Analysis-feedback API endpoint.

Users rate an analysis with thumbs-up / thumbs-down / bug-report from the side
panel, optionally with reason badges and/or a comment. Every submission is
stored. JWT-only (legacy API-key callers get 401) and rate limited, mirroring
the feature-board / referral routes.

The canonical reason lists are part of the API contract — the extension mirrors
them verbatim, so keep the two sides in sync.
"""

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth import get_auth_context, AuthContext
from ...infrastructure import feedback_service

router = APIRouter()

# Per-module limiter, matching the pattern in referrals.py / features.py.
limiter = Limiter(key_func=get_remote_address)

# Canonical reason badges per rating. The extension mirrors these verbatim;
# update both sides together.
UP_REASONS = [
    "Accurate", "Clear & simple", "Caught something",
    "Good sources", "Saved me time",
]
DOWN_REASONS = [
    "Looks wrong", "Confusing", "Missed something",
    "Wrong product", "Not enough detail",
]
CANONICAL_REASONS = {"up": UP_REASONS, "down": DOWN_REASONS}

# A bug report must carry a substantive comment (measured after stripping all
# whitespace, so padding with spaces does not satisfy it).
BUG_COMMENT_MIN_CHARS = 25


def _non_whitespace_len(text: str) -> int:
    """Count characters in ``text`` after removing all whitespace."""
    return len("".join(text.split()))


class FeedbackRequest(BaseModel):
    url_hash: str
    rating: Literal["up", "down", "bug"]
    reasons: List[str] = Field(default_factory=list)
    comment: Optional[str] = None

    @model_validator(mode="after")
    def _enforce_rating_rules(self) -> "FeedbackRequest":
        if self.rating == "bug":
            # Bug reports: no reason badges; comment required + substantive.
            if self.reasons:
                raise ValueError("reasons must be empty for a bug report")
            if (
                self.comment is None
                or _non_whitespace_len(self.comment) < BUG_COMMENT_MIN_CHARS
            ):
                raise ValueError(
                    f"bug reports require a comment of at least "
                    f"{BUG_COMMENT_MIN_CHARS} non-whitespace characters"
                )
        else:
            # up / down: reasons optional but must come from the canonical list.
            allowed = set(CANONICAL_REASONS[self.rating])
            invalid = [r for r in self.reasons if r not in allowed]
            if invalid:
                raise ValueError(
                    f"invalid reasons for rating '{self.rating}': {invalid}"
                )
        return self


class FeedbackResponse(BaseModel):
    ok: bool


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


@router.post("/feedback", response_model=FeedbackResponse)
@limiter.limit("10/minute")
async def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    """Store a thumbs-up / thumbs-down / bug-report on an analysis."""
    auth = _require_jwt_user(auth)
    ok = feedback_service.add_feedback(
        auth.user_id, body.url_hash, body.rating, body.reasons, body.comment
    )
    if not ok:
        raise HTTPException(status_code=503, detail="Could not store feedback")
    return FeedbackResponse(ok=True)
