# Ruh - AI Product Safety Analyzer

## SOURCE OF TRUTH - Complete System Documentation

This document provides comprehensive documentation for the entire Ruh codebase, including all function-level flows, file relationships, and architectural decisions.

---

## Project Overview

**Ruh** is an AI-powered Chrome extension that analyzes product safety by detecting allergens, PFAS compounds, and other harmful substances in consumer products. The system consists of two main components:

1. **Backend**: Python FastAPI server using Claude AI Agent SDK for product analysis
2. **Extension**: Svelte 5 Chrome extension (Manifest V3) for user interface

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (Chrome Browser)                    │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│  EXTENSION (/extension)                                          │
│  ├─ Content Script (content.ts) - Injected into Amazon pages    │
│  ├─ Background Worker (background.ts) - Service worker + auth   │
│  ├─ Side Panel (SidePanelContainer.svelte) - Auth-gated UI      │
│  └─ Auth (lib/supabase.ts, lib/auth-store.svelte.ts)            │
└─────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ↓            ↓             ↓
          HTTP /api/analyze   /api/credits   /api/user
┌─────────────────────────────────────────────────────────────────┐
│  BACKEND (/backend)                                              │
│  ├─ API Layer (FastAPI) - Dual-mode auth (JWT + API key)        │
│  ├─ Domain Layer - Business logic & harm scoring                │
│  └─ Infrastructure Layer - Claude AI, DB, credit service        │
└─────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ↓                         ↓
            ┌──────────────┐          ┌──────────────┐
            │  Claude AI   │          │  Supabase    │
            │  (Anthropic) │          │  (Auth + DB) │
            └──────────────┘          └──────────────┘
```

---

## Complete Function-Level Flow Diagram

### MAIN FEATURE: Product Analysis (User Click → Display Results)

```
═══════════════════════════════════════════════════════════════════
STEP 1: USER VISITS AMAZON PRODUCT PAGE
═══════════════════════════════════════════════════════════════════

[User navigates to Amazon product page]
  ↓
📄 extension/src/content/content.ts::init()
  ├─ Calls: isAmazonProductPage(window.location.href) → boolean
  ├─ Stores: currentProductUrl = window.location.href
  ├─ Sets up: chrome.runtime.onMessage listener
  └─ Calls: startAnalysis()

📄 extension/src/content/content.ts::startAnalysis()
  ├─ Reads: import.meta.env.VITE_API_BASE_URL
  ├─ Reads: import.meta.env.VITE_API_KEY
  ├─ Makes: fetch(API_BASE_URL + '/api/analyze', {
  │         method: 'POST',
  │         headers: { Authorization: `Bearer ${API_KEY}` },
  │         body: JSON.stringify({ product_url: currentProductUrl })
  │       })
  ├─ Stores: state.data = await response.json()
  ├─ Extracts: harmScore = state.data.analysis.product_analysis.overall_score
  └─ Calls: injectTriggerButton(harmScore)

📄 extension/src/content/content.ts::injectTriggerButton(score: number)
  ├─ Creates: <button> element with donut chart SVG
  ├─ Attaches: click event → openSidebar()
  ├─ Injects: Button into page DOM (above product title)
  └─ Returns: void

═══════════════════════════════════════════════════════════════════
STEP 2: BACKEND API PROCESSING (Concurrent with Step 1)
═══════════════════════════════════════════════════════════════════

[HTTP POST /api/analyze arrives at FastAPI]
  ↓
📄 backend/src/api/main.py::app (FastAPI application)
  ├─ Middleware: CORS handler
  ├─ Routes: /api/health → health.router
  └─ Routes: /api/analyze → analyze.router

