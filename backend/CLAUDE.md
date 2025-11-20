# Backend - FastAPI AI Product Safety Server

## Overview

Python FastAPI backend server that powers the Eject product safety analysis system. Uses Anthropic's Claude AI Agent SDK to analyze products for allergens, PFAS compounds, and harmful substances.

**Architecture**: Clean Architecture pattern with clear separation of concerns across API, Domain, and Infrastructure layers.

---

## Function-Level Flow Diagram (All Backend Functions)

### Entry Point

```
📄 run.py::main()
  ├─ Imports: settings from src.infrastructure.config
  ├─ Calls: uvicorn.run(
  │          "src.api.main:app",
  │          host="0.0.0.0",
  │          port=8000,
  │          reload=True
  │        )
  └─ Returns: void (starts server)
```

### API Layer Functions

#### FastAPI Application Setup

```
📄 src/api/main.py::app (FastAPI instance)
  ├─ Creates: FastAPI(title="Eject API", version="1.0.0")
  ├─ Adds: CORSMiddleware(allow_origins=settings.allowed_origins, ...)
  ├─ Includes: health.router (prefix="/api")
  ├─ Includes: analyze.router (prefix="/api")
  └─ Returns: app instance
```

#### Authentication

```
📄 src/api/auth.py::verify_api_key(
      credentials: HTTPAuthorizationCredentials = Security(security)
    ) → None
  ├─ Reads: settings.api_key
  ├─ Compares: credentials.credentials == settings.api_key
  ├─ IF match: Returns None
  └─ IF mismatch: Raises HTTPException(401, "Invalid API key")
```

#### Health Check Endpoint

```
📄 src/api/routes/health.py::get_health() → HealthResponse
  ├─ Gets: current_time = datetime.now(timezone.utc)
  └─ Returns: HealthResponse(
               status="healthy",
               timestamp=current_time.isoformat()
             )
```

#### Product Analysis Endpoint

```
📄 src/api/routes/analyze.py::analyze_product(
      request: AnalysisRequest,
      credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
    ) → AnalysisResponse
  │
  ├─ Step 1: AUTHENTICATION
  │   └─ Dependency injection calls verify_api_key(credentials)
  │
  ├─ Step 2: CACHE CHECK
  │   ├─ Initializes: db = DatabaseService()
  │   ├─ Generates: url_hash = db.generate_url_hash(request.product_url)
  │   ├─ Calls: cached = db.get_cached_analysis(url_hash)
  │   └─ IF cached: Returns AnalysisResponse(cached data, cached=True)
  │
  ├─ Step 3: SCRAPING
  │   ├─ Initializes: scraper_service = ProductScraperService()
  │   ├─ Calls: scraped = scraper_service.try_scrape(request.product_url)
  │   └─ Stores: scraped_product OR None
  │
  ├─ Step 4: AI ANALYSIS (Two Paths)
  │   │
  │   ├─ Path A: IF scraped AND confidence > 0.3
  │   │   ├─ Initializes: claude_query = ClaudeQueryService()
  │   │   ├─ Calls: product_data = claude_query.extract_product_data(
  │   │   │                          scraped.raw_html_product
  │   │   │                        )
  │   │   ├─ Initializes: claude_agent = ProductSafetyAgent()
  │   │   └─ Calls: analysis_data = claude_agent.analyze_extracted_product(
  │   │                               product_data,
  │   │                               request.product_url
  │   │                             )
  │   │
  │   └─ Path B: IF scraping failed OR low confidence
  │       ├─ Initializes: claude_agent = ProductSafetyAgent()
  │       └─ Calls: analysis_data = claude_agent.analyze_product(
  │                                   request.product_url
  │                                 )
  │
  ├─ Step 5: HARM SCORE CALCULATION
  │   ├─ Calls: harm_score = HarmScoreCalculator.calculate(analysis_data)
  │   └─ Computes: overall_score = 100 - harm_score
  │
  ├─ Step 6: BUILD RESPONSE
  │   └─ Creates: analysis = ProductAnalysis(
  │                 product_name=...,
  │                 brand=...,
  │                 overall_score=overall_score,
  │                 allergens_detected=...,
  │                 pfas_detected=...,
  │                 other_concerns=...,
  │                 confidence=...
  │               )
  │
  ├─ Step 7: CACHE STORAGE
  │   └─ Calls: db.store_analysis(url_hash, request.product_url, analysis_response)
  │
  └─ Step 8: RETURN
      └─ Returns: AnalysisResponse(
                    analysis=analysis,
                    alternatives=[],
                    cached=False,
                    url_hash=url_hash
                  )
```

