# Web Scrapers

## Overview

Website-specific web scrapers for extracting product information from retailer pages. Uses factory pattern for scraper selection based on URL.

---

## Function-Level Flow Diagram

### Factory Pattern

```
📄 factory.py::ScraperFactory.get_scraper(url: str) → BaseScraper | None
  │
  ├─ Checks: if 'amazon.com' in url OR 'amazon.' in url
  │   └─ Returns: AmazonScraper()
  │
  ├─ Checks: (Future: other retailers)
  │
  └─ Returns: None (no scraper available for URL)
```

### Amazon Scraper

```
📄 amazon.py::AmazonScraper.scrape(url: str) → ScrapedProduct
  │
  ├─ Step 1: HTTP REQUEST
  │   ├─ Defines: headers = {
  │   │            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...',
  │   │            'Accept-Language': 'en-US,en;q=0.9',
  │   │            'Accept': 'text/html,application/xhtml+xml,...',
  │   │            'Accept-Encoding': 'gzip, deflate, br',
  │   │            'Connection': 'keep-alive'
  │   │          }
  │   ├─ Calls: async with httpx.AsyncClient() as client:
  │   │          response = await client.get(url, headers=headers, timeout=10)
  │   └─ Gets: html = response.text
  │
  ├─ Step 2: HTML PARSING
  │   ├─ Creates: soup = BeautifulSoup(html, 'lxml')
  │   │
  │   ├─ Extracts: title = soup.select_one('#productTitle')?.get_text(strip=True)
  │   ├─ Extracts: brand = soup.select_one('#bylineInfo')?.get_text(strip=True)
  │   ├─ Extracts: price = soup.select_one('.a-price .a-offscreen')?.get_text(strip=True)
  │   │
  │   ├─ Extracts: features = []
  │   │   └─ For each soup.select('#feature-bullets li'):
  │   │       └─ features.append(li.get_text(strip=True))
  │   │
  │   ├─ Extracts: details = soup.select('#productDetails_detailBullets_sections1 tr')
  │   │   └─ For each row: {label: value}
  │   │
  │   └─ Extracts: description = soup.select_one('#productDescription')?.get_text(strip=True)
  │
  ├─ Step 3: INGREDIENT/MATERIAL EXTRACTION
  │   ├─ Defines: keywords = ['ingredient', 'material', 'composition', 'contains', 'made from']
  │   │
  │   ├─ Searches features for keywords:
  │   │   └─ For each feature:
  │   │       └─ IF any keyword in feature.lower():
  │   │           └─ Add to relevant_sections
  │   │
  │   ├─ Searches details for keywords:
  │   │   └─ For each detail:
  │   │       └─ IF any keyword in label.lower():
  │   │           └─ Add to relevant_sections
  │   │
  │   └─ Builds: raw_html_product = '\n'.join([
  │                title,
  │                brand,
  │                ...relevant_sections,
  │                description
  │              ])
  │
  ├─ Step 4: CONFIDENCE CALCULATION
  │   ├─ Initializes: confidence = 0.0
  │   ├─ IF title found: confidence += 0.3
  │   ├─ IF brand found: confidence += 0.2
  │   ├─ IF ingredients/materials found: confidence += 0.5
  │   └─ Caps: confidence = min(1.0, confidence)
  │
  └─ Returns: ScrapedProduct(
                raw_html_product=raw_html_product,
                confidence=confidence
              )
```

---

## File-Level Import Relationships

```
base.py
  IMPORTS:
    - abc.{ABC, abstractmethod}
    - typing.TYPE_CHECKING (for ScrapedProduct type hint)
  IMPORTED BY:
    - factory.py
    - amazon.py

factory.py
  IMPORTS:
    - typing.{Optional}
    - .base.BaseScraper
    - .amazon.AmazonScraper
  IMPORTED BY:
    - ../product_scraper.py

amazon.py
  IMPORTS:
    - re, logging, datetime, typing
    - httpx.AsyncClient
    - bs4.BeautifulSoup
    - .base.BaseScraper
    - ...domain.models.ScrapedProduct
  IMPORTED BY:
    - factory.py
```

