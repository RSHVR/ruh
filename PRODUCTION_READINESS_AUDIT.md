# Ruh Production Readiness Audit

> **Target**: 1000 DAU | **Date**: 2026-02-06 | **Version**: 0.2.2
> **Previous Audit**: 2025-12-26 (v0.2.0, Score: 58/100)

---

## Executive Summary

| Metric                    | v0.2.0    | v0.2.2        | Delta |
| ------------------------- | --------- | ------------- | ----- |
| **Overall Score**         | 58/100    | **72/100**    | +14   |
| **Critical Issues**       | 12        | **4**         | -8    |
| **High Priority**         | 18        | **10**        | -8    |
| **Medium Priority**       | 25        | **16**        | -9    |
| **Estimated Remediation** | 4-6 weeks | **2-3 weeks** | -50%  |

### Component Scores

| Component                | v0.2.0 | v0.2.2 | Status                                                    |
| ------------------------ | ------ | ------ | --------------------------------------------------------- |
| Backend API              | 65     | **78** | Auth fixed, rate limiting solid, CORS configured          |
| Backend Domain           | 70     | **75** | Solid logic, validation logger added, still no unit tests |
| Backend Infrastructure   | 55     | **78** | Search caching, token tracking, multi-agent, timeouts     |
| Extension Content Script | 55     | **68** | CSP added, localhost removed, still no AbortController    |
| Extension Background     | 50     | **55** | Minor improvements, still needs message validation        |
| Extension UI             | 65     | **65** | Unchanged                                                 |
| Testing                  | 15     | **35** | LangGraph tests added, benchmark framework, still gaps    |
| DevOps/Infrastructure    | 45     | **60** | Secret Manager, Cloud Build, extension CI/CD              |

### Traffic Light Summary

- **Ready for Production**: Authentication (constant-time), rate limiting, CORS (code-level), CSP, caching, graceful degradation, token tracking
- **Needs Work**: Retry logic, error message sanitization, structured logging, unit tests
- **Blockers**: `set-env.sh` CORS wildcard, error details in 500 responses, no unit tests for core domain logic, no privacy policy

### Changes Since Last Audit (20 commits)

| Category           | Changes                                                                                                                                                     |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Security Fixes** | Constant-time auth, CSP in manifest, CORS configured, .env.example cleaned                                                                                  |
| **New Subsystems** | Multi-agent (Cohere/LangGraph), custom search service, Trafilatura extraction, review vector service, validation logger, ingredient research, token tracker |
| **Testing**        | 15 LangGraph test classes (403 lines), comprehensive benchmark framework                                                                                    |
| **DevOps**         | Extension CI/CD via GitHub Actions, Secret Manager setup script                                                                                             |

---

## 1. Security Audit

### 1.1 Authentication & Authorization

| Item                   | v0.2.0 | v0.2.2   | Notes                                            |
| ---------------------- | ------ | -------- | ------------------------------------------------ |
| API Key Authentication | PASS   | **PASS** | Bearer token via HTTPBearer                      |
| Key Comparison         | FAIL   | **PASS** | Now uses `secrets.compare_digest()`              |
| Admin Separation       | WARN   | **WARN** | Same key for admin and user endpoints            |
| Key Rotation           | FAIL   | **WARN** | Secret Manager supports rotation, no auto-rotate |

### 1.2 Secrets Management

| Issue                      | v0.2.0   | v0.2.2   | Notes                                                     |
| -------------------------- | -------- | -------- | --------------------------------------------------------- |
| `.env` files in repo       | CRITICAL | **PASS** | `.env` in `.gitignore`, never committed to history        |
| API keys in `set-env.sh`   | CRITICAL | **PASS** | Now reads from env vars: `${ANTHROPIC_API_KEY:?Error}`    |
| Real key in `.env.example` | HIGH     | **PASS** | Placeholder values only (`sk-ant-api03-your-key-here`)    |
| Secret Manager setup       | FAIL     | **PASS** | `setup-secrets.sh` creates 3 secrets with IAM grants      |
| `.env` file on disk        | N/A      | **WARN** | Local `.env` contains real keys (not in git, but on disk) |

