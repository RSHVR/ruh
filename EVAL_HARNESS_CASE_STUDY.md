# Building a Trustworthy LLM Agent Eval: A Debugging Case Study

*A multi-hour session turning a silently-broken agent benchmark into a fair, observable, prompt-tuned harness — with the actual bugs, fixes, and measured before/after numbers.*

---

## Executive summary

This is a field report from a single working session on the **Ruh** product-safety analyzer (a Chrome extension + FastAPI backend that flags allergens, PFAS, and other harmful substances in consumer products and derives a 0–100 harm score). The artifact under work is a **5-config agent benchmark** in `backend/scripts/benchmark/`: five different ways of wiring the *same* task — analyze a product's pre-extracted ingredient list, do web research, and emit a `ProductSafetyAnalysis` JSON — scored against a hand-labeled ground truth.

The five configs:

| Config | Architecture |
| --- | --- |
| `claude_agentsdk_async_cached` | Anthropic `AsyncAnthropic`, hand-rolled tool loop |
| `cohere_asyncv2_cached` | Cohere `AsyncClientV2`, native `response_format=json_schema` |
| `claude_langgraph12_cached` | LangGraph `create_react_agent` (Claude) |
| `cohere_langgraph12` | LangGraph `create_react_agent` (Cohere) |
| `claude_cohere_coordinated_cached` | LangGraph `StateGraph`: Cohere does cheap labor, Claude adjudicates |

The session began with a benchmark that *looked* like it was working and ended with one I'd actually trust. Between those two states sat: a disk-full Docker recovery, six latent migration bugs, a prior run that was silently **ungrounded** (empty knowledge base), two LangGraph configs doing **zero real research** while scoring well, a harness validation bug that made the most-thorough config look like the *worst*, a degenerate ground-truth set that graded `0÷0`, and finally a held-out-validated prompt-tuning loop.

The headline lesson, in five costumes: **a passing eval can be silently wrong, and apparent model failures are usually harness bugs.** The most expensive misjudgment available here was to read the first leaderboard and conclude "Cohere can't detect allergens" or "the Agent SDK config can't produce valid JSON." Both were false; both were the harness.

All work lives on branch `harness-fixes-observability` (9 commits, `09c0655..af12799`). Every number below was re-aggregated from the per-run `output/*/runs/<config>/<product>/run0/metrics.json` files.

---

## 1. Environment recovery (brief)

Docker was down because the disk was full. The recovered ~26 GB came almost entirely from **Docker's build cache**, which is invisible to `docker images` and only shows under `docker system df` (pruning must hit build cache + dead containers + dangling volumes, not just images). A macOS gotcha: `df -h /` reports the **sealed, read-only system volume**, not real free space — the number that matters is `df -h /System/Volumes/Data`.

Local Supabase had to come up because the benchmark's **knowledge base** — 32 priority allergens + 75 PFAS compounds — lives in Postgres, and the agents' entire grounding depends on it. This dependency is the seed of bug #3.

---

## 2. The migration smoke test: 6 real bugs surfaced by replaying from zero

Bringing up a clean local Supabase means replaying **every migration from an empty database**. Production never does this — it applies migrations by hand in the SQL editor, one at a time, against a database that already has the prior state. That manual path **hides** an entire class of bug. Clean-slate replay is a real integration test, and it immediately failed six ways (commit `09c0655`):

| # | File | Bug | Fix |
| --- | --- | --- | --- |
| a | `000_drop_all.sql` | `DROP POLICY ... ON <table>` on tables that don't exist yet. `IF EXISTS` guards the *policy*, not the *table*, so it still errors on a fresh DB. | Drop the redundant policy statements; `DROP TABLE ... CASCADE` removes policies anyway. |
| b | two files both versioned `002` | `schema_migrations` primary-key collision on version `"002"`. | Rename one → `0021_seed_allergens_pfas.sql`. |
| c | `008_update_search_reviews_rpc.sql` | `CREATE OR REPLACE FUNCTION` cannot change a function's **return type** (illegal in Postgres). | `DROP FUNCTION` first, then create. |
| d | `010_create_ingredient_research.sql` | A GIN index expression used `array_to_string`, which is `STABLE` — index expressions must be `IMMUTABLE`. | Wrap it in an `IMMUTABLE` SQL helper. |
| e | `012_fix_security_findings.sql` | Carried a **stale copy** of a function that reverted an earlier migration's columns; used unsupported `CREATE POLICY IF NOT EXISTS`; and **never enabled RLS** on `ingredient_research` — so its policy was dormant and the table was exposed. | Reconcile the function to the `008` column set; drop the unsupported syntax; `ENABLE ROW LEVEL SECURITY`. |
| f | Supabase CLI | `storage-api` crashed on startup. | Upgrade CLI `2.58 → 2.102`. |

