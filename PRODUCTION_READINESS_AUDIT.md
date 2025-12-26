# Ruh Production Readiness Audit

> **Target**: 1000 DAU | **Date**: 2025-12-26 | **Version**: 0.2.0

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Overall Score** | 58/100 |
| **Critical Issues** | 12 |
| **High Priority** | 18 |
| **Medium Priority** | 25 |
| **Estimated Remediation** | 4-6 weeks |

### Component Scores

| Component | Score | Status |
|-----------|-------|--------|
| Backend API | 65/100 | Good foundation, needs security hardening |
| Backend Domain | 70/100 | Solid logic, no tests |
| Backend Infrastructure | 55/100 | Missing retry logic, async issues |
| Extension Content Script | 55/100 | No timeout/retry, security gaps |
| Extension Background | 50/100 | No message validation |
| Extension UI | 65/100 | Good architecture, accessibility gaps |
| Testing | 15/100 | Critical gap - E2E only |
| DevOps/Infrastructure | 45/100 | Secrets exposed, no CI/CD |

### Traffic Light Summary

- **Ready for Production**: Authentication, rate limiting, clean architecture
- **Needs Work**: Error handling, timeouts, retries, logging
- **Blockers**: Missing CSP, secrets in repo, CORS wildcard, no unit tests

---

## 1. Security Audit

### 1.1 Authentication & Authorization

| Item | Status | Notes |
|------|--------|-------|
| API Key Authentication | PASS | Bearer token via HTTPBearer |
| Key Comparison | **FAIL** | Timing-vulnerable `!=` operator |
| Admin Separation | WARN | Same key for admin and user endpoints |
| Key Rotation | FAIL | No rotation mechanism |

**Recommendation**: Use `secrets.compare_digest()` for constant-time comparison.

### 1.2 Secrets Management [CRITICAL]

| Issue | Severity | Location |
|-------|----------|----------|
| `.env` files committed to repo | CRITICAL | `/backend/.env`, `/extension/.env` |
| API keys in `set-env.sh` | CRITICAL | `/backend/set-env.sh` |
| Real key in `.env.example` | HIGH | `/extension/.env.example` |

**Immediate Action Required**:
1. Remove secrets from git history using `git filter-branch` or `bfg`
2. Rotate all exposed API keys
3. Add `*.env` to `.gitignore`

### 1.3 Input Validation

| Component | Status | Issue |
|-----------|--------|-------|
| Product URL validation | FAIL | No scheme/domain validation |
| API response validation | FAIL | No schema validation (Zod) |
| Message type validation | FAIL | Background worker accepts any message |
| HTML content sanitization | WARN | Scraped HTML passed to Claude unsanitized |

### 1.4 CSP & CORS

| Item | Status | Issue |
|------|--------|-------|
| Backend CORS | **CRITICAL** | `allow_origins=["*"]` allows any origin |
| Extension CSP | **CRITICAL** | No CSP defined in manifest.json |
| localhost in host_permissions | HIGH | Remove before production |

**Recommended Backend CORS**:
```python
allow_origins=["chrome-extension://YOUR_EXTENSION_ID"]
```

**Recommended Extension CSP**:
```json
"content_security_policy": {
  "extension_pages": "script-src 'self'; connect-src https://ruh-api-*.run.app"
}
```

### 1.5 API Security

| Item | Status | Recommendation |
|------|--------|----------------|
| HTTPS enforcement | WARN | Add HSTS headers |
| Request size limits | FAIL | No max body size configured |
| Rate limiting | PASS | 30/min on analyze endpoint |
| Distributed rate limiting | FAIL | Single-instance only (Redis needed) |

---

## 2. Reliability Audit

### 2.1 Error Handling

| Component | Coverage | Issues |
|-----------|----------|--------|
| Backend API routes | 70% | Inconsistent error response format |
| Claude AI calls | 60% | RateLimitError handled, others partial |
| Database operations | 80% | Returns None/False on failure |
| Content script | 40% | No retry, no timeout |
| Background worker | 20% | Silent failures on storage ops |

