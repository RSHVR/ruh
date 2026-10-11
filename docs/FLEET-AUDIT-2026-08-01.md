# Fleet Audit — 2026-08-01 (merge-review package)

> **Author:** orchestrator synthesis of 5 read-only worktree agents (perf, data-model,
> transparency, static-security, cost), all re-run against `development`@`17c047c` after the
> first pass hit the stale `main`/v0.3.0 tree (see MEMORY.md). Every finding below was either
> **independently re-verified by the orchestrator** (marked ✔︎ VERIFIED) or is **agent-reported**
> (marked ◻︎ REPORTED) or **requires a live prod/Friday-pass check** (marked ⚠︎ NEEDS-LIVE).
> **Nothing here has landed on `development`.** This doc is the review queue for Veer + the diffs
> to apply on his go-ahead. Companion: `KB-OPTIMIZATION-PLAN.md` (roadmap), `LORE.md`, `MEMORY.md`.

---

## 0. TL;DR — what to look at first

| # | Finding | Sev | Status | One-line fix |
|---|---------|-----|--------|--------------|
| **S1** | Migration 003 lets any signed-up user WRITE the shared safety cache + allergen/PFAS KB via the public anon key | **CRITICAL** | ⚠︎ NEEDS-LIVE | Port migration 012 (main has it; `development` skips 011→013) — service_role-only writers |
| **S2** | Same 003 policy → any authed user reads/edits ALL `users` rows (email, auth_id, allergen_profile) | **CRITICAL** | ⚠︎ NEEDS-LIVE | Restrict `users` policy `TO service_role` |
| **B1** | `review_vector_service` calls `db.supabase.*` but the object only has `.client` → **hybrid review RAG + review storage are silently DEAD in prod** | **HIGH (P1)** | ✔︎ VERIFIED | `db.supabase` → `db.client` (×5) + a real (unmocked) route test |
| **S3** | Paywall bypass: full analysis detail returned regardless of unlock; gating is client-side only | **HIGH** | ◻︎ REPORTED (high-confidence static) | Server-side strip gated fields for non-unlocked callers |
| **S4** | Prompt injection via client `product_html`/`reviews_html` → poisons the shared `url_hash` cache | **HIGH** | ◻︎ REPORTED | Delimit untrusted content; flip `validate_substances` LOG-ONLY→enforce |
| **D1** | `category` column stores the RETAILER; the product-category multiplier reads a field the agent never emits → **the high-risk-product multiplier is effectively dead** | **HIGH** | ✔︎ VERIFIED | Migration 021 (retailer_key + product_category) + stop writing `category=retailer` + emit a real category |
| **P1** | Synchronous blocking I/O on the whole hot path → effective concurrency ≈ 1 | **HIGH** | ◻︎ REPORTED | `AsyncAnthropic` + `asyncio.to_thread` for Cohere/Supabase |
| **P2** | Single `basic` (¼ vCPU) container via `cf-singleton`; `getRandom`/`max_instances` unused; 6h cron contends on the same instance | **HIGH** | ◻︎ REPORTED | `getRandom(env.RUH_API, N)` + bump instance + throttle cron |
| **R1** | No graceful drain on redeploy → a deploy kills every in-flight ~40s analysis (the MEMORY-noted outage) | **HIGH** | ◻︎ REPORTED | `--timeout-graceful-shutdown 60` + ≥2 instances |
| **C1** | Stage-2 (1000 users) all-in ≈ **$1,450/mo — 4.8× over the $300 cap**; levers are mandatory | **HIGH (planning)** | ✔︎ VERIFIED (rates) | Ship cache-first + ingredient cache + classifiers before scaling |
| **C2** | Cost model assumes 5 **analyses**/user/mo, but the shipped model auto-analyzes EVERY page (caps only unlocks) | **decision** | ◻︎ REPORTED | Veer product decision — cap analyses or absorb page-view cost |

**Launch-blockers (my read):** S1, S2, S3 (integrity/PII/monetization), and B1 (a shipped feature is dead).
S1/S2 severity is gated on ⚠︎ **whether prod ran migration 012 out-of-band** — confirm first (see §5).

---

## 1. Security (static) — the headline is a MISSING migration

