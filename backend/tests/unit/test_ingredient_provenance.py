"""Unit tests for the IngredientProvenance model and its ProductAnalysis field.

Provenance segments the ingredients we surface into: declared (on the label),
found (research tied to THIS product), and inferred (probable given the product
category's manufacturing). The flat ``ingredients`` field stays as declared+found
for back-compat; ``ingredients_by_provenance`` is the richer, optional breakdown.
"""

import pytest
from pydantic import ValidationError

from src.domain.models import (
    InferredIngredient,
    IngredientProvenance,
    ProductAnalysis,
)


def _min_analysis(**overrides) -> ProductAnalysis:
    base = dict(product_url="https://example.com/p", overall_score=80, confidence=0.8)
    base.update(overrides)
    return ProductAnalysis(**base)


# ---------------------------------------------------------------------------
# IngredientProvenance
# ---------------------------------------------------------------------------

def test_provenance_defaults_to_empty_lists():
    p = IngredientProvenance()
    assert p.declared == []
    assert p.found == []
    assert p.inferred == []


def test_inferred_ingredient_holds_name_and_stage():
    i = InferredIngredient(name="residual acrylate monomers", stage="polymer curing")
    assert i.name == "residual acrylate monomers"
    assert i.stage == "polymer curing"


def test_provenance_holds_provided_values():
    p = IngredientProvenance(
        declared=["water", "glycerin"],
        found=["phenoxyethanol"],
        inferred=[InferredIngredient(name="residual acrylate monomers", stage="polymer curing")],
    )
    assert p.declared == ["water", "glycerin"]
    assert p.found == ["phenoxyethanol"]
    assert p.inferred[0].name == "residual acrylate monomers"
    assert p.inferred[0].stage == "polymer curing"


def test_provenance_coerces_inferred_dicts():
    p = IngredientProvenance(inferred=[{"name": "formaldehyde", "stage": "resin finishing"}])
    assert isinstance(p.inferred[0], InferredIngredient)
    assert p.inferred[0].name == "formaldehyde"
    assert p.inferred[0].stage == "resin finishing"


def test_inferred_ingredient_requires_stage():
    with pytest.raises(ValidationError):
        InferredIngredient(name="formaldehyde")  # stage is mandatory


def test_provenance_rejects_stageless_inferred_dict():
    with pytest.raises(ValidationError):
        IngredientProvenance(inferred=[{"name": "formaldehyde"}])


# ---------------------------------------------------------------------------
# ProductAnalysis.ingredients_by_provenance
# ---------------------------------------------------------------------------

def test_product_analysis_provenance_defaults_none():
    assert _min_analysis().ingredients_by_provenance is None


def test_product_analysis_coerces_dict_into_provenance():
    a = _min_analysis(ingredients_by_provenance={
        "declared": ["water"], "found": ["x"],
        "inferred": [{"name": "y", "stage": "surface coating"}],
    })
    assert isinstance(a.ingredients_by_provenance, IngredientProvenance)
    assert a.ingredients_by_provenance.declared == ["water"]
    assert a.ingredients_by_provenance.found == ["x"]
    assert isinstance(a.ingredients_by_provenance.inferred[0], InferredIngredient)
    assert a.ingredients_by_provenance.inferred[0].name == "y"
    assert a.ingredients_by_provenance.inferred[0].stage == "surface coating"


def test_product_analysis_accepts_provenance_object():
    prov = IngredientProvenance(
        declared=["a"], found=[],
        inferred=[InferredIngredient(name="b", stage="mold release")],
    )
    a = _min_analysis(ingredients_by_provenance=prov)
    assert a.ingredients_by_provenance is prov


def test_product_analysis_dump_roundtrips_provenance():
    a = _min_analysis(ingredients_by_provenance={
        "declared": ["water"], "found": [],
        "inferred": [{"name": "z", "stage": "packaging contact"}],
    })
    dumped = a.model_dump()
    assert dumped["ingredients_by_provenance"] == {
        "declared": ["water"], "found": [],
        "inferred": [{"name": "z", "stage": "packaging contact"}],
    }


def test_product_analysis_dump_provenance_none_when_absent():
    assert _min_analysis().model_dump()["ingredients_by_provenance"] is None
