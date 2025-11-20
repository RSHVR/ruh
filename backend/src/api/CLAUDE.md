# API Layer - Presentation

## Overview

FastAPI presentation layer handling HTTP requests, authentication, routing, and CORS middleware.

---

## Function-Level Flow Diagram

### FastAPI Application Setup

```
📄 main.py::app (FastAPI instance)
  ├─ Creates: FastAPI(title="Eject API", version="1.0.0")
  ├─ Adds: CORSMiddleware(
  │         allow_origins=settings.allowed_origins,
  │         allow_credentials=True,
  │         allow_methods=["*"],
  │         allow_headers=["*"]
  │       )
  ├─ Includes: health.router (prefix="/api")
  ├─ Includes: analyze.router (prefix="/api")
  └─ Returns: app instance
```

### Authentication

```
📄 auth.py::verify_api_key(
      credentials: HTTPAuthorizationCredentials = Security(security)
    ) → None
  ├─ Reads: settings.api_key (from environment)
  ├─ Compares: credentials.credentials == settings.api_key
  ├─ IF match: Returns None (authentication successful)
  └─ IF mismatch: Raises HTTPException(401, "Invalid API key")
```

---

## File-Level Import Relationships

```
main.py
  IMPORTS:
    - fastapi.{FastAPI, HTTPException}
    - fastapi.middleware.cors.CORSMiddleware
    - ..infrastructure.config.settings
    - .routes.{health, analyze}
  IMPORTED BY:
    - run.py (as module string "src.api.main:app")
    - tests/e2e/test_product_analysis.py

auth.py
  IMPORTS:
    - fastapi.{HTTPException, Security}
    - fastapi.security.{HTTPAuthorizationCredentials, HTTPBearer}
    - ..infrastructure.config.settings
  IMPORTED BY:
    - .routes.analyze.py
```

---

## Directory Structure

```
/backend/src/api/
├── __init__.py        # Package marker (empty)
├── main.py            # FastAPI app, CORS middleware, route registration
├── auth.py            # Bearer token authentication
└── routes/            # API endpoints → [routes/CLAUDE.md](./routes/CLAUDE.md)
    ├── __init__.py    # Package marker (empty)
    ├── health.py      # GET /api/health
    └── analyze.py     # POST /api/analyze, POST /api/analyze/reviews
```

---

## Files Description

### main.py
**Purpose**: FastAPI application initialization and configuration

**Functions**:
- `app` - FastAPI instance with CORS middleware

**Dependencies**:
- Imports `settings` from infrastructure layer
- Includes routers from `routes/` subdirectory

**Relationships**:
- Entry point loaded by `run.py`
- Imports and registers all route modules
- Used by tests for creating test clients

### auth.py
**Purpose**: API key authentication using Bearer token scheme

**Functions**:
- `verify_api_key()` - FastAPI dependency for protected endpoints

**Dependencies**:
- Reads `settings.api_key` from config

**Relationships**:
- Used as `Depends(verify_api_key)` in `routes/analyze.py`
- Validates all `/api/analyze` requests

### routes/ Subdirectory
Contains individual API endpoint definitions. See [routes/CLAUDE.md](./routes/CLAUDE.md) for details.

---

## Related Documentation

- [Backend Source](../CLAUDE.md) - Parent directory overview
- [Routes](./routes/CLAUDE.md) - API endpoint implementations
- [Infrastructure Config](../infrastructure/CLAUDE.md) - Configuration management

---

Last Updated: 2025-11-18