### 1.3 Input Validation

| Component                 | v0.2.0 | v0.2.2   | Notes                                                   |
| ------------------------- | ------ | -------- | ------------------------------------------------------- |
| Product URL validation    | FAIL   | **WARN** | Pydantic validates type, no scheme/domain check         |
| API response validation   | FAIL   | **WARN** | Pydantic models validate structure, no Zod in extension |
| Message type validation   | FAIL   | **FAIL** | Background worker still accepts any message             |
| HTML content sanitization | WARN   | **WARN** | HTML passed to Claude but within token limits           |
| Client HTML size          | N/A    | **PASS** | Selector-based extraction compresses ~2MB to ~20KB      |

### 1.4 CSP & CORS

| Item                          | v0.2.0   | v0.2.2   | Notes                                                             |
| ----------------------------- | -------- | -------- | ----------------------------------------------------------------- |
| Backend CORS (code)           | CRITICAL | **PASS** | `settings.cors_origins` from env, default: Cloud Run URL          |
| Backend CORS (deploy)         | N/A      | **HIGH** | `set-env.sh` line 34: `ALLOWED_ORIGINS=*` overrides at deploy     |
| Extension CSP                 | CRITICAL | **PASS** | CSP defined: `script-src 'self'; connect-src https://ruh-api-...` |
| localhost in host_permissions | HIGH     | **PASS** | Removed - only `amazon.com`, `amazon.ca`, Cloud Run URL           |

**Remaining issue**: `set-env.sh` line 34 sets `ALLOWED_ORIGINS=*` when updating env vars. This overrides the safe default. Must be changed to specific origins before next deploy.

### 1.5 API Security

| Item                      | v0.2.0 | v0.2.2   | Notes                                                     |
| ------------------------- | ------ | -------- | --------------------------------------------------------- |
| HTTPS enforcement         | WARN   | **WARN** | Cloud Run provides TLS, no HSTS headers                   |
| Request size limits       | FAIL   | **WARN** | Client HTML extraction limits scope, no explicit max body |
| Rate limiting             | PASS   | **PASS** | 100/min global + 30/min per endpoint (slowapi)            |
| Distributed rate limiting | FAIL   | **FAIL** | Still in-memory only, no Redis                            |
| Error detail exposure     | N/A    | **HIGH** | 500 responses include `str(e)` - information disclosure   |

### 1.6 New: Dependency Security

| Package     | Version  | Risk   | Notes                                   |
| ----------- | -------- | ------ | --------------------------------------- |
| anthropic   | >=0.75.0 | Low    | First-party SDK                         |
| cohere      | >=5.0.0  | Low    | First-party SDK                         |
| langchain   | >=0.3.0  | Medium | Large dependency tree, frequent updates |
| langgraph   | >=0.2.0  | Medium | Newer library, less battle-tested       |
| playwright  | >=1.49.0 | Medium | Browser automation - large binary       |
| tavily      | >=0.5.0  | Low    | Search API client                       |
| trafilatura | >=1.12.0 | Low    | Content extraction                      |
| redis       | >=5.2.0  | N/A    | **UNUSED - remove**                     |
| celery      | >=5.4.0  | N/A    | **UNUSED - remove**                     |

---

## 2. Reliability Audit

### 2.1 Error Handling

| Component           | v0.2.0 | v0.2.2  | Notes                                                                           |
| ------------------- | ------ | ------- | ------------------------------------------------------------------------------- |
| Backend API routes  | 70%    | **85%** | RateLimitError → 429, all DB ops wrapped, non-fatal fallbacks                   |
| Claude AI calls     | 60%    | **80%** | RateLimitError caught + re-raised, APIError logged, fallback to DB-only results |
| Database operations | 80%    | **90%** | MockDB fallback, `is_available` checks, all ops return None/False on failure    |
| Search service      | N/A    | **85%** | Tavily → Serper → stale cache → empty (4-level fallback)                        |
| Content script      | 40%    | **45%** | Minor improvements, still no retry/timeout                                      |
| Background worker   | 20%    | **25%** | Still mostly silent failures                                                    |

