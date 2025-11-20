# E2E Tests

## Overview

End-to-end tests for the Eject backend API, testing complete product analysis flows with real AI calls and database operations.

---

## Function-Level Flow Diagram

### Test: Analyze Sunscreen Product

```
📄 test_product_analysis.py::test_analyze_sunscreen()
  │
  ├─ Step 1: SETUP
  │   ├─ Creates: client = AsyncClient(
  │   │            transport=ASGITransport(app=app),
  │   │            base_url="http://test"
  │   │          )
  │   ├─ Reads: settings.api_key
  │   └─ Defines: headers = {"Authorization": f"Bearer {settings.api_key}"}
  │
  ├─ Step 2: API REQUEST
  │   ├─ Defines: payload = {
  │   │            "product_url": "https://www.amazon.com/dp/B004D24D0S"
  │   │            # Neutrogena Ultra Sheer Sunscreen SPF 100+
  │   │          }
  │   └─ Calls: response = await client.post(
  │                "/api/analyze",
  │                json=payload,
  │                headers=headers
  │              )
  │
  ├─ Step 3: ASSERTIONS
  │   ├─ Asserts: response.status_code == 200
  │   ├─ Parses: data = response.json()
  │   ├─ Asserts: "analysis" in data
  │   ├─ Asserts: "product_analysis" in data["analysis"]
  │   ├─ Asserts: data["analysis"]["product_analysis"]["product_name"] is not None
  │   ├─ Asserts: "overall_score" in data["analysis"]["product_analysis"]
  │   ├─ Asserts: "allergens_detected" in data["analysis"]["product_analysis"]
  │   └─ Asserts: "pfas_detected" in data["analysis"]["product_analysis"]
  │
  └─ Returns: Pass/Fail
```

### Test: Analyze Lipstick Product

```
📄 test_product_analysis.py::test_analyze_lipstick()
  │
  ├─ Similar flow to test_analyze_sunscreen
  ├─ Uses: Different product URL (lipstick)
  │   URL: "https://www.amazon.com/dp/B07W4RHDPL"
  │   # Maybelline SuperStay Matte Ink Liquid Lipstick
  │
  └─ Validates: Same assertions as sunscreen test
```

### Test: Invalid API Key

```
📄 test_product_analysis.py::test_invalid_api_key()
  │
  ├─ Step 1: SETUP
  │   ├─ Creates: client (same as above)
  │   └─ Defines: headers = {"Authorization": "Bearer invalid_key_12345"}
  │
  ├─ Step 2: API REQUEST
  │   ├─ Defines: payload = {"product_url": "https://www.amazon.com/dp/B004D24D0S"}
  │   └─ Calls: response = await client.post("/api/analyze", json=payload, headers=headers)
  │
  ├─ Step 3: ASSERTIONS
  │   ├─ Asserts: response.status_code == 401
  │   └─ Asserts: "Invalid API key" in response.json()["detail"]
  │
  └─ Returns: Pass/Fail
```

---

## File-Level Import Relationships

```
test_product_analysis.py
  IMPORTS:
    - pytest
    - httpx.{AsyncClient, ASGITransport}
    - src.api.main.app (FastAPI application)
    - src.infrastructure.config.settings (API key)
  IMPORTED BY:
    - pytest test runner
```

---

## Directory Structure

```
/backend/tests/e2e/
├── __init__.py               # Package marker (empty)
└── test_product_analysis.py  # Product analysis E2E tests
```

---

## File Description

### test_product_analysis.py
**Purpose**: End-to-end testing of product analysis API

**Test Cases**:

1. **`test_analyze_sunscreen()`**
   - Tests: Sunscreen product analysis
   - Product: Neutrogena Ultra Sheer SPF 100+
   - Validates: Complete analysis flow, allergen detection, PFAS detection
   - Duration: ~10-30 seconds (includes AI API calls)

2. **`test_analyze_lipstick()`**
   - Tests: Cosmetic product analysis
   - Product: Maybelline SuperStay Matte Ink
   - Validates: Different product category handling
   - Duration: ~10-30 seconds

3. **`test_invalid_api_key()`**
   - Tests: Authentication failure
   - Validates: 401 response with invalid credentials
   - Duration: < 1 second (fast path, no AI calls)

**Dependencies**:
- pytest (test framework)
- pytest-asyncio (async test support)
- httpx (async HTTP client)
- src.api.main (FastAPI app)
- src.infrastructure.config (settings)

**Relationships**:
- Calls entire backend stack (API → Domain → Infrastructure)
- Makes real Claude AI API calls
- Writes to real Supabase database
- Tests complete end-to-end flow

---

## Test Execution Details

### What These Tests Validate

**Complete Flow**:
1. ✅ API endpoint accepts requests
2. ✅ Authentication works correctly
3. ✅ Product URL scraping succeeds
4. ✅ Claude AI analysis completes
5. ✅ Harm score calculation runs
6. ✅ Database caching works
7. ✅ Response format is correct

**Not Tested**:
- ❌ Scraper fallback logic (if scraping fails)
- ❌ Cache hit path (would need to run same test twice)
- ❌ Error handling for AI API failures
- ❌ Edge cases (invalid URLs, timeout scenarios)

### Test Costs

**API Costs per Test Run**:
- Claude AI: ~$0.01-0.05 per analysis (depending on tokens)
- Supabase: Free tier (database writes)
- Serper: Free tier (web searches)

**Time per Test Run**:
- `test_analyze_sunscreen()`: 10-30 seconds
- `test_analyze_lipstick()`: 10-30 seconds
- `test_invalid_api_key()`: <1 second
- **Total**: ~20-60 seconds for full suite

### Running Tests

```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run specific test
pytest tests/e2e/test_product_analysis.py::test_analyze_sunscreen -v

# Run with output
pytest tests/e2e/ -v -s

# Run with coverage
pytest tests/e2e/ --cov=src --cov-report=html
```

---

## Test Data

### Products Used in Tests

**Sunscreen** (test_analyze_sunscreen):
- ASIN: B004D24D0S
- Product: Neutrogena Ultra Sheer Dry-Touch Sunscreen SPF 100+
- Why: Common consumer product, known ingredients, consistent availability

**Lipstick** (test_analyze_lipstick):
- ASIN: B07W4RHDPL
- Product: Maybelline SuperStay Matte Ink Liquid Lipstick
- Why: Cosmetic category, different analysis patterns than sunscreen

---

## Pytest Configuration

**Marks Used**:
- `@pytest.mark.asyncio` - Enables async test execution

**Fixtures Used**: None (tests use direct instantiation)

**Test Discovery**: pytest finds `test_*.py` files automatically

---

## Future Enhancements

**Planned Tests** (not implemented):
- Cache hit testing (run same analysis twice)
- Scraper fallback path (mock scraper failure)
- Invalid URL handling
- Timeout scenarios
- Rate limiting tests
- Concurrent request handling

**Test Data Management**:
- Consider mocking product pages for consistency
- Add fixtures for common test data
- Implement test database cleanup

---

## Related Documentation

- [Tests Overview](../CLAUDE.md) - Parent directory overview
- [API Routes](../../src/api/routes/CLAUDE.md) - Endpoints being tested
- [Backend Overview](../../CLAUDE.md) - Complete backend documentation

---

Last Updated: 2025-11-18
