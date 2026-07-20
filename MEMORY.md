# MEMORY.md — Mistakes & Solutions Log

> A running log of concrete mistakes we hit and how we fixed them, so we (and future agents)
> don't repeat them. **Append** new entries at the top. One entry per mistake.
> Keep it specific and actionable — symptom, root cause, fix, prevention.
>
> Template:
> ```
> ## YYYY-MM-DD — <short title>
> **Symptom:** what went wrong (error/behavior).
> **Root cause:** the actual reason.
> **Fix:** what resolved it.
> **Prevention:** the rule/test that stops a repeat.
> ```

---

## 2026-06-03 — Client-HTML branch parsed every site with Amazon selectors

**Symptom:** Non-Amazon product HTML would be processed by `AmazonScraper.process_client_html`,
yielding empty/garbage extractions (Amazon selectors don't match other DOMs).
**Root cause:** `backend/src/api/routes/analyze.py` hardcoded `AmazonScraper()` for the client-HTML
branch instead of selecting by URL.
**Fix:** Route the client-HTML branch through `ScraperFactory.get_scraper(url)` (ADR-002).
**Prevention:** Integration test asserting a Walmart URL + HTML selects `WalmartScraper`, not Amazon.

---

## 2026-06-03 — `meta[...]` selectors extract nothing

**Symptom:** A retailer config using `meta[property='og:title']` / `meta[name='description']`
produced empty sections.
**Root cause:** `meta` tags carry their data in the `content=` attribute, but the scraper extracts
via `BeautifulSoup.get_text()`, which returns text *content* — empty for void/attribute-only tags.
**Fix:** Never use `meta[...]` selectors. Use JSON-LD (`script[type='application/ld+json']` — its
text IS the JSON, which `get_text()` returns) + visible elements (`h1`, description containers).
**Prevention:** ADR-004 codifies the JSON-LD backbone; CLAUDE.md/LORE forbid `meta[...]`.

## 2026-06-03 — Pre-existing `svelte-check` errors are NOT from retailer work

**Symptom:** `npm run check` reports 5 errors after adding retailers.
**Root cause:** They live in `extension/src/background/background.ts` (`chrome.runtime.getContexts`
missing on the pinned `@types/chrome` 0.0.254) and `extension/src/components/AnalysisView.svelte`
(`analysis` possibly null) — both untouched by the retailer work and present before it.
**Fix:** None required for this feature. (Future: bump `@types/chrome`; add a null guard in
AnalysisView.) The retailer adapters + content-script refactor add **zero** new type errors.
**Prevention:** Run `npm run check` on a clean baseline before attributing errors to new work.

## 2026-06-03 — Instacart: data is lazy-rendered DOM, NOT the Apollo blob (corrected)

**Symptom:** On a logged-in Instacart product page, the `ingredients`/`nutrition` CSS selectors
extract little, even though the page shows nutrition facts.
**First (wrong) conclusion:** I assumed the data lived in the `<script id="node-apollo-state">` Apollo
cache (~435 KB) and recommended a targeted blob parse. **That was wrong.** On closer inspection the
Apollo blob contains only the *word* "ingredient" — NO script tag contains "Total Fat"/"Cultured".
**Actual root cause:** the nutrition/ingredient content is **lazily rendered on scroll** into DOM
elements with hashed Emotion classes (`e-1qm1lh`) — no stable hook AND no usable state blob
(archetype-D, LORE.md ADR-005). It isn't even in the DOM until the page is scrolled.
**Fix (applied):** (1) extension `instacartAdapter.prepareForCapture()` scrolls before capture so the
content renders; (2) `InstacartScraper` extracts nutrition by a **content keyword-cluster** and
ingredients by an explicit **`Ingredients:` label** — robust to hashed classes. Verified live; tested.
**Prevention:** Don't assume a state blob holds the data just because one exists — grep the blob for the
actual *content strings* (e.g. "Total Fat"), not field-name guesses. For archetype-D (lazy + hashed +
no blob): scroll in the extension + extract by content pattern. NEVER guess ingredients from food words
(it matches recommended-product titles) — gate on an explicit label.

## 2026-06-03 — "Validated" on JSON-LD ≠ usable safety data (IKEA materials were missing)

**Symptom:** IKEA capture looked fine (JSON-LD parsed: name/brand/`material:"Solid wood"`/rating),
but it had NONE of the data needed for actual safety analysis: the per-part materials breakdown
(Particleboard, adhesives, Clear acrylic lacquer, Fiberboard, Acrylic paint), care, safety &
compliance, certifications, Q&A, or reviews. "Solid wood" is marketing copy, not a composition.
**Root cause (two layers):** (1) I declared IKEA "validated" after confirming JSON-LD *parsed* —
without checking the safety-critical sections were present. (2) Those sections aren't in the visible
initial DOM; they render into an on-demand modal. My recon capture was taken before that content
existed, so I never saw the gap.
**Fix:** The full structured data is in `<script type="text/hydrate">` SSR blobs (static, no
interaction). Added an `IkeaScraper._extract_sections` override that parses them into compact
`materials_breakdown`/`care`/`safety_and_compliance`/`certifications` sections + `.pipf-questions-and-answers`/`.pipf-seo-reviews` selectors. Verified on the live page: all sections captured, 27.4KB.
**Prevention:** "Validated" must mean *the safety-relevant fields are present in the extraction*, not
"JSON-LD parsed." For any SPA, check for a serialized state blob (`text/hydrate`, `#node-apollo-state`,
`__NEXT_DATA__`, `__NUXT__`) before assuming the visible DOM is enough or that clicks are required
(LORE.md ADR-005). Re-audit the other apparel/beauty sites (Sephora ingredients, Aritzia) the same way.

_(append future entries above this line)_

## 2026-07-20 — Cherry-pick 50611bb shipped a green-tests-but-broken prod path

Commit 50611bb cherry-picked `analyze.py` from harness-eval but missed TWO files it
depends on: `src/infrastructure/section_parser.py` (module missing → boot ImportError)
and the updated `src/domain/ingredient_matcher.py` (new `toxic_database` kwarg →
runtime TypeError → 500 on EVERY analyze request). The 143-test unit suite was fully
green the whole time — unit tests import modules in isolation and never exercised the
route's real call into the matcher.

**Fix:** copied both files (+ matcher unit tests) from harness-eval.
**Lesson:** after any cross-branch cherry-pick of route/orchestration code, run a true
E2E smoke (`backend/verify-live.sh` against localhost) before calling it done. Green
unit tests do not prove the request path works.