Bug (e) is the scary one: a table that *looked* protected (it had a policy) was actually wide open because RLS was never enabled, so the policy never engaged. Nobody noticed because nobody ever replayed the stack cleanly.

> **Lesson:** Clean-slate replay is a real test. "Apply by hand, one at a time, against existing state" never tests your migrations — it tests 1-step deltas against a moving target.

---

## 3. The benchmark was silently invalid: an empty knowledge base

A prior "smoke" run (preserved as `output/smoke_INVALID_no_kb/`) looked like the three Claude configs had all hard-failed: `api_error`, ~150 ms, **0 tokens**, 15/15 runs. The Cohere configs "succeeded." A natural first read: *Anthropic outage, or a bad key.*

The investigation ruled out the obvious suspects one at a time — transient error, rate limit, bad API key, wrong model ID, even the prompt-cache beta header — each verified working **in isolation**. The root cause was upstream of all of them: the benchmark's `.env` pointed at a **production Supabase that no longer resolves** (DNS failure). So `get_all_allergens()` returned `[]`, the KB system block rendered **empty**, and the Claude configs set `cache_control` on that now-empty text block — which Anthropic **400s** on (you can't cache an empty block). Every Claude config failed in ~150 ms before doing any work.

The Cohere configs didn't 400 — they have no cache block — so they "succeeded." But they succeeded **with the same empty KB**, meaning the entire prior benchmark was **ungrounded**: the agents had no allergen/PFAS list to match against. Every "result" was invalid.

Confirmed in the aggregated metrics:

```
output/smoke_INVALID_no_kb:
  claude_agentsdk_async_cached      fails=15 {api_error: 15}  cost=$0.00  tokens=0
  claude_langgraph12_cached         fails=15 {api_error: 15}  cost=$0.00
  claude_cohere_coordinated_cached  fails=15 {api_error: 15}
  cohere_asyncv2_cached             fails=4  {schema_invalid: 4}  ← "succeeded" but ungrounded
  cohere_langgraph12                fails=0                       ← "succeeded" but ungrounded
```

The fix was one line of config: point the benchmark at the **local** Supabase with the seeded KB. But the lesson is the point.

> **Lesson:** A passing run can be silently wrong. Verify the *inputs*, not just the absence of exceptions. An empty KB produced both a loud failure (Claude) and a quiet one (Cohere) — the quiet one is more dangerous, because it produces *plausible-looking scores from nothing.*

---

## 4. LangSmith observability — and the silent failure it caught in minutes

Next I wired **LangSmith** tracing (free Developer tier: 5,000 traces/month) so every run produces a turn-by-turn **reason → act → observe** waterfall (commit `1e0a348`, see `observability.py` + `OBSERVABILITY.md`). The design is non-invasive: a `root_run(...)` context manager opens one root trace per `(config, product, run)` and is a **cheap no-op when `LANGSMITH_TRACING` is unset**, so the harness still runs fully offline. Per-config instrumentation matches each SDK: `wrap_anthropic()` for the AsyncAnthropic config, `@traceable(run_type="llm")` for the Cohere-SDK config, and **auto-tracing** for the three LangChain/LangGraph configs (which, usefully, also captured tool calls the in-house tracer had missed).

```python
@contextlib.contextmanager
def root_run(name, *, metadata=None, tags=None):
    if not tracing_enabled():
        yield None            # offline: zero overhead
        return
    from langsmith import trace as _ls_trace
    with _ls_trace(name=name, run_type="chain", metadata=metadata, tags=tags) as rt:
        yield rt
```

