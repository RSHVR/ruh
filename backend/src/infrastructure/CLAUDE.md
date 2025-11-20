# Infrastructure Layer - External Services

## Overview

Infrastructure layer handling all external service integrations: Claude AI, Supabase database, web scraping, and configuration management.

---

## Function-Level Flow Diagram (All Infrastructure Functions)

### Configuration Management

```
📄 config.py::Settings (Pydantic BaseSettings)
  ├─ Loads: .env file from environment
  ├─ Validates: Required fields (anthropic_api_key, supabase_url, etc.)
  └─ Exports: settings singleton

Fields:
  - anthropic_api_key: str
  - supabase_url: str
  - supabase_key: str
  - serper_api_key: str
  - api_key: str
  - allowed_origins: List[str]
```

### Database Service (Supabase)

```
📄 database.py::DatabaseService.__init__()
  ├─ Reads: settings.supabase_url
  ├─ Reads: settings.supabase_key
  └─ Creates: self.client = create_client(url, key)

📄 database.py::generate_url_hash(url: str) → str
  └─ Returns: hashlib.sha256(url.encode()).hexdigest()

📄 database.py::get_cached_analysis(url_hash: str) → Dict | None
  ├─ Calls: response = self.client
  │           .table('product_analyses')
  │           .select('*')
  │           .eq('url_hash', url_hash)
  │           .execute()
  ├─ IF response.data exists:
  │   └─ Returns: response.data[0]
  └─ ELSE:
      └─ Returns: None

📄 database.py::store_analysis(
      url_hash: str,
      product_url: str,
      analysis_response: AnalysisResponse
    ) → bool
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
  ├─ Calls: self.client.table('product_analyses').upsert(db_data).execute()
  ├─ Returns: True (on success)
  └─ Returns: False (on exception)
```

### Claude AI Agent (Analysis with Tools)

```
📄 claude_agent.py::ProductSafetyAgent.__init__()
  ├─ Reads: settings.anthropic_api_key
  ├─ Creates: self.client = Anthropic(api_key=...)
  └─ Defines: self.tools = [web_search_tool, web_fetch_tool]

📄 claude_agent.py::analyze_product(url: str) → Dict
  │
  ├─ Builds: system_prompt = "You are an expert product safety analyst..."
  ├─ Builds: user_prompt = f"Analyze product at {url} for allergens, PFAS, toxins"
  │
  ├─ Calls: response = self.client.messages.create(
  │          model="claude-sonnet-4-5-20250929",
  │          max_tokens=8192,
  │          system=system_prompt,
  │          messages=[{role: "user", content: user_prompt}],
  │          tools=[web_search, web_fetch]
  │        )
  │
  ├─ TOOL USE LOOP:
  │   ├─ WHILE response.stop_reason == "tool_use":
  │   │   ├─ For each tool_use in response.content:
  │   │   │   ├─ IF tool.name == "web_search":
  │   │   │   │   └─ Calls: result = _execute_web_search(tool.input)
  │   │   │   └─ IF tool.name == "web_fetch":
  │   │   │       └─ Calls: result = _execute_web_fetch(tool.input['url'])
  │   │   │
  │   │   ├─ Builds: tool_results = [{type: "tool_result", tool_use_id, content}]
  │   │   │
  │   │   └─ Calls: response = self.client.messages.create(
  │   │              model="claude-sonnet-4-5-20250929",
  │   │              max_tokens=8192,
  │   │              messages=[...previous_messages, tool_results]
  │   │            )
  │   │
  │   └─ BREAK when stop_reason == "end_turn"
  │
  ├─ Extracts: final_text = response.content[-1].text
  ├─ Parses: analysis_data = json.loads(final_text)
  └─ Returns: {
               allergens_detected: [...],
               pfas_detected: [...],
               other_concerns: [...],
               confidence: 0.0-1.0
             }

📄 claude_agent.py::analyze_extracted_product(
      product_data: Dict,
      url: str
    ) → Dict
  │
  ├─ Similar to analyze_product but:
  │   ├─ Prompt includes pre-extracted product_data
  │   ├─ Only web_search tool (no web_fetch needed)
  │   └─ Claude searches for manufacturer safety data, MSDS sheets, reviews
  │
  └─ Returns: analysis_data

📄 claude_agent.py::_execute_web_search(query: str) → str
  ├─ Reads: settings.serper_api_key
  ├─ Calls: response = httpx.post(
  │          'https://google.serper.dev/search',
  │          json={'q': query, 'num': 10},
  │          headers={'X-API-KEY': api_key},
  │          timeout=10
  │        )
  ├─ Parses: results = response.json()
  └─ Returns: json.dumps(results)

📄 claude_agent.py::_execute_web_fetch(url: str) → str
  ├─ Calls: response = httpx.get(url, timeout=10, headers={'User-Agent': '...'})
  ├─ Returns: response.text (on success)
  └─ Returns: f"Error: {str(e)}" (on failure)

📄 claude_agent.py::find_alternatives(...) → List[Dict]
  └─ Returns: [] (TODO: Phase 4 implementation stub)
```