📄 backend/src/api/routes/analyze.py::analyze_product(
      request: AnalysisRequest,
      auth: AuthContext
    ) → AnalysisResponse
  │
  ├─ Calls: get_auth_context(credentials) → AuthContext | raises HTTPException
  │   └─ 📄 backend/src/api/auth.py::get_auth_context(credentials)
  │       ├─ Tries: Decode Bearer token as Supabase JWT (HS256, audience "authenticated")
  │       ├─ If valid JWT: looks up user by auth_id, returns AuthContext with tier/credits
  │       ├─ If JWT fails: falls back to static API key comparison (secrets.compare_digest)
  │       └─ Returns: AuthContext(user_id, auth_id, tier, credits_remaining, is_api_key)
  │
  ├─ Initializes: db = DatabaseService()
  ├─ Generates: url_hash = db.generate_url_hash(request.product_url)
  │   └─ 📄 backend/src/infrastructure/database.py::generate_url_hash(url: str) → str
  │       └─ Returns: hashlib.sha256(url.encode()).hexdigest()
  │
  ├─ Checks Cache: cached = db.get_cached_analysis(url_hash)
  │   └─ 📄 backend/src/infrastructure/database.py::get_cached_analysis(url_hash: str) → Dict | None
  │       ├─ Calls: supabase.table('product_analyses').select('*').eq('url_hash', url_hash).execute()
  │       └─ Returns: data[0] if exists else None
  │
  ├─ IF CACHE HIT:
  │   └─ Returns: AnalysisResponse(cached data)
  │
  ├─ IF CACHE MISS - SCRAPING PATH:
  │   │
  │   ├─ Initializes: scraper_service = ProductScraperService()
  │   ├─ Calls: scraped = scraper_service.try_scrape(product_url)
  │   │   └─ 📄 backend/src/infrastructure/product_scraper.py::try_scrape(url: str) → ScrapedProduct | None
  │   │       ├─ Calls: scraper = ScraperFactory.get_scraper(url)
  │   │       │   └─ 📄 backend/src/infrastructure/scrapers/factory.py::get_scraper(url: str) → BaseScraper | None
  │   │       │       ├─ Checks: if 'amazon.com' in url
  │   │       │       └─ Returns: AmazonScraper() OR None
  │   │       │
  │   │       ├─ IF scraper exists:
  │   │       │   └─ Calls: scraper.scrape(url)
  │   │       │       └─ 📄 backend/src/infrastructure/scrapers/amazon.py::scrape(url: str) → ScrapedProduct
  │   │       │           ├─ Makes: httpx.AsyncClient().get(url, headers={...})
  │   │       │           ├─ Parses: soup = BeautifulSoup(html, 'lxml')
  │   │       │           ├─ Extracts: title = soup.select_one('#productTitle').text
  │   │       │           ├─ Extracts: brand = soup.select_one('#bylineInfo').text
  │   │       │           ├─ Extracts: ingredients = find sections with keywords
  │   │       │           ├─ Calculates: confidence score (0-1)
  │   │       │           └─ Returns: ScrapedProduct(raw_html_product, confidence)
  │   │       │
  │   │       └─ Returns: ScrapedProduct OR None (if failed)
  │   │
  │   ├─ IF scraped AND confidence > 0.3:
  │   │   │
  │   │   ├─ Calls: product_data = claude_query.extract_product_data(scraped.raw_html_product)
  │   │   │   └─ 📄 backend/src/infrastructure/claude_query.py::extract_product_data(html: str) → Dict
  │   │   │       ├─ Initializes: client = Anthropic(api_key=settings.anthropic_api_key)
  │   │   │       ├─ Calls: response = client.messages.create(
  │   │   │       │         model="claude-sonnet-4-5-20250929",
  │   │   │       │         messages=[{role: "user", content: prompt + html}],
  │   │   │       │         max_tokens=4096
  │   │   │       │       )
  │   │   │       ├─ Parses: JSON from response.content[0].text
  │   │   │       └─ Returns: {product_name, brand, ingredients, materials, ...}
  │   │   │
  │   │   └─ Calls: analysis_data = claude_agent.analyze_extracted_product(product_data, url)
  │   │       └─ 📄 backend/src/infrastructure/claude_agent.py::analyze_extracted_product(
  │   │                 product_data: Dict, url: str
  │   │             ) → Dict
  │   │           ├─ Initializes: client = Anthropic(api_key=settings.anthropic_api_key)
  │   │           ├─ Defines: tools = [web_search_tool]
  │   │           ├─ Calls: response = client.messages.create(
  │   │           │         model="claude-sonnet-4-5-20250929",
  │   │           │         messages=[{role: "user", content: prompt + product_data}],
  │   │           │         tools=[web_search],
  │   │           │         max_tokens=8192
  │   │           │       )
  │   │           ├─ Handles: Tool use loop (web_search requests)
  │   │           │   └─ For each web_search:
  │   │           │       ├─ Makes: httpx.get('https://google.serper.dev/search', ...)
  │   │           │       └─ Returns: search results to Claude
  │   │           ├─ Parses: Final JSON response
  │   │           └─ Returns: {allergens_detected, pfas_detected, other_concerns, confidence}
  │   │
  │   ├─ IF scraping FAILED OR low confidence:
  │   │   └─ Calls: analysis_data = claude_agent.analyze_product(product_url)
  │   │       └─ 📄 backend/src/infrastructure/claude_agent.py::analyze_product(url: str) → Dict
  │   │           ├─ Similar to analyze_extracted_product but with web_fetch tool
  │   │           ├─ Claude fetches the product page itself
  │   │           └─ Returns: analysis_data
  │   │
  │   ├─ Calculates: harm_score = HarmScoreCalculator.calculate(analysis_data)
  │   │   └─ 📄 backend/src/domain/harm_calculator.py::HarmScoreCalculator.calculate(
  │   │             analysis_data: Dict[str, Any]
  │   │         ) → int
  │   │       ├─ Initializes: total_score = 0
  │   │       ├─ For allergens_detected:
  │   │       │   └─ Adds: severity points (5-30 per allergen)
  │   │       ├─ For pfas_detected:
  │   │       │   └─ Adds: 40 points per PFAS compound
  │   │       ├─ For other_concerns:
  │   │       │   └─ Adds: points based on toxicity level
  │   │       ├─ Applies: category multipliers (pesticides, cleaners)
  │   │       ├─ Caps: max(min(total_score, 100), 0)
  │   │       └─ Returns: harm_score (0-100)
  │   │
  │   ├─ Builds: analysis = ProductAnalysis(
  │   │           product_name=...,
  │   │           overall_score=100 - harm_score,
  │   │           allergens_detected=...,
  │   │           pfas_detected=...,
  │   │           ...
  │   │         )
  │   │
  │   ├─ Stores: db.store_analysis(url_hash, product_url, analysis_response)
  │   │   └─ 📄 backend/src/infrastructure/database.py::store_analysis(
  │   │             url_hash: str, url: str, response: AnalysisResponse
  │   │         ) → bool
  │   │       ├─ Prepares: db_data = {url_hash, product_url, product_name, ...}
  │   │       ├─ Calls: supabase.table('product_analyses').upsert(db_data).execute()
  │   │       └─ Returns: True OR False (on error)
  │   │
  │   └─ Returns: AnalysisResponse(
  │               analysis=analysis,
  │               alternatives=[],
  │               cached=False,
  │               url_hash=url_hash
  │             )

