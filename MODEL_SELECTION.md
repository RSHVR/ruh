# MODEL_SELECTION.md — Production Model Choice & Unit Economics

**Date:** 2026-06-11 · **Status:** Recommendation (pins not yet changed in production code)
**Evidence:** 5-config agent benchmark, n=3 tier-a runs (`backend/scripts/benchmark/output/tier_a5_n3/`,
`sonnet46_sevcal_n3/`), scored by the tuned harm calculator (2026-06-11), per-model prompt levers ON.
**Companion docs:** [`MODEL_QUIRKS.md`](./backend/scripts/benchmark/MODEL_QUIRKS.md) (per-model evidence) ·
[`EVAL_HARNESS_CASE_STUDY.md`](./EVAL_HARNESS_CASE_STUDY.md) (methodology) ·
[`HARNESS_IMPROVEMENTS`-tracked fixes referenced below] · [`AUDIT.md`](./AUDIT.md)

---

## 1. Decision

| Seat | Model | Why |
|---|---|---|
| **Paid tier (user-facing analysis)** | **`claude-sonnet-4-6`** + severity-calibration addendum | Best detection quality measured (allergen F1 0.83; only model catching Peanuts *and* Soy). For a safety product, a missed allergen is the catastrophic failure mode — detection quality outranks a 1-point composite difference. |
| **Free tier** | **`claude-haiku-4-5`** + synthesis-binding addendum | Composite 86 at 22% of Sonnet's cost; PFAS F1 1.00 after the binding lever; bounds free-tier COGS to ~$0.09–0.18/user/month. Also makes "better detection model" a truthful paid-upgrade pitch. |
| **Cohere (Command A / A+)** | **Out of the request path** | Haiku beats Command A on every quality axis at equal price. Command A+ measured at composite 59 at 3.4× Command A's cost (post-fix). The Cohere key is a trial key (20 req/min, 1,000 req/month) — structurally non-production regardless. Keep Cohere only for embeddings/rerank on a paid key if review search ships. |

Prompt levers live in `backend/scripts/benchmark/configs/prompts.py` (`MODEL_EXTRAS`); the production
pipeline should adopt the same addenda when the pins change (`claude_query.py`, `claude_agent.py`).

## 2. Measured performance (n=3, 5 GT products, tuned calculator)

| Model | Composite | Allergen F1 (recall) | PFAS F1 | Harm-cal | Valid | LLM $/request |
|---|---|---|---|---|---|---|
| **Sonnet 4.6** (+ lever v2) | **93** | **0.83 (0.71)** | 1.00 | 13/15 | 15/15 | $0.142 |
| Sonnet 4.5 (current pin) | 94 | 0.80 (0.75) | 1.00 | 14/15 | 15/15 | $0.133 |
| **Haiku 4.5** (+ binding lever) | **86** | 0.55 (0.38) | **1.00** | 12/14 | 14/14 | **$0.035** |
| Command A (03-2025) | 76 | 0.45 (0.29) | 1.00 | 9/15 | 14/15 | $0.040 |
| Command A+ (05-2026) | 59 | 0.38 (0.25) | 0.50 | 7/15 | 14/15 | $0.136* |

\* placeholder pricing (Cohere has published no per-token rate for A+); estimate uses Command A rates.

Context that matters when reading this table:
- The harm-calibration column was re-scored by the **tuned calculator** (floor removed, risk-union
  stacking) — before that fix, scorer defects suppressed every model's harm-cal (see §6 of
  MODEL_QUIRKS.md). Composite weights: 30% valid + 25% allergen F1 + 25% PFAS F1 + 20% harm-cal.
- Per-model prompt levers are part of the measured configuration: Haiku's PFAS F1 went 0.00 → 1.00 via
  one synthesis-binding addendum; Sonnet 4.6's harm-cal 1/15 → 13/15 via severity calibration + the
  calculator fix; Command A+ went 16 → 59 via stopping discipline + a harness-parity fix.
- n=3 on 5 products is directional, not definitive; precision was 1.00 for every cell that produced
  output, so the open frontier is recall and calibration.

## 3. Fully-loaded cost per cold request

The benchmark cost column covers LLM tokens only. Production adds:

