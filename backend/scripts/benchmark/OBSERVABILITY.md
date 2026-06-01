# Agent Observability (LangSmith)

The benchmark emits a **LangSmith trace per run** so you can see each agent's
turn-by-turn loop — what it _saw_, _thought_, _did_, how it _justified_ the action,
and how it _organized_ the final output — across all 5 configs.

## Setup (one-time)

1. Create a free account at **smith.langchain.com** (Developer plan: 1 seat,
   5,000 traces/month, 14-day retention).
2. Settings → **API Keys** → create a key.
3. Add to `backend/.env`:
   ```
   LANGSMITH_TRACING=true
   LANGSMITH_API_KEY=ls__your_key_here
   LANGSMITH_PROJECT=ruh-agent-bench
   ```

That's it. `python -m scripts.run_eval ...` loads `.env` and logs
`LangSmith tracing: ON (project=ruh-agent-bench)`. To disable, unset
`LANGSMITH_TRACING` — the harness runs fully offline with zero overhead.

## What you get

One **root trace per `(config, product, run)`**, named `cfg::product::run0`, tagged
with the config name + provider and carrying `config` / `product_id` / `run_idx` /
`mode` / `failure_type` metadata. Under each root, the full loop nests:

| You want to know…       | Where it is in the trace                                                        |
| ----------------------- | ------------------------------------------------------------------------------- |
| What it saw each turn   | the **input messages** of each LLM child run (prompt + prior tool observations) |
| What it thought         | the LLM run's **output text** (reasoning before the action)                     |
| What action it took     | the **tool_calls** + the nested **tool run** (name + args)                      |
| How it justified it     | the assistant text accompanying the tool call                                   |
| How it organized output | the **final LLM run** that produced the JSON                                    |

Filter the project by `tags` (e.g. `cohere_langgraph12`) or `metadata.product_id`
to compare configs or drill into one product.

## How each config is instrumented

| Config                                                                                | Mechanism                                                                                                                                                             |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `claude_langgraph12_cached`, `cohere_langgraph12`, `claude_cohere_coordinated_cached` | **Auto-traced** — they use LangChain/LangGraph, which emits to LangSmith with no code. (This also captures their tool calls, which our in-house `trace.json` missed.) |
| `claude_agentsdk_async_cached`                                                        | `wrap_anthropic(AsyncAnthropic(...))` — every `messages.create` (incl. tool_use / tool_result blocks) is traced.                                                      |
| `cohere_asyncv2_cached`                                                               | `@traceable(run_type="llm")` on the chat call (no official Cohere wrapper).                                                                                           |

Wiring lives in `scripts/benchmark/observability.py` (`root_run`) +
`runner.py::_run_one`. It's additive: the in-house `Tracer`/`metrics.json` and the
`comparison.html` accuracy report are unchanged.

## Notes & limits

- **Data egress:** prompts, product data, and search results are sent to LangChain's
  cloud. Fine for this benchmark (public product data, no PII) — don't enable it for
  anything sensitive without reviewing.
- **Free-tier ceiling:** 5,000 traces/month. A smoke run ≈ 75 traces, a full eval
  ≈ 275 — negligible unless you re-run heavily.
- **comparison.html** shows a "Reasoning traces in LangSmith" link in its header
  (labeled with `LANGSMITH_PROJECT`).