### 2.2 Retry Mechanisms

| Component           | v0.2.0 | v0.2.2   | Notes                                                        |
| ------------------- | ------ | -------- | ------------------------------------------------------------ |
| Claude API calls    | FAIL   | **FAIL** | No exponential backoff (but graceful degradation to DB-only) |
| Database operations | FAIL   | **WARN** | No retry, but graceful fallback prevents crash               |
| HTTP scraping       | FAIL   | **WARN** | No retry, but Playwright 30s timeout prevents hang           |
| Search service      | N/A    | **PASS** | Fallback chain: Tavily → Serper → stale cache                |
| Extension API calls | FAIL   | **FAIL** | No fetch retry logic                                         |

### 2.3 Timeout Handling

| Component                    | v0.2.0 | v0.2.2   | Notes                                                            |
| ---------------------------- | ------ | -------- | ---------------------------------------------------------------- |
| Claude API                   | None   | **WARN** | No explicit timeout, but Cloud Run 300s timeout provides ceiling |
| Supabase operations          | None   | **WARN** | No query timeout, but client has default                         |
| Amazon scraping (Playwright) | 15s    | **PASS** | Now 30s page load timeout                                        |
| Amazon scraping (httpx)      | N/A    | **PASS** | 30s timeout on httpx.AsyncClient                                 |
| Content script fetch         | None   | **FAIL** | Still no AbortController                                         |

### 2.4 Circuit Breakers

**Status**: Not implemented

**Impact reduced**: Multi-level fallback chains provide similar protection. If Claude fails, DB-only results are returned. If Tavily fails, Serper is tried. This is functionally equivalent to a circuit breaker for most failure scenarios.

### 2.5 Graceful Degradation

| Scenario             | v0.2.0 | v0.2.2   | Notes                                       |
| -------------------- | ------ | -------- | ------------------------------------------- |
| Claude unavailable   | PASS   | **PASS** | Returns database-only results with note     |
| Claude rate limited  | PASS   | **PASS** | Returns 429 with Retry-After header         |
| Scraping fails       | PASS   | **PASS** | Falls back to Claude web_fetch              |
| Database unavailable | PASS   | **PASS** | MockDB fallback, analysis still works       |
| Cache miss           | PASS   | **PASS** | Full analysis pipeline runs                 |
| Trafilatura fails    | N/A    | **PASS** | Falls back to Claude Query extraction       |
| Tavily unavailable   | N/A    | **PASS** | Falls back to Serper, then stale cache      |
| Review storage fails | N/A    | **PASS** | Non-fatal, analysis returns without reviews |

---

## 3. Performance Audit

### 3.1 Response Time Analysis

| Endpoint                       | Expected | Bottleneck                |
| ------------------------------ | -------- | ------------------------- |
| POST /api/analyze (cache hit)  | <500ms   | Supabase lookup           |
| POST /api/analyze (cache miss) | 10-45s   | Claude API + search       |
| POST /api/analyze (DB-only)    | 3-8s     | Scraping + extraction     |
| GET /api/health                | <100ms   | None                      |
| POST /api/reviews/search       | 1-3s     | Embedding + vector search |

### 3.2 New: Cost Optimization Pipeline

The analysis pipeline now minimizes Claude API token usage through a 3-step process:

| Step              | Method                                 | Cost                 |
| ----------------- | -------------------------------------- | -------------------- |
| 1. Extraction     | Trafilatura (rule-based)               | Free                 |
| 2. DB matching    | Local ingredient → allergen/PFAS match | Free                 |
| 3. AI enhancement | Claude only for `needs_research` items | ~$0.01-0.05/analysis |

**Estimated savings**: 40-60% reduction in Claude API costs vs. v0.2.0

### 3.3 Caching Strategy

