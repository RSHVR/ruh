# AUDIT.md — Safety-Data Capture Audit (all retailers)

**Date:** 2026-06-03 · **Method:** live recon via chrome-devtools-mcp on real product pages.
**Companion docs:** [`INDEX.md`](./INDEX.md) · [`LORE.md`](./LORE.md) (ADR-004/005) · [`MEMORY.md`](./MEMORY.md)

---

## Why this audit exists

A retailer being "wired with tests passing" or "JSON-LD parses" does **not** mean we capture the data
needed for a safety analysis. The IKEA review proved it: JSON-LD said `material: "Solid wood"`
(marketing copy), while the real safety signal — adhesives, stain, clear acrylic lacquer,
particleboard, fiberboard, acrylic paint — lived elsewhere and was being missed entirely.

So **"captured" here means: the safety-critical field is actually present in the scraper's
extraction output** — ingredients for beauty/grocery, fabric composition for apparel, per-part
materials for furniture/goods. Not "the page loaded." Not "JSON-LD parsed."

## What the audit checks (per retailer)

1. **Reachable?** Can a product page be loaded at all (bot walls / login gates)?
2. **JSON-LD** — present, and does it carry the *safety* field (not just name/price)?
3. **State blob** — is the data in a serialized SSR/client-state script? (`<script type="text/hydrate">`,
   `#node-apollo-state`, `__NEXT_DATA__`, `__NUXT__`, other big `application/json`). These are static,
   complete, and stable — the preferred source (LORE.md ADR-005).
4. **Visible/static DOM** — is the safety content in the captured `outerHTML`, or interaction-gated
   (accordion/modal/lazy load) so a plain capture misses it?
5. **Verdict** — does the *current scraper config actually extract* the safety data? (verified by
   running the real scraper on the live-captured DOM).

---

## Summary

| Retailer | Reachable | Where the safety data lives | Captured by scraper? | Verdict |
|----------|-----------|------------------------------|----------------------|---------|
| **IKEA** | ✅ | `text/hydrate` SSR blob (per-part materials, care, safety, certs) | ✅ after fix | ✅ **Fixed & verified** |
| **Sephora** | ✅ | static DOM (full INCI list under `data-at="ingredients"`) | ✅ | ✅ **Pass** |
| **Garage** | ✅ | JSON-LD `description` ("85% cotton, 15% recycled cotton" + care) | ✅ | ✅ **Pass** |
| **Uniqlo** | ✅ | JSON-LD `material` ("100% Cotton") | ✅ | ✅ **Pass** |
| **Instacart** | ✅ (logged in) | lazy-rendered hashed-class DOM (NOT the Apollo blob) | ✅ nutrition (fixed); ⚠️ ingredients best-effort | ✅ **Improved & verified** |
| **Aritzia** | ⚠️ intermittent (Cloudflare) | no JSON-LD, no blob, lazy accordion | ❓ unverified (best-effort) | ⚠️ **At risk — needs work** |
| **Walmart** | ⛔ PerimeterX | unknown (likely JSON-LD) | ❓ unverified | ⛔ **Unverified** |
| **H&M** | ⛔ Akamai | unknown (likely JSON-LD + accordion) | ❓ unverified | ⛔ **Unverified** |
| **Costco** | ⛔ Akamai | unknown | ❓ unverified | ⛔ **Unverified** |
| **SHEIN** | ⛔ JS shell | unknown | ❓ unverified | ⛔ **Unverified** |
| **Temu** | 🔒 login wall | unknown | ❓ unverified | 🔒 **Unverified** |

**Bottom line:** 4 verified-good (IKEA fixed; Sephora/Garage/Uniqlo already correct), 1 partial with a
clear fix (Instacart), 1 at-risk (Aritzia), 5 unverifiable without an unblocked/logged-in session.

---

## Per-retailer detail

### ✅ IKEA — fixed
- JSON-LD carries only marketing `material: "Solid wood"`. The real per-part breakdown
  ("Inner side panel: Particleboard", "Main parts: Solid pine, Adhesive, Stain, Clear acrylic lacquer",
  "Drawer bottom: Fiberboard, Acrylic paint"), care, safety & compliance, certifications, "good to know"
  live in **`<script type="text/hydrate">` SSR blobs** — present statically at first load (no clicks).
- **Fix applied:** `IkeaScraper._extract_sections` override parses those blobs into compact labeled
  sections (~1 KB), plus added `.pipf-questions-and-answers` / `.pipf-seo-reviews` selectors.
- **Verified live:** all sections captured in 27.4 KB; reproduces the exact materials breakdown.
- Tests: 8 IKEA unit tests (incl. 3 new hydrate tests).

### ✅ Sephora — pass (no change)
- JSON-LD Product: name/brand/description/rating, **no ingredients**. No state blob.
- The **full INCI list is in the static DOM** under `data-at="ingredients"` (CSS classes are hashed, but
  the `data-at` hook is stable; my config already targets `[data-at*='ingredient' i]`).
- **Verified live:** scraper extracted the full INCI list (Dimethicone, Phenyl Trimethicone, …,
  Fragrance/Parfum, …) — 11.6 KB. Ingredients = the key allergen/PFAS signal — captured. ✅

### ✅ Garage — pass (no change)
- JSON-LD Product. The **fabric composition + care is embedded in the JSON-LD `description`**
  ("Materials & Care Content: 85% cotton, 15% recycled cotton. Care: Wash cold, inside out").
- **Verified live:** `structured_data` captures it (3.9 KB). ✅

