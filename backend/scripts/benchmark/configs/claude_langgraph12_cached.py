"""Config #3: langgraph>=1.0 StateGraph (Claude) + cache_control passthrough.

State machine:
    extract → db_match → classify → research_subgraph → score → save

The research subgraph is a ``create_react_agent`` driving
``ChatAnthropic(model=claude-sonnet-4-5)`` with the system passed as a list
of blocks bearing ``cache_control`` (LangChain passes these straight through
to the Anthropic API). The cached prefix is re-used on every tool-loop turn
of the subgraph and across runs of the same product within the 1hr TTL.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from .base import AgentRunInput, AgentRunOutput, BaseAgentRunner
from .prompts import base_prompt, build_kb_block, build_user_message
from .tool_schemas import make_langchain_tools

# Structured-output schema enforced at generation (create_react_agent.response_format).
from src.domain.extraction_schemas import ProductSafetyAnalysis

logger = logging.getLogger(__name__)

MODEL_ID = "claude-sonnet-4-5-20250929"
CACHE_TTL = "1h"
CACHE_BETA = "extended-cache-ttl-2025-04-11"


class GraphState(TypedDict, total=False):
    product_data: Dict[str, Any]
    product_url: str
    allergen_db: List[Dict[str, Any]]
    pfas_db: List[Dict[str, Any]]
    allergen_profile: List[str]

    matched: Dict[str, Any]
    classified: Dict[str, Any]
    research: Dict[str, Any]
    analysis: Dict[str, Any]
    failure_type: Optional[str]


class ClaudeLangGraph12Runner(BaseAgentRunner):
    name = "claude_langgraph12_cached"
    supports_caching = True

    def __init__(self, api_key: str, temperature: float = 0.3) -> None:
        super().__init__()
        from langchain_anthropic import ChatAnthropic  # noqa: F401  (import probe)
        self._api_key = api_key
        self._temperature = temperature

    async def run(self, inp: AgentRunInput) -> AgentRunOutput:
        # Lazy imports so importing the module doesn't pull langgraph at
        # registry-time.
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.memory import MemorySaver
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import SystemMessage, HumanMessage
        from langgraph.prebuilt import create_react_agent
        from src.domain.ingredient_matcher import match_ingredients_to_databases
        from ..traced_search import TracedSearchService

        traced = TracedSearchService(inp.search_service, inp.tracer)

        # ----- nodes -------------------------------------------------------

        def n_extract(state: GraphState) -> GraphState:
            # No-op: product_data is pre-extracted in the fixture.
            return state

        def n_db_match(state: GraphState) -> GraphState:
            with self._record_phase(inp.tracer, "db_match"):
                matched = match_ingredients_to_databases(
                    ingredients=state["product_data"].get("ingredients", []),
                    materials=state["product_data"].get("materials", []),
                    allergen_database=state["allergen_db"],
                    pfas_database=state["pfas_db"],
                )
            return {**state, "matched": matched}

        def n_classify(state: GraphState) -> GraphState:
            # Trivial classifier — partitions ingredients into safe / needs_research
            # using the DB-match output. The "real" classifier lives in
            # analyze.py; here we just need a stable handoff to the subgraph.
            with self._record_phase(inp.tracer, "classify"):
                all_ing = (state["product_data"].get("ingredients", [])
                           + state["product_data"].get("materials", []))
                matched_names = {
                    a.get("name", "").lower()
                    for a in state.get("matched", {}).get("allergens_detected", [])
                }
                matched_names |= {
                    p.get("name", "").lower()
                    for p in state.get("matched", {}).get("pfas_detected", [])
                }
                needs = [i for i in all_ing if i and i.lower() not in matched_names]
            return {**state, "classified": {"needs_research": needs}}

        async def n_research(state: GraphState) -> GraphState:
            with self._record_phase(inp.tracer, "research"):
                llm = ChatAnthropic(
                    model=MODEL_ID,
                    temperature=self._temperature,
                    anthropic_api_key=self._api_key,
                    model_kwargs={
                        "extra_headers": {"anthropic-beta": CACHE_BETA},
                    },
                )
                system_blocks = [
                    {
                        "type": "text",
                        "text": base_prompt("claude"),
                        "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL},
                    },
                    {
                        "type": "text",
                        "text": build_kb_block(
                            state["allergen_db"],
                            state["pfas_db"],
                            state.get("allergen_profile"),
                        ),
                        "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL},
                    },
                ]
                tools = make_langchain_tools(
                    search_service=traced,
                    supabase_client=inp.supabase_client,
                )
                agent = create_react_agent(
                    model=llm,
                    tools=tools,
                    response_format=ProductSafetyAnalysis,  # enforce schema at generation
                )
                user_msg = HumanMessage(
                    content=build_user_message(state["product_data"], state["product_url"])
                )
                sys_msg = SystemMessage(content=system_blocks)
                try:
                    out = await agent.ainvoke({"messages": [sys_msg, user_msg]})
                except Exception as e:
                    logger.warning("LangGraph subgraph failed: %s", e)
                    return {**state, "research": {}, "failure_type": "api_error"}

                final_text = self._extract_final_text(out.get("messages", []))
                # Schema-enforced structured result (Pydantic instance) -> dict.
                sr = out.get("structured_response")
                structured = sr.model_dump() if sr is not None else None
                # Record Anthropic usage from each AI message if available.
                self._record_lg_usage(inp.token_tracker, out.get("messages", []), MODEL_ID)

            return {**state, "research": {"final_text": final_text, "structured": structured}}

        def n_score(state: GraphState) -> GraphState:
            with self._record_phase(inp.tracer, "score"):
                if state.get("failure_type"):
                    return state
                research = state.get("research", {})
                # Prefer the schema-enforced structured result; fall back to parsing.
                parsed = research.get("structured") or self._safe_json_parse(
                    research.get("final_text", ""))
                if not parsed:
                    return {**state, "failure_type": "schema_invalid", "analysis": {}}
                # Merge DB matches into the analysis (Claude may have missed
                # the canonical names).
                matched = state.get("matched", {})
                self._merge_matches(parsed, matched)
            return {**state, "analysis": parsed}

        def n_save(state: GraphState) -> GraphState:
            return state

        # ----- graph -------------------------------------------------------

        graph = StateGraph(GraphState)
        graph.add_node("extract", n_extract)
        graph.add_node("db_match", n_db_match)
        graph.add_node("classify", n_classify)
        graph.add_node("research", n_research)
        graph.add_node("score", n_score)
        graph.add_node("save", n_save)
        graph.set_entry_point("extract")
        graph.add_edge("extract", "db_match")
        graph.add_edge("db_match", "classify")
        graph.add_edge("classify", "research")
        graph.add_edge("research", "score")
        graph.add_edge("score", "save")
        graph.add_edge("save", END)

        compiled = graph.compile(checkpointer=MemorySaver())

        initial: GraphState = {
            "product_data": inp.product_data,
            "product_url": inp.product_url,
            "allergen_db": inp.allergen_db,
            "pfas_db": inp.pfas_db,
            "allergen_profile": inp.allergen_profile or [],
        }
        try:
            final = await compiled.ainvoke(
                initial, config={"configurable": {"thread_id": f"{inp.product_url}"}}
            )
        except Exception as e:
            logger.warning("LangGraph invocation failed: %s", e)
            return AgentRunOutput(
                analysis=self._empty(inp.product_data),
                failure_type="api_error",
                retry_count=0,
                notes={"model": MODEL_ID},
            )

        return AgentRunOutput(
            analysis=final.get("analysis") or self._empty(inp.product_data),
            failure_type=final.get("failure_type"),
            retry_count=0,
            notes={"model": MODEL_ID},
        )

    # ----- helpers ---------------------------------------------------------

    @staticmethod
    def _extract_final_text(messages: List[Any]) -> str:
        for m in reversed(messages):
            content = getattr(m, "content", None)
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        return c.get("text", "")
        return ""

    @staticmethod
    def _record_lg_usage(token_tracker: Any, messages: List[Any], model: str) -> None:
        for m in messages:
            md = getattr(m, "response_metadata", None) or {}
            usage = md.get("usage") or {}
            if not usage:
                continue

            class _U:
                input_tokens = int(usage.get("input_tokens", 0) or 0)
                output_tokens = int(usage.get("output_tokens", 0) or 0)
                cache_read_input_tokens = int(usage.get("cache_read_input_tokens", 0) or 0)
                cache_creation_input_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)

            try:
                token_tracker.record_usage(
                    call_name="langgraph_claude",
                    model=model,
                    usage=_U(),
                    estimated_input=None,
                )
            except Exception as e:
                logger.debug("Could not record LangGraph usage: %s", e)

    @staticmethod
    def _safe_json_parse(text: str) -> Dict[str, Any]:
        if not text:
            return {}
        s = text.strip()
        if "```" in s:
            after = s.split("```", 1)[1]
            if after.lower().startswith("json"):
                after = after[4:]
            end = after.find("```")
            if end != -1:
                s = after[:end].strip()
        start = s.find("{")
        end = s.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            return json.loads(s[start: end + 1])
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _merge_matches(analysis: Dict[str, Any], matched: Dict[str, Any]) -> None:
        ai_allergens = {a.get("name") for a in analysis.get("allergens_detected", [])}
        for a in matched.get("allergens_detected", []) or []:
            if a.get("name") not in ai_allergens:
                analysis.setdefault("allergens_detected", []).append(a)
        ai_pfas = {p.get("name") for p in analysis.get("pfas_detected", [])}
        for p in matched.get("pfas_detected", []) or []:
            if p.get("name") not in ai_pfas:
                analysis.setdefault("pfas_detected", []).append(p)

    @staticmethod
    def _empty(product_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "product_name": product_data.get("product_name", ""),
            "brand": product_data.get("brand", ""),
            "retailer": "",
            "ingredients": product_data.get("ingredients", []),
            "allergens_detected": [],
            "pfas_detected": [],
            "other_concerns": [],
            "research_sources": [],
            "confidence": 0.0,
        }


def make_runner(**kwargs) -> ClaudeLangGraph12Runner:
    from src.infrastructure.config import settings
    api_key = kwargs.pop("api_key", None) or settings.anthropic_api_key
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return ClaudeLangGraph12Runner(api_key=api_key, **kwargs)
