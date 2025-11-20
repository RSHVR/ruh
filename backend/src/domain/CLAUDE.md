# Domain Layer - Business Logic

## Overview

Core business logic layer containing domain models, entities, value objects, and the harm scoring algorithm. This layer is independent of external frameworks and services.

---

## Function-Level Flow Diagram

### Harm Score Calculation

```
📄 harm_calculator.py::HarmScoreCalculator.calculate(
      analysis_data: Dict[str, Any]
    ) → int
  │
  ├─ Initializes: total_score = 0
  │
  ├─ Step 1: ALLERGEN SCORING
  │   ├─ Gets: allergens = analysis_data.get('allergens_detected', [])
  │   └─ For each allergen:
  │       ├─ Reads: severity = allergen.get('severity', 'moderate')
  │       ├─ Adds points:
  │       │   • 'low' → 5 points
  │       │   • 'moderate' → 15 points
  │       │   • 'high' → 30 points
  │       └─ Accumulates: total_score += points
  │
  ├─ Step 2: PFAS SCORING
  │   ├─ Gets: pfas = analysis_data.get('pfas_detected', [])
  │   └─ For each PFAS compound:
  │       └─ Adds: 40 points to total_score
  │
  ├─ Step 3: OTHER CONCERNS SCORING
  │   ├─ Gets: concerns = analysis_data.get('other_concerns', [])
  │   └─ For each concern:
  │       ├─ Reads: toxicity = concern.get('toxicity_level', 'low')
  │       ├─ Adds points:
  │       │   • 'low' → 5 points
  │       │   • 'medium' → 15 points
  │       │   • 'high' → 25 points
  │       └─ Accumulates: total_score += points
  │
  ├─ Step 4: CATEGORY MULTIPLIERS
  │   ├─ Gets: category = analysis_data.get('product_category', '')
  │   ├─ Applies multipliers:
  │   │   • 'pesticide' or 'cleaner' → total_score *= 1.3
  │   │   • 'food' → total_score *= 1.2
  │   │   • 'cosmetic' → total_score *= 1.1
  │   └─ Rounds: total_score = int(total_score)
  │
  ├─ Step 5: CAPPING (0-100 range)
  │   └─ Applies: total_score = max(0, min(100, total_score))
  │
  └─ Returns: total_score (0-100 integer)

Algorithm: Higher score = more harmful
0-30: Low risk (green)
31-60: Medium risk (yellow)
61-100: High risk (red)
```

---

## File-Level Import Relationships

```
models.py
  IMPORTS:
    - pydantic.{BaseModel, Field}
    - datetime, enum, typing, uuid
  IMPORTED BY:
    - ../api/routes/analyze.py
    - ../infrastructure/claude_query.py
    - ../infrastructure/database.py
    - ../infrastructure/product_scraper.py
    - ../infrastructure/scrapers/amazon.py

harm_calculator.py
  IMPORTS:
    - typing.{Dict, Any}
  IMPORTED BY:
    - ../api/routes/analyze.py
```

---

## Directory Structure

```
/backend/src/domain/
├── __init__.py           # Package marker (empty)
├── models.py             # Pydantic data models (requests, responses, entities)
└── harm_calculator.py    # Harm score calculation algorithm
```

---

## Files Description

### models.py
**Purpose**: Pydantic data models for requests, responses, and domain entities

**Key Models**:

**Request Models**:
- `AnalysisRequest` - Product URL for analysis
- `ReviewInsightsRequest` - Product URL for review insights

**Response Models**:
- `AnalysisResponse` - Complete analysis result with alternatives and cache status
- `ReviewInsightsResponse` - Review insights wrapper

**Domain Entities**:
- `ProductAnalysis` - Core product analysis data
- `Allergen` - Allergen with name and severity
- `PFASCompound` - PFAS chemical with health effects
- `ToxicSubstance` - Other harmful substances
- `AlternativeRecommendation` - Safer product alternatives
- `ReviewInsights` - Safety insights from reviews
- `ScrapedProduct` - Raw scraped data with confidence

**Enums**:
- `Severity` - low, moderate, high
- `ToxicityLevel` - low, medium, high

**Dependencies**: Pure Pydantic models with no internal imports

**Relationships**:
- Used throughout the entire backend
- Defines the domain language and data structures
- Most widely imported module in the codebase

### harm_calculator.py
**Purpose**: Core business logic for calculating product harm scores

**Key Class**:
- `HarmScoreCalculator` - Static class with single `calculate()` method

**Algorithm**:
1. Sum allergen severity points (5-30 per allergen)
2. Add PFAS points (40 per compound)
3. Add other toxicity points (5-25 per concern)
4. Apply category multipliers (1.1x - 1.3x)
5. Cap to 0-100 range

**Dependencies**: Pure Python with no imports except typing

**Relationships**:
- Called by `api/routes/analyze.py::analyze_product()`
- Core calculation that determines the product's safety score
- Independent of all other services (testable in isolation)

---

## Design Principles

### Dependency Inversion
- Domain layer has ZERO dependencies on infrastructure or API layers
- Other layers depend on domain models, not vice versa
- Enables pure business logic testing

### Single Responsibility
- `models.py` - Data structures only
- `harm_calculator.py` - Scoring algorithm only
- Clear separation of concerns

### Pure Functions
- `HarmScoreCalculator.calculate()` is a pure function
- Same input always produces same output
- No side effects, no external dependencies
- Easily testable

---

## Harm Scoring Details

### Scoring Matrix

| Category | Item | Points |
|----------|------|--------|
| **Allergen (low severity)** | Peanuts, Tree nuts, etc. | 5 |
| **Allergen (moderate severity)** | Milk, Eggs, Soy, etc. | 15 |
| **Allergen (high severity)** | Shellfish, Severe reactions | 30 |
| **PFAS Compound** | PFOA, PFOS, GenX, etc. | 40 |
| **Toxic Substance (low)** | Minor concerns | 5 |
| **Toxic Substance (medium)** | Moderate toxicity | 15 |
| **Toxic Substance (high)** | Severe toxicity | 25 |

### Category Multipliers

| Product Category | Multiplier | Rationale |
|------------------|------------|-----------|
| Pesticides, Cleaners | 1.3x | Higher exposure risk |
| Food | 1.2x | Ingestion pathway |
| Cosmetics | 1.1x | Skin absorption |
| Other | 1.0x | Standard scoring |

---

## Related Documentation

- [Backend Source](../CLAUDE.md) - Source code overview
- [API Routes](../api/routes/CLAUDE.md) - Where harm calculator is called
- [Infrastructure](../infrastructure/CLAUDE.md) - Services that provide data to domain

---

Last Updated: 2025-11-18
