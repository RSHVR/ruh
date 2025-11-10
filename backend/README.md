# Eject Backend

AI-powered product safety analysis backend using FastAPI and Claude Agent SDK.

## Setup

### Requirements
- Python 3.13+
- pip or uv

### Installation

1. Install dependencies:
```bash
pip install -e .
# Or for development:
pip install -e ".[dev]"
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. Run the server:
```bash
python run.py
```

The API will be available at http://localhost:8000

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Endpoints

### Health Check
```bash
GET /api/health
```

### Analyze Product
```bash
POST /api/analyze
Content-Type: application/json

{
  "product_url": "https://www.amazon.ca/product/...",
  "allergen_profile": ["peanuts", "dairy"],
  "force_refresh": false
}
```

Response:
```json
{
  "analysis": {
    "product_name": "Product Name",
    "brand": "Brand",
    "overall_score": 75,
    "allergens_detected": [...],
    "pfas_detected": [...],
    "other_concerns": [...],
    "confidence": 0.85
  },
  "alternatives": [],
  "cached": false
}
```

## Testing

Run E2E tests with real Amazon products:
```bash
pytest tests/e2e/test_product_analysis.py -v
```

Run all tests:
```bash
pytest tests/ -v
```

## Architecture

```
backend/
├── src/
│   ├── domain/          # Business logic, entities, harm calculator
│   ├── application/     # Use cases, services
│   ├── infrastructure/  # External dependencies (Claude, DB, Redis)
│   └── api/            # FastAPI routes, middleware
├── tests/
│   ├── unit/           # Unit tests
│   ├── integration/    # Integration tests
│   └── e2e/           # End-to-end tests
└── migrations/        # Database migrations
```

## Phase 1 Status

✅ FastAPI scaffold with clean architecture
✅ Health check endpoint
✅ Claude Agent with WebFetch/WebSearch tools
✅ Harm score calculation formula
✅ E2E tests with Amazon product URLs
⏳ Supabase database integration (Phase 3)
⏳ Redis caching (Phase 3)
⏳ Celery job queue (Phase 3)

## Next Steps

1. Run E2E tests to validate Claude integration
2. Create Supabase migrations for database schema
3. Integrate database queries into agent workflow
4. Add Redis caching layer
5. Set up Celery for parallel processing