| Layer                         | TTL        | v0.2.2 Status                        |
| ----------------------------- | ---------- | ------------------------------------ |
| Search results (L1 in-memory) | 1 hour     | **NEW** - LRU cache, 1000 entries    |
| Search results (L2 Supabase)  | 24 hours   | **NEW** - `search_cache` table       |
| Product analysis (Supabase)   | Indefinite | OK - keyed by URL hash               |
| Review insights (Supabase)    | 7 days     | OK                                   |
| Extension (IndexedDB)         | 30 days    | OK but `clearExpired()` never called |

### 3.4 Database Query Efficiency

| Issue              | v0.2.0 | v0.2.2   | Notes                                                                 |
| ------------------ | ------ | -------- | --------------------------------------------------------------------- |
| JSONB indexes      | FAIL   | **PASS** | GIN indexes added in migrations                                       |
| Connection pooling | FAIL   | **WARN** | Supabase client handles, not explicit                                 |
| Async usage        | FAIL   | **PASS** | Proper async/await throughout, `asyncio.gather()` for parallel search |

---

## 4. Scalability Audit (1000 DAU)

### 4.1 Current Architecture Limits

| Resource             | Limit             | At 1000 DAU      | v0.2.2 Change                   |
| -------------------- | ----------------- | ---------------- | ------------------------------- |
| Claude API           | ~50 RPM tier      | May need upgrade | DB-matching reduces calls ~40%  |
| Cloud Run instances  | Auto-scale (0-10) | OK               | Unchanged                       |
| Supabase connections | 60 (free tier)    | May need upgrade | More tables/queries per request |
| Cohere API           | Standard tier     | Fallback agent   | Only if LangGraph enabled       |
| Tavily API           | 1000/month (free) | May need upgrade | L2 caching reduces calls        |

### 4.2 Cost Projections (1000 DAU, v0.2.2)

| Service             | Usage                         | Est. Monthly Cost  |
| ------------------- | ----------------------------- | ------------------ |
| Claude API          | ~18,000 analyses (40% cached) | $90-180            |
| Cloud Run           | ~1M requests                  | $20-50             |
| Supabase            | Pro tier                      | $25                |
| Tavily/Serper       | ~10,000 searches (cached)     | $10-30             |
| Cohere (embeddings) | ~50,000 embeddings            | $5-15              |
| **Total**           |                               | **$150-300/month** |

**Cost improvement**: ~25% reduction from v0.2.0 estimates due to caching and DB-matching.

---

## 5. Observability Audit

### 5.1 Logging Infrastructure

| Aspect              | v0.2.0     | v0.2.2         | Notes                                           |
| ------------------- | ---------- | -------------- | ----------------------------------------------- |
| Log format          | Plain text | **Plain text** | Still not JSON structured                       |
| Log levels          | Configured | **PASS**       | DEBUG/INFO/WARNING/ERROR properly used          |
| Request correlation | Missing    | **WARN**       | `X-Request-ID` header exposed but not generated |
| Sensitive data      | WARN       | **WARN**       | Product URLs logged (PII considerations)        |
| Step logging        | N/A        | **PASS**       | Clear step markers (Step 1/3, 2/3, 3/3)         |

### 5.2 Metrics & Monitoring

| Metric               | v0.2.0      | v0.2.2                                        |
| -------------------- | ----------- | --------------------------------------------- |
| Request latency      | NOT TRACKED | **NOT TRACKED**                               |
| Error rate           | NOT TRACKED | **NOT TRACKED**                               |
| Claude token usage   | NOT TRACKED | **TRACKED** (TokenTracker with per-call cost) |
| Cache hit rate       | NOT TRACKED | **LOGGED** (cache hit/miss at INFO level)     |
| Search service usage | N/A         | **TRACKED** (query counts, durations)         |
| Cost per analysis    | N/A         | **TRACKED** (stored in Supabase per analysis) |

### 5.3 Alerting

**Status**: No alerting configured (unchanged)

### 5.4 AI-Specific Observability