The traces immediately revealed something the aggregate metrics had **rewarded**: the two LangGraph configs recorded **0 tool calls**. Pulling their tool-run outputs from the LangSmith API showed every `web_search` returning:

```json
{"error": "There is no current event loop in thread 'asyncio_3'"}
```

`cohere_langgraph` had **7/7** searches fail; `claude_langgraph` had **11/14** fail. They were doing **zero real research** and still scoring respectably — by guessing. "Fast and cheap" was "fast and cheap *because it did nothing.*"

> **Lesson:** Observability catches silent failures that aggregate metrics *reward*. A scorecard tells you the answer; a trace tells you whether the agent earned it. Read the reason→act→observe loop, not just the score.

---

## 5. The LangGraph async-tool bug

Root cause (commit `593b66b`): `create_react_agent` runs **synchronous** tools in a worker-thread executor when you call `.ainvoke()`. The sync tool bridged to the async search service via `asyncio.get_event_loop()` — which **raises** in a thread that has no running loop (Python 3.12 removed the implicit-loop fallback). Every search returned an error JSON, which the agent dutifully ignored and proceeded to hallucinate around.

The fix is to make the LangChain tools `async def`, so LangGraph awaits them on the live loop, and to push the sync Supabase lookup off-loop via `asyncio.to_thread`:

```diff
 @tool
-def web_search(query: str, search_type: str = "general") -> str:
+async def web_search(query: str, search_type: str = "general") -> str:
     ...
-    loop = asyncio.get_event_loop()
-    result_str = loop.run_until_complete(_do_search())   # raises in a worker thread
+    result_str = await search_service.search(query=query, search_type=search_type)
```

After the fix: `cohere_langgraph` **9/9** searches returned content; `claude_langgraph` **18/18**. This reframed the whole comparison — the LangGraph configs' earlier numbers were **luck**, not capability.

---

## 6. The pivotal correction: "schema-invalid" was a harness bug, not the model

This is the core of the article.

With grounding and search fixed, a leaderboard finally appeared — and it looked damning for `claude_agentsdk`: only **5/15 valid outputs**, the *worst* of the five. The user pushed back hard, and rightly: *"It's hard to believe agents can't even match structured data. Is the Agent SDK config producing invalid JSON?"*

It wasn't. The investigation (commit `88c0641`) found the `schema_invalid` failures were almost entirely a **single field**: `research_sources.N.type` — **citation metadata**, a label on a source URL. The Pydantic `SourceType` enum allowed `{manufacturer_website, regulatory_action, scientific_study, legal, consumer}`, and the models emitted perfectly reasonable synonyms — `consumer_report`, `consumer_reports`, `legal_action` — **that the prompt itself asks for** (it instructs the agent to run a "legal" search and a "consumer" search). One mismatched citation label `raise`d a `ValidationError` and **discarded an otherwise-complete, fully valid safety analysis** — allergens, PFAS, and concerns all correct.

Two further facts sharpened the picture. First, **100% of `schema_invalid` runs across all configs were "metadata-only"** — not one had a real content problem; every config would be 15/15 valid with the fix. Second, only `cohere_asyncv2` **enforced** the schema at generation (native `response_format`); the other four were **parse-and-pray** — they free-text the JSON and the harness parses it. So the config that *researched the most* (`claude_agentsdk`, which emitted the most `research_sources`) hit the enum gap **most often**. The comparison was structurally **unfair**.

The fix relaxes the metadata field so a citation label can never invalidate a safety analysis: add an `other` member and a `before` validator that normalizes common variants and **falls back to `other` instead of raising**. (A real production bug too — the live app discarded valid analyses for the same reason.)

```python
class SourceType(str, Enum):
    manufacturer_website = "manufacturer_website"
    regulatory_action    = "regulatory_action"
    scientific_study     = "scientific_study"
    legal                = "legal"
    consumer             = "consumer"
    other                = "other"   # catch-all: a citation label never invalidates an analysis

class ResearchSource(BaseModel):
    type: SourceType = Field(default=SourceType.other)
    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, v):
        s = str(v or "").strip().lower()
        s = _SOURCE_TYPE_ALIASES.get(s, s)        # consumer_report→consumer, legal_action→legal, …
        return s if s in {e.value for e in SourceType} else SourceType.other.value
```

