# Experiment Continuation Context

## Problem Statement

We're comparing Claude Sonnet 4 vs Cohere Command A for product safety analysis. Our experiment has a flaw: **we're not measuring apples-to-apples**.

## Current Setup Issues

### Tool Execution Patterns

| Agent            | SDK               | Tool Batching         | Search Execution           |
| ---------------- | ----------------- | --------------------- | -------------------------- |
| Claude           | Native Anthropic  | 7 tools in 1 response | Parallel (asyncio.gather)  |
| Native Cohere    | Native Cohere SDK | 7 tools in 1 response | Sequential (one at a time) |
| LangGraph Cohere | LangGraph wrapper | 1-3 tools per turn    | Sequential                 |

### Timing Results (Flawed)

| Agent            | Time | Concerns |
| ---------------- | ---- | -------- |
| Claude           | 45s  | 3        |
| Native Cohere    | 166s | 3        |
| LangGraph Cohere | 323s | 2        |

## Root Causes

1. **LangGraph ReAct Pattern**: Forces one tool call per turn (model → tool → model → tool...)
2. **Claude Parallel Execution**: Claude requests 7 searches, we execute all in parallel
3. **Native Cohere Sequential**: Cohere SDK is sync, so we execute tools one at a time

## Files to Modify

### 1. `/backend/src/infrastructure/langgraph_agent.py`

- Uses `create_react_agent` from `langgraph.prebuilt`
- Line ~112: `agent = create_react_agent(model=self.llm, tools=self.tools, prompt=...)`
- Problem: ReAct pattern is turn-by-turn, not batched

### 2. `/backend/src/infrastructure/cohere_native_agent.py`

- Uses native `cohere.ClientV2()`
- Tool execution is sequential (await one at a time)
- Need to parallelize with `asyncio.gather`

### 3. Reference Implementation

- `/Users/arshveergahir/Desktop/GitHub Repos/scraper-agent/backend/src/agents/agentic_scraper.py`
- Uses same `create_react_agent` pattern
- Claude naturally batches tool calls; Cohere may not

## Key Insight from scraper-agent

The scraper-agent uses the SAME `create_react_agent` but:

1. Uses Claude (which naturally batches tool calls)
2. Or uses Cohere via LangChain's `ChatCohere`

The issue is likely that **Cohere's model doesn't naturally batch tool calls** like Claude does, not a LangGraph issue.

## Experiments to Run

### Experiment 1: Force Parallel Tool Execution in Native Cohere

```python
# In cohere_native_agent.py, execute all tool calls in parallel
tool_calls = response.message.tool_calls
tasks = [self._execute_tool(tc) for tc in tool_calls]
results = await asyncio.gather(*tasks)
```

### Experiment 2: Check if Cohere via LangChain batches tools

Look at how `ChatCohere` handles tool calls - does it request multiple tools per response?

### Experiment 3: Fair Comparison Criteria

For true parity:

- Same number of API round-trips
- Same search execution pattern (all parallel or all sequential)
- Same tools available

## What We've Proven So Far

1. **Cohere CAN find concerns** - Found 3 when using web_search correctly
2. **Cohere ignored tool warnings** - Used empty database instead of web_search
3. **Claude follows instructions** - Used web_search first, database as supplementary
4. **Native Cohere SDK is 2x faster than LangGraph** - 166s vs 323s
5. **Claude is 3.7x faster than Native Cohere** - 45s vs 166s

## Outstanding Questions

1. Is the speed difference due to parallel tool execution or model inference time?
2. Does Cohere's model naturally batch tool calls like Claude?
3. Would forcing sequential execution for Claude match Cohere's timing?

## Case Study Location

`/backend/CASE_STUDY_CONTEXT.md` - 14 sections, fully documented

## Scripts

- `/backend/scripts/compare_agents.py` - Original 2-way comparison
- `/backend/scripts/compare_all_agents.py` - 3-way comparison (Claude, LangGraph Cohere, Native Cohere)

## Key Code Locations

### Claude Agent Tool Loop

`/backend/src/infrastructure/claude_agent.py:780-830`

- Separates `web_search` and `lookup_ingredient_research` calls
- Executes web_search in parallel via `asyncio.gather`

### LangGraph Agent

`/backend/src/infrastructure/langgraph_agent.py:350-357`

- Tools: `web_search`, `lookup_ingredient_research`, `save_analysis`, `report_failure`
- Uses `create_react_agent` which is turn-by-turn

### Native Cohere Agent

`/backend/src/infrastructure/cohere_native_agent.py`

- Manual tool loop similar to Claude
- Currently executes tools sequentially (fix needed)

## Next Steps

1. **Fix Native Cohere parallel execution** - Use `asyncio.gather` for tool calls
2. **Add timing breakdown** - Measure API time vs search time separately
3. **Test Cohere tool batching** - Does Cohere request multiple tools per response?
4. **Update case study** - Document fair comparison methodology