═══════════════════════════════════════════════════════════════════
STEP 3: USER CLICKS TRIGGER BUTTON → SIDEBAR OPENS
═══════════════════════════════════════════════════════════════════

[User clicks floating donut chart button]
  ↓
📄 extension/src/content/content.ts::openSidebar()
  ├─ Creates: iframe = document.createElement('iframe')
  ├─ Sets: iframe.src = chrome.runtime.getURL('src/sidebar.html')
  ├─ Injects: document.body.appendChild(iframe)
  ├─ Waits: iframe onload event
  ├─ Sends: iframe.contentWindow.postMessage({
  │          type: 'ANALYSIS_DATA',
  │          data: state.data
  │        }, '*')
  └─ Hides: trigger button (display: none)

📄 extension/src/sidebar.html (loaded in iframe)
  └─ Loads: <script type="module" src="/sidebar.js"></script>

📄 extension/src/sidebar.ts::initApp()
  ├─ Gets: app = document.getElementById('app')
  └─ Calls: mount(Sidebar, { target: app })

📄 extension/src/Sidebar.svelte::onMount()
  ├─ Sets up: chrome.runtime.onMessage listener
  ├─ Sets up: window.addEventListener('message', handleMessage)
  └─ Defines: handleMessage(event: MessageEvent)

📄 extension/src/Sidebar.svelte::handleMessage(event)
  ├─ Checks: if (event.data.type === 'ANALYSIS_DATA')
  ├─ Extracts: data = event.data.data
  ├─ Sets: analysis = data (reactive state)
  ├─ Sets: loading = false
  ├─ Calls: cache.set(productUrl, data)
  │   └─ 📄 extension/src/lib/cache.ts::set(key: string, value: AnalysisResponse)
  │       ├─ Opens: db = await openDB('eject-cache', 1)
  │       ├─ Stores: db.put('analyses', { key, value, timestamp })
  │       └─ Returns: void
  └─ Renders: <Sidebar {analysis} />

