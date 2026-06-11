# LORE.md — Architecture Decisions & Invariants

> The **why** behind the build. Record non-obvious decisions, invariants, and trade-offs here.
> Format: lightweight ADRs. Newest at top. When you make an architectural decision or change an
> invariant, add/append an entry. See also [`INDEX.md`](./INDEX.md) and [`MEMORY.md`](./MEMORY.md).

---

## Build status (2026-06-03)

12 retailers wired and green: Amazon (reference) + Walmart, Costco, Instacart, Sephora, H&M, Uniqlo,
SHEIN, Aritzia, Garage, IKEA, Temu. Backend **83 tests pass** (`tests/unit` + `tests/integration`,
incl. factory routing across all 12 + Amazon characterization + IKEA hydrate + Instacart content-pattern).
Extension **59 tests pass** (12 adapters + registry + `prepareForCapture`), `npm run build` clean.
Safety-data capture audited per retailer — see [`AUDIT.md`](./AUDIT.md). `svelte-check` shows 5 **pre-existing** errors in
untouched files (`background.ts`, `AnalysisView.svelte`) — zero new (see [`MEMORY.md`](./MEMORY.md)).
Non-Amazon configs are JSON-LD-based (ADR-004); IKEA + Garage validated live, the rest built from
known structure and refined later against logged-in sessions (per user directive).

## Live re-recon results (2026-06-03)

Second pass with chrome-devtools-mcp on real product pages, to validate/refine the unvalidated
configs. Findings (configs refined for the reachable three; statuses below):

| Retailer | Result | Detail |
|----------|--------|--------|
| Uniqlo | ✅ **VALIDATED** | Product pages reachable; JSON-LD Product includes `material` + `description` (like IKEA) → `structured_data` captures composition. Added `fr-ec-template-pdp` container fallback. |
| Sephora | ✅ **VALIDATED** | Reachable; JSON-LD Product (no ingredients). Stable hooks are `data-at` (`ingredients`, `about_the_product_title`) — CSS classes hashed. Ingredients behind an accordion (client DOM captures it if expanded). Config now targets the `data-at` hooks. |
| Aritzia | 🟡 **partial** | Reachable, but **no JSON-LD** on initial DOM and materials/care are lazy accordions. Uses `ch-` class prefix (`.ch-description`). Added `ch-*` selectors; composition is best-effort. |
| H&M | ⛔ blocked | Product deep-nav → Akamai "Access Denied" (homepage loads). Client-HTML path unaffected. |
| Costco | ⛔ blocked | Akamai "Access Denied". |
| Walmart | ⛔ blocked | PerimeterX `/blocked` redirect (confirmed both passes). |
| Instacart | ✅ **validated (JSON-LD)** | Re-reconned 2026-06-03 with a user-provided logged-in session. Product pages reachable; JSON-LD Product confirmed (name/brand/description/category). Nutrition/ingredient text is present in the DOM (collapsed) but uses hashed Emotion classes / a 435KB `#node-apollo-state` blob — not cheaply targetable; relies on JSON-LD + Claude enrichment (see MEMORY.md). |
| Temu | 🔒 login-gated | Homepage + product links load, but product page → `/login.html`. URL pattern `-g-…html` confirmed. |
| SHEIN | ⛔ JS shell | Homepage is a JS shell; product links not exposed to automation; product pages bot-walled. |

Net: 6 validated/partial by live recon — IKEA, Garage (pass 1); Uniqlo, Sephora (pass 2);
Instacart (pass 3, user-provided logged-in session); Aritzia partial. The remaining are blocked/gated
to *automation*: Walmart, H&M, Costco (Akamai/PerimeterX walls), SHEIN (JS shell), Temu (login wall).
**Costco and Temu could not be logged into** (user, 2026-06-03), so they stay best-effort, served by
the client-HTML path at runtime (INV-1) and refined later. All are fully functional at runtime
regardless of recon reachability.

## Invariants (must stay true)

