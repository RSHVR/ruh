# API Routes

## Overview

API endpoint implementations for health checks and product analysis.

---

## Function-Level Flow Diagram

### Health Check Endpoint

```
📄 health.py::get_health() → HealthResponse
  ├─ Gets: current_time = datetime.now(timezone.utc)
  └─ Returns: HealthResponse(
               status="healthy",
               timestamp=current_time.isoformat()
             )

Route: GET /api/health
Response: { "status": "healthy", "timestamp": "2025-11-18T..." }
```

### Product Analysis Endpoint

```
📄 analyze.py::analyze_product(
      request: AnalysisRequest,
      credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
    ) → AnalysisResponse
  │
  ├─ Step 1: AUTHENTICATION (via Depends)
  │   └─ Calls: verify_api_key(credentials)
  │
  ├─ Step 2: CACHE CHECK
  │   ├─ Initializes: db = DatabaseService()
  │   ├─ Generates: url_hash = db.generate_url_hash(request.product_url)
  │   ├─ Calls: cached = db.get_cached_analysis(url_hash)
  │   └─ IF cached: Returns AnalysisResponse(cached data, cached=True)
  │
  ├─ Step 3: SCRAPING
  │   ├─ Initializes: scraper_service = ProductScraperService()
  │   └─ Calls: scraped = scraper_service.try_scrape(request.product_url)
  │
  ├─ Step 4: AI ANALYSIS
  │   ├─ IF scraped AND confidence > 0.3:
  │   │   ├─ Initializes: claude_query = ClaudeQueryService()
  │   │   ├─ Calls: product_data = claude_query.extract_product_data(scraped.raw_html_product)
  │   │   ├─ Initializes: claude_agent = ProductSafetyAgent()
  │   │   └─ Calls: analysis_data = claude_agent.analyze_extracted_product(product_data, url)
  │   └─ ELSE:
  │       ├─ Initializes: claude_agent = ProductSafetyAgent()
  │       └─ Calls: analysis_data = claude_agent.analyze_product(request.product_url)
  │
  ├─ Step 5: HARM SCORE CALCULATION
  │   ├─ Calls: harm_score = HarmScoreCalculator.calculate(analysis_data)
  │   └─ Computes: overall_score = 100 - harm_score
  │
  ├─ Step 6: BUILD RESPONSE
  │   └─ Creates: analysis = ProductAnalysis(...)
  │
  ├─ Step 7: CACHE STORAGE
  │   └─ Calls: db.store_analysis(url_hash, request.product_url, analysis_response)
  │
  └─ Returns: AnalysisResponse(analysis, alternatives=[], cached=False, url_hash)

Route: POST /api/analyze
Request: { "product_url": "https://amazon.com/..." }
Headers: { "Authorization": "Bearer <api_key>" }
Response: { "analysis": {...}, "alternatives": [], "cached": false, "url_hash": "..." }
```

### Review Insights Endpoint (Implemented but Unused)

```
📄 analyze.py::get_review_insights(
      request: ReviewInsightsRequest,
      credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
    ) → ReviewInsightsResponse
  │
  ├─ Initializes: scraper_service = ProductScraperService()
  ├─ Calls: scraped = scraper_service.try_scrape(request.product_url)
  │
  ├─ IF scraped:
  │   ├─ Initializes: claude_query = ClaudeQueryService()
  │   └─ Calls: insights = claude_query.extract_review_insights(scraped.raw_html_product)
  │
  ├─ IF not scraped:
  │   └─ Raises: HTTPException(500, "Failed to scrape reviews")
  │
  └─ Returns: ReviewInsightsResponse(insights=insights)

Route: POST /api/analyze/reviews
Status: ⚠️ IMPLEMENTED BUT UNUSED (not called by extension frontend)
```

---

## File-Level Import Relationships

```
health.py
  IMPORTS:
    - fastapi.APIRouter
    - pydantic.BaseModel
    - datetime
  IMPORTED BY:
    - ../main.py

analyze.py
  IMPORTS:
    - fastapi.{APIRouter, HTTPException, Depends}
    - datetime, logging
    - ...domain.models.{AnalysisRequest, AnalysisResponse, ProductAnalysis, ReviewInsights}
    - ...domain.harm_calculator.HarmScoreCalculator
    - ...infrastructure.claude_agent.ProductSafetyAgent
    - ...infrastructure.product_scraper.ProductScraperService
    - ...infrastructure.claude_query.ClaudeQueryService
    - ...infrastructure.database.DatabaseService
    - ..auth.verify_api_key
  IMPORTED BY:
    - ../main.py
```

---

## Directory Structure

```
/backend/src/api/routes/
├── __init__.py        # Package marker (empty)
├── health.py          # Health check endpoint (GET /api/health)
└── analyze.py         # Product analysis endpoints (POST /api/analyze, /api/analyze/reviews)
```

---

## Files Description

### health.py
**Purpose**: Simple health check endpoint for monitoring and load balancer probes

**Endpoints**:
- `GET /api/health` - Returns service status and timestamp

**Functions**:
- `get_health()` - Returns health status

**Dependencies**: None (no internal imports)

**Relationships**: Standalone endpoint, no dependencies on other services

### analyze.py
**Purpose**: Core product analysis functionality

**Endpoints**:
- `POST /api/analyze` - Analyzes product from URL (MAIN ENDPOINT)
- `POST /api/analyze/reviews` - Extracts review insights (implemented but unused)

**Functions**:
- `analyze_product()` - Complete product safety analysis flow
- `get_review_insights()` - Review analysis (unused by frontend)

**Dependencies**:
- Domain: `models`, `harm_calculator`
- Infrastructure: `claude_agent`, `claude_query`, `product_scraper`, `database`
- API: `auth.verify_api_key`

**Relationships**:
- Called by extension `content.ts::startAnalysis()`
- Orchestrates all backend services
- Entry point for main product analysis feature

---

## Data Flow Summary

```
Extension Request → analyze.py::analyze_product()
  ↓
  ├─ database.py::get_cached_analysis() [Cache check]
  ├─ product_scraper.py::try_scrape() [Web scraping]
  ├─ claude_query.py::extract_product_data() [Data extraction]
  ├─ claude_agent.py::analyze_extracted_product() [AI analysis]
  ├─ harm_calculator.py::calculate() [Harm scoring]
  └─ database.py::store_analysis() [Cache storage]
  ↓
Extension Response ← AnalysisResponse
```

---

## Related Documentation

- [API Layer](../CLAUDE.md) - Parent directory overview
- [Domain Models](../../domain/CLAUDE.md) - Request/response models
- [Infrastructure Services](../../infrastructure/CLAUDE.md) - External service integrations

---

Last Updated: 2025-11-18