A second coercion in the same commit: `PfasDetected.cas_number` is `null → ""`, because models emit `null` when the CAS number is unknown.

**The impact was dramatic and entirely a harness artifact.** `claude_agentsdk`'s "terrible 5/15 validity" vanished — it went **15/15 valid**, and its composite score jumped from **~57 (looked worst)** to **~77 (tied for first)** with **zero change to the safety content**. The model had been right the whole time; the harness had been throwing its work away.

> **Lesson — the one to lead the article with:** Apparent model failures are usually harness bugs. Over-strict validation on **non-graded metadata** silently discards good outputs, and if one config enforces its schema while others parse-and-pray, the ranking is an **artifact of the harness**. Make the comparison fair before trusting the leaderboard.

---

## 7. Ground truth was degenerate; expanding it; honest pushback

With validity fixed, the next layer of rot showed: the original ground truth had only **5 labeled products, all with empty `expected_allergens`**. So allergen precision/recall was a degenerate **`0 ÷ 0`** — the dashboard's "0.00 allergen accuracy" didn't mean "the models are bad," it meant **"nothing to grade."**

I expanded it to **15 products, 8 carrying real allergen labels** (commit `4d1ad44`):

| Product | Expected allergens |
| --- | --- |
| `skippy_creamy_peanut_butter` | Peanuts, Soy |
| `annies_mac_cheese_classic` | Wheat, Milk |
| `burts_bees_lip_balm_beeswax` | Lanolin, Coconut, Fragrance Mix I/II |
| `mrs_meyers_dish_soap_lavender` | Cocamidopropyl Betaine, Methylisothiazolinone, Fragrance Mix I/II |
| `tfal_nonstick_skillet` | Nickel, Chromium (+ PTFE) |
| `all_clad_d3_stainless_skillet` | Nickel, Chromium |
| `edge_la_mer_non_english` | Lanolin, Fragrance Mix I/II |
| `tide_pods_original` | Fragrance Mix I/II |

**The labeling rule was strict: only KB substances actually present in the ingredient list.** When the user asked to *also* label corn and "every derivative," I pushed back — and this is a methodological point, not pedantry:

- **Corn isn't in the KB.** The agents are explicitly told they can only flag KB substances. Labeling corn as "expected" would penalize correct behavior.
- **Cascading into trace derivatives would make over-flagging the "correct" answer.** The benchmark exists in part to *measure over-flagging.* An over-inclusive answer key would **reward the exact pathology being measured** — a textbook Goodhart inversion, where optimizing the metric destroys the thing the metric was for.

The Fragrance Mix and stainless-steel Nickel/Chromium labels were deliberately marked **borderline-inclusive** so the caveat is honest: those are the labels most open to dispute.

A second improvement in the same commit made the harness durable: `build_comparison.py` now **recomputes** correctness *and* schema validity **fresh from each saved analysis** against the *current* schema and ground truth — so schema fixes and GT edits flow into the report **with no re-run** (this is what made the "every config is now 15/15 valid" verification in §6 a recompute, not a $6 re-run). The composite was reweighted to **30% valid-rate + 25% PFAS F1 + 25% allergen F1 + 20% harm-in-range**.

> **Lesson:** Ground-truth quality *is* the eval. Degenerate (all-empty) labels and over-inclusive labels both mislead — the first hides everything, the second inverts the signal. The answer key must be a *calibrated reference*, not a maximalist wish-list.

---

## 8. Synonym-aware scoring (and why it barely moved the numbers)

The scorer was made to canonicalize **both detected and expected** names through the **KB's own synonym table** before comparing — `dairy/whey/casein → Milk`, `CAPB → Cocamidopropyl Betaine`, `sulfur dioxide → Sulfites` (commit `2590248`, `kb_synonyms.json` exported from the allergen/PFAS synonym columns). This is **deterministic and grounded in the KB**, not fuzzy matching.

The interesting result: it **barely changed the numbers** — a *good* outcome, because it **confirmed the recall figures were already honest.** Clear allergens were matching on canonical names already; the low fragrance/metal recall was **real under-detection**, not a naming artifact. A synonym layer that *did* move the numbers would have meant the prior numbers were lies; one that doesn't is a proof of honesty.