### ✅ Uniqlo — pass (no change)
- JSON-LD `material` is a **real composition** ("100% Cotton") + `description`. `structured_data`
  captures it. ✅ (Richest JSON-LD of the apparel set.)

### ✅ Instacart — improved & verified (fix applied)
- Logged-in session reachable. JSON-LD Product gives name/brand/**description**/category — captured.
- **Correction to the first pass:** the Apollo blob (`#node-apollo-state`, ~435 KB) does **NOT** hold
  the rendered nutrition/ingredient text — only the *word* "ingredient" appears; no script tag contains
  "Total Fat"/"Cultured". The data is **lazily rendered on scroll** into DOM elements with hashed
  Emotion classes (`e-1qm1lh`) — archetype-D, no usable state blob.
- **Fix applied (two-sided):**
  - *Extension* — `instacartAdapter.prepareForCapture()` scrolls the page (then restores position) so
    the lazy sections render into the DOM before `content.ts` snapshots it. Generic hook added to
    `SiteAdapter` (helps any lazy site).
  - *Backend* — `InstacartScraper._extract_sections` override locates the **Nutrition Facts** panel by a
    content keyword-cluster (Total Fat/Sodium/Carbohydrate/Protein/…) and the **ingredient list** by an
    explicit `Ingredients:` label — both robust to hashed classes. Compact output (~1 KB).
- **Verified live:** full nutrition panel captured (Total Fat 7g, Saturated 4g, Cholesterol 25mg,
  Sodium 110mg, Total Carbohydrate 25g, Dietary Fiber, …) on the real product page.
- **Honest limitation:** ingredient lists are often not exposed in a clean labeled block even after
  scroll (retailer-dependent within Instacart); ingredient capture is therefore best-effort. We do NOT
  guess ingredients from food words (that catches recommended-product titles). Nutrition is reliable.

### ⚠️ Aritzia — at risk
- Now serving an **intermittent Cloudflare "Just a moment…" challenge** that blocks automation
  (it loaded on an earlier pass, not on this one).
- When reachable: **no JSON-LD Product, no state blob (`__NEXT_DATA__`/`__NUXT__` absent)**, and the
  fabric composition loads **lazily behind accordions** (`ch-` prefixed, hashed). So a plain capture
  likely misses composition — the current config is best-effort and **unverified**.
- **Recommended fix:** capture needs the extension to expand the materials accordion before snapshotting
  (a `prepareForCapture` interaction), OR find Aritzia's product API/JSON. Requires a reliably reachable
  session. Until then: relies on Claude enrichment from name/brand (INV-3).

### ⛔ Walmart / H&M / Costco / SHEIN — unverifiable now
- Walmart → PerimeterX `/blocked`; H&M & Costco → Akamai "Access Denied"; SHEIN → JS shell with no
  exposed product content to automation. Could not load a product page, so **safety-data capture is
  unverified**. These work at runtime via the user's real session (INV-1), but we have not confirmed the
  configured selectors capture the safety field. Each likely has JSON-LD Product; H&M/Walmart likely keep
  composition/specs in accordions or state blobs that need the same audit once a real session is available.

### 🔒 Temu — unverifiable now
- Product pages redirect to `/login`. URL pattern confirmed; safety-data capture **unverified**.

---

## Cross-cutting findings

1. **Four data-source archetypes** emerged — design configs around which one a site uses:
   - **A. JSON-LD carries it** → Uniqlo (`material`), Garage (in `description`). Cheapest; `structured_data` suffices.
   - **B. Static DOM carries it** → Sephora (INCI under stable `data-at`). Target the stable hook.
   - **C. Only a state blob carries it** → IKEA (`text/hydrate`), Instacart (`#node-apollo-state`). Needs a
     targeted parse override; never dump the whole blob.
   - **D. Interaction-gated, no blob** → Aritzia (lazy accordion). Hardest; needs extension-side expansion.
2. **JSON-LD presence ≠ safety data present.** Always verify the actual field (IKEA's "Solid wood" trap).
3. **"Validated" must mean the safety field is in the extraction output**, proven by running the real
   scraper on a live capture — not "the page loaded" or "JSON-LD parsed."
4. **Bot walls block our *audit*, not the product.** Runtime uses the user's real session (INV-1); but it
   also means we can't confirm those configs until we have a reachable/logged-in session.

## Recommended next actions (priority order)

1. **Instacart** — implement the `#node-apollo-state` targeted parse override (grocery = allergens; high
   value; approach is proven by the IKEA fix). Needs a live logged-in session to map the JSON path.
2. **Aritzia** — add a `prepareForCapture`/accordion-expansion step (or find the product API); re-audit
   when Cloudflare lets the automated browser through.
3. **Re-audit the bot-walled five** (Walmart, H&M, Costco, SHEIN, Temu) once a real/logged-in session can
   capture a product DOM — apply this same checklist and confirm the safety field is extracted.
4. Consider a **generic state-blob harvester** in `BaseScraper` (selective extraction of `__NEXT_DATA__`/
   apollo/`text/hydrate`) so archetype-C sites need less bespoke code.

## What changed in this audit

- **IKEA**: `_extract_sections` hydrate override + Q&A/reviews selectors (`backend/.../scrapers/ikea.py`)
  + 3 new unit tests. Backend suite: **80 passed**.
- **Sephora/Garage/Uniqlo**: confirmed correct as-is (no change).
- Docs: `LORE.md` ADR-005, `MEMORY.md` entries, this `AUDIT.md`.