| Metric                        | v0.2.0 | v0.2.2   | Notes                                                |
| ----------------------------- | ------ | -------- | ---------------------------------------------------- |
| Token usage tracking          | FAIL   | **PASS** | TokenTracker: per-call + per-analysis totals         |
| Model response validation     | FAIL   | **PASS** | ValidationLogger logs misclassifications to Supabase |
| Confidence score distribution | FAIL   | **WARN** | Confidence stored per analysis, no dashboard         |
| Hallucination detection       | FAIL   | **PASS** | `validate_and_filter_substances()` cross-refs DB     |
| Cost tracking                 | N/A    | **PASS** | Per-analysis cost stored with 6-decimal precision    |
| Multi-model comparison        | N/A    | **PASS** | Benchmark framework compares Claude vs Cohere        |

---

## 6. Testing Audit

### 6.1 Unit Test Coverage

| Component                      | v0.2.0 | v0.2.2   | Priority                           |
| ------------------------------ | ------ | -------- | ---------------------------------- |
| HarmScoreCalculator            | 0%     | **0%**   | P0                                 |
| match_ingredients_to_databases | 0%     | **0%**   | P0                                 |
| verify_api_key                 | 0%     | **0%**   | P0                                 |
| LangGraph agent components     | N/A    | **~70%** | Covered (15 test classes)          |
| TokenTracker pricing           | N/A    | **~80%** | Covered in test_langgraph_agent.py |
| DatabaseService                | 0%     | **0%**   | P1                                 |
| AmazonScraper                  | 0%     | **0%**   | P1                                 |
| SearchToolService              | N/A    | **0%**   | P1                                 |
| ValidationLogger               | N/A    | **0%**   | P2                                 |
| Extension utils                | 0%     | **0%**   | P2                                 |

### 6.2 Integration Tests

**Status**: Empty directories exist but no tests (unchanged)

### 6.3 E2E Tests

| Test                          | Status                     |
| ----------------------------- | -------------------------- |
| Health endpoint               | PASS                       |
| Product analysis (sunscreen)  | PASS                       |
| Product analysis (frying pan) | PASS                       |
| Allergen profile              | PASS (no assertions)       |
| Invalid URL                   | WARN (accepts 200/422/500) |

### 6.4 Benchmark Framework (NEW)

| Capability                                | Status |
| ----------------------------------------- | ------ |
| Multi-agent comparison (Claude vs Cohere) | PASS   |
| Three-way comparison                      | PASS   |
| Token tracking per run                    | PASS   |
| Cost estimation                           | PASS   |
| Search tracing                            | PASS   |
| Configurable runs/temperature             | PASS   |
| Report generation (JSON + Markdown)       | PASS   |

### 6.5 Load Testing

**Status**: Not performed (unchanged)

### 6.6 Security Testing

**Status**: No SAST/DAST configured (unchanged)

---

## 7. Operations Audit

### 7.1 CI/CD Pipeline

| Item                       | v0.2.0     | v0.2.2    | Notes                                               |
| -------------------------- | ---------- | --------- | --------------------------------------------------- |
| GitHub Actions (Extension) | FAIL       | **PASS**  | Build + Chrome Web Store publish on push to main    |
| GitHub Actions (Backend)   | FAIL       | **FAIL**  | Backend uses Cloud Build only                       |
| Automated testing on PR    | FAIL       | **FAIL**  | No PR gate                                          |
| Linting/type checking      | Local      | **Local** | mypy strict + ruff + black configured but not in CI |
| Security scanning          | FAIL       | **FAIL**  | No SAST/DAST                                        |
| Cloud Build (Backend)      | Configured | **PASS**  | Triggers on push to main/master                     |

### 7.2 Deployment Process

| Aspect              | v0.2.0    | v0.2.2   | Notes                                            |
| ------------------- | --------- | -------- | ------------------------------------------------ |
| Automated deploy    | HIGH risk | **PASS** | Cloud Build auto-deploys on push                 |
| Secret management   | FAIL      | **PASS** | Google Secret Manager with setup script          |
| Staging environment | FAIL      | **FAIL** | Still no staging                                 |
| Rollback mechanism  | FAIL      | **WARN** | Cloud Run revisions exist, no automated rollback |
| Post-deploy config  | FAIL      | **WARN** | `set-env.sh` has CORS wildcard issue             |