> **Lesson:** Separate deterministic from probabilistic work. KB matching is a **code-level join** through a synonym table, not an LLM string-emit. Let the LLM *research*; let code *match*. (And use a calibration layer to *check* your metrics, not just to inflate them.)

---

## 9. Enforcing structured output at generation — and verify-cheap-first

The user's call: stop parse-and-pray, **enforce structured output on all configs**, re-run. Implemented with **three different mechanisms** because each SDK enforces differently (commit `0549b7c`):

- **`claude_langgraph12`**: `create_react_agent(response_format=ProductSafetyAnalysis)`
- **`claude_cohere_coordinated`**: the final adjudication node uses `llm.with_structured_output(ProductSafetyAnalysis, include_raw=True)`
- **`claude_agentsdk`**: a **forced `submit_analysis` tool** whose `input_schema` *is* the Pydantic JSON schema — once research is done, the model is forced to call it, so the final analysis is **schema-shaped tool input**, never parsed free text:

```python
SUBMIT_TOOL = {
    "name": "submit_analysis",
    "description": "Submit the final product safety analysis as structured data.",
    "input_schema": ProductSafetyAnalysis.model_json_schema(),
}
# ...when research is done, force the call:
final = await client.messages.create(
    ..., tools=[SUBMIT_TOOL],
    tool_choice={"type": "tool", "name": "submit_analysis"},
)
```

A **cheap one-product verification (~$0.50) before the $6 full run** caught two breakages that would otherwise have burned the budget. First, **`response_format` is broken for `ChatCohere` in `create_react_agent`** — it raises *"last message is not a ToolMessage or HumanMessage"* (upstream incompatibility); `cohere_langgraph` was reverted to parsing, valid under the relaxed schema. Second, **the forced tool sometimes nested the payload under `{"analysis": {...}}`** — added an unwrap:

```python
if isinstance(analysis, dict) and "analysis" in analysis and "product_name" not in analysis:
    analysis = analysis["analysis"]
```

The full enforced run (`output/smoke_oldprompt_enforced/`, old prompts, schema enforced) then completed clean: **75 runs, $7.97, 0 failures, all 15/15 valid**. The result was a near-tie — `claude_agentsdk` **75** / `cohere_asyncv2` **75**:

```
output/smoke_oldprompt_enforced (composite):
  75  cohere_asyncv2_cached            valid=14/15  harm_ok=9/15   allgF1=0.40  pfasF1=1.00
  75  claude_agentsdk_async_cached     valid=15/15  harm_ok=4/15   allgF1=0.58  pfasF1=1.00
  64  cohere_langgraph12               valid=15/15  harm_ok=5/15   allgF1=0.75  pfasF1=0.33
  56  claude_langgraph12_cached        valid=15/15  harm_ok=1/15   allgF1=0.64  pfasF1=0.33
  56  claude_cohere_coordinated_cached valid=15/15  harm_ok=1/15   allgF1=0.67  pfasF1=0.33
```

> **Lesson:** Enforce structured output **at generation** — forced tool / `response_format` / `with_structured_output` — not at parse time. Each provider does it differently; expect provider-specific quirks. And **verify on one example before spending on a full run.**

---

## 10. The real model quirks, finally measurable

With a tight, fair harness, the *genuine* differences emerged — and all three are **flagging-discipline** problems, not capability ceilings. **Cohere under-detects allergens**: `cohere_asyncv2` recall ~**29%** (`tp/fp/fn = 6/3/15` on old prompts), stopping early. **Claude over-flags concerns and over-scores harm**: the Claude configs hit harm-in-range on only **1–4 / 15**, with allergen false positives of **11–28**. **The LangGraph configs over-flag PFAS** — precision ~**20%** (`pfas tp/fp = 1/4`), hallucinating fluorinated cosmetic silicones as PFAS.

The mechanism is crucial: **the harm score is not emitted by the model.** A deterministic `HarmScoreCalculator` derives it from the flagged substances, so "Claude over-scores harm" literally *means* "Claude over-flags concerns and over-rates severity." All three quirks reduce to one knob — **flagging discipline** — which is exactly what a prompt can move.

