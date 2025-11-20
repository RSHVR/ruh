# Test Suite

## Overview

Test suite for the Eject backend. Currently implements End-to-End (E2E) tests with real product analysis. Unit and integration test directories exist but are empty (development scaffolding).

---

## Test Structure

```
/backend/tests/
├── __init__.py          # Package marker (empty)
├── unit/                # ⚠️ EMPTY - No unit tests yet
│   └── __init__.py      # Package marker (empty)
├── integration/         # ⚠️ EMPTY - No integration tests yet
│   └── __init__.py      # Package marker (empty)
└── e2e/                 # E2E tests → [e2e/CLAUDE.md](./e2e/CLAUDE.md)
    ├── __init__.py      # Package marker (empty)
    └── test_product_analysis.py  # Product analysis E2E tests
```

---

## Test Coverage

### Implemented Tests

**E2E Tests** (`e2e/test_product_analysis.py`):
- ✅ Full product analysis flow
- ✅ Real API requests
- ✅ Real Claude AI calls
- ✅ Real database operations
- ✅ Authentication testing
- ✅ Error handling

**Test Cases**:
1. `test_analyze_sunscreen()` - Analyze sunscreen product
2. `test_analyze_lipstick()` - Analyze lipstick product
3. `test_invalid_api_key()` - Test authentication failure

### Missing Tests (Development Scaffolding)

**Unit Tests** (`unit/`):
- ⚠️ Empty directory
- Intended for: `harm_calculator.py`, `database.py`, `scrapers/`

**Integration Tests** (`integration/`):
- ⚠️ Empty directory
- Intended for: API endpoint tests, database integration

---

## Running Tests

### E2E Tests

```bash
# From /backend directory
pytest tests/e2e/test_product_analysis.py -v

# Run all tests
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html
```

### Requirements

**Environment Variables** (in `.env`):
- `ANTHROPIC_API_KEY` - Required for Claude AI
- `SUPABASE_URL` - Required for database
- `SUPABASE_KEY` - Required for database
- `API_KEY` - Required for authentication
- `SERPER_API_KEY` - Required for web search

**Dependencies**:
- pytest
- pytest-asyncio
- httpx

---

## File-Level Relationships

```
tests/
  ├─ e2e/test_product_analysis.py
  │    IMPORTS:
  │      - pytest
  │      - httpx.{AsyncClient, ASGITransport}
  │      - src.api.main.app
  │      - src.infrastructure.config.settings
  │
  ├─ unit/ (empty)
  │
  └─ integration/ (empty)
```

---

## Test Strategy

### Why E2E First?

**Advantages**:
- Validates entire system works together
- Catches integration issues
- Tests real-world scenarios
- Validates Claude AI behavior

**Disadvantages**:
- Slower execution (AI API calls)
- Expensive (API costs)
- Less isolated failures

### Future Test Strategy

**Unit Tests** (TODO):
- `harm_calculator.py` - Pure logic testing
- `database.py` - Mock Supabase client
- `scrapers/amazon.py` - Mock HTTP responses

**Integration Tests** (TODO):
- API endpoints with mocked external services
- Database operations with test database
- Faster than E2E, more isolated than current tests

---

## Related Documentation

- [Backend Overview](../CLAUDE.md) - Backend directory overview
- [E2E Tests](./e2e/CLAUDE.md) - E2E test details
- [API Routes](../src/api/routes/CLAUDE.md) - Endpoints being tested

---

Last Updated: 2025-11-18
