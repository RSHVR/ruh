# API Layer (`/backend/src/api/`)

## Overview

The API layer provides the HTTP interface for the Ruh product safety analysis system. Built with FastAPI, it implements a RESTful API with Bearer token authentication, rate limiting (via slowapi), and CORS support for Chrome extensions.

## Files

| File | Purpose | Lines | Key Functions |
|------|---------|-------|---------------|
| `main.py` | FastAPI app entry point, middleware, router registration | 75 | `lifespan()`, `root()` |
| `auth.py` | Bearer token authentication | 34 | `verify_api_key()` |
| `routes/analyze.py` | Product analysis and review insights endpoints | 563 | `validate_and_filter_substances()`, `analyze_product()`, `get_review_insights()` |
| `routes/health.py` | Health check endpoint | 30 | `health_check()` |
| `routes/admin.py` | Administrative endpoints for validation monitoring | 255 | `get_validation_logs()`, `get_validation_stats()` |

## API Endpoints

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| GET | `/` | No | 100/min | API info |
| GET | `/api/health` | No | 100/min | Health check |
| POST | `/api/analyze` | Yes | 30/min | Analyze product for harmful substances |
| GET | `/api/analyze/{url_hash}/reviews` | Yes | 100/min | Get consumer review insights |
| GET | `/api/admin/validation-logs` | Yes | 100/min | Query validation logs |
| GET | `/api/admin/validation-stats` | Yes | 100/min | Get validation statistics |

## Production Readiness Issues

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **Critical** | CORS allows all origins (`*`) | main.py:52 | Restrict to specific origins |
| **Critical** | No input validation on product_url | analyze.py:166 | Add URL validation |
| **Critical** | Timing-vulnerable API key comparison | auth.py:26 | Use `secrets.compare_digest()` |
| **High** | No unit tests for API layer | All files | Add comprehensive tests |
| **High** | No request timeout for Claude AI calls | analyze.py | Add timeout configuration |
| **Medium** | LOG-ONLY validation mode ships invalid data | analyze.py:130 | Switch to STRICT mode |

## Dependencies

### Internal
- `src.infrastructure.config.settings`
- `src.domain.models.*`
- `src.domain.harm_calculator.HarmScoreCalculator`
- `src.infrastructure.claude_agent.ProductSafetyAgent`
- `src.infrastructure.database.db`

### External
- `fastapi` - Web framework
- `slowapi` - Rate limiting
- `pydantic` - Request/response validation

## Test Coverage

| Endpoint | E2E Tests | Unit Tests |
|----------|-----------|------------|
| `GET /api/health` | Yes | No |
| `POST /api/analyze` | Yes (4 tests) | No |
| `GET /api/analyze/{url_hash}/reviews` | No | No |
| Admin endpoints | No | No |

**Overall Coverage**: ~22% of endpoints have any test coverage