The single most important structural fact: **migration `012_fix_security_findings` exists on `main`/v0.3.0
but is ABSENT on `development`** (which jumps `011` → `013`). So the RLS hardening `main` received was
never carried onto the active branch. Everything in this section flows from that.

- **S1 — CRITICAL — authenticated write to the shared safety cache + KB.** `003_enable_rls.sql:37-40,
  53-61, 153-156, 165-168`. Policies use `auth.role() = 'authenticated'` with no ownership predicate /
  no `WITH CHECK`. A free account's Supabase JWT + the public anon key (shipped in the extension) can
  hit PostgREST directly and `UPDATE product_analyses` (set `overall_score=100`, wipe
  `allergens_detected`/`pfas_detected`) for any `url_hash` — poisoning the globally-shared cache served
  to everyone — and `DELETE`/`UPDATE` the `allergens`/`pfas_compounds` KB. For a product-*safety* app
  this is the worst-case integrity failure. **Fix:** migration 021 — drop the `… OR auth.role() =
  'authenticated'` writers; keep public `SELECT USING(true)`; writers `TO service_role`.
- **S2 — CRITICAL — cross-user `users` read/write (PII).** `003:37-40` `FOR ALL USING(service_role OR
  authenticated)` → any authed user `SELECT *` (emails, auth_ids, allergen profiles) and
  `UPDATE`/`DELETE` arbitrary users. Also feeds S-series user-id enumeration. **Fix:** policy `TO
  service_role`; keep per-user "own" SELECT/UPDATE only.
- **S3 — HIGH — paywall bypass (client-side gating only).** `analyze.py:88-92, 140-148, 811-820` and
  **`GET /api/analyze/cached` (`:281-308`)** always return the full `analysis` (allergens, pfas,
  other_concerns, research_sources). `analysis_unlocked` is just a flag the Svelte UI switches on;
  `deduct`/`unlocked_analyses` is never consulted on the data-return path. `GET
  /api/analyze/cached?product_url=<cached>` returns full detail for free (60/min, no body). **Fix:**
  when caller is non-unlimited and not in `unlocked_analyses`, omit gated fields server-side (return
  score + counts only) until a successful unlock.
- **S4 — HIGH — prompt injection → cache poisoning.** `analyze.py:365-383, 545-552`;
  `claude_query.py:307-329, 382-390`. `product_html`/`reviews_html` are attacker-controlled and
  concatenated into Claude prompts with no delimiting/guardrail; a crafted page can steer the model to
  suppress findings + inflate the score, then that result is cached by `url_hash` for all future
  visitors. The identity guard (`domain/identity.py`) checks name/brand vs URL slug only — it does
  **not** validate substances, so suppression passes. **Fix:** delimit untrusted content as data;
  flip `validate_substances` from LOG-ONLY to enforce (also KB-plan §E); consider not caching (or
  trust-flagging) client-HTML-only analyses.
- **S5 — HIGH — `user_searches` / `user_interactions` cross-user read** (`003:77-80, 112-115`). Same
  `authenticated FOR ALL` pattern. **Fix:** `TO service_role`.
- **M1 — MED — static API key is public AND guards admin.** `VITE_API_KEY` is baked into the extension
  bundle (`extension/src/lib/api.ts:4`, `background.ts:38-39`) and equals the backend `API_KEY` that
  protects `/api/admin/*` (`admin.py:23`) and the cron (`worker.js:41`). Anyone can read admin/
  validation data + run unlimited `/api/analyze` (Claude cost abuse). **Fix:** separate admin auth
  from the client key; treat the shipped key as public (rate/cost limits only).
- **M2 — MED — `deduct_credit` / `process_referral_conversion` trust `p_user_id`, default PUBLIC
  EXECUTE.** `013:146-214`, `016:67-154`; no `REVOKE`/`GRANT` in any migration. If PostgREST-reachable,
  `deduct_credit(victim_id, hash)` drains a victim's credits and `process_referral_conversion(id)`
  farms the +10 referral reward without a real analysis. Backend always calls with a server-derived id,
  so this is only exploitable via direct DB access. **Fix:** `REVOKE EXECUTE … FROM anon, authenticated,
  public` on all credit/referral SECURITY DEFINER functions; or add an `auth.uid()→user_id` check.