| Component | Cost | Note |
|---|---|---|
| Analysis (Sonnet 4.6, ~5 tool iterations, 1h prompt cache) | $0.142 | measured |
| Analysis (Haiku 4.5 path) | $0.035 | measured; prompt cache fires (prefix > 4096 tok) |
| Web searches (~5/request) | **$0.005 (Serper)** / $0.040 (Tavily) | search-cost plumbing gap means benchmark cost columns exclude this; estimated from trace search counts |
| Extraction step | ~$0.010 | if moved to Haiku per harness review (#16); currently Sonnet |
| Review embeddings (Cohere) | ~$0.001–0.01 | only if review search ships; gate it |

**Cold request ≈ $0.16 (Sonnet path) · ≈ $0.06 (Haiku path).** A cache-hit request ≈ $0.00 (Supabase
lookup only).

## 4. Unit economics at $7.99 / 100 requests (free: 5/month)

- Net revenue after Stripe (2.9% + $0.30): **$7.46/user/month → $0.0746 per entitled request.**
- A cold Sonnet request ($0.16) costs **2.1×** the per-request revenue. The business is therefore a
  **cache-economics business**: only cache misses cost money, and the analysis catalog is shared
  across all users.

**Break-even cache-hit rate (at 100% quota utilization):**

| Path | Profitable when hit rate exceeds |
|---|---|
| Sonnet 4.6 (paid) | **~55%** |
| Haiku 4.5 (free/triage) | ~0–20% (nearly always) |

Typical SaaS quota utilization is 30–50%, roughly doubling the slack: at 40 requests/month consumed,
Sonnet breaks even near a 0% hit rate and earns ~$4–6/user at 50–85% hit rates.

**Free-tier exposure:** 5 requests × miss rate × $0.06 ≈ **$0.09–0.18 per free user/month** on Haiku.
On Sonnet it would be ~3× that — the seat assignment is the cost control.

## 5. Scaling projection

Assumptions (stated, adjustable): paid users consume 40/100 on average; free users consume 5/5; mix of
1 paid : 5 free; cache-hit rate grows with scale because product popularity is Zipf-shaped; Serper for
search; paid=Sonnet, free=Haiku.

| Stage | Assumed hit rate | Monthly LLM COGS per 1,000 paid + 5,000 free | Net revenue | Gross margin |
|---|---|---|---|---|
| Early | 40% | $3.8k (paid) + $0.9k (free) = **$4.7k** | $7.5k | **~37%** |
| Growth | 65% | $2.2k + $0.5k = **$2.7k** | $7.5k | **~64%** |
| Mature | 85% | $0.96k + $0.22k = **$1.2k** | $7.5k | **~84%** |

Structural property worth underlining: **COGS per request falls as the user base grows** (shared
catalog). Fixed infra is second-order at these scales: Cloudflare Containers + Supabase Pro ≈
$50–150/month; Stripe is in the net-revenue line; Anthropic throughput is a rate-limit tier, not an
architecture problem.

## 6. Margin levers, in priority order

1. **URL canonicalization** (harness review #12) — tracking params currently fragment the cache key;
   every fragment is a ~$0.16 duplicate analysis. Highest-ROI fix for the business model: the adapters
   already extract canonical product IDs (ASIN etc.).
2. **Client cache-before-call** (#11) — the extension never consults its local IndexedDB cache before
   POSTing today.
3. **`ingredient_research` precompute** — per-ingredient research cache (already on main) makes cold
   products partially warm; cold-cost trends toward the Haiku floor as the ingredient table fills.
4. **Batch API for catalog refreshes** — stored full HTML + Anthropic Batch (50% off) makes re-analysis
   sweeps (e.g., after scorer/prompt changes) half-price.
5. **Search provider** — Serper ($0.001) vs Tavily ($0.008) is an 8× swing on the search line.

## 7. Risks & caveats

- **Sample size:** n=3 over 5 labeled products; rankings were stable across n=1 → n=3 and across the
  calculator retune, but absolute numbers carry noise. The 6-product held-out set exists for the next
  validation round.
- **Haiku recall (0.38)** is the free tier's known quality gap — acceptable for a free tier, wrong for
  paid. If free-tier quality complaints matter commercially, a Haiku-flags→Sonnet-escalation triage
  keeps blended cost ≈ Haiku while recovering most recall.
- **Cache staleness vs margin tension:** the server cache currently has no TTL/version gating (harness
  review #18); aggressive caching is the margin engine but stale safety data is a product risk. Ship
  `analysis_version` + a 90-day refresh via Batch.
- **Cohere trial limits** make any Cohere-in-request-path plan a non-starter until a production key is
  priced in; embeddings-only usage is cheap but should be gated to actual feature usage.
- **A+ pricing unknown** — revisit only if Cohere publishes rates that undercut Command A *and* the
  stopping-discipline fix holds on a fuller eval.
- Benchmark measures the analysis step on pre-extracted product data; production adds
  extraction/scraping variance per retailer (see `AUDIT.md` for per-retailer capture quality).

## 8. Implementation checklist (when approved)

- [ ] Pin `claude-sonnet-4-6` in `backend/src/infrastructure/claude_query.py` + `claude_agent.py`
      (one knob each post-parameterization); adopt the severity-calibration addendum in the production
      analysis prompt.
- [ ] Add tier routing: free → `claude-haiku-4-5` + binding addendum; paid → Sonnet 4.6.
- [ ] Ship canonicalization + client cache-check (margin levers 1–2).
- [ ] Wire `search_count`/search cost into token tracking (close the bookkeeping gap).
- [ ] Re-analyze cached catalog via Batch API after the pin change (`analysis_version` bump).
- [ ] Validate tier routing on the held-out set before rollout.

---

*Artifacts: `backend/scripts/benchmark/output/{tier_a5_n3,sonnet46_sevcal_n3}/{report,comparison}.html`,
`replay_harm.py` (offline re-scoring), LangSmith project `ruh-benchmark` (full traces). Total evidence
cost: ≈ $13.5 of $400 Anthropic credits; 327/1,000 monthly Cohere trial requests.*