### Claude Query Service (Data Extraction - No Tools)

```
📄 claude_query.py::ClaudeQueryService.__init__()
  ├─ Reads: settings.anthropic_api_key
  └─ Creates: self.client = Anthropic(api_key=...)

📄 claude_query.py::extract_product_data(html: str) → Dict
  │
  ├─ Builds: prompt = "Extract structured product data from HTML:\n" + html
  │
  ├─ Calls: response = self.client.messages.create(
  │          model="claude-sonnet-4-5-20250929",
  │          max_tokens=4096,
  │          messages=[{role: "user", content: prompt}]
  │        )
  │   (NO TOOLS - pure text extraction)
  │
  ├─ Extracts: text = response.content[0].text
  ├─ Parses: data = json.loads(text)
  └─ Returns: {
               product_name: str,
               brand: str,
               ingredients: List[str],
               materials: List[str],
               features: List[str],
               warnings: List[str]
             }

📄 claude_query.py::extract_review_insights(html: str) → ReviewInsights
  │
  ├─ Similar to extract_product_data
  ├─ Prompt: "Extract safety-related insights from product reviews..."
  │
  └─ Returns: ReviewInsights(
               common_concerns: List[str],
               positive_safety_notes: List[str],
               recurring_issues: List[str],
               confidence: float
             )
```

### Product Scraper Service (Orchestration)

```
📄 product_scraper.py::ProductScraperService.__init__()
  └─ (No initialization needed)

📄 product_scraper.py::try_scrape(url: str) → ScrapedProduct | None
  │
  ├─ Calls: scraper = ScraperFactory.get_scraper(url)
  │
  ├─ IF scraper exists:
  │   ├─ Calls: result = await scraper.scrape(url)
  │   └─ Returns: result (ScrapedProduct)
  │
  └─ ELSE:
      └─ Returns: None
```

---

## File-Level Import Relationships

```
config.py
  IMPORTS:
    - pydantic_settings.{BaseSettings, SettingsConfigDict}
  IMPORTED BY:
    - ../../run.py
    - ../api/main.py
    - ../api/auth.py
    - ./claude_agent.py
    - ./claude_query.py
    - ./database.py

database.py
  IMPORTS:
    - supabase.{create_client, Client}
    - .config.settings
  IMPORTED BY:
    - ../api/routes/analyze.py

claude_agent.py
  IMPORTS:
    - anthropic.{Anthropic, RateLimitError, APIError}
    - httpx (for web_search and web_fetch tools)
    - .config.settings
  IMPORTED BY:
    - ../api/routes/analyze.py

claude_query.py
  IMPORTS:
    - anthropic.Anthropic
    - .config.settings
    - ..domain.models.{ScrapedProduct, ReviewInsights}
  IMPORTED BY:
    - ../api/routes/analyze.py

product_scraper.py
  IMPORTS:
    - .scrapers.factory.ScraperFactory
    - ..domain.models.ScrapedProduct
  IMPORTED BY:
    - ../api/routes/analyze.py
```