- **M3 — MED — public-writable cache tables.** `search_cache` (`009:41-44`) + `extracted_content`
  (`011:55-59`) are `USING(true) WITH CHECK(true)` no-role → PUBLIC; `ingredient_research` (010) has
  **RLS never enabled** on this branch. These feed the analysis pipeline → cache-poisoning path. **Fix:**
  `TO service_role` + `ALTER TABLE ingredient_research ENABLE ROW LEVEL SECURITY` (this is what 012 did).
- **L-series:** `validation_logs` authed-read-all (info disclosure, no PII); `set_current_user_id`
  SECURITY DEFINER without `SET search_path`; `set-env.sh` `ALLOWED_ORIGINS=*` with credentials (dormant
  — active deploy is the CF Worker with a restricted origin list); debug key-prefix log.

**Key-handling verdict (all PASS except the static key):** ANTHROPIC / Supabase service_role / SERPER /
TAVILY / COHERE / SUPABASE_JWT_SECRET are all Worker-secret → container-env, never logged, never in the
extension. The anon key is public *by design* — its safety rests entirely on RLS, which is why S1/S2/S5
matter. Static `API_KEY` FAILs (public + over-scoped, M1). JWT verify is correct (HS256, audience,
expiry, alg pinned; API-key path constant-time). **No SQL injection** — all RPCs parameterized; the only
`EXECUTE` is a constant string. Prompt injection (S4) is the real injection risk.

---

## 2. Correctness — a shipped feature is silently dead

- **B1 — HIGH (P1) — hybrid review RAG + review storage throw `AttributeError` in prod. ✔︎ VERIFIED.**
  `review_vector_service.py` uses `db.supabase.table(...)` / `db.supabase.rpc(...)` at lines 318, 352,
  414, 447, 512, where `db` is the `DatabaseService` singleton (`from .database import db`).
  `DatabaseService` (`database.py:18-42`) defines only `self.client` (+ an `is_available` property) —
  **no `supabase` attribute, no `__getattr__`, nothing sets it at runtime.** So every review store /
  summary / semantic+lexical search call raises `AttributeError`, is caught by the surrounding
  try/except (INV-3 degradation), and returns empty. Net: **`review_chunks` is never populated, review
  summaries never stored, and ADR-009 hybrid RAG returns nothing — in production, silently.**
  - Why tests are green: `test_review_hybrid.py:30-31` monkeypatches `rvs.db` with a `SimpleNamespace`
    and stubs `_semantic_candidates` / `_lexical_candidates` — the real `db.supabase` calls are never
    exercised. Exactly the mock-boundary class from the 2026-08-01 wrapper outage (MEMORY.md).
  - **Interaction with P3 (below):** because these calls fail *fast*, the review pipeline currently
    adds less latency than the perf audit assumed (Cohere embeds + the Claude review-insights call still
    run; the DB store/search abort immediately). **Fixing B1 will make the RAG actually work AND add
    back the DB round-trips — so the P3 "move reviews off the critical path" fix becomes MORE important
    once B1 lands, not less.** Sequence them together.
  - **Fix:** `db.supabase` → `db.client` (5 sites) + a real integration test that calls
    `store_reviews`/`get_health_relevant_reviews` against a fake `db.client` (not a stubbed private
    method) so the attribute seam is covered. **⚠︎ Final proof:** query prod for `SELECT count(*) FROM
    review_chunks` — expect ≈0 if it's been dead since ADR-009 shipped.
  - Note: `review_insights` (the Claude health summary) is a **separate** path — stored via
    `database.py::cache_review_insights` using `self.client` — and **does** work + persist. Only the
    `review_vector_service` (chunks + RAG) path is dead.

---

## 3. Performance & robustness

All four originally-flagged issues re-confirmed on `17c047c`; the `safety_agent.py` wrapper is a thin
router that (default config `use_langgraph_agent=False`) calls the same synchronous `ProductSafetyAgent`.
**Latency budget (reasoned, no live run): p50 ≈ 40–48s, p90 breaches 45s.** The agent custom-search loop
dominates at ~22–35s; the review sub-pipeline adds ~10–19s (see B1 caveat) *after* the score is built.

- **P1 — HIGH — synchronous blocking I/O, no concurrency.** No `AsyncAnthropic`, no `cache_control`,
  `to_thread` only on the disabled LangGraph path + the referral hook. Anthropic/Cohere/Supabase clients
  are sync, called from `async def`. One analysis holds the event loop ~40s; concurrent users serialize.
  Uvicorn = 1 worker, no flags. **Fix:** `AsyncAnthropic` + `await`; wrap Cohere/Supabase in
  `asyncio.to_thread`.