### 7.3 Documentation

| Item                     | v0.2.0         | v0.2.2                                  |
| ------------------------ | -------------- | --------------------------------------- |
| CLAUDE.md (architecture) | Excellent      | **Excellent**                           |
| API documentation        | Auto-generated | **Auto-generated** (FastAPI)            |
| Deployment docs          | Partial        | **Good** (deploy.sh + setup-secrets.sh) |
| Benchmark docs           | N/A            | **PASS** (scripts + configs)            |
| Runbooks                 | Missing        | **Missing**                             |
| Incident response        | Missing        | **Missing**                             |

---

## 8. Compliance Audit

### 8.1 Chrome Web Store Requirements

| Requirement              | v0.2.0             | v0.2.2                 |
| ------------------------ | ------------------ | ---------------------- |
| Manifest V3              | PASS               | **PASS**               |
| Single purpose           | PASS               | **PASS**               |
| Minimal permissions      | PASS               | **PASS**               |
| No remote code execution | PASS               | **PASS**               |
| Content Security Policy  | FAIL               | **PASS**               |
| Privacy policy           | NEEDS VERIFICATION | **NEEDS VERIFICATION** |

### 8.2 Data Privacy (GDPR/CCPA)

| Aspect            | v0.2.0  | v0.2.2      | Notes                                      |
| ----------------- | ------- | ----------- | ------------------------------------------ |
| User consent      | WARN    | **WARN**    | No explicit consent flow                   |
| Data retention    | PARTIAL | **PARTIAL** | 30-day cache, review embeddings indefinite |
| Right to deletion | FAIL    | **FAIL**    | No mechanism                               |
| Privacy policy    | MISSING | **MISSING** | Required for store                         |

### 8.3 AI Transparency

| Aspect                  | v0.2.0 | v0.2.2                         |
| ----------------------- | ------ | ------------------------------ |
| Model disclosure        | PASS   | **PASS**                       |
| Confidence scores       | PASS   | **PASS**                       |
| Token/cost transparency | FAIL   | **PASS** (stored per analysis) |
| Limitations disclosure  | FAIL   | **FAIL**                       |

---

## 9. Remaining Critical Issues (Release Blockers)

### BLOCKER 1: `set-env.sh` CORS Wildcard

**File**: `backend/set-env.sh`, line 34
**Issue**: `ALLOWED_ORIGINS=*` is set during Cloud Run env update, overriding the safe default
**Fix**: Change to `ALLOWED_ORIGINS=https://ruh-api-948739110049.us-central1.run.app,chrome-extension://YOUR_EXTENSION_ID`
**Effort**: 5 minutes

### BLOCKER 2: Error Details in 500 Responses

**Files**: `backend/src/api/routes/analyze.py` (multiple locations)
**Issue**: `detail=f"Review search failed: {str(e)}"` exposes internal error messages
**Fix**: Return generic message in production, log details server-side
**Effort**: 30 minutes

### BLOCKER 3: No Unit Tests for Core Domain Logic

**Files**: `harm_calculator.py`, `ingredient_matcher.py`
**Issue**: The harm score calculation (determines product safety ratings users see) has 0% test coverage. A regression here could misrate products.
**Fix**: Write parametrized tests covering edge cases
**Effort**: 4-6 hours

### BLOCKER 4: No Privacy Policy

**Issue**: Required for Chrome Web Store listing and GDPR compliance
**Fix**: Draft privacy policy covering data collection, retention, third-party services (Claude API, Supabase, Cohere)
**Effort**: 2-4 hours

---

## 10. Prioritized Remediation Roadmap

### Phase 1: Release Blockers (1-2 days)