> **Lesson:** Prompt-engineer against **measured tendencies, per model**. And know which of your numbers are LLM outputs vs. downstream computations — harm here is downstream of flagging, so you fix it by fixing flagging.

---

## 11. Iterative prompt engineering against a held-out set

The user set the discipline explicitly: *improve coverage, but **do not overfit the fixed eval** — validate on random products.* So I built a **held-out set of 6 real, non-eval products** (`datasets/held_out_v1.json` + `held_out_gt_v1.json`), each chosen to catch a specific quirk:

| Held-out product | Catches |
| --- | --- |
| Nutella | multi-allergen recall (Tree Nuts / Milk / Soy) |
| Lansinoh pure lanolin | single-ingredient allergen recall (Lanolin) |
| Mariani dried apricots | synonym recall (sulfur dioxide → Sulfites) |
| Cuisinart PTFE pan | **true** PFAS positive (must still fire) |
| GreenPan ceramic pan | PFAS **false-positive** control (must stay clean) |
| Pyrex glass cup | benign/inert control — harm must be **~0** |

The method: **diagnose on the eval + traces → change the prompt to target the *tendency* (never a product) → measure on held-out.** A change counts only if it helps held-out **without regressing the eval.**

### Round 1 — calibration, KB-discipline, per-model addenda (commit `2508df4`)

A shared **CALIBRATION rule** ("presence ≠ harm; an inert/benign product should have ZERO entries; default `low` severity; verify each entry is actually in the ingredient list before adding it"), a stronger **KB-discipline rule** ("fluorinated cosmetic silicones are NOT PFAS → `other_concerns`, **never** `pfas_detected`"), an **allergen-thoroughness rule** ("check EVERY ingredient + synonyms"), plus **per-model addenda** selected by `base_prompt(model)`:

```python
CLAUDE_ADDENDUM = """...You tend toward over-caution — flagging speculative concerns and
over-rating severity. ...Prefer omission over a weak or "just in case" flag. Default to
"low" severity; a benign everyday product should yield few or no concerns."""

COHERE_ADDENDUM = """...Be exhaustive on allergen detection. Go through EACH ingredient
one by one and check it (and its synonyms) against the full allergen knowledge base
before you finish. ...Thoroughness on allergens is your priority."""

def base_prompt(model=""):
    m = model.lower()
    addendum = COHERE_ADDENDUM if ("cohere" in m or "command" in m) else CLAUDE_ADDENDUM
    return STATIC_BASE_PROMPT + "\n\n" + addendum
```

**Held-out result:** `cohere_asyncv2` allergen recall **29% → 100%**; PFAS false-positives **eliminated** (GreenPan clean for all configs). But harm calibration was only *partly* fixed — `claude_agentsdk` got the Pyrex cup to **0**, while `claude_langgraph` still scored the glass cup at **58**.

### Round 2 — scope `other_concerns` to substance hazards only (commit `af12799`)

The traces showed *why* the benign glass cup over-scored: configs were flagging **non-substance** "concerns" — mechanical (shattering, thermal shock), legal/marketing (false advertising, country-of-origin), quality (durability). A glass cup has none of the harmful *substances* the analysis is about, but it has plenty of *opinions* about glass. Added a **SCOPE rule**:

```diff
 3. **OTHER CONCERNS**
+   - SCOPE: other_concerns are for HARMFUL SUBSTANCES present in the product ONLY ...
+     NOT product quality or physical safety.
+   - DO NOT include: physical/mechanical hazards (breakage, shattering, thermal shock...),
+     product-quality issues (durability, country-of-origin), or marketing/labeling disputes.
+   - A recall or lawsuit counts ONLY if it concerns a harmful SUBSTANCE (e.g. benzene),
+     never if it concerns breakage, quality, or advertising.
```

**Held-out result:** `claude_langgraph` Pyrex **58 → 0**; harm calibration up; round-1 allergen/PFAS wins preserved; the real PTFE hazard still detected by all configs (no over-suppression).

Held-out composites confirm the trajectory (`output/round1_heldout`, `round2_heldout`):