- **P2 — HIGH — single container + cron contention.** `worker.js:28` `getContainer(env.RUH_API)` →
  `cf-singleton-container` → one DO → one `basic` (¼ vCPU/1 GiB) instance; `max_instances:2` never used.
  The 6h rescan cron (`worker.js:37-68`) POSTs `/api/analyze` sequentially to that same instance,
  contending with live traffic. **Fix:** `getRandom(env.RUH_API, 2)`; `instance_type: standard-1`;
  throttle the cron.
- **P3 — HIGH — review pipeline inline on the critical path** (~10–19s, deferrable). Return the analysis
  immediately; move storage/RAG/insights to `BackgroundTasks`/`asyncio.create_task`, served via the
  existing `GET /analyze/{url_hash}/reviews`. Collapse the N+1 review insert into one bulk insert; parse
  reviews once (currently parsed twice). **(Sequence with B1 — see §2.)**
- **P4 — MED-HIGH — no prompt caching + `count_tokens` preflight per call.** Full KB re-sent every
  tool-loop iteration with no `cache_control` (drives the $0.271 mean). `count_tokens` fires a blocking
  Anthropic round-trip before *every* create just to log an estimate. **Fix:** `cache_control:{"type":
  "ephemeral"}` on the static KB block (cache-read = 0.1× input); delete the preflight `count_tokens`
  (use `response.usage`).
- **P5 — MED — static KB reloaded per request** (3 sequential blocking selects, uncached, 32/75/50 rows)
  + reviews double-parsed. **Fix:** module-level KB cache w/ TTL; reuse the parsed review list; batch the
  5 health-query embeds into one `co.embed`.
- **Robustness:** **R1 — no graceful drain** (`main.py` lifespan is a no-op; no
  `--timeout-graceful-shutdown`; single instance) → a deploy kills in-flight analyses (the MEMORY
  outage). **R2 — no server-side deadline** (45s unbounded; only `max_iterations=10`) → wrap in
  `asyncio.wait_for(~35s)`, return the computed `basic_analysis` on timeout (degrade path exists). **R3
  — no client timeout/retry** (mitigated for revisits by the new `/analyze/cached` probe, but a
  first-analysis stall hangs the UI). **R4 — 429 handling asymmetric** (extracted path degrades; the
  web_fetch fallbacks re-raise 429). **R5 — cold start** on `basic` after `sleepAfter=15m`.

---

## 4. Data model (SQL validated by the agent in a throwaway Postgres 16)

- **D1 — HIGH — `category` = retailer + a dead scoring multiplier. ✔︎ VERIFIED.** `analyze.py:671`
  literally writes `"category": analysis.retailer` into the stored row (values like "Amazon Canada"/
  "Amazon.ca"). Separately, `harm_calculator.py:154` reads `analysis_data.get("category","")` for the
  product-category multiplier — but the agent never emits a top-level product `category` (its only
  `category` fields are per-`other_concern`), so at score time that value is empty → the multiplier
  defaults to 1.0. **So the "high-risk product type" multiplier is effectively dead, and the stored
  `category` column is unusable for analytics or the §I/§G#11 category→exposure map.** **Fix:** migration
  021 — add `retailer_key` (controlled vocab) + `product_category` (real: cosmetic/food/apparel/…);
  backfill `retailer_key` from the polluted legacy columns; stop writing `category=retailer`; have the
  agent emit a real `product_category` so the multiplier (and §I exposure class) can key off it.
- **D2 — HIGH — 14% duplicate rows + no family key.** 81 rows → 70 distinct normalized URLs (KB §F1).
  **Fix:** migration 022 — non-destructive `product_family_hash` (two-tier read: exact → family) +
  a FK-safe one-time dedup (repoint `user_searches.analysis_id` and `review_chunks.url_hash` to the
  survivor BEFORE delete — a naive delete errors on the FK). Backfill via the Python normalizer, not SQL.
