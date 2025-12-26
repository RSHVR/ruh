# Tests & Configuration (`/backend/tests/`)

## Overview

The Ruh backend testing infrastructure is currently **minimal**, with only E2E (end-to-end) tests implemented. The test suite uses pytest with pytest-asyncio for async support.

**Critical Finding**: Unit and integration test directories exist but are empty. Significant components are completely untested.

## Current Test Coverage

### Implemented Tests

| Test File | Tests | What's Tested |
|-----------|-------|---------------|
| `tests/e2e/test_product_analysis.py` | 5 | Health endpoint, 2 product analyses, allergen profile, invalid URL |

### Coverage Gaps

| Component | Priority | Reason |
|-----------|----------|--------|
| `HarmScoreCalculator` | **P0** | Core business logic with complex scoring |
| `match_ingredients_to_databases()` | **P0** | Fallback safety mechanism |
| `verify_api_key()` | **P0** | Security-critical function |
| `DatabaseService` | **P1** | All database operations untested |
| `AmazonScraper` | **P1** | Scraper logic untested |
| `validate_and_filter_substances()` | **P1** | Validation logic |
| Rate limiting | **P2** | No tests verify limits work |

## Test Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

## Production Readiness Issues

| Severity | Issue | Recommendation |
|----------|-------|----------------|
| **Critical** | No unit tests for HarmScoreCalculator | Create test_harm_calculator.py |
| **Critical** | No unit tests for auth | Create test_auth.py |
| **Critical** | No unit tests for ingredient matching | Create test_ingredient_matcher.py |
| **Critical** | Docker runs as root | Add non-root USER instruction |
| **High** | E2E tests use real external services | Add mock-based tests |
| **High** | No test coverage reporting | Add pytest-cov to CI |
| **High** | Unused dependencies (redis, celery) | Remove or document |

## Dockerfile Issues

| Issue | Current | Recommendation |
|-------|---------|----------------|
| Non-root user | Missing | Add `USER` instruction |
| Health check | Missing | Add HEALTHCHECK |
| Layer caching | Suboptimal | Copy pyproject.toml first |

## Recommended Test Expansion

### Priority 1 - Unit Tests (Immediate)

```python
# tests/unit/test_harm_calculator.py
- test_calculate_empty_analysis()
- test_calculate_single_allergen_low_severity()
- test_calculate_pfas_detected()
- test_calculate_with_category_multiplier()
- test_calculate_caps_at_100()

# tests/unit/test_auth.py
- test_verify_valid_api_key()
- test_verify_invalid_api_key()
- test_verify_missing_credentials()

# tests/unit/test_ingredient_matcher.py
- test_exact_match_allergen()
- test_fuzzy_match_allergen()
- test_deduplication_keeps_highest_confidence()
```

### Priority 2 - Integration Tests

```python
# tests/integration/test_database.py
- Mock Supabase client
- Test caching, storing, URL hashing

# tests/integration/test_scraper.py
- Mock httpx responses
- Test HTML parsing, error handling
```