| Config | R1 composite | R2 composite | R2 harm-in-range |
| --- | --- | --- | --- |
| `claude_agentsdk_async_cached` | 90 | **93** | 4/6 |
| `claude_langgraph12_cached` | 81 | **88** | 3/6 |
| `claude_cohere_coordinated_cached` | 84 | **87** | 2/6 |
| `cohere_langgraph12` | 82 | **85** | 3/6 |
| `cohere_asyncv2_cached` | 60 | **80** | 3/6 |

### Final eval confirmation

Re-running the **new prompts on the original 15 products**, *both runs enforced* so the comparison isolates the **prompt effect** (`smoke_oldprompt_enforced` → `smoke`):

| Config | Composite old→new | Harm-in-range old→new | Allergen FP old→new | Cost old→new |
| --- | --- | --- | --- | --- |
| `claude_agentsdk_async_cached` | **75 → 85** | 4 → **8** /15 | 13 → **5** | $3.00 → **$1.88** |
| `cohere_asyncv2_cached` | **75 → 84** | 9 → **13** /15 | 3 → 3 | $0.64 → $0.62 |
| `claude_cohere_coordinated_cached` | **56 → 66** | 1 → **8** /15 | 11 → **7** | $0.80 → $0.67 |
| `cohere_langgraph12` | **64 → 67** | 5 → **9** /15 | 4 → 6 | $0.76 → $0.77 |
| `claude_langgraph12_cached` | **56 → 61** | 1 → **4** /15 | 15 → **7** | $2.78 → $2.41 |

**Composite rose for all five configs. Harm calibration ~doubled** (`claude_agentsdk` 4→8, `cohere_asyncv2` 9→13, coordinated 1→8). **Allergen false positives dropped** (`claude_agentsdk` 13→5, `claude_langgraph` 15→7). And cost *fell* — `claude_agentsdk` $3.00 → $1.88 — because **calibrated reasoning is less verbose**: telling the model to stop flagging speculatively cut its output tokens.