📄 extension/src/components/Sidebar.svelte (UI Component)
  ├─ Receives: analysis prop (AnalysisResponse)
  ├─ Extracts: productAnalysis = analysis.analysis.product_analysis
  ├─ Computes: harmScore = getHarmScore(productAnalysis)
  │   └─ 📄 extension/src/lib/utils.ts::getHarmScore(analysis: ProductAnalysis) → number
  │       └─ Returns: 100 - analysis.overall_score
  │
  ├─ Computes: riskLevel = getRiskLevel(harmScore)
  │   └─ 📄 extension/src/lib/utils.ts::getRiskLevel(score: number) → RiskLevel
  │       ├─ Returns: 'low' if score < 30
  │       ├─ Returns: 'medium' if score < 60
  │       └─ Returns: 'high' if score >= 60
  │
  ├─ Computes: riskClass = getRiskClass(riskLevel)
  │   └─ 📄 extension/src/lib/utils.ts::getRiskClass(level: RiskLevel) → string
  │       └─ Returns: CSS class name ('risk-low' | 'risk-medium' | 'risk-high')
  │
  ├─ Renders: Donut chart SVG with harmScore
  ├─ Renders: Product name and brand
  ├─ Renders: Allergens list (if any)
  ├─ Renders: PFAS list (if any)
  ├─ Renders: Other concerns list (if any)
  └─ Renders: Confidence score and timestamp
```

---

## File-Level Import Graph

### Backend Dependencies

```
run.py
  └─ src.infrastructure.config.settings

src/api/main.py
  ├─ src.infrastructure.config.settings
  └─ src.api.routes.{health, analyze, admin, credits, user}

src/api/auth.py
  ├─ src.infrastructure.config.settings
  ├─ src.infrastructure.database.db (lazy import in _resolve_user_from_jwt)
  └─ jwt (PyJWT)

src/api/routes/health.py
  └─ (no internal imports)

src/api/routes/analyze.py
  ├─ src.domain.models.*
  ├─ src.domain.harm_calculator.HarmScoreCalculator
  ├─ src.infrastructure.claude_agent.ProductSafetyAgent
  ├─ src.infrastructure.product_scraper.ProductScraperService
  ├─ src.infrastructure.claude_query.ClaudeQueryService
  ├─ src.infrastructure.database.DatabaseService
  └─ src.api.auth.{get_auth_context, AuthContext}

src/api/routes/credits.py
  ├─ src.api.auth.{get_auth_context, AuthContext}
  └─ src.infrastructure.credit_service

src/api/routes/user.py
  ├─ src.api.auth.{get_auth_context, AuthContext}
  └─ src.infrastructure.database.db

src/infrastructure/credit_service.py
  └─ src.infrastructure.database.db

src/domain/models.py
  └─ (no internal imports - pure Pydantic models)

src/domain/harm_calculator.py
  └─ (no internal imports - pure logic)

src/infrastructure/config.py
  └─ (no internal imports - Pydantic settings)

src/infrastructure/database.py
  └─ src.infrastructure.config.settings

src/infrastructure/claude_agent.py
  └─ src.infrastructure.config.settings

src/infrastructure/claude_query.py
  ├─ src.infrastructure.config.settings
  └─ src.domain.models.ScrapedProduct

src/infrastructure/product_scraper.py
  ├─ src.infrastructure.scrapers.factory.ScraperFactory
  └─ src.domain.models.ScrapedProduct

src/infrastructure/scrapers/factory.py
  ├─ src.infrastructure.scrapers.base.BaseScraper
  └─ src.infrastructure.scrapers.amazon.AmazonScraper

src/infrastructure/scrapers/base.py
  └─ (abstract base - no imports)

src/infrastructure/scrapers/amazon.py
  ├─ src.infrastructure.scrapers.base.BaseScraper
  └─ src.domain.models.ScrapedProduct
```

### Extension Dependencies

```
sidebar.ts
  ├─ ./app.css
  └─ ./Sidebar.svelte

Sidebar.svelte
  ├─ ./components/Sidebar.svelte
  ├─ ./lib/api.{api}
  ├─ ./lib/cache.{cache}
  └─ ./types.{AnalysisResponse}

components/Sidebar.svelte
  ├─ @/types.*
  └─ @/lib/utils.*

content/content.ts
  └─ (no file imports - uses chrome API and import.meta.env)

