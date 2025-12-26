# Domain Layer (`/backend/src/domain/`)

## Overview

The domain layer contains the core business logic for the Ruh product safety analyzer. This layer implements data models, harm score calculation, and ingredient matching. It follows clean architecture principles with no dependencies on infrastructure or API layers.

## Files

| File | Purpose | Lines | Key Classes/Functions |
|------|---------|-------|----------------------|
| `models.py` | Pydantic data models for API requests/responses | 204 | 14 classes, 1 enum |
| `harm_calculator.py` | Harm score calculation algorithm | 202 | `HarmScoreCalculator` class |
| `ingredient_matcher.py` | Database-level substance matching fallback | 163 | `match_ingredients_to_databases()` |

## Key Models

| Model | Purpose |
|-------|---------|
| `ProductAnalysis` | Complete analysis of a product's safety |
| `AllergenDetection` | Detected allergen with severity |
| `PFASDetection` | Detected PFAS compound with health effects |
| `ToxinConcern` | Other harmful substances |
| `AnalysisRequest` | Request payload for product analysis |
| `AnalysisResponse` | Complete response with analysis and alternatives |

## HarmScoreCalculator

Calculates harm score (0-100) based on detected substances using a weighted formula:

- **Allergens**: 8-50 points per detection (severity-based)
- **PFAS**: 40 points per compound
- **Other Concerns**: 5-40 points (category-based)
- **Multipliers**: 1.15-1.4x for high-risk product categories (pesticides, cleaners)
- **Confidence Penalty**: Additional points if confidence < 0.7
- **Minimum Score**: 25 if any concerns detected

## Production Readiness Issues

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **Critical** | No unit tests for harm calculation | harm_calculator.py | Add comprehensive unit tests |
| **Critical** | No unit tests for ingredient matching | ingredient_matcher.py | Add edge case tests |
| **High** | `get_risk_level()` unused with different thresholds | harm_calculator.py:185 | Remove dead code or sync with `ProductAnalysis.risk_level` |
| **High** | No input validation in `similar()` | ingredient_matcher.py:16 | Add type checking |
| **Medium** | Unvalidated string enums in models | models.py | Use Literal types |
| **Low** | Hardcoded model version | models.py:69 | Move to configuration |

## Dependencies

### Internal
- None (pure domain layer)

### External
- `pydantic` - Data validation
- `difflib` - Fuzzy string matching
- Standard library only