**Honest caveats** (recorded so the article doesn't overclaim):

- Allergen recall **dipped slightly** for the configs that had been over-flagging — a precision/recall **rebalance**, not a free win. Watch the trade-off.
- Some eval PFAS "false positives" may be a **GT-labeling gap** rather than model error — CeraVe/MAC may genuinely contain a KB fluoro-silicone we didn't label.
- PFAS on the eval is effectively **n=1** (one true positive, T-fal/Cuisinart), so PFAS F1 swings hard on a single call. The held-out PFAS controls (GreenPan negative, Cuisinart positive) exist precisely to add signal the eval lacks.
- The Fragrance Mix and stainless Nickel/Chromium labels are **borderline-inclusive** by design.

> **Lesson:** Diagnose on the eval, **validate on held-out** fresh products; a change counts only if it generalizes. Target the *tendency*, never the product. Watch precision/recall trades. Iterate cheaply and observe deltas.

---

## Final standings

On the tight, enforced, prompt-tuned harness (`output/smoke`):

| Rank | Config | Composite | Allergen recall | Harm-in-range | Cost (15 products) |
| --- | --- | --- | --- | --- | --- |
| 1 | `claude_agentsdk_async_cached` | **85** | best (F1 0.76) | 8/15 | $1.88 |
| 2 | `cohere_asyncv2_cached` | **84** | lower (F1 0.45) | **13/15** | **$0.62** |
| 3 | `cohere_langgraph12` | 67 | 0.65 | 9/15 | $0.77 |
| 4 | `claude_cohere_coordinated_cached` | 66 | 0.70 | 8/15 | $0.67 |
| 5 | `claude_langgraph12_cached` | 61 | 0.70 | 4/15 | $2.41 |

`claude_agentsdk` takes the top composite (best allergen recall). But `cohere_asyncv2` is the **value pick**: one point behind, **best harm calibration (13/15)**, at **~3× lower cost ($0.62 vs $1.88)**. The LangGraph and coordinated configs trail on harm calibration and PFAS precision.

The more important result than the ranking: **every one of these numbers is now trustworthy**, where on the morning's first leaderboard *none of them were.*

---

## Lessons for setting up LLM evals

1. **A passing eval can be silently invalid.** Verify the *inputs* — is the knowledge base populated? Is search actually returning content? An empty KB produced both a loud failure and a quiet one; the quiet one is worse.
2. **Apparent model failures are usually harness bugs.** Over-strict metadata validation, cache-control on an empty block, an async tool that can't reach its event loop — all looked like the model failing. None were.
3. **Make the comparison fair.** If one config enforces its output schema and the others parse-and-pray, the ranking measures your harness, not the models. `claude_agentsdk` went 57→77 composite from a *citation-label* fix.
4. **Observability catches what aggregate metrics reward.** Read the reason→act→observe trace. "Fast and cheap" was "did nothing." A score is an outcome; a trace is the work.
5. **Ground-truth quality *is* the eval.** All-empty labels grade `0÷0`; over-inclusive labels invert the signal (Goodhart). The answer key is a calibrated reference, not a wish-list — push back when asked to inflate it.
6. **Separate deterministic from probabilistic.** KB matching is a code-level join through a synonym table; the LLM should research, code should match. A calibration layer that *doesn't* move your numbers proves they were honest.
7. **Enforce structured output at generation, per provider** (forced tool / `response_format` / `with_structured_output`), and **verify on one example before the full run.** A ~$0.50 check caught two breakages that would have wasted a ~$6 run.
8. **Prompt-engineer against measured tendencies, per model** (Claude over-cautious → calibrate down; Cohere concise → be exhaustive). Know which numbers are model outputs vs. downstream computations — harm is downstream of flagging discipline.
9. **Anti-overfitting: diagnose on the eval, validate on a held-out set of fresh real products.** A change counts only if it generalizes. Watch precision/recall trade-offs honestly.
10. **Iterate cheaply and observe deltas:** diagnose → targeted fix → measure on held-out → confirm on eval. Make the harness recompute from saved outputs so schema/GT fixes flow in without re-running.

---

## Appendix — artifacts

**Branch:** `harness-fixes-observability` (9 commits, `09c0655..af12799`)

| Commit | What |
| --- | --- |
| `09c0655` | Fix Supabase migrations to apply cleanly on a fresh database (6 bugs) |
| `1e0a348` | Add LangSmith observability + agent comparison report |
| `593b66b` | Fix LangGraph tools failing on a missing event loop (async tools) |
| `88c0641` | Stop citation metadata from invalidating valid analyses (SourceType relax) |
| `4d1ad44` | Expand ground truth to 15 products; recompute scoring fresh |
| `2590248` | Score detections synonym-aware against the KB synonym table |
| `0549b7c` | Enforce structured output at generation across configs |
| `2508df4` | Prompt round 1: calibration + KB-discipline + per-model addenda |
| `af12799` | Prompt round 2: scope `other_concerns` to substance hazards only |

**Key source files**
- `backend/scripts/benchmark/configs/prompts.py` — shared prompt, calibration/scope rules, `base_prompt(model)` addenda
- `backend/scripts/benchmark/configs/*.py` — the 5 configs (+ `tool_schemas.py` async-tool fix, `registry.py`)
- `backend/scripts/benchmark/build_comparison.py` — fresh recompute of validity + correctness; composite weighting; `comparison.html`
- `backend/scripts/benchmark/observability.py` + `OBSERVABILITY.md` — LangSmith `root_run` wiring
- `backend/src/domain/extraction_schemas.py` — `ProductSafetyAnalysis`, relaxed `SourceType`, `cas_number` coercion
- `backend/supabase/migrations/` — the 6 migration fixes
- `backend/scripts/benchmark/datasets/` — `ground_truth_v1.json` (15), `held_out_v1.json` / `held_out_gt_v1.json` (6), `kb_synonyms.json`

**Output directories (each `runs/<config>/<product>/run0/{metrics.json,analysis.json}`)**

| Dir | State |
| --- | --- |
| `output/smoke_INVALID_no_kb` | the ungrounded (empty-KB) invalid run |
| `output/smoke_langgraph_broken` | pre async-tool-fix |
| `output/smoke_pre_enforcement` | schema-fixed, before generation-time enforcement |
| `output/smoke_oldprompt_enforced` | old prompts, enforced (75 runs, $7.97, 0 fail) |
| `output/round1_heldout`, `output/round2_heldout` | held-out validation per prompt round |
| `output/smoke` | **final**: new prompts, enforced |
| `output/comparison.html` | rendered side-by-side report |
