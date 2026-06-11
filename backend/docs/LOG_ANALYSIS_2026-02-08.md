# Log Analysis — 2026-02-08

**Session**: 10:49:41 – 10:55:20 PST
**Environment**: Local dev (`debug=True`), Uvicorn with WatchFiles reloader
**Requests**: 2 product analyses (both `POST /api/analyze`, both `200 OK`)
**Raw logs**: [RAW_LOGS_2026-02-08.md](./RAW_LOGS_2026-02-08.md)

---

## Request Summary

| #   | Product                                                        | Duration | Iterations | Searches | Tokens      | Cost        |
| --- | -------------------------------------------------------------- | -------- | ---------- | -------- | ----------- | ----------- |
| 1   | Paula's Choice 2% BHA Liquid Salicylic Acid Exfoliant (118 ml) | **100s** | 8          | 21       | 137,307     | $0.4549     |
| 2   | Paula's Choice 8% AHA Gel Exfoliant (100 ml)                   | **62s**  | 4          | 11       | 46,020      | $0.1726     |
|     | **Totals**                                                     | **162s** | **12**     | **32**   | **183,327** | **$0.6275** |

---

## Pipeline Execution Flow (per request)

Both requests followed the same path:

```
Cache MISS → Client HTML received → Amazon scraper → Section parser
→ DB ingredient matching (0 results) → Ingredient classification
→ Claude Agent (multi-iteration with Tavily search) → Merge → Validate → Store
→ Review parsing (FAILED) → Review health analysis (SKIPPED)
```

---

## BUG: Section Parser Extracts 0 Ingredients (P0)

**Both** analyses returned `0 ingredients, 0 materials` from the section parser despite 60% confidence.

```
Section parser: Paula's Choice SKIN PERFECTING 2% BHA Liquid Salic... (0 ingredients, 0 materials, 60% confidence)
Section parser: Paula's Choice SKIN PERFECTING 8% AHA Gel Exfolian... (0 ingredients, 0 materials, 60% confidence)
```

**Impact**: Since 0 ingredients are extracted, the entire DB matching step is a no-op:

- `Matching 0 ingredients and 0 materials against databases`
- `Database matching complete: 0 allergens, 0 PFAS, 0 toxic substances`
- `Ingredient preprocessing: 0 safe, 0 known concerns, 0 need research`

This forces Claude to do **all** ingredient identification from scratch via web search, which is why Product 1 needed 8 iterations and 21 searches. The 3-step pipeline (DB match → classify → Claude) is effectively reduced to a 1-step pipeline (Claude does everything).

**Root cause hypothesis**: The Amazon HTML scraper extracts product info into structured fields, but the section parser may not be looking in the right place for ingredients. The scraper logged `2.6KB product, 7.7KB reviews` for Product 1 — the product HTML is heavily compressed, and ingredients may be in a section the parser doesn't recognize.

**Recommended fix**: Investigate `section_parser.py` to see why it returns 60% confidence but 0 ingredients. The confidence should be lower if no ingredients were found, or the parser needs to handle Amazon's ingredient section selectors.

---

## BUG: Review Parsing Mismatch (P1)

The Amazon scraper detects reviews via string matching, but BeautifulSoup fails to parse them:

**Product 1:**

```
📝 Found 13 reviews embedded in product page        (scraper - string match)
📝 BeautifulSoup found 0 total review divs          (review_vector_service - DOM parse)
```

**Product 2:**

```
📝 Found 8 reviews embedded in product page
📝 BeautifulSoup found 0 total review divs
```

The scraper uses `data-hook='review'` string matching to count reviews, but the `review_vector_service` uses BeautifulSoup to parse `<div>` elements with that attribute and finds nothing. This could be:

1. The HTML is being chunked/truncated before BS4 parsing
2. The selector used by `review_vector_service` differs from the scraper's selector
3. Amazon's review HTML uses a structure BS4 doesn't match (e.g., nested shadow DOM, lazy-loaded content)

**Result**: Review health analysis is skipped for both products (`⏭️ SKIP STEP 8`), meaning users get no review-based safety signals.

---

## Ingredient Research DB is Empty

Every `lookup_ingredient_research` call returned no results:

| Ingredient        | Result            |
| ----------------- | ----------------- |
| Salicylic Acid    | No research found |
| Polysorbate 20    | No research found |
| Tetrasodium EDTA  | No research found |
| Butylene Glycol   | No research found |
| Green Tea Extract | No research found |
| Phenoxyethanol    | No research found |
| Propylene Glycol  | No research found |
| Sodium Benzoate   | No research found |
| Glycolic Acid     | No research found |

**Impact**: The `ingredient_research` table appears unpopulated. This forces Claude to web-search every ingredient individually, adding ~2-4s per ingredient. For Product 1, this added at least 3 extra iterations (iter3-iter7 were almost entirely ingredient research).

**Recommendation**: Pre-populate the `ingredient_research` table with common cosmetic ingredients. The 9 ingredients above are extremely common in skincare — having pre-computed research for even the top 100 ingredients would significantly reduce iteration count and cost.

---

## Token Growth Analysis (Product 1)

Context window grows linearly as search results accumulate:

| Iteration | Input Tokens | Output Tokens | Cumulative Input Growth | Cost    |
| --------- | ------------ | ------------- | ----------------------- | ------- |
| 1         | 5,538        | 327           | —                       | $0.0215 |
| 2         | 8,902        | 384           | +61%                    | $0.0325 |
| 3         | 14,472       | 305           | +63%                    | $0.0480 |
| 4         | 16,052       | 189           | +11%                    | $0.0510 |
| 5         | 17,924       | 173           | +12%                    | $0.0564 |
| 6         | 22,502       | 198           | +26%                    | $0.0705 |
| 7         | 23,643       | 100           | +5%                     | $0.0724 |
| 8         | 24,689       | 1,909         | +4%                     | $0.1027 |

