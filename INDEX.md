# INDEX.md — Ruh Feature & File Map

> Source-of-truth index of **what the codebase does** and **which files do it**.
> Keep this current: when you add/move a feature, update the relevant table row.
> Companion docs: [`CLAUDE.md`](./CLAUDE.md) (how to work here + standards), [`LORE.md`](./LORE.md) (architecture decisions), [`MEMORY.md`](./MEMORY.md) (mistakes & solutions), [`AUDIT.md`](./AUDIT.md) (per-retailer safety-data capture audit).

Last updated: 2026-06-03

---

## 1. Top-level layout

| Item | Purpose |
|------|---------|
| `backend/` | FastAPI server: analysis pipeline, Claude AI integration, Supabase, scraper subsystem, token tracking |
| `extension/` | Chrome MV3 extension (Svelte 5 + TS): content script, background worker, side panel UI, retailer adapters |
| `CLAUDE.md` | System documentation + engineering standards + workspace guide |
| `INDEX.md` | This file — feature/file map |
| `LORE.md` | Architecture decision records (the "why") |
| `MEMORY.md` | Log of mistakes and their solutions |
| `ruh-brand-guide.md` | Brand identity, colors, design |
| `PRODUCTION_READINESS_AUDIT.md` | Security/production assessment |
| `README.md` | Quick start |

---

## 2. Backend features

| Feature | Description | Key file(s) | Notable symbols |
|---------|-------------|-------------|-----------------|
| Analyze endpoint | Main analysis pipeline: cache → scrape/client-HTML → Claude → score → store | `backend/src/api/routes/analyze.py` | `analyze_product()` |
| Auth | Bearer token verification | `backend/src/api/auth.py` | `verify_api_key()` |
| Rate limiting | Per-IP throttling via slowapi | `backend/src/api/routes/analyze.py` | `Limiter` |
| API models | Pydantic request/response contracts | `backend/src/domain/models.py` | `AnalysisRequest`, `AnalysisResponse`, `ProductAnalysis`, `ScrapedProduct`, `ReviewInsights` |
| Harm scoring | Weighted 0–100 harm score | `backend/src/domain/harm_calculator.py` | `HarmScoreCalculator.calculate()` |
| Ingredient matching | Python-side DB comparison (fast fallback) | `backend/src/domain/ingredient_matcher.py` | `match_ingredients_to_databases()` |
| **Scraper base (ABC)** | Abstract + shared template-method logic for all scrapers | `backend/src/infrastructure/scrapers/base.py` | `BaseScraper` |
| **Amazon scraper** | Amazon selectors + structured review extraction | `backend/src/infrastructure/scrapers/amazon.py` | `AmazonScraper` |
| **Scraper factory** | Selects scraper by URL (registry) | `backend/src/infrastructure/scrapers/factory.py` | `ScraperFactory.get_scraper()` |
| Scraper service | Wraps factory with Playwright fallback | `backend/src/infrastructure/product_scraper.py` | `ProductScraperService.try_scrape()` |
| Claude query | Extract structured product data from HTML | `backend/src/infrastructure/claude_query.py` | `ClaudeQueryService.extract_product_data()` |
| Claude agent | Full agent with web_search/web_fetch tools | `backend/src/infrastructure/claude_agent.py` | `ProductSafetyAgent.analyze_product()` |
| Database | Supabase cache, knowledge bases, logging | `backend/src/infrastructure/database.py` | `DatabaseService`, `db` |
| Review vectors | Cohere embeddings + pgvector search | `backend/src/infrastructure/review_vector_service.py` | `ReviewVectorService` |
| Validation logging | Log invalid substances (log-only mode) | `backend/src/infrastructure/validation_logger.py` | `validation_logger` |
| Token tracking | Track Claude token usage + cost | `backend/src/infrastructure/token_tracker.py` | `TokenTracker` |
| Config | Pydantic settings from `.env` | `backend/src/infrastructure/config.py` | `Settings`, `settings` |
| App entry | FastAPI app + routers + CORS | `backend/src/api/main.py`, `backend/run.py` | `app` |

---

## 3. Extension features

| Feature | Description | Key file(s) | Notable symbols |
|---------|-------------|-------------|-----------------|
| Content script | Detect product page, capture DOM, call API, inject button | `extension/src/content/content.ts` | `init()`, `startAnalysis()`, `injectTriggerButton()` |
| **Retailer adapters** | Per-site detection + reviews fetching (registry) | `extension/src/lib/retailers/` (see §5) | `SiteAdapter`, `getAdapter()` |
| Amazon lib | ASIN extraction, session reviews fetch | `extension/src/lib/amazon.ts` | `extractASIN()`, `fetchReviews()` |
| Background worker | Side-panel open-state tracking via polling | `extension/src/background/background.ts` | `isSidePanelOpenForTab()` |
| Side panel container | Tab state, load analysis from storage | `extension/src/SidePanelContainer.svelte` | — |
| Analysis view | Donut score, allergens, PFAS, concerns | `extension/src/components/AnalysisView.svelte` | — |
| Loading screen | Animated loading messages | `extension/src/components/LoadingScreen.svelte` | — |
| API client | Backend communication | `extension/src/lib/api.ts` | `analyzeProduct()` |
| Cache | IndexedDB 30-day cache | `extension/src/lib/cache.ts` | `CacheManager` |
| Storage sync | Per-tab analysis state | `extension/src/lib/storage-sync.ts` | `saveTabAnalysis()` |
| Utils | Harm score, risk level, formatting | `extension/src/lib/utils.ts` | `getHarmScore()`, `getRiskLevel()` |
| Types | Shared TS interfaces | `extension/src/types/index.ts` | `AnalysisRequest`, `AnalysisResponse` |
| Manifest | MV3 permissions, content-script matches | `extension/public/manifest.json` | — |
| Build | Vite multi-entry build | `extension/vite.config.ts` | — |