background/background.ts
  └─ ../lib/supabase.{initSupabase, getSupabaseClient}

lib/supabase.ts
  └─ @supabase/supabase-js

lib/auth-store.svelte.ts
  ├─ @supabase/supabase-js (types)
  └─ ./supabase.{getSupabaseClient}

lib/api.ts
  └─ @/types.{AnalysisResponse}

lib/cache.ts
  └─ @/types.{AnalysisResponse, CachedAnalysis}

lib/utils.ts
  └─ @/types.{ProductAnalysis, RiskLevel}

types/index.ts
  └─ (no imports - pure type definitions)
```

---

## Cross-Directory Relationships

### Backend: Clean Architecture Pattern

```
API Layer (src/api/)
  ↓ calls
Domain Layer (src/domain/)
  ↓ uses
Infrastructure Layer (src/infrastructure/)
  ↓ calls
External Services (Anthropic, Supabase, Web)
```

**Key Dependency Rule**: Higher layers depend on lower layers. Infrastructure is called by Domain/API but never calls them back (dependency inversion).

### Extension: Component-Based Architecture

```
Content Script (content/)
  ↓ creates
Sidebar App (Sidebar.svelte)
  ↓ uses
Libraries (lib/)
  ↓ uses
Types (types/)
```

**Key Pattern**: Content script is isolated (no imports) to avoid bundling issues. Sidebar app handles all state management and API communication.

---

## Extension Build: Manifest & Environment Handling

### Build-Time Manifest Transformation

`extension/public/manifest.json` includes `http://localhost:8000` in `host_permissions` and CSP `connect-src` for local development. A custom Vite plugin (`ruh-manifest` in `vite.config.ts`) strips all localhost entries in production builds:

- **Production** (`vite build`, the default): localhost removed from `host_permissions` and `connect-src`
- **Development** (`vite build --mode development`): localhost preserved

The plugin runs in the `closeBundle` hook, reads `public/manifest.json`, conditionally filters localhost entries based on `mode`, and writes the result to `dist/manifest.json`. The manifest is NOT copied by `viteStaticCopy` — only icons and CSS are.

### Environment Variables

API configuration is provided via `VITE_*` env vars, baked into JS at build time by Vite:

| Variable | Local Dev (`.env`) | CI (workflow env) |
|----------|-------------------|-------------------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | `https://ruh-api-948739110049.us-central1.run.app` |
| `VITE_API_KEY` | dev key in `.env` | `${{ secrets.VITE_API_KEY }}` |
| `VITE_SUPABASE_URL` | Supabase project URL | `${{ secrets.VITE_SUPABASE_URL }}` |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon key | `${{ secrets.VITE_SUPABASE_ANON_KEY }}` |

**There are no hardcoded localhost fallbacks in the TypeScript source.** If `VITE_API_BASE_URL` is missing at build time, the extension fails explicitly rather than silently sending credentials to `localhost` over HTTP:
- `background.ts` returns an error response (`'API URL not configured'`)
- `api.ts` falls back to empty string (fetch will fail naturally)

### CI Build (`.github/workflows/build-extension.yml`)

The workflow sets `VITE_API_BASE_URL` and `VITE_API_KEY` as env vars on the build step. The `VITE_API_KEY` must be configured as a GitHub repository secret.

---

## Authentication & Credit System

### Product Model

Analysis auto-runs on every Amazon product page for ALL tiers (backend cost absorbed as growth investment). The harm score donut is always visible for free. Credits gate the **detailed results view** (allergens, PFAS, concerns list), not the analysis itself.

| Tier | Credits/month | Trigger | Detail View |
|------|--------------|---------|-------------|
| Free | 5 | Manual (click donut → side panel → "Unlock" button) | Gated |
| Basic | 15 | Manual | Gated |
| Middle | 30 | Manual | Gated |
| Unlimited | Unlimited | Auto (full results shown immediately) | Always visible |

1 credit = 1 detailed analysis view. Once unlocked, a product stays unlocked permanently (no re-charge on revisit).

### Backend: Dual-Mode Auth

`backend/src/api/auth.py` implements a JWT-first, API-key-fallback authentication flow:

1. Extract Bearer token from `Authorization` header
2. Try decoding as Supabase JWT (PyJWT, HS256, audience `"authenticated"`)
3. If valid JWT → look up/create user by `auth_id`, fetch tier + credits → return `AuthContext`
4. If JWT fails → compare against static API key (constant-time via `secrets.compare_digest`)
5. If both fail → 401

