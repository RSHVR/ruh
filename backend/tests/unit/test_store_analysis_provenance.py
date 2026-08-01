"""Plumbing test: store_analysis serializes ingredients_by_provenance.

Mirrors how research_sources is serialized into the stored row. A fake Supabase
client captures the upserted ``db_data`` so we can assert the provenance value is
normalized (pydantic object -> dict, dict passthrough, absent -> None) without a
real database.
"""

from types import SimpleNamespace

import pytest

from src.infrastructure.database import DatabaseService
from src.domain.models import IngredientProvenance, InferredIngredient, OriginInfo

_OMIT = object()


class _FakeUpsertQuery:
    def __init__(self, capture):
        self._capture = capture

    def upsert(self, data, **kwargs):
        self._capture["db_data"] = data
        self._capture["on_conflict"] = kwargs.get("on_conflict")
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


def _payload(provenance, include_key=True, origin=_OMIT):
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
    if include_key:
        analysis["ingredients_by_provenance"] = provenance
    if origin is not _OMIT:
        analysis["origin"] = origin
    return {"analysis": analysis}


async def test_store_serializes_provenance_object(captured_service):
    svc, capture = captured_service
    prov = IngredientProvenance(
        declared=["water", "glycerin"],
        found=["phenoxyethanol"],
        inferred=[InferredIngredient(name="residual acrylate monomers", stage="polymer curing")],
    )

    ok = await svc.store_analysis("hash1", "https://x/p", _payload(prov))

    assert ok is True
    assert capture["table"] == "product_analyses"
    assert capture["db_data"]["ingredients_by_provenance"] == {
        "declared": ["water", "glycerin"],
        "found": ["phenoxyethanol"],
        "inferred": [{"name": "residual acrylate monomers", "stage": "polymer curing"}],
    }


async def test_store_passes_through_provenance_dict(captured_service):
    svc, capture = captured_service
    prov = {"declared": ["a"], "found": [], "inferred": [{"name": "b", "stage": "dyeing & finishing"}]}

    await svc.store_analysis("hash2", "https://x/p", _payload(prov))

    assert capture["db_data"]["ingredients_by_provenance"] == prov


async def test_store_serializes_absent_provenance_as_none(captured_service):
    svc, capture = captured_service

    await svc.store_analysis("hash3", "https://x/p", _payload(None, include_key=False))

    assert capture["db_data"]["ingredients_by_provenance"] is None
    # existing research_sources plumbing must still be intact.
    assert capture["db_data"]["research_sources"] == []


async def test_store_serializes_origin_object(captured_service):
    svc, capture = captured_service
    origin = OriginInfo(
        summary="Likely US-grown romaine.",
        region="US-CA",
        alert="As of late July 2026 the CDC is investigating an E. coli outbreak in romaine.",
    )

    await svc.store_analysis(
        "hash4", "https://x/p", _payload(None, include_key=False, origin=origin)
    )

    assert capture["db_data"]["origin"] == {
        "summary": "Likely US-grown romaine.",
        "region": "US-CA",
        "alert": "As of late July 2026 the CDC is investigating an E. coli outbreak in romaine.",
    }


async def test_store_serializes_absent_origin_as_none(captured_service):
    svc, capture = captured_service

    await svc.store_analysis("hash5", "https://x/p", _payload(None, include_key=False))

    assert capture["db_data"]["origin"] is None