- **INV-1 — Client HTML is the primary data source.** The extension sends the user's authenticated
  DOM (`document.documentElement.outerHTML`) to `/api/analyze`; server-side Playwright is a *fallback*.
  For login-gated sites the backend cannot fetch the page itself, so `process_client_html` selectors
  are the real integration surface, not `scrape()`.
- **INV-2 — Adding a retailer is configuration, not new control flow.** A new site = a `BaseScraper`
  subclass declaring selector config + a `SiteAdapter` in the extension + a manifest entry. No edits
  to `analyze.py`'s branching, the Claude layers, or the scoring.
- **INV-3 — Graceful degradation.** If a scraper/extension adapter is missing or fails, the pipeline
  must still work via the Claude `web_fetch` fallback. A bad selector should degrade confidence, never
  500 the request.
- **INV-4 — Amazon stays green.** Amazon is the reference implementation and the regression canary.
  Any refactor of shared scraper logic must keep Amazon's extraction output identical (characterization
  tests in `backend/tests/unit/test_amazon_scraper.py`).

---

## ADR-003 — Extension uses a SiteAdapter registry (open/closed)

**Status:** Adopted 2026-06-03.
**Context:** `content.ts` hardcoded `isAmazonProductPage()` and imported Amazon-only `extractASIN`/`fetchReviews`. Supporting 12 sites by `if/else` chains would violate OCP and bloat the content script.
**Decision:** Introduce `extension/src/lib/retailers/` with a `SiteAdapter` interface
(`name`, `matches(url)`, `isProductPage(url)`, optional `extractId(url)`, optional `fetchReviews()`).
`content.ts` resolves the active adapter via `getAdapter(url)` and is retailer-agnostic. Amazon becomes
one adapter wrapping the existing `lib/amazon.ts`.
**Consequences:** New site = new adapter file + registry line + manifest entry. Reviews fetching is
opt-in per adapter (many sites have no usable client-session reviews endpoint; those omit `fetchReviews`).

## ADR-002 — Client-HTML path is factory-driven (open/closed)

**Status:** Adopted 2026-06-03.
**Context:** `analyze.py` instantiated `AmazonScraper()` directly for the client-HTML branch,
regardless of URL — so a Walmart page's HTML would be parsed with Amazon selectors.
**Decision:** The client-HTML branch resolves the scraper through `ScraperFactory.get_scraper(url)`
and calls `process_client_html()` on it. If the factory returns `None`, fall back to sending the raw
(lightly trimmed) HTML to Claude. `process_client_html` lives on `BaseScraper`.
**Consequences:** Correct selectors per retailer with zero new branching in the route.

## ADR-001 — Config-driven scraper base (template method)

**Status:** Adopted 2026-06-03.
**Context:** `AmazonScraper` (~620 lines) mixed generic mechanics (Playwright fetch, section text
extraction, exclude-section removal, confidence, client-HTML processing, error results) with
Amazon-specific config (selectors, review data-hooks, retailer-name map). Duplicating all of it per
retailer would be ~600 lines × 11 and a maintenance trap (DRY/SOLID violation).
**Decision:** Lift the generic mechanics into `BaseScraper` as concrete methods using the **template
method** pattern. Subclasses declare class attributes only:
`DOMAIN_PATTERNS`, `RETAILER_NAME`, `PRODUCT_SECTION_SELECTORS`, `REVIEWS_SECTION_SELECTORS`,
`EXCLUDE_SELECTORS`. `can_scrape`, `scrape`, `process_client_html`, `_extract_sections`,
`_fetch_with_playwright`, `_calculate_confidence`, `_create_error_result`, `_extract_retailer` are
inherited. A retailer overrides a method **only** when its DOM needs it (e.g. Amazon overrides
`_extract_reviews_structured` and `_extract_product_attributes`; the base provides a generic selector-dump
review extractor).
**Consequences:** A typical retailer scraper is ~30–60 lines of config. Amazon keeps its overrides.
Guarded by characterization tests (INV-4) following TDD red→green→refactor.