- **D3 — MED — FK ON DELETE gaps.** `user_searches.analysis_id` and `user_interactions.alternative_id`
  have no on-delete action → they block deleting/deduping an analysis (proven in PG16). **Fix:** migration
  023 → `ON DELETE SET NULL`. (ADR-006's `invited_user_id` gap is **already fixed** in migration 018.)
  Every FK to `users(id)` already has an action, so **account deletion is not FK-blocked.**
- **D4 — MED — redundant + unused indexes (write amplification).** 10 explicit indexes duplicate a
  UNIQUE/PK's implicit btree (e.g. `idx_product_url_hash` over the `product_url_hash` UNIQUE); several are
  never queried (`review_chunks` rating/verified filters run in Python; `category`/`harm_score`/`cost`/
  `tokens` never filtered). `feature_requests` composite is `(status,hidden)` but the query filters
  `hidden` alone → seq scan. **Fix:** DROP list + reorder `(hidden,status)` (full SQL in the agent report).
- **D5 — MED — `analysis_feedback` double-defined** (001 creates it; 017 `DROP…CASCADE` + recreates with
  a different shape) and its `url_hash` has **no FK** to `product_analyses`. **Fix:** confirm 017 is the
  intended shape; add the FK after dedup.
- **Missing indexes with real queries:** `referrals(referrer_user_id, created_at DESC)`,
  `feature_requests(user_id, created_at)`, `product_analyses(product_family_hash)`.

---

## 5. Transparency — persistence is fixed; render has the gaps

- research_sources persistence is **wired end-to-end** on `17c047c` (produce → `store_analysis` →
  `models.py` → fresh + cache-hit + `/analyze/cached` paths). The earlier "route drops it" was the stale
  tree. ✔︎ (HEAD commit message corroborates.) **Doc fix:** KB-plan §C0 body (lines ~162-165) still says
  "0/81 persist / route drops it" — contradicts its own banner; update it.
- **T1 — render gap (this is the real "sources on every card" bug).** In `AnalysisView.svelte`, only
  `other_concerns` cards call `findingSources(name, research_sources)`; **allergen cards (`:514-531`) and
  PFAS cards (`:548-570`) use only `extractSources(inline URL)` and DROP the structured
  `research_sources[]`.** There is **no global "all sources" section**, so safe products (0 findings) and
  any citation whose `finding` doesn't token-match a concern render **zero** sources.
  `ScoreSummaryView` shows none. **Fix:** allergen/PFAS cards call `findingSources`; add a global
  all-sources fallback section (guarantees sources on every card incl. safe products); teaser count on
  the gated view.
- **T2 — `review_insights` served + stored but never typed/rendered** (not in `types/index.ts`, no view).
  Pure client-side add. (Note: with B1 unfixed, the RAG that would enrich reviews is dead anyway — but
  `review_insights` from the Claude summary path does flow.)
- **⚠︎ NEEDS-LIVE:** confirm migration **015 is actually applied in prod** — if not, `store_analysis`'s
  research_sources write hits an unknown column and is swallowed non-fatally (`analyze.py:702-703`), so
  persistence would silently no-op while fresh responses still look fine.

---

## 6. Cost — Stage 1 fits, Stage 2 needs every lever

Rates grounded (Sonnet 4.5 $3/$15 per 1M; Tavily advanced $0.008; Cohere embed $0.12/1M + rerank
$2/1k; CF Workers $5 + `basic` container; Supabase Pro $25). Per-analysis all-in ≈ **$0.282**
($0.271 tracked + ~$0.011 Cohere, which isn't in `token_tracker`). Agent synthesis + per-ingredient
Tavily searches ≈ **75% of cost.**

| | Stage 1 — 100 users (~500 analyses/mo) | Stage 2 — 1000 users (~5000/mo) |
|---|---|---|
| AI all-in | ~$141 | ~$1,410 |
| Fixed (Supabase $25 + CF ~$5–20) | ~$31 | ~$40 |
| **Total** | **≈$172 ✅ under $300** | **≈$1,450 ❌ ~4.8× over** |

- **C1 — Stage 2 blows the cap on AI variable cost alone.** Need effective **≤$0.052/analysis** (from
  $0.282) — a 5.4× cut — via cutting *billable* analyses (cache) and *per-analysis* cost. Levers ranked
  ($/mo saved at Stage 2, estimates): cache-first probe **~$820**, classifiers/canonicalizer **~$100–140**,
  ingredient-research cache **~$101**, variant progressive-analysis **~$50–140** (overlaps cache-first —
  don't sum naively). Optional Sonnet→Haiku on the KB-known path ≈ **$340** but carries quality risk.
- **C2 — LOAD-BEARING ASSUMPTION (Veer decision).** The cost model assumes **5 analyses/user/mo**, but
  the *shipped* model (CLAUDE.md) **auto-runs the full analysis on every product page** and caps only
  *detail-unlocks* at 5. If analyses stay uncapped, cost scales with pages-viewed (≫5) and **even Stage 1
  could breach $300.** This is the biggest single swing on feasibility and needs a product decision: cap
  the analysis, or keep auto-analyze and absorb/optimize the page-view cost. It also interacts with the
  free-tier definition and pricing.
- **⚠︎ NEEDS-LIVE (C0 instrumentation):** the real cache-hit / cross-user overlap rate is currently
  unmeasurable (`search_cache`/`ingredient_research` empty; per-call search/source counts not persisted).
  The 25%/58% hit-rate assumptions drive the Stage-2 number — land KB-plan §C0 instrumentation to measure.

---

## 7. Proposed migration/PR sequence (for Veer's go-ahead — nothing applied yet)

1. **Security hotfix (migration 021)** — port 012: drop `authenticated`-writer policies on
   `product_analyses`/`allergens`/`pfas_compounds`/`users`/`user_searches`/`user_interactions`
   (service_role-only writers, keep public SELECT where intended); `REVOKE EXECUTE` on credit/referral
   SECURITY DEFINER fns; lock down `search_cache`/`extracted_content`/`ingredient_research`. **Gated on
   the ⚠︎ live `pg_policies` check first** — if prod ran 012 out-of-band, scope shrinks. *(S1/S2/S5/M2/M3)*
2. **B1 code fix** — `db.supabase`→`db.client` (×5) + a real route/integration test. Trivial, isolated,
   high-value; TDD (add the unmocked test first — it should fail with `AttributeError`). *(P1-correctness)*
3. **S3 paywall enforcement** — strip gated fields server-side for non-unlocked callers on `/analyze`
   + `/analyze/cached`. *(monetization)*
4. **Perf batch** — `AsyncAnthropic` + `to_thread`; `getRandom` + instance bump + cron throttle; move
   reviews off the critical path (with B1); prompt `cache_control` + drop `count_tokens`; graceful drain
   + `asyncio.wait_for`. *(P1–P5, R1–R2 — the 45s budget)*
5. **Data-model migrations 021b/022/023** — retailer/category split (+ agent emits `product_category`),
   `product_family_hash` + FK-safe dedup, FK ON DELETE fixes, index cleanup. *(D1–D5; also unblocks
   KB-plan §F variant cache + §I exposure class)*
6. **Transparency render** — allergen/PFAS `findingSources` + global all-sources section + teaser count;
   render `review_insights`. *(T1/T2)*
7. **S4 prompt-injection hardening + flip `validate_substances` to enforce** — overlaps KB-plan §E.

**Every one of these must go through the full loop before it lands:** TDD (real test at the mocked seam),
`uv run pytest tests/unit tests/integration -q` + extension `pnpm run check` (5 known errors) +
`pnpm dlx vitest@3 run` + `pnpm run build`, then commit → push → `zsh backend/launch-deploy.sh` → live
probe. **None of that has been done** — these are reviewed proposals awaiting Veer.

---

## 8. What needs a live check (feed the Friday adversarial pass or a read-only prod query)

1. **`pg_policies` in prod** — does prod carry migration 012's fixes (making S1/S2/S5/M3 already-mitigated),
   or the raw 003 policies? Gates the whole security section's severity.
2. **PostgREST reachability + anon/authenticated grants** (esp. EXECUTE on `deduct_credit`,
   `process_referral_conversion`) — gates whether S-series/M2 are remotely exploitable vs. defense-in-depth.
3. **`SELECT count(*) FROM review_chunks`** — expect ≈0, confirming B1 has been dead in prod.
4. **Is migration 015 applied?** — gates whether research_sources actually persists in prod (§5).
5. **S3 end-to-end** — a JWT/API-key caller gets full detail from `/analyze/cached` on a cached product
   with no unlock.
6. **Cache-hit / overlap rate** — the Stage-2 cost swing (needs §C0 instrumentation).
