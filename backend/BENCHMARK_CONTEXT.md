# Benchmark Suite Context - Resume Point

**Last Updated:** 2026-02-06

## Current Status: Implementation Complete, Awaiting Products

The rigorous benchmark test suite for Claude vs Cohere agent comparison is fully implemented and ready to run. Only pending item is user-provided Amazon product URLs for testing.

---

## What Was Built

### Problem Being Solved

The original case study had methodological flaws:

- N=1 runs (no statistical power)
- Temperature mismatch (Claude ~1.0, Cohere 0.3)
- No tracing of what models searched vs what they selected
- Single product tested

### Solution: New Benchmark Suite

Location: `backend/scripts/benchmark/`

| File               | Purpose                                          |
| ------------------ | ------------------------------------------------ |
| `config.py`        | Controlled parameters (temp=0.3 for all agents)  |
| `products.py`      | Test product definitions (needs user URLs)       |
| `runner.py`        | Main orchestrator                                |
| `metrics.py`       | Statistical analysis (CI, t-tests, CV)           |
| `report.py`        | Markdown report generation                       |
| `tracer.py`        | Detailed tool call tracing                       |
| `traced_search.py` | Search wrapper that captures all queries/results |

### Key Features

1. **Fair comparison**: Temperature=0.3 for ALL agents
2. **Statistical rigor**: 5 runs per product per agent, paired t-tests, confidence intervals
3. **Full tracing**: Every tool call, search query, and result captured
4. **Comparison reports**: Side-by-side what each agent searched vs included

---

## Agent Modifications Made

### Claude Agent (`src/infrastructure/claude_agent.py`)

- Added `temperature` parameter to `__init__`
- Passes temperature to all 4 `messages.create()` calls
- Default remains 1.0 for backward compatibility

### LangGraph Agent (`src/infrastructure/langgraph_agent.py`)

- Made temperature configurable (was hardcoded 0.3)
- Fixed prompt to explicitly allow Reddit as valid evidence source

### Cohere Native Agent (`src/infrastructure/cohere_native_agent.py`)

- Made temperature configurable
- Fixed evidence requirements to include Reddit sources

---

## Output Files Generated

When benchmark runs, outputs to specified directory:

```
/tmp/benchmark/
├── benchmark_results.json    # Raw metrics
├── benchmark_report.md       # Statistical analysis with CI, t-tests
├── traces.json              # All tool calls + results (machine-readable)
├── trace_claude_1.md        # Per-run detailed trace
├── trace_claude_2.md
├── trace_cohere_langgraph_1.md
├── ...
└── comparison_report.md     # Side-by-side agent behavior
```

---

## How to Run

```bash
cd backend && source .venv/bin/activate

# Default run (uses PatchRx only, 5 runs per agent)
python -m scripts.benchmark.runner --output /tmp/benchmark

# Custom options
python -m scripts.benchmark.runner \
  --runs 3 \
  --temperature 0.3 \
  --agents claude cohere_langgraph \
  --output ./benchmark_results
```

---

## What's Pending

### 1. Add Test Products (Required)

User needs to provide 3-5 Amazon product URLs. Edit `backend/scripts/benchmark/products.py`:

```python
BENCHMARK_PRODUCTS = [
    # Already have PatchRx
    BenchmarkProduct(
        url="https://www.amazon.ca/dp/B0BNW7WNLL",
        product_name="PatchRx Pimple Patches",
        ...
    ),

    # ADD MORE HERE:
    BenchmarkProduct(
        url="https://www.amazon.ca/dp/XXXXXXXXXX",
        product_name="...",
        brand="...",
        ingredients=["..."],
        category="food|skincare|cleaning|cookware|personal_care",
    ),
]
```

Recommended categories to test:

- Skincare (already have PatchRx)
- Food/supplement (allergen testing)
- Cookware (PFAS testing)
- Cleaning product
- Personal care

### 2. Run Full Benchmark

After adding products:

```bash
python -m scripts.benchmark.runner --output ./results
```

Expected: ~75 runs (3 agents × 5 products × 5 runs)
Estimated cost: $20-25 USD

---

## Key Findings Already Documented

### Cohere Literal Interpretation Issue

**Problem:** Cohere was not including Reddit/consumer sources despite finding them.

**Root Cause:** Prompt said "MUST have credible source (.gov, .edu, PubMed)" - Cohere interpreted this literally and excluded Reddit.

**Fix Applied:** Added explicit statement: "Reddit user experiences ARE valid evidence for skin reactions, allergies"

**Lesson:** Cohere requires explicit permissions; Claude infers intent. This is documented in `CASE_STUDY_CONTEXT.md` Section 11.

---

## Files Modified in This Session

1. `src/infrastructure/claude_agent.py` - Added temperature parameter
2. `src/infrastructure/langgraph_agent.py` - Made temperature configurable, fixed Reddit allowance
3. `src/infrastructure/cohere_native_agent.py` - Made temperature configurable, fixed Reddit allowance
4. `CASE_STUDY_CONTEXT.md` - Added Section 11 on literal interpretation
5. `scripts/benchmark/*` - Created entire benchmark suite

---

## Related Documents

- `backend/CASE_STUDY_CONTEXT.md` - Full case study findings
- `backend/AGENT_COMPARISON.md` - Original comparison notes
- `backend/ANALYSIS_RESULT.md` - Earlier analysis results
- `backend/docs/PRD_CUSTOM_EXTRACTION.md` - Product extraction PRD

---

## Resume Commands

```bash
# Check benchmark imports work
cd backend && source .venv/bin/activate
python -c "from scripts.benchmark import run_benchmark; print('OK')"

# Dry run with current products
python -m scripts.benchmark.runner --runs 1 --agents claude --output /tmp/test

# Full benchmark (after adding products)
python -m scripts.benchmark.runner --output ./benchmark_results
```