### 2.2 Retry Mechanisms

| Component | Status | Recommendation |
|-----------|--------|----------------|
| Claude API calls | FAIL | Add exponential backoff (3 retries) |
| Database operations | FAIL | Add retry with backoff |
| HTTP scraping | FAIL | Add retry for 429/503 |
| Extension API calls | FAIL | Add fetch retry logic |

### 2.3 Timeout Handling

| Component | Timeout | Status |
|-----------|---------|--------|
| Claude API | None | CRITICAL - can hang indefinitely |
| Supabase operations | None | HIGH - no query timeout |
| Amazon scraping | 15s | OK but consider 30s |
| Content script fetch | None | CRITICAL - add AbortController |

### 2.4 Circuit Breakers

**Status**: Not implemented anywhere

**Recommendation**: Add circuit breaker for Claude API to prevent cascade failures

### 2.5 Graceful Degradation

| Scenario | Handling | Status |
|----------|----------|--------|
| Claude unavailable | Falls back to web_fetch | PASS |
| Scraping fails | Falls back to Claude agent | PASS |
| Database unavailable | MockDB fallback | PASS |
| Cache miss | Fetches fresh data | PASS |

---

## 3. Performance Audit

### 3.1 Response Time Analysis

| Endpoint | Expected | Bottleneck |
|----------|----------|------------|
| POST /api/analyze | 5-30s | Claude API (largest factor) |
| GET /api/health | <100ms | None |
| Scraping | 1-15s | Amazon response time |

### 3.2 Database Query Efficiency

| Issue | Impact | Fix |
|-------|--------|-----|
| No JSONB indexes | Slow allergen/PFAS lookups | Add GIN indexes |
| No connection pooling | Connection overhead | Use pooled client |
| Sync client in async context | Blocks event loop | Use async client |

### 3.3 Caching Strategy

| Layer | TTL | Status |
|-------|-----|--------|
| Backend (Supabase) | Indefinite | OK - keyed by URL hash |
| Extension (IndexedDB) | 30 days | OK but `clearExpired()` never called |
| Review insights | 7 days | OK |

### 3.4 Bundle Size (Extension)

| File | Size | Status |
|------|------|--------|
| background.js | ~5KB | OK |
| content.js | ~8KB | OK |
| sidepanel.js | ~50KB | OK (Svelte + components) |
| **Total** | ~65KB | GOOD - well under 200KB target |

---

## 4. Scalability Audit (1000 DAU)

### 4.1 Current Architecture Limits

| Resource | Limit | At 1000 DAU |
|----------|-------|-------------|
| Claude API | ~50 RPM tier | May need upgrade |
| Cloud Run instances | Auto-scale | OK |
| Supabase connections | 60 (free tier) | May need upgrade |

### 4.2 Rate Limiting for Scale

| Current | For 1000 DAU | Change Needed |
|---------|--------------|---------------|
| 30/min per IP | Per-user limits | Add API key-based limiting |
| In-memory storage | Redis-backed | Add Redis for distributed |

### 4.3 Cost Projections (1000 DAU)

| Service | Usage | Est. Monthly Cost |
|---------|-------|-------------------|
| Claude API | ~30,000 analyses | $150-300 |
| Cloud Run | ~1M requests | $20-50 |
| Supabase | Pro tier | $25 |
| **Total** | | **$200-400/month** |

---

## 5. Observability Audit

### 5.1 Logging Infrastructure

| Aspect | Status | Recommendation |
|--------|--------|----------------|
| Log format | Plain text | Switch to JSON structured |
| Log levels | Configured | OK |
| Request correlation | Missing | Add request ID middleware |
| Sensitive data | WARN | API key prefix logged |

### 5.2 Metrics & Monitoring

| Metric | Status |
|--------|--------|
| Request latency | NOT TRACKED |
| Error rate | NOT TRACKED |
| Claude token usage | NOT TRACKED |
| Cache hit rate | NOT TRACKED |

**Recommendation**: Add Prometheus metrics endpoint

### 5.3 Alerting

**Status**: No alerting configured