#### Review Insights Endpoint (Implemented but Unused)

```
📄 src/api/routes/analyze.py::get_review_insights(
      request: ReviewInsightsRequest,
      credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
    ) → ReviewInsightsResponse
  │
  ├─ Initializes: scraper_service = ProductScraperService()
  ├─ Calls: scraped = scraper_service.try_scrape(request.product_url)
  │
  ├─ IF scraped:
  │   ├─ Initializes: claude_query = ClaudeQueryService()
  │   └─ Calls: insights = claude_query.extract_review_insights(
  │                          scraped.raw_html_product
  │                        )
  │
  ├─ IF not scraped:
  │   └─ Raises: HTTPException(500, "Failed to scrape reviews")
  │
  └─ Returns: ReviewInsightsResponse(insights=insights)
```

### Domain Layer Functions

#### Harm Score Calculation

```
📄 src/domain/harm_calculator.py::HarmScoreCalculator.calculate(
      analysis_data: Dict[str, Any]
    ) → int
  │
  ├─ Initializes: total_score = 0
  │
  ├─ Step 1: ALLERGEN SCORING
  │   ├─ Gets: allergens = analysis_data.get('allergens_detected', [])
  │   └─ For each allergen:
  │       ├─ Reads: severity = allergen.get('severity', 'moderate')
  │       ├─ Adds: 5 (low), 15 (moderate), or 30 (high) points
  │       └─ Accumulates: total_score += points
  │
  ├─ Step 2: PFAS SCORING
  │   ├─ Gets: pfas = analysis_data.get('pfas_detected', [])
  │   └─ For each PFAS:
  │       └─ Adds: 40 points to total_score
  │
  ├─ Step 3: OTHER CONCERNS SCORING
  │   ├─ Gets: concerns = analysis_data.get('other_concerns', [])
  │   └─ For each concern:
  │       ├─ Reads: toxicity = concern.get('toxicity_level', 'low')
  │       ├─ Adds: 5 (low), 15 (medium), or 25 (high) points
  │       └─ Accumulates: total_score += points
  │
  ├─ Step 4: CATEGORY MULTIPLIERS
  │   ├─ Gets: category = analysis_data.get('product_category', '')
  │   ├─ IF 'pesticide' OR 'cleaner': total_score *= 1.3
  │   └─ IF 'food': total_score *= 1.2
  │
  ├─ Step 5: CAPPING
  │   └─ Applies: total_score = max(0, min(100, int(total_score)))
  │
  └─ Returns: total_score (0-100)
```

### Infrastructure Layer Functions

#### Configuration

```
📄 src/infrastructure/config.py::Settings (Pydantic BaseSettings)
  ├─ Loads: Environment variables from .env
  ├─ Defines: anthropic_api_key, supabase_url, supabase_key, api_key, allowed_origins
  └─ Exports: settings = Settings() singleton
```

#### Database Operations

```
📄 src/infrastructure/database.py::DatabaseService.__init__()
  ├─ Reads: settings.supabase_url, settings.supabase_key
  ├─ Calls: create_client(url, key)
  └─ Stores: self.client = Supabase client

📄 src/infrastructure/database.py::generate_url_hash(url: str) → str
  └─ Returns: hashlib.sha256(url.encode()).hexdigest()

📄 src/infrastructure/database.py::get_cached_analysis(url_hash: str) → Dict | None
  ├─ Calls: response = self.client.table('product_analyses')
  │                     .select('*')
  │                     .eq('url_hash', url_hash)
  │                     .execute()
  ├─ IF response.data: Returns response.data[0]
  └─ ELSE: Returns None

📄 src/infrastructure/database.py::store_analysis(
      url_hash: str,
      product_url: str,
      analysis_response: AnalysisResponse
    ) → bool
  │
  ├─ Builds: db_data = {
  │            'url_hash': url_hash,
  │            'product_url': product_url,
  │            'product_name': analysis.product_name,
  │            'brand': analysis.brand,
  │            'overall_score': analysis.overall_score,
  │            'allergens_detected': json.dumps(allergens),
  │            'pfas_detected': json.dumps(pfas),
  │            'other_concerns': json.dumps(concerns),
  │            'confidence': analysis.confidence,
  │            'analyzed_at': datetime.now(timezone.utc).isoformat()
  │          }
  │
  ├─ Calls: self.client.table('product_analyses').upsert(db_data).execute()
  ├─ Returns: True (on success)
  └─ Returns: False (on exception)
```

