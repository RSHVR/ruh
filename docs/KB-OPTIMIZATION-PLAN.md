# KB & Research Optimization Plan

> **Status:** proposal / analysis. Nothing here is implemented, with one update:
> since this analysis ran, `research_sources` now persists (8–16 sources/analysis
> as of 2026-08-01 afternoon) — §C0's first bullet is done; the `ingredient_research`
> / `search_cache` halves remain open.
> **Author:** data-analysis pass over production Supabase (read-only), 2026-08-01.
> **Goal (Veer's words):** "be more consistent given similar products, reduce random
> searching, increase the canonical sources we check" + "don't rescan the whole product
> if the user changed the variant like color or multi-packs."
> **Companion docs:** [`LORE.md`](../LORE.md) (ADRs/invariants), [`INDEX.md`](../INDEX.md) (file map),
> [`CLAUDE.md`](../CLAUDE.md) (standards). Corpus: 81 `product_analyses`, 142 `validation_logs`,
> KBs of 32 allergens / 75 PFAS / 50 toxic substances.
>
> **── 2026-08-01 evening expansion (Veer) ──** Beyond the original KB/consistency/variant
> analysis (§0–§H), this doc now carries **four compatibility corrections** folded into §B/§C2/§E/§F,
> and **five new roadmap sections**: **§I** exposure-aware risk, **§J** industrial-depth allergens,
> **§K** geographic provenance → environmental-contamination cross-ref (R&D), **§L** custom
> classifiers in Cloudflare containers (≤45s constraint), **§M** scaling & cost (100/1000 users,
> <$300/mo). Figures tagged `[FLEET-PENDING]` are being backfilled by a concurrent read-only audit
> fleet (perf, data-model, transparency, security, cost). See the **re-scoring side-effect** note at
> the end — a deliberate UX consequence of §E + §I landing.

---

## 0. TL;DR — the five numbers that drive this plan

| # | Finding | Number | Where it hurts |
|---|---------|--------|----------------|
| 1 | Claude's substance flags that **fail KB name/synonym match** | **28% of allergen flags, 62% of PFAS flags** (27/97, 5/8) | Consistency + KB gap. Every miss is a substance the KB can't reason about deterministically. |
| 2 | **Same ingredient, different verdict** across products | phenoxyethanol flagged in 13 / present-but-unflagged in 8; ethylhexylglycerin 5 vs 15; disodium EDTA 3 vs 16 | Consistency. The verdict is a per-run LLM judgment, not a KB lookup. |
| 3 | **Search/research evidence is not persisted at all** | `research_sources` 0/81, `review_insights` 0/81, `ingredient_research` 0 rows, `search_cache` 0 rows | We literally cannot see "random searching." Only proxy: 6 API calls median, up to 9; $0.271 mean/analysis. |
| 4 | **Duplicate rows for the exact same product** | 81 rows → 70 distinct normalized URLs = **11 redundant rows (14%)**; 9 products stored 2–3× | Wasted re-analysis + inconsistent stored verdicts for one product. |
| 5 | **`category` column carries no category** — it stores the retailer, itself unnormalized | values are "Amazon Canada"/"Amazon.ca"/"Amazon", "H&M"/"H&M Canada (hm.com/en_ca)" | Consistency-by-category is unmeasurable from stored data today. |

**Root cause tying 1, 2 and 5 together:** matching and verdict assignment happen on **raw Claude
strings** with no canonicalization. `analyze.py::validate_substances` does a case-insensitive
exact match of `name` against KB name/synonym sets — no INCI resolution, no CI-code handling, no
"Fragrance/Parfum" folding. So the same molecule enters as "Coconut", "Cocos Nucifera", "Coconut Oil
(Cocos Nucifera Oil)" and is scored three different ways.

---

## 1. Quick wins this week (high impact / low effort)

1. **Ship the ingredient normalization layer (§B).** One module, pure functions, unit-testable.
   Directly attacks findings #1, #2, #5. **[S–M]**
2. **Expand KB synonyms from the validation-log evidence (§A).** These are not guesses — they are
   the exact strings Claude already emitted that missed the KB. **[S]**
3. **Persist what we already compute (§C0): instrumentation fix.** `research_sources` and
   `review_insights` are produced by the agent and dropped on the floor; `ingredient_research` and
   `search_cache` are never written. Until these persist, "reduce random searching" is unfalsifiable.
   **[S]**
4. **Backfill-safe dedup: add `product_family_hash` + fix the same-product duplicates (§F).**
   11 redundant rows exist that current normalization already *should* have collapsed. **[S]**
5. **Deterministic verdict table for the top ~30 repeat ingredients (§E).** Freeze
   severity/inclusion for phenoxyethanol, ethylhexylglycerin, disodium EDTA, etc. so identical
   inputs stop producing different outputs. **[M]**

Everything below is the detail and the longer tail.

---

## A. KB expansion — exact substances & synonyms to add

Evidence = `validation_logs` (Claude flagged it, no KB match) + high-frequency `other_concerns`
base-names absent from all three KBs. Frequencies are from the 81-analysis corpus.

### A1. Allergens — add as **synonyms to existing rows** (INCI / botanical names). **[S]**
These all resolve to allergens we already have; they miss only because the KB lacks the INCI name.

| Existing allergen | Add synonyms (seen in logs) | Evidence |
|---|---|---|
| Coconut | `Cocos Nucifera`, `Cocos Nucifera Oil`, `Coconut Oil` | flagged invalid 2×; +2 products |
| Soy | `Glycine Soja`, `Glycine Soja Sterols`, `Soybean`, `Hydrolyzed Soy Protein` | invalid 3× across products |
| Sesame | `Sesamum Indicum`, `Sesame Seed Oil` | invalid 1× |
| Wheat | `Hydrolyzed Wheat Protein`, `Hydroxypropyltrimonium Hydrolyzed Wheat Protein` | invalid 1× |
| Tree Nuts | ensure combined strings like `Tree Nuts (Macadamia)` resolve via §B, not a new synonym | invalid 1× |

### A2. Allergens — **new rows** (true gaps, botanical actives). **[S]**
| New allergen | INCI / synonyms | Evidence |
|---|---|---|
| Shea Butter | `Butyrospermum Parkii`, `Butyrospermum Parkii Butter` | invalid 1× |
| Chamomile | `Chamomilla Recutita`, `Matricaria`, `Chamomilla Recutita (Matricaria) Flower Extract` | invalid 1× |

### A3. Fragrance allergens — the biggest single allergen gap. **[S–M]**
Claude repeatedly emits **standalone EU-26 fragrance allergens** and a bare **"Fragrance"/"Parfum"**,
all of which miss because the KB only stores them *inside* the `Fragrance Mix I/II` synonym arrays.

- Add a dedicated allergen row **"Fragrance/Parfum"** with synonyms
  `Fragrance`, `Parfum`, `Fragrance (Parfum)`, `Fragrance/Parfum`, `Parfum/Fragrance`.
  (Seen invalid/other-concern **10+ times** — the single most frequent miss.)
- Promote the EU-26 allergens to **first-class synonyms** so they match when reported alone:
  `Linalool`, `Limonene`, `Citronellol`, `Geraniol`, `Coumarin`, `Benzyl Salicylate`,
  `Benzyl Alcohol`, `Hydroxycitronellal`, `Eugenol`, `Isoeugenol`, `Cinnamal`. (Linalool, Limonene,
  Citronellol, Geraniol each appear 2–3× flagged and 5–6× present-unflagged — see §E.)
- Handle the `(oxidized)` suffix ("Linalool (oxidized)", "Limonene (oxidized)") in §B, not as
  separate synonyms.

### A4. PFAS — **new rows** (true gaps). **[S]**
| New PFAS | Synonyms | Evidence |
|---|---|---|
| PFA (Perfluoroalkoxy alkane) | `PFA`, `Perfluoroalkoxy` | invalid 1× (footwear/apparel coatings) |
| FEP (Fluorinated ethylene propylene) | `FEP` | invalid 1× |

`PTFE` and `Fluoropolymer` already exist; they miss only as combined strings
(`Polytetrafluoroethylene (PTFE)`) → fixed by §B, no KB change needed.

### A5. Toxic substances — **new rows** (frequent `other_concerns`, in no KB). **[M]**
Ranked by frequency / #products. These are the substances the agent keeps describing free-hand
in `other_concerns` because there is no KB entry to anchor a consistent severity.

| Add to `toxic_substances` | freq | #prod | category |
|---|---|---|---|
| Cyclopentasiloxane (D5) *(+ Cyclotetrasiloxane D4)* | 5 | 4 | silicone / bioaccumulative |
| Ethylhexylglycerin | 5 | 5 | preservative-booster / irritant |
| Azo Dyes *(+ Disperse Dyes)* | 5+2 | 5+2 | textile dye / sensitizer |
| Triethanolamine (TEA) | 3 | 2 | amine / nitrosamine precursor |
| Disodium EDTA *(+ Tetrasodium EDTA)* | 3 | 3 | chelator / penetration enhancer |
| Chemical UV filters: Homosalate, Octocrylene, Octisalate, Avobenzone *(+ Oxybenzone)* | 2 each | 2 each | endocrine-active sunscreen actives |
| PEG compounds (PEG-100 Stearate, PEG-20…) | 3 | 2 | 1,4-dioxane / ethylene-oxide contamination route |
| 1,4-Dioxane | 2 | 2 | carcinogen (contaminant) |
| Polysorbate 20 / 80 | 2 | 2 | ethoxylated / dioxane route |
| Permethrin | 3 | 1 | pesticide (treated textiles) |
| Potassium Sorbate, Sodium Benzoate | 3/2 | 3/2 | preservative |
| Acetone | 2 | 2 | VOC solvent |

> Note: `Phthalates`, `PFOA`, `Parabens`, `Benzyl/Phenoxyethanol` also surface in `other_concerns`
> but **already exist** in a KB — they show up only as un-normalized strings
> ("PFOA (Perfluorooctanoic acid)", "Parabens (Methylparaben, …)"). Those are a §B problem, not a
> KB gap. Do **not** duplicate them.

---

## B. Ingredient normalization layer (spec)

**Problem quantified:** 28% of allergen flags and 62% of PFAS flags miss the KB purely on string
form; the corpus contains both `aqua`(2)/`water`(10), `parfum`(3)/`fragrance`(4),
`tocopherol`(11)/`vitamin e`(1) as distinct tokens, and 5 raw CI colour-index codes
(`CI 60730`, `CI 14700`, `CI 15985`, `CI 77491`, …) that never resolve. New module:
`backend/src/domain/ingredient_normalizer.py`. Pure, deterministic, unit-tested (TDD, per
CLAUDE.md). Applied **before** KB matching in `analyze.py::validate_substances` *and* before
`ingredient_matcher.match_ingredients_to_databases`.

**`canonicalize(name: str) -> CanonSet`** pipeline:
1. **Casefold + Unicode NFKC + whitespace/punct collapse.** Strip trailing marketing
   ("- High concentration skin irritation", "(oxidized)", "may be soy-derived").
2. **Split combined strings:** `"Polytetrafluoroethylene (PTFE)"` → {`polytetrafluoroethylene`,
   `ptfe`}; `"Tree Nuts (Macadamia)"` → {`tree nuts`, `macadamia`}. Emit **all** surface forms;
   match if **any** hits the KB.
3. **INCI ↔ common map** (static dict, seeded from A1/A3 + a starter INCI table):
   `aqua→water`, `parfum→fragrance`, `tocopherol→vitamin e`, `cocos nucifera→coconut`,
   `glycine soja→soy`, `sesamum indicum→sesame`, `butyrospermum parkii→shea butter`,
   `chamomilla recutita/matricaria→chamomile`, `alcohol denat.→denatured alcohol`, …
4. **CI colour-index normalization:** regex `ci\s?\d{4,5}` → canonical `CI #####`, and map the
   named forms (`CI 19140 → Tartrazine/Yellow 5`, `CI 76060 → p-Phenylenediamine`) into existing
   allergen synonyms.
5. **CAS passthrough:** if a `\d{2,7}-\d{2}-\d` CAS is present, match on CAS first (already done for
   PFAS — extend to toxic + allergen).
6. **Our own composition-splitter output form (Veer fix, 2026-08-01):** `normalize_composition`
   (ADR-007, `domain/composition.py`) emits per-fibre entries like `"Viscose 75% (Shell)"` /
   `"Elastane 5% (Lining)"`. `canonicalize` MUST strip the trailing `(<part>)` label **and** the
   `NN%` quantity and resolve the bare fibre (`viscose`, `elastane`) — otherwise apparel findings
   never hit the KB. **Add a dedicated unit test for this exact input form.** (This is the seam where
   our two internal normalizers meet; an untested contract here silently drops every apparel match.)

**Contract:** `canonicalize` returns a set of candidate keys; `validate_substances` and the matcher
check membership of *any* candidate. Return value is stable and order-independent (Schema-Driven).
**Acceptance test:** replay the 27 invalid-allergen + 5 invalid-PFAS log strings → **≥ 90% now
resolve** to the right KB row. This is the single highest-leverage change; it improves consistency
(§1/#1, #2) and shrinks the KB-gap list (§A) at the same time.

---

## C. Canonical-source-first research

### C0. Prerequisite — instrument, because today we are blind. **[S, do first]**
- ~~`research_sources` is produced by the agent's structured output (migration 015) but **0/81 rows
  persist it** → the route drops it.~~ **DONE (2026-08-01):** `research_sources` now persists
  end-to-end (produce → `store_analysis` → serve, incl. `/analyze/cached`); confirmed by the
  transparency fleet pass. The gap **moved to the render layer** — allergen/PFAS cards and safe
  products drop the structured sources (`FLEET-AUDIT-2026-08-01.md` §5 T1). `review_insights` persists
  but is never rendered client-side (T2). ⚠ Still verify migration 015 is actually **applied in prod**
  (else the write silently no-ops).
- `ingredient_research` (migration 010) and `search_cache` (migration 009) are **empty** → the
  pre-computed research cache and L2 search cache are effectively not in use. The in-memory LRU
  (`SearchToolService`) evaporates per container.
- **Only after C0** can we measure duplicate/near-duplicate searches, wasted-vs-used sources, and
  per-analysis search counts that Veer asked about. Right now the sole proxy is `api_call_count`
  (median 6, max 9) and `total_cost_usd` (mean $0.271, p90 $0.467, max $0.635).

### C1. Per-category canonical source registry. **[M]**
Today domain filters live in `search_clients/tavily.py::DOMAIN_FILTERS`, keyed **only** by
`search_type`, not by product category. What exists vs. what's missing:

| Present today | `*.gov`, `healthcanada.gc.ca`, PubMed, `nih.gov`, `iarc.who.int`, `arxiv`, `*.edu`, `epa.gov`, `cdc.gov`, **EWG**, **CIR** (`cosmetic-ingredient-review.org`), **INCIDecoder**, `uscourts.gov`, Reuters/NYT/WSJ, Reddit, MakeupAlley |
|---|---|
| **Missing canonical** | **PubChem** (`pubchem.ncbi.nlm.nih.gov`), **ECHA** (`echa.europa.eu`), **CFIA** (`inspection.canada.ca`), **cosmeticsinfo.org**, **OEKO-TEX** (`oeko-tex.com`), **Cornucopia** (`cornucopia.org`), **Labdoor**, **NIH ODS** (`ods.od.nih.gov`) |

Add a **category → source list** dimension (config, per SOLID/ADR-004 spirit — config, not control
flow). Detect category from the product (cosmetic if INCI-shaped ingredient list; textile if apparel
retailer/composition; food if grocery/nutrition; supplement if NIH-ODS-shaped):

| Category | Check these FIRST (before open web) |
|---|---|
| Cosmetics/personal care | CIR, INCIDecoder, cosmeticsinfo.org, EWG Skin Deep, PubChem |
| Food/grocery | CFIA, FDA, EWG Food Scores, Cornucopia, active CDC/FDA/CFIA outbreak feeds (ties ADR-008) |
| Textiles/apparel | OEKO-TEX, ECHA (REACH SVHC), EPA |
| Supplements | NIH ODS, Labdoor, FDA |
| Cookware/homeware | EPA, ECHA, manufacturer MSDS |

**Update (2026-08-03, Veer's source batch):** additional canonical sources — Health Canada Cosmetic
Ingredient Hotlist + FDA cosmetic ingredients (cosmetics); NJ RTK Fact Sheets + NIOSH + CDC chemical
fact sheets + OSHA (toxic substances / homeware / industrial); CPSC + Health Canada + Amazon.ca recall
feeds (all categories → recall alerts). Full categorization, **tiering**, and the scrape-and-store
ingestion pipeline are in **§N**. Advocacy sources (EWG, Safe Cosmetics) stay Tier-3 — concern-surfacing
+ cite-through only, never a severity anchor.

### C2. Cache-before-search. **[M, depends on C0]**
Before issuing a `search_type="ingredient"` query, check `ingredient_research` by
canonical name / synonym / CAS (the migration-010 `search_ingredient_research` RPC + GIN indexes
already exist). On hit, inject the cached findings and **skip the search**. Lowering `web_fetch max_uses` /
native `web_search max_uses` (currently 3 / 5) once the cache carries the per-ingredient load must be
**category-aware (Veer fix, 2026-08-01)**: **cosmetics/personal-care** can lean hard on the
ingredient cache and drop to low headroom; **food/grocery MUST keep search headroom** so the ADR-008
active outbreak/origin checks still run — those are time-sensitive and deliberately NOT cached (§D).
Key `max_uses` off the detected category (§C1), never a global constant. **Target:** cut per-analysis
searches from ~6 toward ~2–3 for cosmetics whose ingredients are already researched, while food keeps
its outbreak/origin budget.

---

## D. Per-ingredient research reuse

**Spec:** the same ingredient must never be re-researched within *N* days across products.
`ingredient_research` (migration 010) is the store; it is currently **empty**, so 100% of
per-ingredient research today is redundant across products that share ingredients — and the corpus
is *saturated* with shared ingredients (phenoxyethanol appears in 21 products, ethylhexylglycerin
20, disodium EDTA 19, tocopherol 11×…).

- **Backfill job:** for every substance in the three KBs (157 total) run the research pipeline once,
  write to `ingredient_research`, set `research_version`. One-time ~$ cost, amortized forever.
- **Runtime:** on analysis, resolve each canonicalized ingredient (§B) against `ingredient_research`
  first; only research the residue. Re-research only when `last_updated` older than *N* days
  (suggest 180d for scientific/IARC, 30d for regulatory/outbreak per ADR-008).
- **Savings estimate:** with median 6 API calls/analysis and per-ingredient searches being the bulk,
  a warm `ingredient_research` cache plausibly removes the 3–5 per-ingredient searches on repeat
  ingredients — i.e. most of the $0.271 mean drops toward the extraction+synthesis floor for the
  common case. Exact figure is measurable only after C0 lands. **[M]**

---

## E. Consistency mechanism — where inconsistency actually enters

**It is not extraction. It is severity/inclusion assignment.** Evidence (substance flagged in some
products but present-and-unflagged in others, same corpus):

| Ingredient | flagged in | present but **unflagged** in |
|---|---|---|
| phenoxyethanol | 13 | 8 |
| ethylhexylglycerin | 5 | 15 |
| disodium EDTA | 3 | 16 |
| sodium hydroxide | 3 | 13 |
| butylene glycol | 1 | 13 |
| sodium benzoate | 2 | 11 |
| propylene glycol | 7 | 2 |
| citronellol / linalool / limonene | 2–3 | 5–6 |

The extraction step *sees* the ingredient in all of them; the agent's free-judgment then flags it
some of the time. Deterministic KB matching exists but runs in **LOG-ONLY mode**
(`analyze.py`: `# LOG-ONLY MODE: Keep all substances for now`) — so the KB neither adds the misses
nor enforces a stable verdict.

**Fix (layered):**
1. **§B normalization + §A KB expansion** so the deterministic matcher actually fires for these
   ingredients (today 28%/62% slip past it).
2. **Deterministic verdict for KB-known substances:** once a substance resolves to a KB row, its
   **severity comes from the KB** (`severity_default`, `risk_classification`), not from the model.
   The model may add context/description but may not change whether a KB substance is included or its
   base severity. This makes "phenoxyethanol" score identically everywhere.
3. **Flip validation from LOG-ONLY to enforce** (the `TODO` already sketched in `analyze.py`):
   KB-confirmed substances always included; unmatched model proposals go to `other_concerns`
   (never silently into allergens/PFAS) and get logged as KB candidates (feeding §A on a loop).
   **Every enforced finding must carry BOTH its canonical KB name AND the matched surface form**
   (the exact string as it appeared in the product's ingredient list) — Veer fix, 2026-08-01. The
   extension's whole-token `namesMatch` highlighting keys on the *surface form* to connect a finding
   to its on-page ingredient chip, so collapsing to the canonical name alone silently breaks the
   finding↔chip highlight linkage. Schema: each finding object gains `matched_surface_form` beside
   the canonical `name` (severity/verdict still come from the KB row per point 2).
4. **Acceptance metric:** re-run the corpus; for each of the top-30 shared ingredients the
   flagged/unflagged split should collapse to all-flagged or all-unflagged. Track variance of
   `overall_score` within a `product_family` (§F) → target near-0 for identical composition.

---

## F. Variant no-rescan design

### F1. What the data shows
- **Exact same product stored multiple times:** 81 rows → **70 distinct normalized URLs**; 9
  products stored 2–3× (ASINs `B0CKWP1Z9J`×3, `B0F633ZC7J`×3, `B0F6VGGDGC`×2, `B0D2BKLRBM`×2 …).
  `product_url_hash` is UNIQUE, so these are **historical rows written before
  `_normalize_product_url` existed** (or via a path that bypassed the upsert). Measured redundant
  spend is only $1.03 because most dup rows predate token tracking — the real cost is **inconsistent
  stored verdicts for one product** and cache misses on revisit.
- **Variant params actually present** in stored Amazon URLs: `th`(23), `psc`(17) — already stripped
  by ASIN extraction; plus `pd_rd_*`, `pf_rd_*`, `sp_csd`, `dib`, `qid` (all tracking, correctly
  dropped). Non-Amazon URLs already lose *all* query params (so Uniqlo `colorDisplayCode` /
  `sizeDisplayCode` variants **already collapse** — good).
- **Hosts:** amazon.ca 64, hm.com 7, shein 4, ikea 3, others 1 each.

### F2. Current normalizer (`database.py::_normalize_product_url`)
Amazon → `https://{host}/dp/{ASIN}`; everything else → `https://{host}{path}` lowercased, query
stripped. So the variant axis differs by retailer:

| Retailer | Variant lives in | Current behavior | Rule to add |
|---|---|---|---|
| Amazon | child ASIN (color/size = **different** ASIN); `th`/`psc` (same ASIN) | ASIN-level dedup only | Optional: collapse child→**parent ASIN** for *size/pack* variants only (parent ASIN not reliably in URL → needs page signal; low priority) |
| H&M | `productpage.NNNNNNN0NN.html` — trailing digits = colour/article | different path → **not** collapsed | family = base article `productpage.NNNNNNN` (strip trailing colour code) |
| SHEIN | `-p-NNNNNN.html` product id + slug | slug differs → **not** collapsed | family = extract `-p-<id>`; ignore the descriptive slug |
| Uniqlo | `colorDisplayCode` / `sizeDisplayCode` query | already collapsed | keep (but see safety valve) |
| Grocery | pack-count in slug (`-6-pack`, `-2-x-1l`) | path differs → not collapsed | strip pack-count tokens for *food* only |

### F3. Cache-key change (non-destructive migration)
- **Do NOT change `product_url_hash`.** Changing normalization changes existing hashes → old cache
  becomes unreachable (a silent cache-miss, INV-3-safe, but throws away warm cache and cannot be
  reversed row-by-row).
- **Add a column `product_family_hash`** = SHA256 of the **family key** (F2). Backfill it for all 81
  rows. Lookup becomes two-tier: exact `product_url_hash` → else `product_family_hash`.
- Keep `product_url_hash` as the write key so each real variant still gets its own row; the family
  hash is only a *read* fallback.
- **Wire the two-tier lookup into `GET /api/analyze/cached` too, not only `POST /api/analyze`**
  (Veer fix, 2026-08-01). The cache-first probe is what lets revisits skip DOM capture; if the probe
  checks only `product_url_hash`, a variant revisit 404s on the probe and the extension re-captures +
  re-analyzes anyway — defeating the family cache entirely. Both the probe and the analyze route must
  perform the identical exact-hash → family-hash fallback.

### F4. Safety valve — variants **can** differ in composition (recommended behavior)
Silent reuse is wrong for composition-varying axes. Split the variant axes:

- **Composition-invariant (size, pack count, quantity):** serve the family cache **transparently**.
- **Composition-variant (colour, scent, flavour):** serve the family cache **but** with a visible
  banner — *"Showing the analysis for the {analyzed} variant; this colour/scent may use different
  dyes or fragrance. Re-scan to be exact."* and offer a one-tap re-scan that writes a new
  variant-level row. **Recommendation: the labeled-reuse path, not silent reuse** — it preserves
  trust (a Ruh core value) and still saves the scan for the 80% who don't care about the delta,
  while never hiding a real composition difference. For apparel dyes and scented cosmetics
  specifically, default to variant-level keying (colour is composition).

### F5. Extension side — send the REAL variant URL; family logic is server-side ONLY
**Correction (Veer, 2026-08-01):** the earlier draft here (mirror the family rule in each adapter's
`canonicalUrl` and key the client cache on the family) **contradicts F3/F4** and would break the
"re-scan to be exact" escape hatch. If the extension collapses variants to a family URL *before*
POSTing, the server never learns which real variant the user is on — so it cannot write a
variant-level row on re-scan, and cannot show the correct colour/scent banner (F4).

**Decision:** family/variant logic lives **entirely server-side**. The extension ALWAYS sends the
user's real, full variant URL to both `POST /api/analyze` and `GET /api/analyze/cached`. The server
does the two-tier lookup (F3), decides family-vs-variant reuse (F4), and returns whether the result is
an exact or a family-level match. The client IndexedDB cache may still key on the real variant URL (no
family collapse client-side); worst case it re-probes the server, which is cheap (cache-first probe,
no DOM capture on a family hit). This preserves **INV-1** (client ships the true authenticated DOM/URL)
and **INV-2** (no new client control flow), and keeps the one-tap re-scan → new-variant-row path
intact. Net: the adapter gains nothing new; the server owns families.

---

## G. Prioritized backlog (impact / effort)

| Order | Item | Effort | Impact | Attacks |
|---|---|---|---|---|
| 1 | §C0 instrument: persist `research_sources`/`review_insights`, start writing `ingredient_research`/`search_cache` | S | Unblocks all measurement | #3 |
| 2 | §B ingredient normalization layer | S–M | Very high | #1 #2 #5 |
| 3 | §A1–A4 KB synonym/entry expansion from logs | S | High | #1 |
| 4 | §F3 `product_family_hash` + dedup the 11 rows | S | High | #4 |
| 5 | §E deterministic KB verdict + flip LOG-ONLY→enforce | M | Very high | #2 |
| 6 | §A5 toxic-substance KB rows | M | Medium-high | #1 |
| 7 | §D backfill `ingredient_research` (157 substances) + runtime reuse | M | High (cost) | #3 |
| 8 | §C1 per-category canonical source registry | M | Medium-high | canonicality |
| 9 | §C2 cache-before-search + lower max_uses | M | Medium (cost) | #3 |
| 10 | §F2/F5 per-retailer family rules (H&M, SHEIN) + adapter `canonicalUrl` | M | Medium | #4 |
| 11 | Normalize the `retailer`/`category` columns to a controlled vocab + add a **real** product-category field | S | Medium (measurement) | #5 |
| 12 | **§I** exposure-aware risk multipliers in `HarmScoreCalculator` + re-tuned High/Med/Low bands + plain-language exposure line | M | Very high | accuracy (NEW) |
| 13 | **§J** industrial-depth allergens (derivation chains, distance, processing-depth severity) + real user allergen/concern profiles (settings + signup) | L | High | accuracy/UX (NEW) |
| 14 | **§L** classifier #1 scannable-product gate (`identity.py` upgrade) → #2 variant classifier → progressive analysis | L | High | 45s + cost (NEW) |
| 15 | **§M** scaling & cost model (100 / 1000 users, <$300) — sets pricing + which levers ship first | S | High (planning) | cost (NEW) |
| 16 | **§K** geographic provenance → environmental-contamination cross-ref (EPA/USGS/Health Canada/ECCC) | XL | High (differentiator) | R&D (NEW) |

**Sequencing note:** 1 → 2 → 3 unlock the rest. 2 and 3 are co-dependent (the normalizer's INCI map
and the KB synonym list are the same evidence); build them together. 5 must come after 2+3 or it will
enforce an under-matching KB and *remove* valid findings. **For the NEW vision items:** §M (15) is
cheap and should come early — it decides which cost levers are mandatory and informs pricing. §I (12)
is high-accuracy-value and independent; it can proceed in parallel, but its band re-tune must be
validated against the corpus (the leather-jacket < synthetic-tee and pan-PFAS > raincoat-PFAS
invariants). §L (14) is gated by the ≤45s budget — build classifier #1 (scannable gate) and #2
(variant) first because both *save* time; the rest only if they don't add latency. §J (13) needs the
real user-profile schema. §K (16) is R&D and sequenced LAST (biggest build). Shipping §E enforcement +
§I multipliers triggers the **re-scoring side-effect** — see the dedicated note below.

---

## H. Explicitly out of scope / open questions
- Parent-ASIN resolution for Amazon size/pack variants needs a page-level signal (parent ASIN isn't
  reliably in the URL). Deferred — low volume in the data.
- `N`-day freshness windows for `ingredient_research` (§D) and per-category source weights (§C1) want
  a product decision from Veer.
- Whether to fork any cache per buyer region stays **no** (ADR-008 already decided global-by-hash).
- Retailer-label normalization (§G #11) is trivial but touches stored rows; fold into the §F3
  migration.

---

# PART II — Expanded vision (2026-08-01)

> Everything above (§0–§H) is the data-driven KB/consistency/variant work. Below is the product
> vision Veer added on 2026-08-01. It keeps the same discipline (evidence, effort/impact, dependency
> sequencing); numbers still being measured by the audit fleet are marked `[FLEET-PENDING: <agent>]`.
> **Shipped invariant that governs all of this:** every claim must distinguish **confirmed** from
> **category-typical**, be scientifically accurate, and avoid both fearmongering and libel.

---

## I. Exposure-aware risk (NEW — high priority)

**Premise: hazard = substance × exposure route.** The same substance is not equally dangerous in a
pan, a raincoat, and a lipstick. Today `HarmScoreCalculator` weights by substance severity ×
per-finding category multiplier (risk-union combination — see `harm_calculator.py` docstring), but it
has **no exposure axis**. Adding one is the single biggest accuracy win after §E.

### I1. Exposure classes (most → least internalized)
Every scannable product resolves to exactly one class:

| Class | Examples | Why it ranks here |
|---|---|---|
| **Ingested** | food, supplements, toothpaste, lip products | goes inside the body directly |
| **Absorbed / leave-on** | lotions, sunscreen, deodorant, leave-on cosmetics | prolonged skin absorption, not rinsed |
| **Prolonged-contact / inner-wear** | underwear, bras, socks, bedding, baby clothing | hours of direct skin contact, often occluded/sweat |
| **Brief-contact / outer-wear** | jackets, shoes, outerwear, bags | limited, intermittent skin contact |
| **Indirect vector** | non-stick cookware, food packaging/storage, water bottles | product isn't consumed, but **transfers** a substance into an ingestion/absorption route — **can outrank direct contact** |

The indirect-vector class is the subtle one: **a PFAS non-stick pan routes to *ingestion***, so it
must score **higher** than the same PFAS in a raincoat (outer-wear). This is the headline behavior.

### I2. Deterministic multipliers in `HarmScoreCalculator`
- Add an `exposure_class → multiplier` table (deterministic config, unit-tested — SDD/TDD per
  CLAUDE.md), applied to each finding's contribution as a **second axis on top of** the existing
  per-finding category multiplier. Indirect-vector findings are **re-routed to the ingestion
  multiplier** with an explicit note attached.
- Veer approved scores moving. **Re-tune the High/Med/Low bands** (currently 0–30 safe / 31–60
  moderate / 61–80 high / 81–100 dangerous) so the distribution stays sane after multipliers.
  `[FLEET-PENDING: none — this is a tuning task.]` Method: apply the multiplier table to the
  81-analysis corpus, re-plot the score distribution, choose bands that keep the two acceptance
  invariants true (below) and don't collapse everything into "high."
- **Acceptance invariants (must hold):** leather jacket (outer-wear, brief) **<** synthetic tee
  (inner-wear, prolonged); PFAS pan (indirect → ingestion) **>** PFAS raincoat (outer-wear).

### I3. Plain-language explanation (trust invariant)
The card must **state the exposure reasoning in plain words**, not just move a number:
- "Scored as outer-wear — limited skin contact."
- "Non-stick surface can transfer PFAS into food — treated as ingestion."
This keeps the confirmed-vs-typical invariant visible and prevents the score change from reading as
arbitrary. No fearmongering: the explanation is mechanistic, not alarmist.

### I4. Where `exposure_class` comes from
- **Short term:** deterministic map from a real product category (needs §G #11's category field).
- **Longer term:** the scannable-product / identity classifier (§L #1) emits `exposure_class` as a
  side output. Prefer the config map now, migrate to the classifier when it lands.
- Effort **[M]**. Depends on a real category field (§G #11). Ties the §I side-effect to §E — see the
  re-scoring note.
- **Fleet finding (2026-08-01, `FLEET-AUDIT-2026-08-01.md` §4 D1):** the existing product-category
  multiplier is currently **dead** — `analyze.py:671` overwrites the stored `category` with the
  retailer, and at score time `harm_calculator.py:154` reads a top-level `category` the agent never
  emits (so it defaults to 1.0). §I therefore isn't just *adding* an exposure axis; it must **first fix
  the category pipeline** (agent emits a real `product_category`; migration 021) or neither the category
  nor the exposure multiplier will fire.

---

## J. Industrial-depth allergens (NEW)

**Premise: soy / corn / peanut are feedstocks, not just ingredients.** Their derivatives —
lecithin, tocopherols, maltodextrin, dextrose, citric acid, xanthan gum, modified food starch,
"natural flavor," refined oils — are many processing steps removed, yet sensitive people still react
(variably, by processing depth). The KB today treats allergens as flat name/synonym sets; it can't
reason about derivation.

### J1. Derivation chains in the KB
- KB learns **derivation chains**: `feedstock → derivative → processing_depth`. Examples:
  corn → {dextrose, maltodextrin, citric acid, xanthan gum, modified food starch, "natural flavor",
  some tocopherols}; soy → {lecithin, tocopherols, hydrolyzed soy protein, mono/diglycerides,
  vegetable oil}; peanut → {refined vs. cold-pressed peanut oil}.
- Schema: an allergen row gains a `derivation` structure —
  `{feedstock, derivative_name, processing_depth, residual_protein_likelihood}`.
- **Flag aggressively but honestly.** Show **derivation distance** ("corn-derived, highly processed")
  and **scale severity by processing depth**: refined oils / tocopherols (low residual protein) →
  lower severity; hydrolyzed proteins / flours → higher. Confirmed-vs-typical invariant in practice:
  *"contains soy lecithin (soy-derived, highly refined — most soy-allergic people tolerate it, but not
  all)."*

### J2. Full food-preservative coverage
Extend toxic/preservative KB coverage (ties §A5): sorbates, benzoates, nitrites/nitrates, **sulfites**
(a declared allergen in CA/US), BHA/BHT, propionates, natamycin, EDTA. Sulfites especially must be
first-class.

### J3. User allergen / concern profiles (settings AND signup)
- **3 toggleable harm profiles:** corn, soy, peanut — feedstock-level (enabling one surfaces **all**
  its derivatives with derivation distance).
- **User-concern modes:** young children, chronic illness, sensitive skin — each reweights what's
  surfaced (e.g. sensitive skin boosts fragrance/preservative sensitizers; young children boost
  endocrine-actives).
- Build out **real user allergen profiles** — schema stub exists `[FLEET-PENDING: datamodel-audit to
  confirm the stub table/columns]`. Collected at **both** signup (like region/ToS, ADR-008) **and**
  editable in settings.
- **Backend threading:** the analysis accepts the profile like `user_region` (ADR-008): an
  `AnalysisRequest` field → prompt line + **deterministic post-filter** (a profile-on substance is
  always surfaced and reweighted, never hidden). **Pin a route test that the profile actually reaches
  the wrapper** — this is exactly the mockable-boundary seam that caused the 2026-08-01 wrapper outage
  (MEMORY.md); a green mocked suite will not catch signature drift here.
- **Cache implication:** profiles are per-user; the global-by-hash cache (ADR-008) can't bake one in.
  Apply the profile as a **deterministic post-process/re-rank on the cached analysis** — surface and
  reweight already-detected substances by the user's profile — **not** a cache fork. Limit to state
  honestly: substances not detected at all can't be surfaced retroactively; the profile mainly
  reweights/highlights detected ones and drives "we screened for your soy concern" messaging.
- Effort: derivation KB + preservatives **[M–L]**; profiles (schema + signup + settings + threading)
  **[L]**. Very high value for the allergy-sensitive segment (a real differentiator).

---

## K. Geographic provenance → environmental-contamination cross-ref (NEW — R&D-flagged)

**Premise (food, for now):** resolve where a food was grown/processed, then cross-reference **public**
environmental-contamination datasets. This expands Ruh's DB **beyond product data** — a genuine moat,
and a genuine R&D risk. Do not overpromise.

### K1. Location resolution — honest about the floor
- Farm-level **if discoverable** (some brands publish; some lot/establishment codes decode);
  **county-level is the realistic floor**, and the UI must say so. Many products will resolve only to
  country/region — that is a real **data-availability** limitation, not a bug. Flag it plainly.
- Sources: brand disclosures, USDA/CFIA establishment codes, public lot/batch decoding, and the
  ADR-008 origin-research pipeline (extend it, don't rebuild).

### K2. Environmental dataset (a NEW DB — public sources ONLY)
- Build a US + Canada environmental-contamination dataset from **public sources only** — **EPA, USGS,
  Health Canada, ECCC**. **NOT** scraped proprietary maps (legal + ToS exposure).
- Contents: drinking-water advisories, soil/groundwater contamination (EPA Superfund/ECHO, USGS
  water-quality, Health Canada water advisories, ECCC), and — **if fertilizer/pesticide inputs are
  discoverable for a region** — those too.
- Shape: ETL the public datasets → a normalized `env_contamination` table keyed by geographic unit
  (US county FIPS, Canadian census division). `[FLEET-PENDING: datamodel-audit — table shape + whether
  PostGIS is warranted vs. a FIPS/name key.]`

### K3. Surfacing — labeled caveats, sourced, non-libelous
- Region-level overlaps surface as **clearly-labeled caveats with source + as-of date**: *"This
  product's stated growing region (X County) overlaps an EPA groundwater advisory for [contaminant]
  (source, as-of date). This is a regional environmental note, not a test of this product."*
- The confirmed-vs-typical invariant is **legally load-bearing here**: a regional overlap is **not** a
  claim the product is contaminated. Language stays precautionary, sourced, and about the *region*,
  never the brand.

### K4. Status
- **R&D-flagged; sequenced LAST (§G #16, [XL]).** Biggest differentiator, biggest build. **Prototype
  first:** pick ONE dataset (e.g. EPA drinking-water advisories) + county resolution for a handful of
  real products, prove the join, and measure caveat quality / false-positive rate before scaling.

---

## L. Custom classifiers in separate Cloudflare containers (NEW)

**Premise:** replace LLM judgment with small deterministic models where it improves
reliability/cost/latency. Each classifier is its own CF container (SOLID single-responsibility,
independently deployable/scalable). **HARD CONSTRAINT: end-to-end analysis stays ≤45s. Every
classifier must SAVE time or run async/off-path — never add latency to the critical path.**

### L1. Build order (Veer-specified — do NOT reorder the first three)
1. **Scannable-product gate** — is this even a product Ruh should scan/score? A tire, a laptop, a
   gift card get **no** harm score and aren't scanned. This is a **classifier upgrade of the existing
   `domain/identity.py` guard** (which already rejects drifted/wrong-product analyses). Runs FIRST,
   cheap, and **short-circuits non-scannable products before any Claude call** — pure latency + cost
   win.
2. **Variant classifier → progressive analysis** — given a new variant of an already-analyzed
   product, classify the **delta** (same composition? colour-only? genuinely new ingredient?) and
   analyze **only the delta**, not a full re-scan. This is the engine behind the §F family cache —
   "analyze the delta." Net latency/cost win on variant revisits.
3. **Then reorder sensibly** among:
   - **Ingredient canonicalizer / NER** — deterministic raw-string → canonical-KB-entry mapping
     (could subsume/accelerate §B; replaces an LLM extraction step or runs off-path).
   - **Garbage-extraction detector** — catch junk extraction (wrong page, empty, hallucinated)
     **before** it costs a synthesis call (saves a wasted Claude call).
   - **Review health-relevance scorer** — pre-score which reviews are health-relevant before
     embedding/RAG (cuts Cohere embed volume; off-path/pre-filter).
4. **Research-source relevance classifier — LAST** (Veer: iffy). Idea: relevant sources get more
   agent attention. Veer is skeptical it earns its keep; build only after the others prove out.

### L2. Latency accounting (the ≤45s gate)
- Each classifier's placement is justified against the measured critical path. **Perf-audit
  (2026-08-01, `FLEET-AUDIT-2026-08-01.md` §3): p50 ≈ 40–48s, p90 breaches 45s; the Claude custom-search
  agent loop dominates at ~22–35s, and the review sub-pipeline adds ~10–19s (deferrable — move off the
  critical path per P3).** A classifier on the critical path is allowed **only if it removes more time
  than it adds** (scannable-gate removes a whole Claude round-trip; variant removes most of a $0.27
  scan). Off-path classifiers (review relevance, source relevance) run async and must not delay the
  response.
- Cost angle (cost-audit 2026-08-01): classifiers/canonicalizer save ~$100–140/mo at Stage 2 (scannable
  gate skips ~10% unanalyzable pages at $0.282 each; canonicalizer shortens synthesis + cuts searches).
  A primary cost lever (see §M3).

### L3. Deployment shape
- Separate CF container per classifier: small models (distilled / embedding-based / logistic on
  features), **not** LLMs, so they're fast and cheap. The Durable Object orchestrator calls them; a
  classifier being **down degrades gracefully to the current LLM path** (INV-3). This also keeps each
  independently benchmarkable against the 45s budget.

---

## M. Scaling & cost (NEW)

**Targets (Veer):** all-in monthly (Cloudflare + Supabase + AI) **under $300** at **both** stages —
**stage 1 = 100 users, stage 2 = 1000 users.** Post-beta free tier = **5 analyses/user/month.**
Pricing is informed by these numbers.

### M1. The cost driver
Fresh analyses dominate: **mean $0.271, p90 $0.467, max $0.635, median 6 API calls/analysis** (§0/§C0).
Storage/requests are small beside AI spend. So the whole game is: **minimize fresh-analysis count and
per-fresh cost.** `[FLEET-PENDING: cost-audit — per-component breakdown of $0.271, per-stage all-in
model, ranked levers in $.]`

### M2. Two stages (cost-audit CONFIRMED 2026-08-01 — see `FLEET-AUDIT-2026-08-01.md` §6)
Per-analysis all-in ≈ **$0.282** ($0.271 tracked + ~$0.011 Cohere embed+rerank, which `token_tracker`
does not price). Fixed infra: Supabase Pro $25 + CF Workers $5–20.
- **Stage 1 — 100 users (~500 analyses/mo):** AI ~$141 + fixed ~$31 = **≈$172/mo ✅ comfortably under
  $300** on the naive Sonnet path — no levers strictly required.
- **Stage 2 — 1000 users (~5,000 analyses/mo):** AI ~$1,410 + fixed ~$40 = **≈$1,450/mo ❌ ~4.8× over.**
  Needs effective **≤$0.052/analysis** (from $0.282, a 5.4× cut) → the cache/classifier levers are
  **mandatory.** `[FLEET-PENDING: real cache-hit rate — needs §C0 instrumentation; sets the exact
  Stage-2 figure.]`
- **⚠ Load-bearing product decision (Veer):** this model assumes **5 analyses/user/mo**, but the shipped
  design auto-analyzes **every product page** and caps only detail-*unlocks* at 5. If analyses stay
  uncapped, cost scales with pages-viewed (≫5) and **even Stage 1 can breach $300.** Cap the analysis,
  or keep auto-analyze and absorb/optimize — this decision gates the whole cost model and free-tier size.

### M3. Cost levers (the path to <$300 at 1000 users)
Ranked by $/mo saved at Stage 2 (cost-audit 2026-08-01, estimates pending real hit-rate): **cache-first
probe ~$820**, **classifiers/canonicalizer ~$100–140**, **ingredient-research cache ~$101**, **variant
progressive-analysis ~$50–140** (overlaps cache-first — do NOT sum naively). Optional Sonnet→Haiku on the
KB-known path ≈$340/mo but with quality risk. Detail:
1. **Ingredient-research cache (§D)** — removes 3–5 per-ingredient searches on repeat ingredients;
   the corpus is saturated with shared ingredients (phenoxyethanol in 21 products, etc.). Biggest
   single lever.
2. **Cache-first probe + family cache (§F)** — revisits and variants skip DOM capture + re-analysis
   entirely ($0 AI on a hit).
3. **Variant progressive-analysis (§L #2)** — a variant costs the delta, not a full $0.27 scan.
4. **Classifiers replacing LLM calls (§L)** — scannable-gate short-circuits non-products; garbage
   detector / canonicalizer remove wasted synthesis calls.
- The effective $/analysis must fall from $0.27 toward the extraction+synthesis floor as the cache
  warms. Prompt caching on the static KB system prompt (a perf/cost finding) compounds this.

### M4. Pricing implication
Free tier = 5 analyses. Paid tiers (basic 15 / middle 30 / unlimited) must price **above the marginal
cost after levers**. `[FLEET-PENDING: cost-audit — marginal $/analysis → floor price per tier.]` The
under-$300 constraint at 1000 users, minus paid-tier revenue, is the real gate on the free-tier size.

---

## Re-scoring side-effect (UX consideration — honest note)

When **§E** (KB enforcement / deterministic verdicts) and **§I** (exposure multipliers) land,
**re-analyzed products will score differently than their cached versions.** This is the correction
*working* — the old scores were the inconsistent per-run LLM judgments §E exists to eliminate — but it
is a visible UX event:
- a user who saw "72" last week may see "65" after a re-scan;
- two users on the same product (one on an old cached row, one fresh) may see different scores until
  the cache turns over.

Options (decide at build time):
- **(a) Batch re-score** the cache when the enforcement/multiplier version bumps — cleanest, costs a
  re-analysis sweep (a real $ spike at 1000 users; see §M).
- **(b) Version + badge** — carry a `scoring_version` on each analysis; when a row is behind, badge the
  card ("scoring model updated — re-scan for the latest") and offer one-tap re-scan (reuses the §F
  re-scan path). Cheap, honest, defers cost.
- **(c) Drift** — let cached rows drift, re-score on natural revisit. Cheapest, most inconsistent.

**Recommendation: (b).** It preserves trust (a Ruh core value) without a forced-sweep cost spike, and
it reuses the §F `scoring_version` / `research_version` columns. Tie the scoring version to both the
KB-enforcement and exposure-multiplier revisions.

---

## Fleet audit (in progress — 2026-08-01 evening)

Five read/prototype worktree agents are auditing **performance & robustness**, **data model**,
**transparency (sources on every card)**, **static security (RLS / keys / IDOR)**, and **cost**. Their
evidence backfills the `[FLEET-PENDING]` markers above and may add backlog items. **Nothing they
produce lands on `development` unreviewed** — the orchestrator verifies and merges. A separate
**Friday-after-7pm scheduled routine** runs the live-API adversarial pass (auth bypass / RLS escape /
IDOR / credit manipulation), gated to that window only.

> **Fleet reports are IN (2026-08-01 evening)** — all five re-ran on the correct commit (`17c047c`).
> Full prioritized, verified findings + proposed diffs + launch-blockers live in
> **[`FLEET-AUDIT-2026-08-01.md`](./FLEET-AUDIT-2026-08-01.md)**. Headlines: a **missing security
> migration** (003's `authenticated`-write policies were never fixed on `development` — the shared
> safety cache + allergen/PFAS KB are writable by any signed-up user via the public anon key; pending a
> live `pg_policies` check), a **client-side-only paywall** (full detail returned without an unlock),
> and a **silently-dead hybrid review RAG** (`review_vector_service` calls `db.supabase` but the object
> only has `.client`). Nothing has landed — all await Veer's review. (First pass hit the stale
> `main`/v0.3.0 tree — MEMORY.md.)

---

## N. Canonical source ingestion & consumer-product recall alerts (NEW — 2026-08-03, Veer)

Veer supplied a batch of canonical/authoritative sources. Split by **how we use each**:
**direct-search-toward** (add to the §C1 registry so the agent checks them first), **scrape-and-store**
(ETL the structured content into our DB — raw + synthesized — feeding §A/§D/§E), and
**mine-for-primary-sources** (low-tier synthesis content; extract the papers it cites, do NOT treat the
page itself as authority).

**Tiering discipline (the scientific-accuracy invariant):** government/regulatory = **Tier-1**
(authoritative for severity/enforcement); advocacy/consumer-org and blogs = **Tier-3** (surface concerns
+ cite-through only — NEVER anchor a severity or a "confirmed" claim on them; several lean precautionary
and some ratings are actively contested). Storing a Tier-3 claim as fact is exactly the fearmongering /
libel risk the confirmed-vs-category-typical invariant exists to prevent. Every stored record carries
`source_tier` + provenance + as-of date.

### N1. Tier-1 regulatory hazard / ingredient DBs → SCRAPE + store raw + synthesized
Feeds §A (new substances/synonyms), §D (`ingredient_research`), §E (deterministic KB severity). Each is
a per-substance structured document → store the **RAW** doc + a **SYNTHESIZED** extract (canonical name,
CAS, hazard class, severity, restriction status, source + as-of).

| Source | What | Feeds | Scrape notes |
|--------|------|-------|--------------|
| **NJ RTK Hazardous Substance Fact Sheets** (`web.doh.nj.gov/rtkhsfs`, A–Z + carcinogen flag) | ~1,900 per-substance hazard fact sheets (health effects, exposure, PEL, carcinogen status) | toxic_substances, severity | Structured A–Z index + a `carcinogen=True` filter that is a ready severity signal — highly scrapable |
| **NIOSH chemicals / Pocket Guide** (`cdc.gov/niosh/chemicals`) | Per-chemical exposure limits, IDLH, hazards | toxic_substances, severity | Structured gov DB |
| **CDC chemical fact sheets** (`cdc.gov/chemical-emergencies/chemical-fact-sheets`) | Acute-exposure chemical fact sheets | toxic_substances | Fact-sheet format |
| **Health Canada Cosmetic Ingredient Hotlist** (`canada.ca …/hotlist`) | Prohibited + restricted cosmetic ingredients (CA regulatory) | cosmetics KB, §E enforcement | A prohibited/restricted list is a **hard severity anchor**; scrape both tables |
| **FDA cosmetic ingredients** (`fda.gov/cosmetics/…`) | FDA ingredient guidance / prohibited | cosmetics KB | Reference + targeted scrape |
| **OSHA toxic industrial chemicals** (`osha.gov/…`) | Industrial chemical hazards | toxic_substances (textile/industrial) | Reference / scrape |

### N2. Consumer-product recall / safety-alert feeds → direct-search + periodic ingest
**Extends ADR-008 alerts from food-only to ALL product types** (cosmetics, apparel, homeware…). Surfaced
as labeled, sourced, as-of-dated caveats — same contract as outbreak alerts (never fabricated; category-
level vs product-confirmed stated explicitly).

| Source | Scope |
|--------|-------|
| **CPSC Recalls** (`cpsc.gov/Recalls`) + **SaferProducts** (`saferproducts.gov`, incident search) | US consumer-product recalls + incident reports |
| **Health Canada Recalls & Advisories** (`recalls-rappels.canada.ca`) | Canada recalls/advisories, all product types |
| **Amazon.ca product-safety alerts** (`amazon.ca/product-safety-alerts`) | Retailer recall feed (matches the CA retailer focus) |
| **Health Canada consumer product safety education** (`canada.ca/…`) | Reference / framing |
| **ICPHSO** (`icphso.org`) | Consumer-product health/safety org — reference |

### N3. Tier-3 advocacy / synthesis → concern-surfacing + cite-through ONLY (never a severity anchor)
| Source | Use | Caveat |
|--------|-----|--------|
| **EWG Skin Deep** (`ewg.org/skindeep` + ratings methodology) | Consumer-facing hazard framing, ingredient concern flags | Advocacy; ratings contested/precautionary — present as "EWG rates…", not as our verdict |
| **Campaign for Safe Cosmetics** (`safecosmetics.org/chemicals`) | Chemical concern narratives | Advocacy — cite-through to primary sources |
| **Clean Label Project** (`cleanlabelproject.org/blog`) | Product-testing findings | NGO testing; verify methodology before citing |
| **Fibercheck blog** (`fibercheck.app/blog`) | Textile/fiber safety synthesis | Synthesize; verify claims against primary sources |
| **mommypotamus — toxins in clothing** | **PAPERS ONLY** — extract the primary research it cites; ignore the post's own claims | Blog is Tier-3; its cited papers may be Tier-1 |

### N4. Storage + build implications
- **Schema:** a `source_documents` table (raw content + url + `source_tier` + `fetched_at` + content
  hash) linked to synthesized extracts; the per-substance synthesized extract lands in
  `ingredient_research` (§D) / the KBs (§A) tagged with `source_tier` + provenance. Folds into the §28
  data-model work.
- **Ingestion:** one-time bulk scrape of N1 + periodic refresh (regulatory ~30d, recalls daily/weekly per
  ADR-008 cadence). **Recon each target's structure before scraping** (ADR-005 discipline: verify the
  page actually holds the fields — NJ RTK / Health Canada Hotlist are structured; blogs are not).
- **Sequencing:** N1 pairs with §A/§D/§E; N2 rides the ADR-008 alert-prompt contract; N3 is opportunistic.
  This is a DB-expansion workstream alongside §K (environmental datasets) — same ETL pattern, same
  **public-sources-only** posture.
- **Open decisions (Veer):** per-source trust weights; refresh cadence per tier; whether recall alerts
  **gate the score** or only **annotate** (recommend annotate, like ADR-008, to avoid over-penalizing).
