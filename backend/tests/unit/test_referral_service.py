"""Unit tests for the referral service.

Mirrors ``test_feature_service.py``: the service talks to Supabase through the
global ``db`` singleton, which we replace with a hand-rolled fake query builder
so the pure normalization / aggregation / RPC-dispatch logic is exercised with
no network or real client. The fake additionally supports ``upsert`` and
``rpc`` (which the feature service does not use).
"""

from collections import defaultdict, deque
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.infrastructure import referral_service


# ---------------------------------------------------------------------------
# Fake Supabase query builder (tables + rpc)
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Mimics one supabase-py table chain: table(...).select/upsert...execute()."""

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

    def upsert(self, payload, **kwargs):
        self._op = "upsert"
        self._payload = payload
        return self

    # Filters / ordering are no-ops for the fake.
    def eq(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        return self._store.handle_table(self._table, self._op, self._payload)


class _FakeRpc:
    def __init__(self, store, name, params):
        self._store = store
        self._name = name
        self._params = params

    def execute(self):
        return self._store.handle_rpc(self._name, self._params)


class _FakeClient:
    def __init__(self, store):
        self._store = store

    def table(self, name):
        return _FakeQuery(self._store, name)

    def rpc(self, name, params):
        return _FakeRpc(self._store, name, params)


class FakeStore:
    """Drives a fake supabase client.

    Select results are consumed FIFO per table. Upserts are captured for
    assertions and return the next queued row-set (defaulting to echoing the
    payload). RPC calls are captured and return queued data, or raise a queued
    error to exercise the swallow-errors path.
    """

    def __init__(self):
        self.select_queue = defaultdict(deque)
        self.upsert_returns = defaultdict(deque)
        self.upserted = []      # list of (table, payload)
        self.inserted = []      # list of (table, payload)
        self.rpc_returns = deque()
        self.rpc_calls = []     # list of (name, params)
        self.rpc_error = None

    def queue_select(self, table, data):
        self.select_queue[table].append(data)

    def queue_upsert_return(self, table, rows):
        self.upsert_returns[table].append(rows)

    def queue_rpc_return(self, data):
        self.rpc_returns.append(data)

    def handle_table(self, table, op, payload):
        if op == "select":
            data = self.select_queue[table].popleft() if self.select_queue[table] else []
            return _FakeResult(data)
        if op == "upsert":
            self.upserted.append((table, payload))
            rows = (
                self.upsert_returns[table].popleft()
                if self.upsert_returns[table]
                else payload
            )
            return _FakeResult(rows)
        if op == "insert":
            self.inserted.append((table, payload))
            return _FakeResult(payload)
        raise AssertionError(f"unexpected op {op!r}")

    def handle_rpc(self, name, params):
        self.rpc_calls.append((name, params))
        if self.rpc_error is not None:
            raise self.rpc_error
        data = self.rpc_returns.popleft() if self.rpc_returns else 0
        return _FakeResult(data)


@pytest.fixture
def store(monkeypatch):
    s = FakeStore()
    fake_db = SimpleNamespace(is_available=True, client=_FakeClient(s))
    monkeypatch.setattr(referral_service, "db", fake_db)
    return s


@pytest.fixture
def unavailable_db(monkeypatch):
    monkeypatch.setattr(
        referral_service, "db", SimpleNamespace(is_available=False, client=None)
    )


# ---------------------------------------------------------------------------
# add_referrals
# ---------------------------------------------------------------------------

def test_add_referrals_normalizes_dedupes_excludes_self_and_invalid(store):
    me = uuid4()
    # Own email is looked up first (mixed-case in the DB, normalized in code).
    store.queue_select("users", [{"email": "Me@Example.com"}])
    # Three valid, unique, non-self emails will be attempted; all are new.
    store.queue_upsert_return("referrals", [
        {"id": str(uuid4())}, {"id": str(uuid4())}, {"id": str(uuid4())},
    ])

    emails = [
        " Friend@Example.com ",   # -> friend@example.com (valid)
        "friend@example.com",     # dupe of the above -> skipped
        "me@example.com",         # own email -> skipped
        "not-an-email",           # invalid -> skipped
        "a@b.co",                 # valid
        "c@d.io",                 # valid
    ]

    result = referral_service.add_referrals(me, emails)

    assert result == {"added": 3, "skipped": 3}
    # Only the three normalized, unique, non-self emails were upserted.
    table, payload = store.upserted[0]
    assert table == "referrals"
    assert sorted(r["invited_email"] for r in payload) == [
        "a@b.co", "c@d.io", "friend@example.com",
    ]
    assert all(r["referrer_user_id"] == str(me) for r in payload)


def test_add_referrals_counts_existing_conflicts_as_skipped(store):
    me = uuid4()
    store.queue_select("users", [{"email": "me@example.com"}])
    # Two valid emails attempted, but the upsert (ignore_duplicates) returns only
    # one new row — the other already existed and was silently ignored.
    store.queue_upsert_return("referrals", [{"id": str(uuid4())}])

    result = referral_service.add_referrals(me, ["new@x.com", "old@x.com"])

    assert result == {"added": 1, "skipped": 1}


def test_add_referrals_all_invalid_or_self_skips_upsert(store):
    me = uuid4()
    store.queue_select("users", [{"email": "me@example.com"}])

    result = referral_service.add_referrals(me, ["bad", "also-bad", "me@example.com"])

    assert result == {"added": 0, "skipped": 3}
    assert store.upserted == []  # nothing valid -> no DB write


def test_add_referrals_handles_missing_own_email(store):
    me = uuid4()
    store.queue_select("users", [])  # no user row / no email on file
    store.queue_upsert_return("referrals", [{"id": str(uuid4())}])

    result = referral_service.add_referrals(me, ["friend@x.com"])

    assert result == {"added": 1, "skipped": 0}


def test_add_referrals_returns_all_skipped_when_db_unavailable(unavailable_db):
    result = referral_service.add_referrals(uuid4(), ["a@b.com", "c@d.com"])
    assert result == {"added": 0, "skipped": 2}


# ---------------------------------------------------------------------------
# list_referrals
# ---------------------------------------------------------------------------

def test_list_referrals_returns_items_and_summary(store):
    me = uuid4()
    store.queue_select("referrals", [
        {"invited_email": "a@x.com", "status": "invited", "created_at": "2026-07-01T00:00:00+00:00"},
        {"invited_email": "b@x.com", "status": "signed_up", "created_at": "2026-07-02T00:00:00+00:00"},
        {"invited_email": "c@x.com", "status": "credited", "created_at": "2026-07-03T00:00:00+00:00"},
        {"invited_email": "d@x.com", "status": "credited", "created_at": "2026-07-04T00:00:00+00:00"},
    ])

    listing = referral_service.list_referrals(me)

    assert len(listing.referrals) == 4
    assert listing.referrals[0].invited_email == "a@x.com"
    assert listing.summary.invited == 1
    assert listing.summary.signed_up == 1
    assert listing.summary.credited == 2


def test_list_referrals_empty_when_db_unavailable(unavailable_db):
    listing = referral_service.list_referrals(uuid4())
    assert listing.referrals == []
    assert listing.summary.invited == 0
    assert listing.summary.signed_up == 0
    assert listing.summary.credited == 0


# ---------------------------------------------------------------------------
# process_conversion
# ---------------------------------------------------------------------------

def test_process_conversion_returns_rpc_int(store):
    store.queue_rpc_return(1)

    assert referral_service.process_conversion(uuid4()) == 1
    name, params = store.rpc_calls[0]
    assert name == "process_referral_conversion"
    assert "p_user_id" in params


def test_process_conversion_zero_when_no_match(store):
    store.queue_rpc_return(0)
    assert referral_service.process_conversion(uuid4()) == 0


def test_process_conversion_handles_list_wrapped_scalar(store):
    store.queue_rpc_return([1])
    assert referral_service.process_conversion(uuid4()) == 1


def test_process_conversion_handles_dict_wrapped_scalar(store):
    store.queue_rpc_return([{"process_referral_conversion": 1}])
    assert referral_service.process_conversion(uuid4()) == 1


def test_process_conversion_swallows_errors_and_returns_zero(store):
    store.rpc_error = RuntimeError("db exploded")
    # Runs inside the analyze path — must never raise.
    assert referral_service.process_conversion(uuid4()) == 0


def test_process_conversion_zero_when_db_unavailable(unavailable_db):
    assert referral_service.process_conversion(uuid4()) == 0
