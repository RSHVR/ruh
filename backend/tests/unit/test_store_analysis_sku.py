"""Plumbing test: store_analysis persists the product SKU.

Mirrors test_store_analysis_provenance — a fake Supabase client captures the
upserted ``db_data`` so we assert the sku is written (present -> value, absent
-> None) without a real database. Pins the store seam so a future refactor of
the db_data dict can't silently drop sku (cf. MEMORY.md: mockable-boundary bugs).
"""

from types import SimpleNamespace

import pytest

from src.infrastructure.database import DatabaseService

_OMIT = object()


class _FakeUpsertQuery:
    def __init__(self, capture):
        self._capture = capture

    def upsert(self, data, **kwargs):
        self._capture["db_data"] = data
        return self

    def execute(self):
        return SimpleNamespace(data=[self._capture["db_data"]])


class _FakeClient:
    def __init__(self, capture):
        self._capture = capture

    def table(self, name):
        self._capture["table"] = name
        return _FakeUpsertQuery(self._capture)


@pytest.fixture
def captured_service():
    svc = DatabaseService()
    capture: dict = {}
    svc.client = _FakeClient(capture)  # is_available -> True (client is not None)
    return svc, capture


def _payload(sku=_OMIT):
    analysis = {
        "product_name": "Test Product",
        "brand": "Test Brand",
        "overall_score": 80,
        "ingredients": ["water", "glycerin"],
        "allergens": [],
        "pfas_compounds": [],
        "other_concerns": [],
        "research_sources": [],
        "confidence": 0.8,
    }
    if sku is not _OMIT:
        analysis["sku"] = sku
    return {"analysis": analysis}


async def test_store_persists_sku(captured_service):
    svc, capture = captured_service

    ok = await svc.store_analysis("hash-sku-1", "https://x/p", _payload("ABC-123"))

    assert ok is True
    assert capture["table"] == "product_analyses"
    assert capture["db_data"]["sku"] == "ABC-123"


async def test_store_absent_sku_is_none(captured_service):
    svc, capture = captured_service

    await svc.store_analysis("hash-sku-2", "https://x/p", _payload())  # sku omitted

    assert capture["db_data"]["sku"] is None