#### Claude AI Agent

```
📄 src/infrastructure/claude_agent.py::ProductSafetyAgent.__init__()
  ├─ Reads: settings.anthropic_api_key
  ├─ Creates: self.client = Anthropic(api_key=...)
  └─ Defines: self.tools = [web_search_tool, web_fetch_tool]

📄 src/infrastructure/claude_agent.py::analyze_product(url: str) → Dict
  │
  ├─ Builds: system_prompt = "You are an expert product safety analyst..."
  ├─ Builds: user_prompt = f"Analyze this product: {url}"
  │
  ├─ Calls: response = self.client.messages.create(
  │          model="claude-sonnet-4-5-20250929",
  │          max_tokens=8192,
  │          system=system_prompt,
  │          messages=[{role: "user", content: user_prompt}],
  │          tools=[web_search, web_fetch]
  │        )
  │
  ├─ Enters: Tool use loop
  │   ├─ WHILE response has stop_reason == "tool_use":
  │   │   ├─ For each tool_use block:
  │   │   │   ├─ IF tool == "web_search":
  │   │   │   │   └─ Calls: _execute_web_search(input)
  │   │   │   └─ IF tool == "web_fetch":
  │   │   │       └─ Calls: _execute_web_fetch(url)
  │   │   │
  │   │   ├─ Builds: tool_results = [{type: "tool_result", ...}]
  │   │   └─ Calls: response = self.client.messages.create(...) with tool_results
  │   │
  │   └─ Continues until stop_reason == "end_turn"
  │
  ├─ Extracts: final_text = response.content[-1].text
  ├─ Parses: analysis_data = json.loads(final_text)
  └─ Returns: {allergens_detected, pfas_detected, other_concerns, confidence}

📄 src/infrastructure/claude_agent.py::analyze_extracted_product(
      product_data: Dict,
      url: str
    ) → Dict
  │
  ├─ Similar to analyze_product but:
  │   ├─ Prompt includes pre-extracted product_data
  │   ├─ Only web_search tool (no web_fetch needed)
  │   └─ Claude searches for manufacturer safety data
  │
  └─ Returns: analysis_data

📄 src/infrastructure/claude_agent.py::_execute_web_search(query: str) → str
  ├─ Reads: settings.serper_api_key
  ├─ Calls: httpx.post(
  │          'https://google.serper.dev/search',
  │          json={'q': query},
  │          headers={'X-API-KEY': api_key}
  │        )
  ├─ Parses: results = response.json()
  └─ Returns: JSON string of search results

📄 src/infrastructure/claude_agent.py::_execute_web_fetch(url: str) → str
  ├─ Calls: httpx.get(url, timeout=10)
  ├─ Returns: response.text
  └─ Returns: error message (on failure)

📄 src/infrastructure/claude_agent.py::find_alternatives(...) → List[Dict]
  └─ Returns: [] (TODO: Phase 4 implementation)
```

#### Claude Query Service (Data Extraction)

```
📄 src/infrastructure/claude_query.py::ClaudeQueryService.__init__()
  ├─ Reads: settings.anthropic_api_key
  └─ Creates: self.client = Anthropic(api_key=...)

📄 src/infrastructure/claude_query.py::extract_product_data(html: str) → Dict
  │
  ├─ Builds: prompt = "Extract structured product data from this HTML..."
  ├─ Calls: response = self.client.messages.create(
  │          model="claude-sonnet-4-5-20250929",
  │          max_tokens=4096,
  │          messages=[{role: "user", content: prompt + html}]
  │        )
  │   (NO TOOLS - pure extraction)
  │
  ├─ Extracts: text = response.content[0].text
  ├─ Parses: data = json.loads(text)
  └─ Returns: {product_name, brand, ingredients, materials, features, ...}

📄 src/infrastructure/claude_query.py::extract_review_insights(html: str) → ReviewInsights
  │
  ├─ Similar to extract_product_data
  ├─ Prompt: "Extract safety-related review insights..."
  └─ Returns: ReviewInsights(common_concerns, positive_safety_notes, ...)
```

#### Product Scraper Service

```
📄 src/infrastructure/product_scraper.py::ProductScraperService.__init__()
  └─ (No initialization needed)

📄 src/infrastructure/product_scraper.py::try_scrape(url: str) → ScrapedProduct | None
  │
  ├─ Calls: scraper = ScraperFactory.get_scraper(url)
  │
  ├─ IF scraper:
  │   ├─ Calls: result = await scraper.scrape(url)
  │   └─ Returns: result (ScrapedProduct)
  │
  └─ ELSE:
      └─ Returns: None
```