| Task                                     | Effort | Status   |
| ---------------------------------------- | ------ | -------- |
| Fix `set-env.sh` CORS wildcard           | 5m     | **TODO** |
| Sanitize error messages in 500 responses | 30m    | **TODO** |
| Write unit tests for HarmScoreCalculator | 4h     | **TODO** |
| Write unit tests for ingredient_matcher  | 4h     | **TODO** |
| Draft privacy policy                     | 3h     | **TODO** |

### Phase 2: Stability Hardening (Week 1)

| Task                                        | Effort | Status |
| ------------------------------------------- | ------ | ------ |
| Add retry with backoff for Claude API       | 4h     | TODO   |
| Add AbortController to extension fetch      | 2h     | TODO   |
| Add background worker message validation    | 4h     | TODO   |
| Sanitize error details in all 500 responses | 2h     | TODO   |
| Remove unused redis/celery dependencies     | 30m    | TODO   |
| Add request size limit middleware           | 1h     | TODO   |

### Phase 3: Observability (Week 2)

| Task                                    | Effort | Status |
| --------------------------------------- | ------ | ------ |
| Switch to structured JSON logging       | 4h     | TODO   |
| Add request ID middleware               | 2h     | TODO   |
| Add Sentry error tracking               | 2h     | TODO   |
| Create basic Cloud Monitoring dashboard | 4h     | TODO   |

### Phase 4: Testing & CI (Week 2-3)

| Task                                | Effort | Status |
| ----------------------------------- | ------ | ------ |
| Unit tests for auth module          | 2h     | TODO   |
| Unit tests for SearchToolService    | 4h     | TODO   |
| Integration tests for database      | 8h     | TODO   |
| Add backend GitHub Actions workflow | 4h     | TODO   |
| Add PR gate (lint + type + test)    | 2h     | TODO   |

### Phase 5: Polish (Week 3+)

| Task                          | Effort | Status |
| ----------------------------- | ------ | ------ |
| Load testing (100 concurrent) | 8h     | TODO   |
| HSTS headers                  | 30m    | TODO   |
| Rate limit response headers   | 1h     | TODO   |
| Prometheus metrics endpoint   | 8h     | TODO   |
| Accessibility audit           | 4h     | TODO   |
| Create deployment runbook     | 4h     | TODO   |

---

## Appendix A: File Inventory (v0.2.2)

### Backend (30+ Python files)

- `/backend/src/api/` - 5 files (main, auth, routes: health, analyze, admin)
- `/backend/src/domain/` - 4 files (models, harm_calculator, ingredient_matcher, + init)
- `/backend/src/infrastructure/` - 16 files (config, database, claude_agent, claude_query, langgraph_agent, cohere_native_agent, safety_agent, product_scraper, search_tool_service, search_clients/\*, token_tracker, validation_logger, review_vector_service, ingredient_research_service, trafilatura_extractor, extraction_service)
- `/backend/tests/` - 2 files (e2e/test_product_analysis, test_langgraph_agent)
- `/backend/scripts/` - 3 files (compare_agents, compare_all_agents, benchmark/\*)
- `/backend/supabase/migrations/` - 12 SQL files

### Extension (12 TypeScript/Svelte files)

- `/extension/src/content/` - 2 files
- `/extension/src/background/` - 1 file
- `/extension/src/components/` - 2 files
- `/extension/src/lib/` - 5 files
- `/extension/src/types/` - 1 file
- `/extension/src/` - 4 files (entry points)

---

## Appendix B: Dependency Audit (v0.2.2)

### Backend

| Package        | Version   | Risk   | Notes                                 |
| -------------- | --------- | ------ | ------------------------------------- |
| fastapi        | >=0.115.0 | Low    | Well-maintained                       |
| anthropic      | >=0.75.0  | Low    | First-party SDK (updated from 0.39.0) |
| supabase       | >=2.0.0   | Low    | Active development                    |
| beautifulsoup4 | >=4.12.0  | Low    | Mature library                        |
| cohere         | >=5.0.0   | Low    | First-party SDK (NEW)                 |
| langchain      | >=0.3.0   | Medium | Large dependency tree (NEW)           |
| langgraph      | >=0.2.0   | Medium | Newer library (NEW)                   |
| playwright     | >=1.49.0  | Medium | Browser automation binary (NEW)       |
| tavily         | >=0.5.0   | Low    | Search API client (NEW)               |
| trafilatura    | >=1.12.0  | Low    | Content extraction (NEW)              |
| slowapi        | latest    | Low    | Rate limiting                         |
| redis          | >=5.2.0   | N/A    | **UNUSED - remove**                   |
| celery         | >=5.4.0   | N/A    | **UNUSED - remove**                   |