---

## ADR-005 — Interaction-gated content: prefer SSR hydration blobs over click-automation

**Status:** Adopted 2026-06-03 (after a real-data review caught a gap).
**Context:** A pointed review of the IKEA capture showed the *safety-critical* data was missing:
per-part materials ("Inner side panel: Particleboard", "Main parts: Solid pine, Adhesive, Stain,
Clear acrylic lacquer"), care, safety & compliance, certifications, Q&A, reviews. JSON-LD only
carries marketing-level `material:"Solid wood"` — useless for detecting adhesives/lacquers/
particleboard (formaldehyde/VOC sources). Investigation: that data is **not in the visible initial
DOM** — it renders into an on-demand `.pipf-product-details-modal` and tab-navigated sub-panels.
My first "validated" was based on a capture taken before/without that content — wrong.
**Options weighed:** (a) extension drives modal/accordion clicks before capture — fragile, per-site,
hard to test; (b) read a structured data source. IKEA embeds the full structured product data in
`<script type="text/hydrate">` SSR (preact) blobs that are present **statically at first load, no
interaction**. `outerHTML` (and thus the extension capture) already includes them.
**Decision:** Prefer SSR state blobs over click-automation. `IkeaScraper` overrides `_extract_sections`
to parse the hydrate blobs into compact, labeled `materials_breakdown` / `care` /
`safety_and_compliance` / `certifications` sections (~1KB), plus adds `.pipf-questions-and-answers`
and `.pipf-seo-reviews` selectors. **Never dump the whole blob** (~226KB) — extract only the relevant
fields (cf. the Instacart Apollo lesson). Verified on the live page: all 7 sections captured in 27.4KB.
**General rule:** before assuming content needs an extension click, look for a serialized state blob —
`<script type="text/hydrate">` (preact/IKEA), `__NEXT_DATA__` (Next.js), `__NUXT__` (Vue), or an Apollo
cache. It's static, complete, and stable — strictly better than DOM scraping. A bespoke
`_extract_sections`/override is the sanctioned exception to ADR-001's config-only rule when a site's
real data lives in such a blob. **But verify the blob actually holds the data** — grep it for the
content strings, not field-name guesses (Instacart's Apollo blob looked promising but held none of the
nutrition/ingredient text; MEMORY.md).

**Archetype-D fallback (lazy + hashed classes + NO blob)** — e.g. Instacart nutrition/ingredients:
(1) extension `SiteAdapter.prepareForCapture()` scrolls/expands so the content renders into the DOM
before capture; (2) the scraper extracts by **content pattern** (a keyword-cluster for nutrition facts;
an explicit `Ingredients:` label for ingredients) rather than by selector. Never guess ingredients from
food words — it catches recommended-product titles. This is the hardest archetype and is best-effort.

## ADR-004 — JSON-LD is the universal data backbone for new retailers

**Status:** Adopted 2026-06-03.
**Context:** Recon (chrome-devtools-mcp) of IKEA + Garage confirmed both embed
`<script type="application/ld+json">` Product schema (name, brand, description, sku,
aggregateRating, sometimes material/color). This holds across modern SPA retailers and is
far more stable than per-site CSS class names (which are hashed/churned).
`BeautifulSoup.get_text()` returns a `<script>` tag's text, so a single selector
`script[type='application/ld+json']` feeds the raw JSON to Claude, which parses it.
**Decision:** Every new retailer config includes a `structured_data` section selector for
JSON-LD, plus `h1` for title, plus a small set of **visible** site-specific selectors for the
data JSON-LD usually omits (ingredients for beauty, fabric composition for apparel, care/details).
**Do NOT use `meta[...]` selectors** — their data is in `content=` attributes, which text
extraction returns empty for.
**Consequences:** Configs are resilient and uniform (~30-50 lines). Unvalidated sites still get a
working baseline from JSON-LD; visible selectors are refined later against real sessions.

## Recon: bot-blocking sites & the client-HTML escape hatch

Walmart redirected automated deep-navigation to `/blocked` (PerimeterX/HUMAN) even though the
homepage loaded. Temu/Shein/Costco/Instacart similarly resist automation or require login. This
does **not** break the product: per INV-1 the extension ships the *real user's* organically-loaded,
logged-in DOM, which these defenses don't touch. So recon-time blocking only limits our ability to
*validate* selectors now, not the runtime path. Blocked/gated sites get JSON-LD-based configs flagged
**unvalidated** below and are refined later (user directive 2026-06-03: "make do with what's
available now, come back to the gated ones to expand").

---

## Per-retailer challenge notes / specs

Universal recipe (all sites): `PRODUCT_SECTION_SELECTORS` starts with
`{"name":"structured_data","selector":"script[type='application/ld+json']"}` and `{"name":"title","selector":"h1"}`,
then site-specific visible selectors below. `EXCLUDE_SELECTORS` drop header/footer/nav/recommendations.
Extension adapters need only `matches`+`isProductPage` (no `fetchReviews` — only Amazon has a session
reviews endpoint). Reviews come through JSON-LD `review`/`aggregateRating` where present.

| Retailer | Domain regex | Product URL pattern | Recon | JSON-LD | Site-specific visible selectors (ingredients/materials/details) | Notes |
|----------|--------------|---------------------|-------|---------|-----------------------------------------------------------------|-------|
| Walmart | `walmart\.com` | path `/ip/` | blocked (deep-nav) | yes | `[data-testid*='product-description']`, `#product-overview`, `.dangerous-html` | bot-walled; unvalidated |
| Costco | `costco\.com` | path `.product.` or `/p/` | gated/partial | likely | `#product-details-tabs`, `.product-info-description`, `[class*='spec']` | unvalidated |
| Instacart | `instacart\.com` | path `/products/` | login-gated | partial | `[data-testid*='item-details']`, `[class*='ingredient' i]`, `[class*='nutrition' i]` | unvalidated; grocery → ingredients/nutrition |
| Sephora | `sephora\.com` | path `/product/` (id `-P\d+`) | bot-walled | yes | `[class*='Ingredient' i]`, `#ingredients`, `[data-comp*='Ingredients']` | beauty → ingredients critical; unvalidated |
| H&M | `(www2\.)?hm\.com` | path `/productpage.\d+.html` | bot-walled | yes | `[class*='materials' i]`, `[class*='composition' i]`, `#section-descriptionAccordion` | apparel composition; unvalidated |
| Uniqlo | `uniqlo\.com` | path `/products/E?\d+` | partial | yes | `[class*='material' i]`, `[class*='composition' i]`, `.product-description` | apparel; unvalidated |
| Shein | `shein\.com` | path `-p-\d+\.html` | bot-walled | partial | `[class*='material' i]`, `.product-intro__description`, `[class*='detail' i]` | heavy bot-wall; unvalidated |
| Aritzia | `aritzia\.com` | path `/product/` | bot-walled | yes | `[class*='materials' i]`, `[class*='fabric' i]`, `[data-testid*='detail']` | apparel; unvalidated |
| Garage | `garageclothing\.com` | path `/p/.+\.html` | **VALIDATED** | yes (name/brand/desc/sku/rating) | `.product-detail`, `[class*='productdetails' i]` (fabric in accordion) | Shopify-ish; details in accordion |
| IKEA | `ikea\.com` | path `/p/` | **VALIDATED** | yes (**incl. material/color**) | `.pipf-product-details-modal`, `[class*='product-details' i]` | furniture; JSON-LD richest |
| Temu | `temu\.com` | path `-g-\d+\.html` | bot-walled | partial | `[class*='goods-desc' i]`, `[class*='material' i]`, `[class*='detail' i]` | heavy bot-wall; unvalidated |
