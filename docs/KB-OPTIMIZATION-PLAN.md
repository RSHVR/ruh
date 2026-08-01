# KB & Research Optimization Plan

> **Status:** proposal / analysis. Nothing here is implemented.
> **Author:** data-analysis pass over production Supabase (read-only), 2026-08-01.
> **Goal (Veer's words):** "be more consistent given similar products, reduce random
> searching, increase the canonical sources we check" + "don't rescan the whole product
> if the user changed the variant like color or multi-packs."
> **Companion docs:** [`LORE.md`](../LORE.md) (ADRs/invariants), [`INDEX.md`](../INDEX.md) (file map),
> [`CLAUDE.md`](../CLAUDE.md) (standards). Corpus: 81 `product_analyses`, 142 `validation_logs`,
> KBs of 32 allergens / 75 PFAS / 50 toxic substances.

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

**Contract:** `canonicalize` returns a set of candidate keys; `validate_substances` and the matcher
check membership of *any* candidate. Return value is stable and order-independent (Schema-Driven).
**Acceptance test:** replay the 27 invalid-allergen + 5 invalid-PFAS log strings → **≥ 90% now
resolve** to the right KB row. This is the single highest-leverage change; it improves consistency
(§1/#1, #2) and shrinks the KB-gap list (§A) at the same time.

---

## C. Canonical-source-first research

### C0. Prerequisite — instrument, because today we are blind. **[S, do first]**
- `research_sources` is produced by the agent's structured output (migration 015) but **0/81 rows
  persist it** → the route drops it. Wire `research_sources` (and `review_insights`) through
  `store_analysis`.
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

### C2. Cache-before-search. **[M, depends on C0]**
Before issuing a `search_type="ingredient"` query, check `ingredient_research` by
canonical name / synonym / CAS (the migration-010 `search_ingredient_research` RPC + GIN indexes
already exist). On hit, inject the cached findings and **skip the search**. Lower
`web_fetch max_uses` / native `web_search max_uses` (currently 3 / 5) once the cache carries the
per-ingredient load. **Target:** cut per-analysis searches from ~6 toward ~2–3 for products whose
ingredients are already researched.

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

### F5. Extension side
Mirror the family rule in each `SiteAdapter` as a `canonicalUrl(url)` so the client cache
(IndexedDB, 30-day) keys on the same family and doesn't re-POST for a known variant. Keeps
extension and backend cache keys aligned (INV-2: config per adapter, no new control flow).

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

**Sequencing note:** 1 → 2 → 3 unlock the rest. 2 and 3 are co-dependent (the normalizer's INCI map
and the KB synonym list are the same evidence); build them together. 5 must come after 2+3 or it will
enforce an under-matching KB and *remove* valid findings.

---

## H. Explicitly out of scope / open questions
- Parent-ASIN resolution for Amazon size/pack variants needs a page-level signal (parent ASIN isn't
  reliably in the URL). Deferred — low volume in the data.
- `N`-day freshness windows for `ingredient_research` (§D) and per-category source weights (§C1) want
  a product decision from Veer.
- Whether to fork any cache per buyer region stays **no** (ADR-008 already decided global-by-hash).
- Retailer-label normalization (§G #11) is trivial but touches stored rows; fold into the §F3
  migration.
