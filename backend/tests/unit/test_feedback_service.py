"""Unit tests for the analysis-feedback service.

Mirrors ``test_referral_service.py`` / ``test_feature_service.py``: the service
talks to Supabase through the global ``db`` singleton, replaced here with a
hand-rolled fake that captures inserts (and can be made to raise) so the pure
persistence logic is exercised with no network or real client.
"""

from collections import defaultdict, deque
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.infrastructure import feedback_service


# ---------------------------------------------------------------------------
# Fake Supabase query builder (insert only)
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, store, table):
        self._store = store
        self._table = table
        self._op = "select"
        self._payload = None

    def select(self, *args, **kwargs):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def eq(self, *args, **kwargs):
        return self

    def execute(self):
        return self._store.handle(self._table, self._op, self._payload)


class _FakeClient:
    def __init__(self, store):
        self._store = store

    def table(self, name):
        return _FakeQuery(self._store, name)


class FakeStore:
    """Captures inserts; an insert returns the next queued row-set (defaulting to
    echoing its payload). Set ``insert_error`` to make the next insert raise."""

    def __init__(self):
        self.insert_returns = defaultdict(deque)
        self.inserted = []       # list of (table, payload)
        self.insert_error = None

    def queue_insert_return(self, table, rows):
        self.insert_returns[table].append(rows)

    def handle(self, table, op, payload):
        if op == "insert":
            if self.insert_error is not None:
                raise self.insert_error
            self.inserted.append((table, payload))
            rows = (
                self.insert_returns[table].popleft()
                if self.insert_returns[table]
                else [payload]
            )
            return _FakeResult(rows)
        raise AssertionError(f"unexpected op {op!r}")


@pytest.fixture
def store(monkeypatch):
    s = FakeStore()
    monkeypatch.setattr(
        feedback_service, "db",
        SimpleNamespace(is_available=True, client=_FakeClient(s)),
    )
    return s


@pytest.fixture
def unavailable_db(monkeypatch):
    monkeypatch.setattr(
        feedback_service, "db", SimpleNamespace(is_available=False, client=None)
    )


# ---------------------------------------------------------------------------
# add_feedback
# ---------------------------------------------------------------------------

def test_add_feedback_inserts_row_with_all_fields(store):
    uid = uuid4()
    ok = feedback_service.add_feedback(uid, "hash123", "up", ["Accurate"], None)

    assert ok is True
    table, payload = store.inserted[0]
    assert table == "analysis_feedback"
    assert payload == {
        "user_id": str(uid),
        "url_hash": "hash123",
        "rating": "up",
        "reasons": ["Accurate"],
        "comment": None,
    }


def test_add_feedback_stores_comment_for_bug(store):
    ok = feedback_service.add_feedback(
        uuid4(), "h", "bug", [], "something is genuinely broken here"
    )
    assert ok is True
    _, payload = store.inserted[0]
    assert payload["rating"] == "bug"
    assert payload["reasons"] == []
    assert payload["comment"] == "something is genuinely broken here"


def test_add_feedback_returns_false_when_db_unavailable(unavailable_db):
    assert feedback_service.add_feedback(uuid4(), "h", "up", [], None) is False


def test_add_feedback_returns_false_on_exception(store):
    store.insert_error = RuntimeError("insert failed")
    assert feedback_service.add_feedback(uuid4(), "h", "down", [], None) is False
    assert store.inserted == []


def test_add_feedback_returns_false_when_insert_returns_no_rows(store):
    store.queue_insert_return("analysis_feedback", [])  # insert returned nothing
    assert feedback_service.add_feedback(uuid4(), "h", "up", [], None) is False
