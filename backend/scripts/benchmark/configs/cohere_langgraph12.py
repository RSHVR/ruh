"""Config #4: same StateGraph as config #3 but with ChatCohere.

No prompt caching (provider gap). Same node layout
(extract → db_match → classify → research_subgraph → score → save).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from .base import AgentRunInput, AgentRunOutput, BaseAgentRunner
from .prompts import base_prompt, build_kb_block, build_user_message
from .tool_schemas import make_langchain_tools

logger = logging.getLogger(__name__)

MODEL_ID = "command-a-03-2025"


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


class CohereLangGraph12Runner(BaseAgentRunner):
    name = "cohere_langgraph12"
    supports_caching = False

    def __init__(self, api_key: str, temperature: float = 0.3) -> None:
        super().__init__()
        from langchain_cohere import ChatCohere  # noqa: F401
        self._api_key = api_key
        self._temperature = temperature

    async def run(self, inp: AgentRunInput) -> AgentRunOutput:
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.memory import MemorySaver
        from langchain_cohere import ChatCohere
        from langchain_core.messages import HumanMessage
        from langgraph.prebuilt import create_react_agent
        from src.domain.ingredient_matcher import match_ingredients_to_databases
        from ..traced_search import TracedSearchService

        traced = TracedSearchService(inp.search_service, inp.tracer)

        def n_extract(state):
            return state

        def n_db_match(state):
            with self._record_phase(inp.tracer, "db_match"):
                matched = match_ingredients_to_databases(
                    ingredients=state["product_data"].get("ingredients", []),
                    materials=state["product_data"].get("materials", []),
                    allergen_database=state["allergen_db"],
                    pfas_database=state["pfas_db"],
                )
            return {**state, "matched": matched}

        def n_classify(state):
            with self._record_phase(inp.tracer, "classify"):
                pass  # symmetry with config 3
            return state

        async def n_research(state):
            with self._record_phase(inp.tracer, "research"):
                llm = ChatCohere(
                    model=MODEL_ID,
                    temperature=self._temperature,
                    cohere_api_key=self._api_key,
                )
                tools = make_langchain_tools(
                    search_service=traced,
                    supabase_client=inp.supabase_client,
                )
                # ChatCohere expects plain string system content.
                system_text = base_prompt("cohere") + "\n" + build_kb_block(
                    state["allergen_db"], state["pfas_db"], state.get("allergen_profile")
                )
                # NOTE: create_react_agent(response_format=...) is broken for ChatCohere
                # ("last message is not a ToolMessage or HumanMessage" upstream), so this
                # config falls back to parsing the final text — which the relaxed schema
                # now accepts. The other configs enforce structured output at generation.
                agent = create_react_agent(model=llm, tools=tools, prompt=system_text)
                user_msg = HumanMessage(
                    content=build_user_message(state["product_data"], state["product_url"])
                )
                try:
                    out = await agent.ainvoke({"messages": [user_msg]})
                except Exception as e:
                    logger.warning("LangGraph (Cohere) subgraph failed: %s", e)
                    return {**state, "research": {}, "failure_type": "api_error"}
                final_text = self._extract_final_text(out.get("messages", []))
                sr = out.get("structured_response")
                structured = sr.model_dump() if sr is not None else None
                self._record_lg_usage(inp.token_tracker, out.get("messages", []), MODEL_ID)
            return {**state, "research": {"final_text": final_text, "structured": structured}}

        def n_score(state):
            with self._record_phase(inp.tracer, "score"):
                if state.get("failure_type"):
                    return state
                research = state.get("research", {})
                parsed = research.get("structured") or self._safe_json_parse(
                    research.get("final_text", ""))
                if not parsed:
                    return {**state, "failure_type": "schema_invalid", "analysis": {}}
                self._merge_matches(parsed, state.get("matched", {}))
            return {**state, "analysis": parsed}

        def n_save(state):
            return state

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
            logger.warning("LangGraph (Cohere) failed: %s", e)
            return AgentRunOutput(
                analysis=self._empty(inp.product_data),
                failure_type="api_error",
                notes={"model": MODEL_ID},
            )

        return AgentRunOutput(
            analysis=final.get("analysis") or self._empty(inp.product_data),
            failure_type=final.get("failure_type"),
            retry_count=0,
            notes={"model": MODEL_ID},
        )

    # Same helpers as the Claude variant ------------------------------------

    @staticmethod
    def _extract_final_text(messages):
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
    def _record_lg_usage(token_tracker, messages, model):
        for m in messages:
            md = getattr(m, "response_metadata", None) or {}
            usage = md.get("token_count") or md.get("usage") or {}
            if not usage:
                continue

            class _U:
                input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
                output_tokens = int(usage.get("output_tokens") or usage.get("response_tokens") or 0)

            try:
                token_tracker.record_usage(
                    call_name="langgraph_cohere",
                    model=model,
                    usage=_U(),
                    estimated_input=None,
                )
            except Exception as e:
                logger.debug("Could not record LangGraph Cohere usage: %s", e)

    @staticmethod
    def _safe_json_parse(text):
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
    def _merge_matches(analysis, matched):
        ai_allergens = {a.get("name") for a in analysis.get("allergens_detected", [])}
        for a in matched.get("allergens_detected", []) or []:
            if a.get("name") not in ai_allergens:
                analysis.setdefault("allergens_detected", []).append(a)
        ai_pfas = {p.get("name") for p in analysis.get("pfas_detected", [])}
        for p in matched.get("pfas_detected", []) or []:
            if p.get("name") not in ai_pfas:
                analysis.setdefault("pfas_detected", []).append(p)

    @staticmethod
    def _empty(product_data):
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


def make_runner(**kwargs) -> CohereLangGraph12Runner:
    from src.infrastructure.config import settings
    api_key = kwargs.pop("api_key", None) or settings.cohere_api_key
    if not api_key:
        raise RuntimeError("COHERE_API_KEY not set")
    return CohereLangGraph12Runner(api_key=api_key, **kwargs)
