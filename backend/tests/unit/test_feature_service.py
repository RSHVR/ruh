"""Unit tests for the feature-request board service.

The service talks to Supabase through the global ``db`` singleton. These tests
replace that singleton with a hand-rolled fake query builder so we exercise the
pure aggregation / toggle logic without any network or real client.
"""

from collections import defaultdict, deque
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.infrastructure import feature_service


# ---------------------------------------------------------------------------
# Fake Supabase query builder
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Mimics one supabase-py query chain: table(...).select/insert/delete...execute()."""

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

    def delete(self):
        self._op = "delete"
        return self

    # Filters / ordering are no-ops for the fake — logic is verified via the
    # queued results and captured mutations.
    def eq(self, *args, **kwargs):
        return self

    def gte(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        return self._store.handle(self._table, self._op, self._payload)


class _FakeClient:
    def __init__(self, store):
        self._store = store

    def table(self, name):
        return _FakeQuery(self._store, name)


class FakeStore:
    """Drives a fake supabase client.

    Select results are consumed FIFO per table (in the order the code queries
    them). Inserts and deletes are captured for assertions; an insert returns
    the next queued row-set for that table, or echoes its payload by default.
    """

    def __init__(self):
        self.select_queue = defaultdict(deque)
        self.insert_returns = defaultdict(deque)
        self.inserted = []  # list of (table, payload)
        self.deleted = []   # list of table names

    def queue_select(self, table, data):
        self.select_queue[table].append(data)

    def queue_insert_return(self, table, rows):
        self.insert_returns[table].append(rows)

    def handle(self, table, op, payload):
        if op == "select":
            data = self.select_queue[table].popleft() if self.select_queue[table] else []
            return _FakeResult(data)
        if op == "insert":
            self.inserted.append((table, payload))
            rows = (
                self.insert_returns[table].popleft()
                if self.insert_returns[table]
                else [payload]
            )
            return _FakeResult(rows)
        if op == "delete":
            self.deleted.append(table)
            return _FakeResult([])
        raise AssertionError(f"unexpected op {op!r}")


@pytest.fixture
def store(monkeypatch):
    s = FakeStore()
    fake_db = SimpleNamespace(is_available=True, client=_FakeClient(s))
    monkeypatch.setattr(feature_service, "db", fake_db)
    return s


@pytest.fixture
def unavailable_db(monkeypatch):
    monkeypatch.setattr(
        feature_service, "db", SimpleNamespace(is_available=False, client=None)
    )


# ---------------------------------------------------------------------------
# list_features
# ---------------------------------------------------------------------------

def test_list_features_returns_empty_when_db_unavailable(unavailable_db):
    assert feature_service.list_features(uuid4()) == []


def test_list_features_aggregates_votes_and_flags_voted_by_me(store):
    me = uuid4()
    other = uuid4()
    f1, f2 = str(uuid4()), str(uuid4())

    store.queue_select("feature_requests", [
        {"id": f1, "user_id": str(me), "title": "Dark mode",
         "description": "please", "status": "open", "created_at": "2026-07-01T00:00:00+00:00"},
        {"id": f2, "user_id": str(other), "title": "CSV export",
         "description": None, "status": "planned", "created_at": "2026-07-02T00:00:00+00:00"},
    ])
    store.queue_select("feature_votes", [
        {"feature_id": f1, "user_id": str(me)},
        {"feature_id": f1, "user_id": str(other)},
        {"feature_id": f2, "user_id": str(other)},
    ])

    items = feature_service.list_features(me)

    by_id = {i.id: i for i in items}
    assert by_id[f1].vote_count == 2
    assert by_id[f1].voted_by_me is True
    assert by_id[f2].vote_count == 1
    assert by_id[f2].voted_by_me is False


def test_list_features_sorts_by_votes_then_recency(store):
    me = uuid4()
    low = str(uuid4())      # 1 vote
    high_old = str(uuid4()) # 3 votes, older
    high_new = str(uuid4()) # 3 votes, newer -> should come first among ties

    store.queue_select("feature_requests", [
        {"id": low, "user_id": str(me), "title": "Low", "description": None,
         "status": "open", "created_at": "2026-07-10T00:00:00+00:00"},
        {"id": high_old, "user_id": str(me), "title": "HighOld", "description": None,
         "status": "open", "created_at": "2026-07-01T00:00:00+00:00"},
        {"id": high_new, "user_id": str(me), "title": "HighNew", "description": None,
         "status": "open", "created_at": "2026-07-05T00:00:00+00:00"},
    ])
    store.queue_select("feature_votes",
        [{"feature_id": high_old, "user_id": str(uuid4())} for _ in range(3)]
        + [{"feature_id": high_new, "user_id": str(uuid4())} for _ in range(3)]
        + [{"feature_id": low, "user_id": str(uuid4())}]
    )

    ordered = [i.id for i in feature_service.list_features(me)]
    assert ordered == [high_new, high_old, low]


def test_list_features_respects_limit(store):
    me = uuid4()
    store.queue_select("feature_requests", [
        {"id": str(uuid4()), "user_id": str(me), "title": f"F{i}", "description": None,
         "status": "open", "created_at": f"2026-07-{i+1:02d}T00:00:00+00:00"}
        for i in range(10)
    ])
    store.queue_select("feature_votes", [])

    assert len(feature_service.list_features(me, limit=3)) == 3


# ---------------------------------------------------------------------------
# create_feature
# ---------------------------------------------------------------------------

def test_create_feature_auto_votes_submitter(store):
    me = uuid4()
    new_id = str(uuid4())
    store.queue_insert_return("feature_requests", [{
        "id": new_id, "user_id": str(me), "title": "New idea",
        "description": "details", "status": "open",
        "created_at": "2026-07-20T00:00:00+00:00",
    }])

    item = feature_service.create_feature(me, "New idea", "details")

    assert item is not None
    assert item.id == new_id
    assert item.vote_count == 1
    assert item.voted_by_me is True
    # Submitter's auto-vote was written referencing the new feature.
    voted_tables = [t for t, _ in store.inserted]
    assert "feature_requests" in voted_tables
    assert "feature_votes" in voted_tables
    vote_payload = next(p for t, p in store.inserted if t == "feature_votes")
    assert vote_payload["feature_id"] == new_id
    assert vote_payload["user_id"] == str(me)


def test_create_feature_returns_none_when_db_unavailable(unavailable_db):
    assert feature_service.create_feature(uuid4(), "Title") is None


# ---------------------------------------------------------------------------
# toggle_vote
# ---------------------------------------------------------------------------

def test_toggle_vote_inserts_when_absent(store):
    me, feature = uuid4(), uuid4()
    store.queue_select("feature_votes", [])                # existing check -> none
    store.queue_select("feature_votes", [{"id": str(uuid4())}])  # post-toggle count -> 1

    result = feature_service.toggle_vote(me, feature)

    assert result.voted is True
    assert result.vote_count == 1
    assert ("feature_votes", {"feature_id": str(feature), "user_id": str(me)}) in store.inserted
    assert store.deleted == []


def test_toggle_vote_deletes_when_present(store):
    me, feature = uuid4(), uuid4()
    store.queue_select("feature_votes", [{"id": str(uuid4())}])  # existing check -> present
    store.queue_select("feature_votes", [])                      # post-toggle count -> 0

    result = feature_service.toggle_vote(me, feature)

    assert result.voted is False
    assert result.vote_count == 0
    assert store.deleted == ["feature_votes"]
    assert store.inserted == []


# ---------------------------------------------------------------------------
# count_user_features_today
# ---------------------------------------------------------------------------

def test_count_user_features_today(store):
    store.queue_select("feature_requests", [{"id": str(uuid4())} for _ in range(3)])
    assert feature_service.count_user_features_today(uuid4()) == 3


def test_count_user_features_today_zero_when_db_unavailable(unavailable_db):
    assert feature_service.count_user_features_today(uuid4()) == 0
