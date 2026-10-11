"""DB-seam tests: ReviewVectorService reaches Supabase through the real DatabaseService.

FLEET-AUDIT B1 / MEMORY 2026-08-01: the service called ``db.supabase.*``, but
DatabaseService only exposes ``client``. The AttributeError was swallowed (INV-3), so
review storage and hybrid RAG were silently dead in prod. test_review_hybrid.py could not
catch it: it replaces ``db`` with a SimpleNamespace and stubs the two retrievers, which are
exactly the methods holding the broken access.

Here ``db`` is a real DatabaseService with only its Supabase ``client`` swapped for a fake,
so a wrong attribute name on ``db`` fails these tests. Cohere (embed/rerank) is stubbed
because it is a network seam, not the one under test.
"""

from types import SimpleNamespace

import pytest

import src.infrastructure.review_vector_service as rvs
from src.infrastructure.database import DatabaseService


class _FakeQuery:
    def __init__(self, client, table):
        self._client = client
        self._table = table

    def insert(self, data):
        self._client.calls.append(("insert", self._table, data))
        return self

    def upsert(self, data, **kwargs):
        self._client.calls.append(("upsert", self._table, data))
        return self

    def select(self, *columns):
        return self

    def eq(self, column, value):
        self._client.calls.append(("eq", self._table, (column, value)))
        return self

    def execute(self):
        return SimpleNamespace(data=self._client.rows.get(self._table, [{"id": "row"}]))


class _FakeRpc:
    def __init__(self, client, fn):
        self._client = client
        self._fn = fn

    def execute(self):
        return SimpleNamespace(data=self._client.rows.get(self._fn, []))


class _FakeSupabaseClient:
    def __init__(self):
        self.calls: list = []
        self.rows: dict = {}

    def table(self, name):
        return _FakeQuery(self, name)

    def rpc(self, fn, params):
        self.calls.append(("rpc", fn, params))
        return _FakeRpc(self, fn)


@pytest.fixture
def client(monkeypatch):
    service = DatabaseService()
    fake = _FakeSupabaseClient()
    service.client = fake  # is_available -> True; the rest of the real class is untouched
    monkeypatch.setattr(rvs, "db", service)
    return fake


@pytest.fixture
def svc(monkeypatch):
    service = rvs.ReviewVectorService()
    monkeypatch.setattr(service, "embed_text", lambda text, input_type="search_query": None)
    monkeypatch.setattr(service, "embed_batch", lambda texts, input_type="search_document": [None] * len(texts))
    monkeypatch.setattr(service, "rerank", lambda query, documents, top_n=10: [])
    return service


def _review(rid, text, rating=2):
    return {"id": rid, "review_text": text, "review_rating": rating, "verified_purchase": True}


async def test_store_reviews_writes_chunks_and_summary(client, svc, monkeypatch):
    async def parsed(url, html):
        return [_review("a", "gave me a rash", 1), _review("b", "fine", 5)]

    monkeypatch.setattr(svc, "parse_reviews_for_url", parsed)

    stored, failed = await svc.store_reviews("hash1", "https://x/p", "<html/>")

    assert (stored, failed) == (2, 0)
    assert [c[1] for c in client.calls if c[0] == "insert"] == ["review_chunks", "review_chunks"]
    assert [c[1] for c in client.calls if c[0] == "upsert"] == ["review_summaries"]


def test_semantic_candidates_call_search_reviews_rpc(client, svc, monkeypatch):
    monkeypatch.setattr(svc, "embed_text", lambda text, input_type="search_query": [0.1, 0.2])
    client.rows["search_reviews"] = [_review("s", "itchy skin")]

    result = svc._semantic_candidates("irritation", "hash1", top_k=5)

    assert result == [_review("s", "itchy skin")]
    assert client.calls[0][:2] == ("rpc", "search_reviews")


def test_lexical_candidates_call_search_reviews_lexical_rpc(client, svc):
    client.rows["search_reviews_lexical"] = [_review("l", "PFOA residue")]

    result = svc._lexical_candidates("PFOA", "hash1", top_k=5)

    assert result == [_review("l", "PFOA residue")]
    assert client.calls[0] == ("rpc", "search_reviews_lexical", {"p_query": "PFOA", "p_url_hash": "hash1", "p_limit": 5})


async def test_get_review_summary_reads_review_summaries(client, svc):
    client.rows["review_summaries"] = [{"url_hash": "hash1", "total_reviews": 3}]

    assert await svc.get_review_summary("hash1") == {"url_hash": "hash1", "total_reviews": 3}
    assert ("eq", "review_summaries", ("url_hash", "hash1")) in client.calls


async def test_health_relevant_reviews_returns_a_db_lexical_hit(client, svc):
    """End to end through both real retrievers: Cohere is down (no embedding), so the
    lexical RPC alone must surface the exact-term review."""
    client.rows["search_reviews_lexical"] = [_review("l", "product left PFOA residue on my pan")]

    results = await svc.get_health_relevant_reviews("hash1", max_reviews=15)

    assert [r["review_text"] for r in results] == ["product left PFOA residue on my pan"]