---

## Directory Structure

```
/backend/src/infrastructure/
├── __init__.py              # Package marker (empty)
├── config.py                # Environment configuration (Pydantic settings)
├── database.py              # Supabase client and queries
├── claude_agent.py          # Claude AI with tools (web_search, web_fetch)
├── claude_query.py          # Claude AI for data extraction (no tools)
├── product_scraper.py       # Scraping orchestration service
└── scrapers/                # Web scraper implementations → [scrapers/CLAUDE.md](./scrapers/CLAUDE.md)
    ├── __init__.py          # Package marker (empty)
    ├── base.py              # Abstract base scraper
    ├── factory.py           # Scraper factory (URL-based selection)
    └── amazon.py            # Amazon product page scraper
```

---

## Files Description

### config.py
**Purpose**: Centralized configuration management using Pydantic settings

**Key Features**:
- Loads environment variables from `.env`
- Validates required API keys and URLs
- Type-safe configuration access

**Dependencies**: None (pure Pydantic)

**Relationships**:
- Imported by nearly all backend modules
- Single source of truth for configuration

### database.py
**Purpose**: Supabase PostgreSQL database client and operations

**Key Functions**:
- `generate_url_hash()` - SHA256 hash for cache keys
- `get_cached_analysis()` - Retrieve cached product analysis
- `store_analysis()` - Store new analysis results

**Dependencies**:
- Supabase Python client
- config.settings

**Relationships**:
- Called by `api/routes/analyze.py` for caching
- Implements 30-day cache TTL (via Supabase RLS policies)

### claude_agent.py
**Purpose**: Claude AI agent with tool use for product safety analysis

**Key Features**:
- Uses Claude Sonnet 4.5 with tools
- web_search tool (via Serper API)
- web_fetch tool (direct HTTP requests)
- Agentic loop for multi-step analysis

**Key Functions**:
- `analyze_product()` - Full analysis with web scraping by Claude
- `analyze_extracted_product()` - Analysis of pre-scraped data
- `_execute_web_search()` - Google search via Serper
- `_execute_web_fetch()` - HTTP GET requests

**Dependencies**:
- Anthropic SDK
- httpx for HTTP requests
- config.settings

**Relationships**:
- Called by `api/routes/analyze.py`
- Main AI intelligence of the system

### claude_query.py
**Purpose**: Claude AI for structured data extraction (no tools)

**Key Features**:
- Pure text extraction from HTML
- No tool use (faster, cheaper)
- Structured JSON output

**Key Functions**:
- `extract_product_data()` - Extract product details from HTML
- `extract_review_insights()` - Extract safety insights from reviews

**Dependencies**:
- Anthropic SDK
- domain.models

**Relationships**:
- Called by `api/routes/analyze.py` after successful scraping
- Converts raw HTML to structured data

### product_scraper.py
**Purpose**: Orchestrates web scraping using appropriate scrapers

**Key Functions**:
- `try_scrape()` - Attempts to scrape product page

**Dependencies**:
- scrapers.factory
- domain.models

**Relationships**:
- Called by `api/routes/analyze.py`
- Delegates to appropriate scraper via factory pattern

---

## Architecture Patterns

### Separation of Concerns

**claude_agent.py vs claude_query.py**:
- `claude_agent.py` - Complex analysis with tools (agentic, multi-step)
- `claude_query.py` - Simple extraction without tools (fast, single-shot)

**Why separate?**
- Different use cases require different configurations
- Tool use adds latency and cost
- Extraction is deterministic, analysis is exploratory

### Factory Pattern

**Scraper selection**:
- Factory pattern in `scrapers/factory.py`
- URL-based scraper selection
- Easily extensible for new retailers

---

## Related Documentation

- [Backend Source](../CLAUDE.md) - Source overview
- [Scrapers](./scrapers/CLAUDE.md) - Web scraper implementations
- [API Routes](../api/routes/CLAUDE.md) - Where infrastructure services are called

---

Last Updated: 2025-11-18
