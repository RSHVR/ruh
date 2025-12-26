# Infrastructure Layer (`/backend/src/infrastructure/`)

## Overview

The infrastructure layer provides external service integrations including database access (Supabase), AI services (Anthropic Claude), web scraping, configuration management, and validation logging.

## Files

| File | Purpose | Lines | Key Classes |
|------|---------|-------|-------------|
| `config.py` | Environment configuration via pydantic-settings | 52 | `Settings` |
| `database.py` | Supabase database operations | 379 | `DatabaseService` |
| `claude_agent.py` | Claude AI product safety analysis | 616 | `ProductSafetyAgent` |
| `claude_query.py` | Claude AI HTML data extraction | 280 | `ClaudeQueryService` |
| `product_scraper.py` | Product scraping orchestration | 66 | `ProductScraperService` |
| `validation_logger.py` | Validation failure logging | 211 | `ValidationLogger` |

## Configuration (config.py)

### Required Environment Variables
| Variable | Purpose |
|----------|---------|
| `anthropic_api_key` | Claude AI API key |
| `api_key` | API authentication key |

### Optional Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `supabase_url` | "" | Supabase project URL |
| `supabase_key` | "" | Supabase API key |
| `api_host` | "0.0.0.0" | API server host |
| `api_port` | 8000 | API server port |
| `debug` | false | Debug mode |
| `log_level` | "INFO" | Logging level |

## Key Services

### DatabaseService
- Supabase client wrapper with caching
- Methods: `get_cached_analysis()`, `store_analysis()`, `get_all_allergens()`, `get_all_pfas()`
- Uses global singleton `db` instance

### ProductSafetyAgent
- Claude AI agent with web_search and web_fetch tools
- Two analysis paths: `analyze_product()` (fallback) and `analyze_extracted_product()` (primary)
- Model: `claude-sonnet-4-5-20250929`

### ClaudeQueryService
- Extracts structured data from HTML without tools
- Methods: `extract_product_data()`, `extract_review_insights()`

## Production Readiness Issues

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **Critical** | No retry logic for Claude API calls | claude_agent.py | Add exponential backoff |
| **Critical** | HTTP client never closed | claude_agent.py:613 | Use context manager |
| **High** | Sync Supabase client in async functions | database.py | Use async client or thread pool |
| **High** | No timeout on database operations | database.py | Add timeout configuration |
| **High** | Missing try/except in `extract_review_insights` | claude_query.py:74 | Add error handling |
| **Medium** | Hardcoded model version | claude_agent.py:20 | Move to config |
| **Medium** | Global singleton not thread-safe | database.py:379 | Use dependency injection |

## Dependencies

### External
- `anthropic` - Claude AI SDK
- `supabase` - Database client
- `httpx` - Async HTTP client
- `pydantic-settings` - Configuration