```python
@dataclass
class AuthContext:
    user_id: Optional[UUID]     # Internal user ID (None for API key)
    auth_id: Optional[UUID]     # Supabase Auth UID (None for API key)
    tier: str                   # 'free', 'basic', 'middle', 'unlimited'
    credits_remaining: int      # -1 for unlimited or API key
    is_api_key: bool            # True if legacy static API key
```

The analyze routes use `Depends(get_auth_context)`. Admin routes remain on `Depends(verify_api_key)`. The `AnalysisResponse` includes `user_tier`, `credits_remaining`, and `analysis_unlocked` fields when the caller is JWT-authenticated.

### Database Schema (Migration 013)

`backend/supabase/migrations/013_add_auth_and_credits.sql` adds:

- **`users` extensions**: `auth_id`, `email`, `display_name`, `avatar_url`, `auth_provider`
- **`user_tiers`**: one row per user — `tier` ENUM (free/basic/middle/unlimited), `monthly_credits`
- **`credit_ledger`**: server-authoritative balance — `credits_remaining`, `cycle_start`/`cycle_end`, `total_used_this_cycle`
- **`credit_transactions`**: audit trail — `action` ENUM (monthly_reset/detail_view/admin_grant/tier_change/refund), `amount`, `balance_after`
- **`unlocked_analyses`**: prevents double-charging — `UNIQUE(user_id, url_hash)`

Key SQL functions (all `SECURITY DEFINER`, `SET search_path = ''`):

- **`deduct_credit(p_user_id, p_url_hash)`**: Atomic RPC — checks tier (unlimited bypass), checks unlock (idempotent), deducts with row lock, records transaction + unlock
- **`reset_monthly_credits()`**: For pg_cron — resets expired cycles based on `cycle_end`
- **`initialize_user_credits(p_user_id, p_tier, p_monthly_credits)`**: Creates tier + ledger rows on first login

RLS: users can `SELECT` their own rows, `service_role` can manage all.

### Credit API Routes

`backend/src/api/routes/credits.py`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/credits/me` | GET | Returns tier, balance, monthly_credits, total_used, cycle_end |
| `/api/credits/deduct` | POST | Body: `{url_hash}`. Deducts 1 credit. Returns 402 if empty |
| `/api/credits/check/{url_hash}` | GET | Returns `{unlocked, tier, credits_remaining}` |

`backend/src/api/routes/user.py`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/user/me` | GET | User profile (auto-creates on first JWT request) |

All credit endpoints require JWT auth (return 401 for legacy API key callers).

### Credit Service

`backend/src/infrastructure/credit_service.py` is the single entry point for credit operations:

- `get_user_credits(user_id)` → `CreditInfo` dataclass
- `deduct_credit(user_id, url_hash)` → `DeductResult` dataclass (calls the `deduct_credit` RPC)
- `is_analysis_unlocked(user_id, url_hash)` → bool
- `get_or_create_user_from_auth(auth_id, email, ...)` → UUID

### Extension: Supabase Auth

**`extension/src/lib/supabase.ts`**: Supabase client singleton with a `ChromeStorageAdapter` that bridges the sync `localStorage`-like API Supabase expects with async `chrome.storage.local`. Uses PKCE flow (`flowType: 'pkce'`), `detectSessionInUrl: false`.

**`extension/src/lib/auth-store.svelte.ts`**: Reactive auth state using Svelte 5 runes. Exposes `session`, `user`, `loading`, `creditBalance`, `userTier`, `isAuthenticated`. Methods: `initialize()`, `signInWithGoogle()`, `signInWithEmail()`, `signUp()`, `signOut()`, `refreshCredits()`, `getAccessToken()`.

**`extension/public/auth-callback.html`**: OAuth popup redirect handler. Extracts tokens (implicit flow) or auth code (PKCE flow) from the redirect URL, sends to background worker via `chrome.runtime.sendMessage({ type: 'AUTH_CALLBACK' })`.

### Extension: Background Worker Auth

`extension/src/background/background.ts` initializes Supabase on startup and uses `getAuthHeader()` for API calls:

1. Check for Supabase session → send `Bearer <jwt>`
2. If no session → fall back to `Bearer <VITE_API_KEY>`