**Key observation**: Iteration 8 (the final one) produced 1,909 output tokens — the actual JSON response. All prior iterations were tool-use loops with small outputs (100-384 tokens). The last iteration accounts for 22.6% of total cost.

**Insight**: Iterations 1→3 show the biggest input growth (+61%, +63%) because that's when bulk search results are being added. Later iterations grow more slowly as Claude narrows its research.

---

## Search Performance

### Tavily Search Stats

| Metric                              | Value                        |
| ----------------------------------- | ---------------------------- |
| Total searches across both requests | 32                           |
| Search cache hits                   | **0**                        |
| Average Tavily response time        | 1.6s - 4.2s                  |
| Tavily extract calls                | 4 (8 URLs total, 0 failures) |
| All Tavily calls returned           | 5 results each               |

### Search Cost Breakdown

| Type             | Count | Unit Cost | Total       |
| ---------------- | ----- | --------- | ----------- |
| Tavily search    | ~26   | $0.0080   | ~$0.208     |
| Tavily extract   | ~6    | $0.0020   | ~$0.012     |
| **Search total** |       |           | **~$0.220** |

### Search Cache Miss Rate: 100%

Despite having an `_extracted` suffix search cache, zero queries hit the cache. Notably, the query `"Paula's Choice class action lawsuit settlement"` was searched in **both** requests but didn't cache between them. This suggests the cache is either not being written or has very strict TTL.

---

## Search Types by Claude's Strategy

Claude follows a consistent multi-phase research pattern:

| Phase      | Search Types                              | Purpose                        |
| ---------- | ----------------------------------------- | ------------------------------ |
| 1 (iter1)  | manufacturer, regulatory, legal, consumer | Brand-level safety signals     |
| 2 (iter2)  | ingredient × 5                            | Individual ingredient toxicity |
| 3 (iter3+) | ingredient (deeper), consumer (reactions) | Follow-up on flagged items     |
| Final      | regulatory (FDA/Health Canada)            | Regulatory verification        |

This is a good research strategy, but the ingredient phase could be eliminated if the ingredient research DB were populated.

---

## HTML Compression (Working Well)

| Product   | Raw HTML   | Compressed | Reduction |
| --------- | ---------- | ---------- | --------- |
| Product 1 | 2,553.7 KB | 10.3 KB    | 99.6%     |
| Product 2 | 1,725.3 KB | 5.4 KB     | 99.7%     |

The Amazon scraper's compression is extremely effective. This keeps Claude's input context manageable.

---

## Cost Comparison: Product 1 vs Product 2

| Metric          | Product 1 (2% BHA) | Product 2 (8% AHA) | Delta |
| --------------- | ------------------ | ------------------ | ----- |
| Iterations      | 8                  | 4                  | -50%  |
| Claude API cost | $0.3109            | $0.0966            | -69%  |
| Search cost     | ~$0.144            | ~$0.076            | -47%  |
| Total           | $0.4549            | $0.1726            | -62%  |
| Duration        | ~100s              | ~62s               | -38%  |

Product 2 was significantly cheaper because Claude converged in fewer iterations. This may be because:

- Glycolic acid (the active ingredient) has more straightforward safety data
- Claude found enough information sooner to make its assessment
- Product 2 had a higher harm score (57 vs 25), suggesting more clear-cut concerns

---

## Harm Scores

| Product          | Harm Score | Allergens | PFAS | Risk Level |
| ---------------- | ---------- | --------- | ---- | ---------- |
| 2% BHA Exfoliant | 25         | 0         | 0    | Low        |
| 8% AHA Exfoliant | 57         | 2         | 0    | Medium     |

Product 2 scored higher because it contains phenoxyethanol and sodium benzoate (preservatives that are known allergens for some individuals), plus glycolic acid at 8% concentration.

---

## Issues Ranked by Priority

| Priority | Issue                                     | Impact                                           | Effort              |
| -------- | ----------------------------------------- | ------------------------------------------------ | ------------------- |
| **P0**   | Section parser returns 0 ingredients      | Forces Claude to do all work, 2-4x cost          | Medium              |
| **P0**   | Ingredient research DB empty              | Every ingredient triggers web search             | Low (data entry)    |
| **P1**   | Review parsing fails (BS4 ≠ string match) | No review-based safety signals                   | Medium              |
| **P2**   | Search cache 100% miss rate               | Repeated queries not cached, wasted Tavily spend | Low-Medium          |
| **P3**   | Product 1 used 8 iterations ($0.45)       | Cost efficiency concern at scale                 | Depends on P0 fixes |

---

## Recommendations

1. **Fix section parser ingredient extraction** — This is the highest-leverage fix. If the parser correctly extracted ingredients, the DB matching step would work, the classifier would pre-categorize them, and Claude would only need 2-3 iterations instead of 8.

2. **Seed `ingredient_research` table** — Start with the top 200 cosmetic ingredients (salicylic acid, glycolic acid, phenoxyethanol, etc.). Each failed lookup adds ~1 iteration to the Claude agent loop.

3. **Debug review HTML parsing** — The scraper finds `data-hook='review'` strings but BS4 can't parse them. Add debug logging to see what HTML `review_vector_service` actually receives.

4. **Investigate search cache writes** — Verify that Tavily search results are being written to the `search_cache` table after each query. The 100% miss rate suggests a write failure or schema mismatch.

5. **Consider iteration caps** — Product 1 used 8 iterations. If the agent loop had a soft cap at 5 with forced output, cost would drop by ~30% with minimal quality loss (iterations 6-7 were diminishing returns at 100-198 output tokens each).