#### Scraper Factory

```
📄 src/infrastructure/scrapers/factory.py::ScraperFactory.get_scraper(
      url: str
    ) → BaseScraper | None
  │
  ├─ IF 'amazon.com' in url OR 'amazon.' in url:
  │   └─ Returns: AmazonScraper()
  │
  └─ ELSE:
      └─ Returns: None
```

#### Amazon Scraper

```
📄 src/infrastructure/scrapers/amazon.py::AmazonScraper.scrape(
      url: str
    ) → ScrapedProduct
  │
  ├─ Step 1: HTTP FETCH
  │   ├─ Defines: headers = {'User-Agent': '...', 'Accept-Language': 'en-US', ...}
  │   ├─ Calls: async with httpx.AsyncClient() as client:
  │   │          response = await client.get(url, headers=headers, timeout=10)
  │   └─ Gets: html = response.text
  │
  ├─ Step 2: HTML PARSING
  │   ├─ Creates: soup = BeautifulSoup(html, 'lxml')
  │   ├─ Extracts: title = soup.select_one('#productTitle').get_text()
  │   ├─ Extracts: brand = soup.select_one('#bylineInfo').get_text()
  │   ├─ Extracts: features = soup.select('#feature-bullets li')
  │   └─ Extracts: details = soup.select('#productDetails_detailBullets_sections1')
  │
  ├─ Step 3: INGREDIENT/MATERIAL EXTRACTION
  │   ├─ Searches: Keywords like 'ingredients', 'materials', 'composition'
  │   ├─ Finds: Relevant sections in features and details
  │   └─ Builds: raw_html_product (concatenated relevant sections)
  │
  ├─ Step 4: CONFIDENCE CALCULATION
  │   ├─ Initializes: confidence = 0.0
  │   ├─ IF title found: confidence += 0.3
  │   ├─ IF brand found: confidence += 0.2
  │   ├─ IF ingredients found: confidence += 0.5
  │   └─ Caps: confidence = min(1.0, confidence)
  │
  └─ Returns: ScrapedProduct(
                raw_html_product=raw_html_product,
                confidence=confidence
              )
```

### Test Functions

```
📄 tests/e2e/test_product_analysis.py::test_analyze_sunscreen()
  ├─ Creates: client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
  ├─ Calls: response = await client.post('/api/analyze', json={...}, headers={...})
  ├─ Asserts: response.status_code == 200
  ├─ Asserts: 'analysis' in response.json()
  └─ Asserts: harm_score is calculated

📄 tests/e2e/test_product_analysis.py::test_analyze_lipstick()
  └─ Similar to test_analyze_sunscreen with different product

📄 tests/e2e/test_product_analysis.py::test_invalid_api_key()
  ├─ Calls: POST /api/analyze with wrong API key
  └─ Asserts: response.status_code == 401
```

---

## File-Level Import Relationships

### API Layer Imports

```
src/api/main.py
  IMPORTS:
    - fastapi.{FastAPI, HTTPException}
    - fastapi.middleware.cors.CORSMiddleware
    - src.infrastructure.config.settings
    - src.api.routes.{health, analyze}
  IMPORTED BY:
    - run.py (as module string)
    - tests/e2e/test_product_analysis.py

src/api/auth.py
  IMPORTS:
    - fastapi.{HTTPException, Security}
    - fastapi.security.{HTTPAuthorizationCredentials, HTTPBearer}
    - src.infrastructure.config.settings
  IMPORTED BY:
    - src/api/routes/analyze.py

src/api/routes/health.py
  IMPORTS:
    - fastapi.APIRouter
    - pydantic.BaseModel
    - datetime
  IMPORTED BY:
    - src/api/main.py

src/api/routes/analyze.py
  IMPORTS:
    - fastapi.{APIRouter, HTTPException, Depends}
    - src.domain.models.*
    - src.domain.harm_calculator.HarmScoreCalculator
    - src.infrastructure.claude_agent.ProductSafetyAgent
    - src.infrastructure.product_scraper.ProductScraperService
    - src.infrastructure.claude_query.ClaudeQueryService
    - src.infrastructure.database.DatabaseService
    - src.api.auth.verify_api_key
  IMPORTED BY:
    - src/api/main.py
```

### Domain Layer Imports