---

## 4. Cross-cutting flows

- **Analyze (primary, client-HTML):** `content.ts::startAnalysis()` captures `document.documentElement.outerHTML` + session reviews → POST `/api/analyze` → `analyze.py::analyze_product()` → factory picks scraper → `scraper.process_client_html()` → `ClaudeQueryService.extract_product_data()` → `match_ingredients_to_databases()` + `ProductSafetyAgent` → `HarmScoreCalculator.calculate()` → store + respond → button injected.
- **Analyze (fallback, server scrape):** when no client HTML → `ProductScraperService.try_scrape()` (Playwright) → if low confidence → `ProductSafetyAgent.analyze_product()` (web_fetch).
- **Caching:** `db.get_cached_analysis(url_hash)` (server) + IndexedDB `CacheManager` (client).
- **Side panel:** button click → background `OPEN_SIDE_PANEL` → `SidePanelContainer` loads tab analysis → `AnalysisView`.

---

## 4b. Supported retailers

12 retailers, each = a `BaseScraper` subclass (`backend/src/infrastructure/scrapers/<name>.py`)
registered in `factory.py` + a `SiteAdapter` (`extension/src/lib/retailers/<name>.ts`) registered
in `retailers/index.ts` + a `manifest.json` entry. Each has unit tests
(`backend/tests/unit/test_<name>_scraper.py`, `extension/src/lib/retailers/<name>.test.ts`).

| Retailer | Scraper class | Product URL marker | Recon status |
|----------|---------------|--------------------|--------------|
| Amazon | `AmazonScraper` | `/dp/`, `/gp/product/` | reference (structured reviews) |
| Walmart | `WalmartScraper` | `/ip/` | blocked (PerimeterX) |
| Costco | `CostcoScraper` | `.product.` | blocked (Akamai) |
| Instacart | `InstacartScraper` | `/products/` | **validated** (JSON-LD + content-pattern nutrition facts; needs extension scroll; ingredients best-effort) |
| Sephora | `SephoraScraper` | `/product/` | **validated** (`data-at` hooks) |
| H&M | `HMScraper` | `productpage.` | blocked (Akamai) |
| Uniqlo | `UniqloScraper` | `/products/` | **validated** (JSON-LD incl. material) |
| SHEIN | `SheinScraper` | `-p-…​.html` | blocked (JS shell) |
| Aritzia | `AritziaScraper` | `/product/` | partial (no JSON-LD, lazy) |
| Garage | `GarageScraper` | `/p/…​.html` | **validated** (JSON-LD) |
| IKEA | `IkeaScraper` | `/p/` | **validated** (JSON-LD + `text/hydrate` parse: per-part materials, care, safety, certs, Q&A, reviews) |
| Temu | `TemuScraper` | `-g-…​.html` | login-gated (URL pattern confirmed) |

All non-Amazon scrapers are config-only (no method overrides), built on the JSON-LD backbone
(ADR-004). "Unvalidated" = selectors built from known structure, not yet confirmed against a live
logged-in session; they still work via the client-HTML path (INV-1) and Claude fallback (INV-3),
and are refined later. See [`LORE.md`](./LORE.md) per-retailer notes.

## 5. Extension points for adding a retailer  ⭐

Adding a new e-commerce site touches exactly these places. After the SOLID refactor (see [`LORE.md`](./LORE.md) ADR-001/002/003) most of this is **configuration, not new code**.

**Backend:**
1. `backend/src/infrastructure/scrapers/<retailer>.py` — subclass `BaseScraper`, declare class attrs: `DOMAIN_PATTERNS`, `RETAILER_NAME`, `PRODUCT_SECTION_SELECTORS`, `REVIEWS_SECTION_SELECTORS`, `EXCLUDE_SELECTORS`. Override `_extract_reviews_structured` only if the site has a special review DOM.
2. `backend/src/infrastructure/scrapers/factory.py` — append `<Retailer>Scraper()` to `self.scrapers`.
3. `backend/tests/unit/test_<retailer>_scraper.py` — selector-extraction + `can_scrape` tests against a saved fixture.

**Extension:**
4. `extension/src/lib/retailers/<retailer>.ts` — a `SiteAdapter` (`matches`, `isProductPage`, optional `fetchReviews`/`extractId`), registered in `extension/src/lib/retailers/index.ts`.
5. `extension/public/manifest.json` — add domain to `content_scripts[].matches` **and** `host_permissions`.

**Historical coupling (pre-refactor) — fixed by the refactor:**
- `analyze.py` hardcoded `AmazonScraper()` for the client-HTML branch (open/closed violation) → now uses `ScraperFactory`.
- `content.ts` hardcoded `isAmazonProductPage()` + Amazon-only imports → now uses the adapter registry.

---

## 6. Tests

| Category | Location | Coverage | Runner |
|----------|----------|----------|--------|
| Unit | `backend/tests/unit/` | Scraper selector extraction, `can_scrape`, factory routing (TDD target) | `uv run pytest tests/unit -v` |
| Integration | `backend/tests/integration/` | analyze route branching, factory + client-HTML | `uv run pytest tests/integration -v` |
| E2E | `backend/tests/e2e/test_product_analysis.py` | Real product URLs (slow, hits Claude) | `uv run pytest tests/e2e -v` |
| Extension | `extension/` | `npm run check` (types) + adapter unit tests (Vitest, if configured) | `npm run check` |

Config: `backend/pyproject.toml` → `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`).