---

## Directory Structure

```
/backend/src/infrastructure/scrapers/
├── __init__.py        # Package marker (empty)
├── base.py            # Abstract base scraper (ABC)
├── factory.py         # Factory for scraper selection
└── amazon.py          # Amazon product page scraper
```

---

## Files Description

### base.py
**Purpose**: Abstract base class defining scraper interface

**Key Features**:
- Abstract `scrape()` method
- Enforces contract for all scrapers

**Code**:
```python
class BaseScraper(ABC):
    @abstractmethod
    async def scrape(self, url: str) -> 'ScrapedProduct':
        pass
```

**Dependencies**: None (abstract base)

**Relationships**:
- Inherited by all concrete scrapers
- Ensures consistent interface

### factory.py
**Purpose**: Factory pattern for selecting appropriate scraper based on URL

**Key Functions**:
- `get_scraper(url)` - Returns scraper instance or None

**Algorithm**:
1. Checks URL domain
2. Returns appropriate scraper instance
3. Easily extensible for new retailers

**Dependencies**:
- base.BaseScraper
- amazon.AmazonScraper

**Relationships**:
- Called by `../product_scraper.py::try_scrape()`
- Central routing for scraping logic

### amazon.py
**Purpose**: Scrapes Amazon product pages for product data

**Key Features**:
- Real browser User-Agent to avoid bot detection
- CSS selectors for Amazon's HTML structure
- Keyword-based ingredient/material extraction
- Confidence scoring (0.0-1.0)

**CSS Selectors Used**:
- `#productTitle` - Product name
- `#bylineInfo` - Brand/manufacturer
- `.a-price .a-offscreen` - Price
- `#feature-bullets li` - Key features/details
- `#productDetails_detailBullets_sections1 tr` - Product details table
- `#productDescription` - Full description

**Confidence Scoring**:
- 0.3 - Title found
- 0.2 - Brand found
- 0.5 - Ingredients/materials found
- Sum capped at 1.0

**Dependencies**:
- httpx - Async HTTP client
- BeautifulSoup4 - HTML parsing
- base.BaseScraper
- domain.models.ScrapedProduct

**Relationships**:
- Instantiated by factory.py
- Returns ScrapedProduct to product_scraper.py
- Data passed to claude_query.py for extraction

---

## Scraping Strategy

### Why Custom Scraping?

**Advantages**:
- Faster than Claude web_fetch (no AI latency)
- More reliable extraction of structured data
- Lower cost (no AI API calls for scraping)
- Better handling of JavaScript-rendered content

**Fallback**:
- If scraping fails (confidence < 0.3), Claude's web_fetch tool is used
- Provides robustness against changes in HTML structure

### Confidence Threshold

**Current threshold**: 0.3 (30%)

**Rationale**:
- Minimum: Title only (0.3) = basic product identification
- Good: Title + Brand (0.5) = decent confidence
- Excellent: Title + Brand + Ingredients (1.0) = full extraction

**Used in**: `api/routes/analyze.py`
```python
if scraped and scraped.confidence > 0.3:
    # Use scraped data path
else:
    # Fallback to Claude web_fetch
```

---

## Future Extensibility

### Adding New Scrapers

To add a new retailer (e.g., Walmart):

1. **Create scraper**: `walmart.py`
```python
class WalmartScraper(BaseScraper):
    async def scrape(self, url: str) -> ScrapedProduct:
        # Implement Walmart-specific scraping
        pass
```

2. **Update factory**: `factory.py`
```python
if 'walmart.com' in url:
    return WalmartScraper()
```

3. **No other changes needed** - factory pattern isolates changes

---

## Related Documentation

- [Infrastructure Layer](../CLAUDE.md) - Parent directory overview
- [Product Scraper Service](../CLAUDE.md) - Orchestration layer
- [Domain Models](../../domain/CLAUDE.md) - ScrapedProduct definition

---

Last Updated: 2025-11-18