```
src/domain/models.py
  IMPORTS:
    - pydantic.{BaseModel, Field}
    - datetime, enum, typing, uuid
  IMPORTED BY:
    - src/api/routes/analyze.py
    - src/infrastructure/claude_query.py
    - src/infrastructure/database.py
    - src/infrastructure/product_scraper.py
    - src/infrastructure/scrapers/amazon.py

src/domain/harm_calculator.py
  IMPORTS:
    - typing.{Dict, Any}
  IMPORTED BY:
    - src/api/routes/analyze.py
```

### Infrastructure Layer Imports

```
src/infrastructure/config.py
  IMPORTS:
    - pydantic_settings.{BaseSettings, SettingsConfigDict}
  IMPORTED BY:
    - run.py
    - src/api/main.py
    - src/api/auth.py
    - src/infrastructure/claude_agent.py
    - src/infrastructure/claude_query.py
    - src/infrastructure/database.py

src/infrastructure/database.py
  IMPORTS:
    - supabase.{create_client, Client}
    - src.infrastructure.config.settings
  IMPORTED BY:
    - src/api/routes/analyze.py

src/infrastructure/claude_agent.py
  IMPORTS:
    - anthropic.{Anthropic, RateLimitError, APIError}
    - src.infrastructure.config.settings
  IMPORTED BY:
    - src/api/routes/analyze.py

src/infrastructure/claude_query.py
  IMPORTS:
    - anthropic.Anthropic
    - src.infrastructure.config.settings
    - src.domain.models.ScrapedProduct
  IMPORTED BY:
    - src/api/routes/analyze.py

src/infrastructure/product_scraper.py
  IMPORTS:
    - src.infrastructure.scrapers.factory.ScraperFactory
    - src.domain.models.ScrapedProduct
  IMPORTED BY:
    - src/api/routes/analyze.py

src/infrastructure/scrapers/factory.py
  IMPORTS:
    - src.infrastructure.scrapers.base.BaseScraper
    - src.infrastructure.scrapers.amazon.AmazonScraper
  IMPORTED BY:
    - src/infrastructure/product_scraper.py

src/infrastructure/scrapers/base.py
  IMPORTS:
    - abc.{ABC, abstractmethod}
  IMPORTED BY:
    - src/infrastructure/scrapers/factory.py
    - src/infrastructure/scrapers/amazon.py

src/infrastructure/scrapers/amazon.py
  IMPORTS:
    - httpx, bs4.BeautifulSoup
    - src.infrastructure.scrapers.base.BaseScraper
    - src.domain.models.ScrapedProduct
  IMPORTED BY:
    - src/infrastructure/scrapers/factory.py
```

---

## Directory Structure

```
/backend/
├── run.py                          # Entry point - starts uvicorn server
├── pyproject.toml                  # Python project config, dependencies
├── requirements.txt                # Pip requirements
├── uv.lock                         # UV lock file
├── Dockerfile                      # Docker container config
├── .env                            # Environment variables (git-ignored)
├── .env.example                    # Example environment config
├── README.md                       # Backend setup docs
├── DEPLOY.md                       # Deployment documentation
├── IMPLEMENTATION_SUMMARY.md       # Implementation summary
│
├── src/                            # Source code → [src/CLAUDE.md](./src/CLAUDE.md)
├── migrations/                     # ⚠️ BLOAT: Legacy migrations → [migrations/CLAUDE.md](./migrations/CLAUDE.md)
├── supabase/                       # Supabase database → [supabase/CLAUDE.md](./supabase/CLAUDE.md)
└── tests/                          # Test suite → [tests/CLAUDE.md](./tests/CLAUDE.md)
```

---

## Bloat Identification

### ⚠️ BLOAT: Legacy Migrations Directory

**Location**: `./migrations/`

**Evidence**:
- Contains old SQL files superseded by `./supabase/migrations/`
- Old schema missing tables and columns
- Not used in production

**Files**:
- `001_create_tables.sql` (outdated schema)
- `002_seed_knowledge_base.sql` (legacy seed data)

---

## Key Technologies

- **Framework**: FastAPI (async Python web framework)
- **AI**: Anthropic Claude Sonnet 4.5 with Agent SDK
- **Database**: Supabase (PostgreSQL with real-time features)
- **Scraping**: httpx + BeautifulSoup4
- **Testing**: pytest with async support
- **Deployment**: Docker + Google Cloud Run

---

## Related Documentation

- [Root Documentation](../CLAUDE.md) - Complete system overview
- [Source Code](./src/CLAUDE.md) - Detailed source code documentation
- [Database](./supabase/CLAUDE.md) - Supabase schema and migrations
- [Tests](./tests/CLAUDE.md) - Test suite documentation

---

Last Updated: 2025-11-18