### Extension

| Package | Version | Risk | Notes                |
| ------- | ------- | ---- | -------------------- |
| svelte  | ^5.0.0  | Low  | Active development   |
| idb     | ^8.0.0  | Low  | Minimal, well-tested |

---

## Appendix C: Critical Issue Checklist

### Resolved Since v0.2.0

- [x] ~~Use constant-time key comparison~~ (secrets.compare_digest)
- [x] ~~Add Content Security Policy to manifest~~ (CSP in manifest.json)
- [x] ~~Fix CORS to specific origins only~~ (config.py cors_origins)
- [x] ~~Remove localhost from host_permissions~~ (manifest.json)
- [x] ~~Clean .env.example of real keys~~ (placeholder values)
- [x] ~~Add .env to .gitignore~~ (was already there, never committed)

### Still Open

- [ ] Fix `set-env.sh` CORS wildcard (`ALLOWED_ORIGINS=*`)
- [ ] Sanitize error details in 500 responses
- [ ] Add retry logic with exponential backoff (Claude API)
- [ ] Add AbortController to extension fetch calls
- [ ] Implement message validation in background worker
- [ ] Create unit tests for HarmScoreCalculator
- [ ] Create unit tests for ingredient_matcher
- [ ] Create unit tests for authentication
- [ ] Set up GitHub Actions CI for backend
- [ ] Add Sentry or similar error tracking
- [ ] Create privacy policy for Chrome Web Store
- [ ] Remove unused redis/celery dependencies

---

## Appendix D: New Architecture Components (v0.2.2)

### Multi-Agent System

```
ProductSafetyAgentWrapper (safety_agent.py)
  ├─ Claude Agent (claude_agent.py) - DEFAULT
  │   ├─ Native tools: web_search, web_fetch
  │   └─ Custom tools: Tavily/Serper search
  ├─ LangGraph Agent (langgraph_agent.py) - EXPERIMENTAL
  │   ├─ Cohere Command R+ model
  │   └─ LangGraph ReACT pattern
  └─ Cohere Native Agent (cohere_native_agent.py) - EXPERIMENTAL
      └─ Direct Cohere SDK usage
```

### Analysis Pipeline (v0.2.2)

```
Request → Cache Check → Extract (Trafilatura | Claude Query)
  → DB Match (allergen/PFAS knowledge base)
  → Classify (safe | known | needs_research)
  → AI Enhancement (only needs_research items)
  → Merge (DB + AI results)
  → Validate (cross-ref DB, log misclassifications)
  → Score (HarmScoreCalculator)
  → Store + Return
  → Review Analysis (embeddings → semantic search → Claude health concerns)
```

### Search Service

```
SearchToolService
  ├─ L1 Cache: In-memory LRU (1000 entries, 1hr TTL)
  ├─ L2 Cache: Supabase search_cache (24hr TTL)
  ├─ Primary: Tavily API (with content extraction)
  ├─ Fallback: Serper API
  └─ Last resort: Stale cache or empty results
```

---

## Audit Methodology

This audit was conducted using:

1. Full codebase exploration of backend and extension source
2. Git history analysis (20 commits since v0.2.0)
3. Line-by-line review of security-critical files (auth, config, CORS, manifest)
4. Comparison against v0.2.0 audit findings
5. Cross-reference with Chrome Web Store requirements

**Auditor**: Claude Code (Opus 4.6)
**Audit Date**: February 6, 2026
**Previous Audit**: December 26, 2025 (v0.2.0, Score: 58/100)
**Next Review**: Recommended after Phase 2 completion
