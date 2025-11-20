# Backend Source Code

## Overview

Main source code for the Eject backend following clean architecture principles with clear separation across API, Domain, and Infrastructure layers.

---

## Function-Level Flow Diagram (All src/ Functions)

See [backend/CLAUDE.md](../CLAUDE.md) for complete function flows covering:
- API Layer: FastAPI routes, authentication, request/response handling
- Domain Layer: Business logic (harm calculation), data models
- Infrastructure Layer: External services (Claude AI, Supabase, web scraping)

---

## File-Level Import Relationships

```
api/                    (Presentation Layer)
  ├─ main.py           → config.settings, routes.*
  ├─ auth.py           → config.settings
  └─ routes/
      ├─ health.py     → (no internal imports)
      └─ analyze.py    → auth.*, domain.*, infrastructure.*

application/            (⚠️ BLOAT: Empty layer)
  └─ __init__.py       → (empty file)

domain/                 (Business Logic)
  ├─ models.py         → (no internal imports - pure Pydantic)
  └─ harm_calculator.py → (no internal imports - pure logic)

infrastructure/         (External Dependencies)
  ├─ config.py         → (no internal imports - Pydantic settings)
  ├─ database.py       → config.settings
  ├─ claude_agent.py   → config.settings
  ├─ claude_query.py   → config.settings, domain.models
  ├─ product_scraper.py → domain.models, scrapers.factory
  └─ scrapers/
      ├─ base.py       → (abstract base)
      ├─ factory.py    → base.*, amazon.*
      └─ amazon.py     → base.*, domain.models
```

---

## Directory Structure

```
/backend/src/
├── __init__.py                     # Package marker (empty)
│
├── api/                            # API/Presentation Layer → [api/CLAUDE.md](./api/CLAUDE.md)
│   ├── __init__.py                # Package marker (empty)
│   ├── main.py                    # FastAPI app setup, CORS, middleware
│   ├── auth.py                    # API key authentication
│   └── routes/                    # API endpoints → [api/routes/CLAUDE.md](./api/routes/CLAUDE.md)
│       ├── __init__.py            # Package marker (empty)
│       ├── health.py              # Health check endpoint
│       └── analyze.py             # Product analysis endpoint
│
├── application/                    # ⚠️ BLOAT: Application Layer → [application/CLAUDE.md](./application/CLAUDE.md)
│   └── __init__.py                # Empty - unused architectural layer
│
├── domain/                         # Domain Layer → [domain/CLAUDE.md](./domain/CLAUDE.md)
│   ├── __init__.py                # Package marker (empty)
│   ├── models.py                  # Pydantic data models
│   └── harm_calculator.py         # Harm scoring algorithm
│
└── infrastructure/                 # Infrastructure Layer → [infrastructure/CLAUDE.md](./infrastructure/CLAUDE.md)
    ├── __init__.py                # Package marker (empty)
    ├── config.py                  # Configuration management
    ├── database.py                # Supabase client
    ├── claude_agent.py            # Claude AI agent with tools
    ├── claude_query.py            # Claude query service (data extraction)
    ├── product_scraper.py         # Scraping orchestration
    └── scrapers/                  # Web scrapers → [infrastructure/scrapers/CLAUDE.md](./infrastructure/scrapers/CLAUDE.md)
        ├── __init__.py            # Package marker (empty)
        ├── base.py                # Abstract base scraper
        ├── factory.py             # Scraper factory pattern
        └── amazon.py              # Amazon product scraper
```

---

## Architecture Pattern: Clean Architecture

### Layer Responsibilities

**API Layer** (`api/`)
- HTTP request/response handling
- Route definitions
- Authentication/authorization
- Input validation
- Calls Domain and Infrastructure layers

**Domain Layer** (`domain/`)
- Core business logic
- Domain models (entities, value objects)
- Business rules (harm score calculation)
- NO external dependencies (pure Python)

**Infrastructure Layer** (`infrastructure/`)
- External service integrations
- Database access (Supabase)
- AI services (Claude)
- Web scraping
- Configuration management

### Dependency Rule

```
API Layer
  ↓ (depends on)
Domain Layer  ←  Infrastructure Layer
```

- API layer depends on Domain and Infrastructure
- Domain layer is independent (no imports from other layers)
- Infrastructure layer depends on Domain for models
- Infrastructure never calls API

---

## Bloat Identification

### ⚠️ BLOAT: Application Layer

**Location**: `./application/`

**Evidence**:
- Directory contains only empty `__init__.py`
- No use case implementations
- Business logic exists directly in `domain/` and orchestration in `api/routes/`

**Impact**: None (completely unused)

---

## Related Documentation

- [Backend Overview](../CLAUDE.md) - Complete backend function flows
- [API Layer](./api/CLAUDE.md) - Presentation layer details
- [Domain Layer](./domain/CLAUDE.md) - Business logic details
- [Infrastructure Layer](./infrastructure/CLAUDE.md) - External services details

---

Last Updated: 2025-11-18