**Needed**:
- 5xx error rate > 1%
- P95 latency > 30s
- Claude API rate limit hits
- Database connection failures

### 5.4 AI-Specific Observability

| Metric | Status | Priority |
|--------|--------|----------|
| Token usage tracking | FAIL | HIGH |
| Model response validation | FAIL | HIGH |
| Confidence score distribution | FAIL | MEDIUM |
| Hallucination detection | FAIL | MEDIUM |

---

## 6. Testing Audit

### 6.1 Unit Test Coverage

| Component | Coverage | Priority |
|-----------|----------|----------|
| HarmScoreCalculator | 0% | P0 |
| match_ingredients_to_databases | 0% | P0 |
| verify_api_key | 0% | P0 |
| DatabaseService | 0% | P1 |
| AmazonScraper | 0% | P1 |
| Extension utils | 0% | P2 |

### 6.2 Integration Tests

**Status**: Empty directories exist but no tests

### 6.3 E2E Tests

| Test | Status |
|------|--------|
| Health endpoint | PASS |
| Product analysis (sunscreen) | PASS |
| Product analysis (frying pan) | PASS |
| Allergen profile | PASS (no assertions) |
| Invalid URL | WARN (accepts 200/422/500) |

### 6.4 Load Testing

**Status**: Not performed

**Needed before 1000 DAU**:
- Sustained 100 concurrent users
- Spike test: 0 to 500 users
- Claude API rate limit behavior

### 6.5 Security Testing

**Status**: No SAST/DAST configured

**Recommendation**: Add `bandit` for Python SAST

---

## 7. Operations Audit

### 7.1 CI/CD Pipeline

| Item | Status |
|------|--------|
| GitHub Actions | NOT CONFIGURED |
| Automated testing on PR | FAIL |
| Linting/type checking | Local only |
| Security scanning | FAIL |
| Cloud Build | Configured for deploy |

### 7.2 Deployment Process

| Aspect | Status | Risk |
|--------|--------|------|
| Manual scripts | HIGH | Human error |
| No approval gates | HIGH | Accidental production push |
| No staging environment | HIGH | Untested deploys |
| No rollback mechanism | MEDIUM | Recovery difficulty |

### 7.3 Rollback Capability

**Status**: No automated rollback

**Recommendation**: Configure Cloud Run traffic splitting

### 7.4 Incident Response

**Status**: No runbooks or procedures documented

### 7.5 Documentation

| Item | Status |
|------|--------|
| CLAUDE.md (architecture) | Excellent |
| API documentation | Auto-generated (FastAPI) |
| Deployment docs | Partial (README) |
| Runbooks | Missing |
| Incident response | Missing |

---

## 8. Compliance Audit

### 8.1 Chrome Web Store Requirements

| Requirement | Status |
|-------------|--------|
| Manifest V3 | PASS |
| Single purpose | PASS |
| Minimal permissions | PASS |
| No remote code execution | PASS |
| Content Security Policy | **FAIL** |
| Privacy policy | NEEDS VERIFICATION |

### 8.2 Data Privacy (GDPR/CCPA)

| Aspect | Status | Notes |
|--------|--------|-------|
| User consent | WARN | No explicit consent flow |
| Data retention | PARTIAL | 30-day cache, no user data purge |
| Right to deletion | FAIL | No mechanism |
| Privacy policy | MISSING | Required for store |

### 8.3 AI Transparency

| Aspect | Status |
|--------|--------|
| Model disclosure | PASS | `claude_model` in response |
| Confidence scores | PASS | Included in analysis |
| Limitations disclosure | FAIL | No user-facing disclaimers |

---

## 9. Prioritized Remediation Roadmap

### Phase 1: Critical Security (Week 1-2)

| Task | Effort | Impact |
|------|--------|--------|
| Remove secrets from git history | 2h | Critical |
| Rotate all API keys | 1h | Critical |
| Add CSP to extension manifest | 1h | Critical |
| Fix CORS to specific origins | 30m | Critical |
| Use constant-time key comparison | 30m | Critical |
| Remove localhost from host_permissions | 10m | High |

