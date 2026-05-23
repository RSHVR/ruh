# Ruh — 5-Config Agent Evaluation Suite

Five candidate agent architectures, one hermetic eval, one Plotly HTML report.

## Quick start

```bash
# install deps (adds claude-agent-sdk, langgraph>=1, cohere, plotly, scipy, ...)
cd backend
pip install -e ".[benchmark,dev]"

# unit tests (no API keys required)
pytest tests/unit/

# smoke run — 1 product × 5 configs × 1 run + HTML report (~$2)
python -m scripts.run_eval --mode smoke --max-cost-usd 5

# Tier A (5 anchors, N=5) — ~$25
python -m scripts.run_eval --mode tier-a --runs 5 --max-cost-usd 30

# full eval (Tier A + Tier B), with judge + report, resumable
python -m scripts.run_eval --mode full --max-cost-usd 80 --judge --resume

# concurrency sub-benchmark
python -m scripts.run_eval --mode concurrency --max-cost-usd 20
```

## What's where

```
backend/scripts/benchmark/
├── configs/
│   ├── base.py                  # AgentRunner Protocol + dataclasses
│   ├── prompts.py               # STATIC_BASE_PROMPT + deterministic KB renderer
│   ├── tool_schemas.py          # Anthropic/Cohere/LangChain converters
│   ├── registry.py              # CONFIG_REGISTRY
│   └── *.py                     # 5 config implementations
├── datasets/
│   ├── v1.json                  # 15 pre-extracted product fixtures
│   └── ground_truth_v1.json     # hand labels for 5 anchors
├── tracer.py / traced_search.py # per-run tool-call + phase tracing
├── metrics.py                   # RunMetrics, paired-t, Cohen's d, Holm
├── budget.py                    # BudgetTracker + pre-flight
├── checkpoint.py                # atomic .checkpoint.json + signal handler
├── judge.py                     # Opus 4.7 LLM-as-judge, anonymized A-E
├── runner.py                    # main loop
├── report.py                    # Plotly HTML
└── concurrency.py               # N∈{1,5,15} sub-benchmark
```

## The five configs

| Name                               | Stack                                            | Caching                                      |
| ---------------------------------- | ------------------------------------------------ | -------------------------------------------- |
| `claude_agentsdk_async_cached`     | claude-agent-sdk + AsyncAnthropic                | 1hr ephemeral on tools/system/KB             |
| `cohere_asyncv2_cached`            | cohere.AsyncClientV2 + ToolV2                    | None (provider gap, honest `None` reporting) |
| `claude_langgraph12_cached`        | langgraph 1.x StateGraph + ChatAnthropic         | 1hr cache via cache_control passthrough      |
| `cohere_langgraph12`               | langgraph 1.x StateGraph + ChatCohere            | None                                         |
| `claude_cohere_coordinated_cached` | Cohere classifies/looks-up, Claude judges/scores | 1hr cache on Claude nodes only               |

## Determinism contract

`prompts.build_kb_block(...)` sorts allergens and PFAS by lowercase name and
sorts synonyms before rendering. Two calls with the same KB in different
list order produce **byte-identical** output. This is the single guard
against silent cache misses on Anthropic prompt-cache.

Tests: `pytest tests/unit/test_prompts.py`.

## Budget guardrail

`BudgetTracker.preflight(estimate, cap, margin=1.4)` refuses to start if
the estimated total × 1.4 exceeds the cap. `--force` overrides. Per-run
`add(cost)` raises `BudgetExceeded` on overflow. Mid-eval overflow flushes
partial results and exits gracefully (Tier A is ordered first so anchor
results are preserved).

## Verifying the cache fires

After two runs of the same product on configs 1/3/5, the metrics JSON
for run #2 should show `cache_read_tokens > 0`. If 0, the prefix is not
byte-identical — bug, do not proceed to the full eval.
