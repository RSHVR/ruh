# Scrapers Module (`/backend/src/infrastructure/scrapers/`)

## Overview

The scrapers module provides web scraping functionality for extracting product data from e-commerce websites. It implements a factory pattern with a **config-driven** abstract base class (template method — see repo-root `LORE.md` ADR-001): generic mechanics live in `BaseScraper`, and each retailer is a subclass that declares selector configuration only. 12 retailers are implemented — Amazon (reference, with structured-review overrides) plus Walmart, Costco, Instacart, Sephora, H&M, Uniqlo, SHEIN, Aritzia, Garage, IKEA, and Temu. The primary data path is `process_client_html` (the extension sends the user's authenticated DOM); server-side Playwright `scrape()` is a fallback. Adding a retailer = a config subclass + a `factory.py` registration + tests (see repo-root `INDEX.md` §5).

## Architecture

```
BaseScraper (ABC)
  └── AmazonScraper
        └── ScraperFactory (selects appropriate scraper)
              └── ProductScraperService (orchestrates with fallback)
```

## Files

| File | Purpose | Lines | Key Classes |
|------|---------|-------|-------------|
| `base.py` | Abstract base class | 41 | `BaseScraper` |
| `amazon.py` | Amazon-specific scraper | 312 | `AmazonScraper` |
| `factory.py` | Scraper selection factory | 41 | `ScraperFactory` |

## AmazonScraper

### Supported Domains
- amazon.com, amazon.ca, amazon.co.uk, amazon.de, amazon.fr, amazon.it, amazon.es, amazon.com.au, amazon.co.jp

### Configuration
- **Timeout**: 15 seconds
- **User-Agent**: Chrome 120.0 on macOS
- **Parser**: BeautifulSoup with lxml backend

### Extraction Selectors
- **Product sections**: 11 CSS selectors (title, brand, price, ingredients, description, etc.)
- **Review sections**: 5 CSS selectors (reviews, Q&A)
- **Excluded sections**: 7 CSS selectors (ads, recommendations)

## Production Readiness Issues

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **Critical** | No rate limiting for Amazon requests | amazon.py:96 | Add 1-2 req/sec throttling |
| **Critical** | Static User-Agent will be blocked | amazon.py:29 | Rotate User-Agents |
| **High** | No retry logic for transient failures | amazon.py:92 | Add exponential backoff |
| **High** | 15s timeout may be too short | amazon.py:96 | Consider 30 seconds |
| **High** | No proxy support | amazon.py | Add proxy rotation |
| **High** | Hardcoded CSS selectors are brittle | amazon.py:36 | Add fallback selectors |
| **Medium** | No CAPTCHA detection | amazon.py | Detect and handle block pages |
| **Medium** | No connection pooling | amazon.py:96 | Share httpx.AsyncClient |

## Error Handling

| Exception Type | Handled | Behavior |
|---------------|---------|----------|
| `httpx.TimeoutException` | Yes | Returns error result with confidence=0.0 |
| `httpx.HTTPStatusError` | Yes | Returns error result with status |
| General `Exception` | Yes | Logs traceback, returns error result |

## Dependencies

- `httpx` - Async HTTP client
- `beautifulsoup4` - HTML parsing
- `lxml` - Fast HTML parser backend