### Phase 2: Reliability (Week 2-3)

| Task | Effort | Impact |
|------|--------|--------|
| Add Claude API retry with backoff | 4h | Critical |
| Add request timeouts (30s) | 2h | Critical |
| Add AbortController to extension fetch | 2h | Critical |
| Add message validation to background worker | 4h | High |
| Implement structured JSON logging | 4h | High |
| Add error standardization | 4h | Medium |

### Phase 3: Testing (Week 3-4)

| Task | Effort | Impact |
|------|--------|--------|
| Unit tests for HarmScoreCalculator | 4h | Critical |
| Unit tests for auth | 2h | Critical |
| Unit tests for ingredient_matcher | 4h | Critical |
| Integration tests for database | 8h | High |
| Integration tests for scraper | 8h | High |
| Set up pytest-cov in CI | 2h | High |

### Phase 4: Operations (Week 4-5)

| Task | Effort | Impact |
|------|--------|--------|
| Create GitHub Actions CI workflow | 4h | High |
| Add PR checks (lint, type, test) | 2h | High |
| Set up Sentry error tracking | 2h | High |
| Add basic monitoring dashboard | 4h | Medium |
| Create deployment runbook | 4h | Medium |
| Add Dockerfile non-root user | 1h | Medium |

### Phase 5: Polish (Week 5-6)

| Task | Effort | Impact |
|------|--------|--------|
| Add Prometheus metrics endpoint | 8h | Medium |
| Implement rate limit headers | 2h | Medium |
| Add request ID correlation | 4h | Medium |
| Add accessibility fixes | 4h | Medium |
| Load testing | 8h | Medium |
| Create privacy policy | 4h | Required |

---

## Appendix A: File Inventory

### Backend (21 Python files)
- `/backend/src/api/` - 5 files
- `/backend/src/domain/` - 4 files
- `/backend/src/infrastructure/` - 10 files
- `/backend/tests/` - 2 files

### Extension (12 TypeScript/Svelte files)
- `/extension/src/content/` - 2 files
- `/extension/src/background/` - 1 file
- `/extension/src/components/` - 2 files
- `/extension/src/lib/` - 5 files
- `/extension/src/types/` - 1 file
- `/extension/src/` - 4 files (entry points)

---

## Appendix B: Dependency Audit

### Backend

| Package | Version | Risk | Notes |
|---------|---------|------|-------|
| fastapi | >=0.115.0 | Low | Well-maintained |
| anthropic | >=0.39.0 | Low | First-party SDK |
| supabase | >=2.0.0 | Low | Active development |
| beautifulsoup4 | >=4.12.0 | Low | Mature library |
| redis | >=5.2.0 | N/A | **UNUSED - remove** |
| celery | >=5.4.0 | N/A | **UNUSED - remove** |

### Extension

| Package | Version | Risk | Notes |
|---------|---------|------|-------|
| svelte | ^5.0.0 | Low | Active development |
| idb | ^8.0.0 | Low | Minimal, well-tested |

---

## Appendix C: Critical Issue Checklist

- [ ] Remove secrets from git history
- [ ] Rotate all exposed API keys
- [ ] Add Content Security Policy to manifest
- [ ] Fix CORS to specific origins only
- [ ] Add request timeouts to Claude API calls
- [ ] Add retry logic with exponential backoff
- [ ] Implement message validation in background worker
- [ ] Create unit tests for HarmScoreCalculator
- [ ] Create unit tests for authentication
- [ ] Set up GitHub Actions CI pipeline
- [ ] Add Sentry or similar error tracking
- [ ] Create privacy policy for Chrome Web Store

---

## Audit Methodology

This audit was conducted using:
1. Automated codebase exploration via 10 specialized agents
2. Function-level documentation at each directory
3. Web research on 2025 production readiness standards
4. Cross-reference with Chrome Web Store requirements
5. Comparison against industry best practices for AI applications

**Auditor**: Claude Code (Opus 4.5)
**Audit Date**: December 26, 2025
**Next Review**: Recommended after Phase 2 completion
