"""Unit tests for the feedback request-validation rules.

These exercise the ``FeedbackRequest`` pydantic model directly (no HTTP) so the
rating / reasons / comment rules are pinned as pure units. The route relies on
this model, so a raised ``ValidationError`` here is what becomes a 422 there.
"""

import pytest
from pydantic import ValidationError

from src.api.routes.feedback import (
    FeedbackRequest,
    UP_REASONS,
    DOWN_REASONS,
    BUG_COMMENT_MIN_CHARS,
)


def _mk(**overrides) -> FeedbackRequest:
    base = {"url_hash": "h", "rating": "up", "reasons": [], "comment": None}
    base.update(overrides)
    return FeedbackRequest(**base)


# ---------------------------------------------------------------------------
# Canonical constants (the extension mirrors these verbatim)
# ---------------------------------------------------------------------------

def test_canonical_reason_lists_are_exact():
    assert UP_REASONS == [
        "Accurate", "Clear & simple", "Caught something",
        "Good sources", "Saved me time",
    ]
    assert DOWN_REASONS == [
        "Looks wrong", "Confusing", "Missed something",
        "Wrong product", "Not enough detail",
    ]
    assert BUG_COMMENT_MIN_CHARS == 25


# ---------------------------------------------------------------------------
# rating
# ---------------------------------------------------------------------------

def test_invalid_rating_rejected():
    with pytest.raises(ValidationError):
        _mk(rating="sideways")


# ---------------------------------------------------------------------------
# bug: no reasons, comment required + >= 25 non-whitespace chars
# ---------------------------------------------------------------------------

def test_bug_requires_a_comment():
    with pytest.raises(ValidationError):
        _mk(rating="bug", reasons=[], comment=None)


def test_bug_rejects_short_comment():
    with pytest.raises(ValidationError):
        _mk(rating="bug", comment="too short")  # 8 non-whitespace chars


def test_bug_rejects_comment_padded_with_whitespace():
    # 24 letters spread across spaces -> 24 non-whitespace chars -> rejected,
    # proving total length (28) is not what's counted.
    with pytest.raises(ValidationError):
        _mk(rating="bug", comment="abcde fghij klmno pqrst uvwx")


def test_bug_accepts_exactly_min_comment():
    fb = _mk(rating="bug", comment="abcdefghijklmnopqrstuvwxy")  # 25 chars
    assert fb.rating == "bug"


def test_bug_accepts_min_comment_with_whitespace():
    # 25 letters + spaces (29 total) -> 25 non-whitespace chars -> accepted.
    comment = "abcde fghij klmno pqrst uvwxy"
    fb = _mk(rating="bug", comment=comment)
    assert fb.comment == comment


def test_bug_rejects_reasons_present():
    with pytest.raises(ValidationError):
        _mk(rating="bug", reasons=["Accurate"], comment="abcdefghijklmnopqrstuvwxy")


# ---------------------------------------------------------------------------
# up / down: reasons optional, must be a subset of the canonical list
# ---------------------------------------------------------------------------

def test_up_accepts_valid_reason_subset():
    fb = _mk(rating="up", reasons=["Accurate", "Good sources"])
    assert fb.reasons == ["Accurate", "Good sources"]


def test_up_rejects_unknown_reason():
    with pytest.raises(ValidationError):
        _mk(rating="up", reasons=["Nonexistent"])


def test_up_rejects_down_reason():
    # A valid down-reason is not valid for an up rating.
    with pytest.raises(ValidationError):
        _mk(rating="up", reasons=["Looks wrong"])


def test_down_accepts_valid_reason_subset():
    fb = _mk(rating="down", reasons=["Looks wrong", "Confusing"])
    assert fb.reasons == ["Looks wrong", "Confusing"]


def test_down_rejects_up_reason():
    with pytest.raises(ValidationError):
        _mk(rating="down", reasons=["Accurate"])


def test_up_allows_empty_reasons_and_no_comment():
    fb = _mk(rating="up", reasons=[], comment=None)
    assert fb.reasons == []
    assert fb.comment is None


def test_down_allows_optional_comment():
    fb = _mk(rating="down", reasons=[], comment="short is fine here")
    assert fb.comment == "short is fine here"