Handles `AUTH_CALLBACK` messages from the OAuth popup to establish sessions via `client.auth.exchangeCodeForSession()` (PKCE) or `client.auth.setSession()` (implicit).

### Extension: Side Panel Auth Gate

`extension/src/SidePanelContainer.svelte` rendering flow:

```
loading → auth check →
  NOT logged in → LoginView
  logged in →
    no data → empty state
    loading → LoadingScreen
    error → error state
    complete →
      unlimited tier → AnalysisView (full)
      non-unlimited AND NOT unlocked → ScoreSummaryView + "Unlock" button
      non-unlimited AND unlocked → AnalysisView (full)
```

Components:
- **`LoginView.svelte`**: Google OAuth (primary) + email/password (secondary)
- **`CreditBadge.svelte`**: Sticky header showing tier + remaining credits
- **`ScoreSummaryView.svelte`**: Score donut + finding counts (teaser) + "Unlock Full Report (1 credit)" button

### Extension: Manifest CSP

`extension/public/manifest.json` includes `https://*.supabase.co` in CSP `connect-src`. The Vite `ruh-manifest` plugin preserves Supabase URLs in both dev and production builds (only strips localhost).

### Deployment Checklist

1. Apply migration 013 in Supabase SQL editor
2. Set `SUPABASE_JWT_SECRET` env var on Cloud Run
3. Enable Google + email providers in Supabase Auth dashboard
4. Add `chrome-extension://<EXTENSION_ID>/auth-callback.html` as allowed redirect URL in Supabase
5. Add `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` as GitHub repository secrets
6. Deploy backend first (dual-mode auth accepts both JWT and API key)
7. Publish extension update (sends JWT when available, falls back to API key)
8. Future: Remove static API key fallback once all users have updated

---

## Bloat Identification

### ⚠️ BLOAT: Legacy Migrations

**Location**: `/backend/migrations/`

**Evidence**:
- Contains outdated SQL files: `001_create_tables.sql`, `002_seed_knowledge_base.sql`
- Superseded by `/backend/supabase/migrations/`
- Old schema missing tables (toxic_substances) and columns

**Impact**: None (not used in production)

### ⚠️ BLOAT: Unused Application Layer

**Location**: `/backend/src/application/`

**Evidence**:
- Directory contains only empty `__init__.py`
- No code implements application layer pattern
- Business logic exists in `domain/` and `infrastructure/`

**Impact**: None (empty directory)

### ⚠️ DEVELOPMENT SCAFFOLDING: Empty Test Directories

**Locations**:
- `/backend/tests/unit/` (empty except `__init__.py`)
- `/backend/tests/integration/` (empty except `__init__.py`)

**Evidence**:
- Only E2E tests implemented (`tests/e2e/test_product_analysis.py`)
- Unit and integration test directories created but unused

**Impact**: None (future test scaffolding)

---

## Subdirectory Documentation

### Backend
- [Backend Overview](./backend/CLAUDE.md) - FastAPI server, clean architecture, Claude AI integration

### Extension
- [Extension Overview](./extension/CLAUDE.md) - Svelte 5 Chrome extension, Manifest V3, UI components

---

## Essential Files Summary

**Total Source Files**: 63
- **Backend**: 24 Python files (added auth.py rewrite, credit_service.py, credits.py, user.py)
- **Extension**: 18 TypeScript/Svelte files (added supabase.ts, auth-store.svelte.ts, LoginView, CreditBadge, ScoreSummaryView, auth-callback.html)
- **Database**: 5 SQL migration files (active, added 013_add_auth_and_credits.sql)
- **Tests**: 4 test files
- **Bloat**: 3 files (4.8%)

---

## Key Technologies

### Backend Stack
- **Framework**: FastAPI (Python)
- **AI**: Anthropic Claude Sonnet 4.5 with Agent SDK
- **Database**: Supabase (PostgreSQL)
- **Auth**: Supabase Auth (JWT validation via PyJWT)
- **Scraping**: httpx + BeautifulSoup4
- **Testing**: pytest

### Extension Stack
- **Framework**: Svelte 5
- **Language**: TypeScript
- **Build**: Vite
- **Auth**: @supabase/supabase-js (PKCE OAuth flow)
- **Styling**: Tailwind CSS
- **Storage**: IndexedDB (idb library), chrome.storage.local (auth sessions)
- **Manifest**: Chrome Extension Manifest V3

---

Last Updated: 2026-02-09
