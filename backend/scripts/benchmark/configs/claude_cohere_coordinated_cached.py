"""Config #5: LangGraph StateGraph with coordinated Claude + Cohere.

Cost-allocation strategy:
  - Cohere does the cheap labor: ingredient classification, per-ingredient
    KB lookups, regulatory synthesis.
  - Claude does the expensive judgement: deep research on low-confidence
    items, edge-case adjudication, final scoring + JSON output.

Every Claude invocation passes the same cache_control'd system + KB blocks
so the 1hr ephemeral cache is hit across nodes within a run AND across runs
within the TTL window.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from .base import AgentRunInput, AgentRunOutput, BaseAgentRunner
from .prompts import base_prompt, build_kb_block, build_user_message
from src.domain.extraction_schemas import ProductSafetyAnalysis  # enforced output schema

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
COHERE_MODEL = "command-a-03-2025"
CACHE_TTL = "1h"
CACHE_BETA = "extended-cache-ttl-2025-04-11"


class GraphState(TypedDict, total=False):
    product_data: Dict[str, Any]
    product_url: str
    allergen_db: List[Dict[str, Any]]
    pfas_db: List[Dict[str, Any]]
    allergen_profile: List[str]
    matched: Dict[str, Any]
    cohere_classified: Dict[str, Any]
    cohere_regulatory: str
    claude_deep_research: Dict[str, Any]
    adjudicated: Dict[str, Any]
    analysis: Dict[str, Any]
    failure_type: Optional[str]


class CoordinatedRunner(BaseAgentRunner):
    name = "claude_cohere_coordinated_cached"
    supports_caching = True  # Claude nodes cache; Cohere nodes don't.

    def __init__(self, anthropic_key: str, cohere_key: str, temperature: float = 0.3) -> None:
        super().__init__()
        from langchain_anthropic import ChatAnthropic  # noqa: F401
        from langchain_cohere import ChatCohere       # noqa: F401
        self._anthropic_key = anthropic_key
        self._cohere_key = cohere_key
        self._temperature = temperature

    async def run(self, inp: AgentRunInput) -> AgentRunOutput:
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.memory import MemorySaver
        from langchain_anthropic import ChatAnthropic
        from langchain_cohere import ChatCohere
        from langchain_core.messages import SystemMessage, HumanMessage
        from src.domain.ingredient_matcher import match_ingredients_to_databases
        from ..traced_search import TracedSearchService

        traced = TracedSearchService(inp.search_service, inp.tracer)

        def n_db_match(state):
            with self._record_phase(inp.tracer, "db_match"):
                matched = match_ingredients_to_databases(
                    ingredients=state["product_data"].get("ingredients", []),
                    materials=state["product_data"].get("materials", []),
                    allergen_database=state["allergen_db"],
                    pfas_database=state["pfas_db"],
                )
            return {**state, "matched": matched}

        async def n_cohere_classify(state):
            """Cheap labor: have Cohere classify each ingredient by risk."""
            with self._record_phase(inp.tracer, "cohere_classify"):
                llm = ChatCohere(
                    model=COHERE_MODEL,
                    temperature=self._temperature,
                    cohere_api_key=self._cohere_key,
                )
                ingredients = state["product_data"].get("ingredients", [])[:25]
                prompt = (
                    "Classify each of these product ingredients into one of: "
                    "safe, low_concern, needs_research, high_concern. "
                    "Return STRICT JSON {ingredient: classification}. "
                    "Ingredients:\n" + "\n".join(f"- {i}" for i in ingredients)
                )
                try:
                    resp = await llm.ainvoke([HumanMessage(content=prompt)])
                    md = getattr(resp, "response_metadata", {}) or {}
                    usage = md.get("token_count") or md.get("usage") or {}

                    class _U:
                        input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
                        output_tokens = int(usage.get("output_tokens") or usage.get("response_tokens") or 0)

                    if _U.input_tokens or _U.output_tokens:
                        inp.token_tracker.record_usage(
                            call_name="coord_cohere_classify",
                            model=COHERE_MODEL,
                            usage=_U(),
                        )
                    parsed = self._safe_json_parse(resp.content if isinstance(resp.content, str)
                                                   else self._extract_text(resp.content))
                except Exception as e:
                    logger.warning("Cohere classify failed: %s", e)
                    parsed = {}
            return {**state, "cohere_classified": parsed}

        async def n_cohere_regulatory(state):
            """Cheap labor: Cohere does the regulatory/legal search synthesis."""
            with self._record_phase(inp.tracer, "cohere_regulatory"):
                product = state["product_data"].get("product_name", "")
                brand = state["product_data"].get("brand", "")
                try:
                    reg = await traced.search(
                        query=f"{brand} {product} recall FDA warning Health Canada",
                        search_type="regulatory",
                    )
                except Exception as e:
                    reg = json.dumps({"error": str(e)})
                try:
                    legal = await traced.search(
                        query=f"{brand} {product} class action lawsuit",
                        search_type="legal",
                    )
                except Exception as e:
                    legal = json.dumps({"error": str(e)})
                synthesis = (
                    f"REGULATORY:\n{reg[:1500]}\n\nLEGAL:\n{legal[:1500]}"
                )
            return {**state, "cohere_regulatory": synthesis}

        async def n_claude_deep_research(state):
            """Expensive judgement: Claude with cached system + KB."""
            with self._record_phase(inp.tracer, "claude_deep_research"):
                llm = ChatAnthropic(
                    model=CLAUDE_MODEL,
                    temperature=self._temperature,
                    anthropic_api_key=self._anthropic_key,
                    model_kwargs={"extra_headers": {"anthropic-beta": CACHE_BETA}},
                )
                sys_msg = SystemMessage(content=[
                    {"type": "text", "text": base_prompt("claude"),
                     "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}},
                    {"type": "text",
                     "text": build_kb_block(state["allergen_db"], state["pfas_db"],
                                            state.get("allergen_profile")),
                     "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}},
                ])
                needs = [k for k, v in (state.get("cohere_classified") or {}).items()
                         if v in ("needs_research", "high_concern")]
                user = (
                    build_user_message(state["product_data"], state["product_url"])
                    + "\n\n**Cohere preliminary classifications:** "
                    + json.dumps(state.get("cohere_classified", {}))
                    + "\n\n**Cohere regulatory synthesis:** "
                    + (state.get("cohere_regulatory", "") or "(none)")
                    + "\n\n**Items needing your deep judgement:** "
                    + ", ".join(needs[:15])
                )
                try:
                    resp = await llm.ainvoke([sys_msg, HumanMessage(content=user)])
                    self._record_anthropic_usage(inp.token_tracker, resp, "coord_claude_deep_research")
                    text = resp.content if isinstance(resp.content, str) else self._extract_text(resp.content)
                except Exception as e:
                    logger.warning("Claude deep research failed: %s", e)
                    return {**state, "claude_deep_research": {}, "failure_type": "api_error"}
            return {**state, "claude_deep_research": {"text": text}}

        async def n_claude_adjudicate(state):
            """Claude final pass: produce the strict JSON the schema wants."""
            with self._record_phase(inp.tracer, "claude_adjudicate"):
                if state.get("failure_type"):
                    return state
                llm = ChatAnthropic(
                    model=CLAUDE_MODEL,
                    temperature=0.0,
                    anthropic_api_key=self._anthropic_key,
                    model_kwargs={"extra_headers": {"anthropic-beta": CACHE_BETA}},
                )
                sys_msg = SystemMessage(content=[
                    {"type": "text", "text": base_prompt("claude"),
                     "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}},
                    {"type": "text",
                     "text": build_kb_block(state["allergen_db"], state["pfas_db"],
                                            state.get("allergen_profile")),
                     "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}},
                ])
                user = (
                    "Given the prior research, produce the FINAL JSON analysis "
                    "in the exact schema. Reply with ONLY the JSON object, no prose.\n\n"
                    "Prior research text:\n"
                    + (state.get("claude_deep_research", {}).get("text", "") or "")
                )
                # Enforce the schema at generation; include_raw=True keeps the raw
                # AIMessage so we can still record token usage.
                structured_llm = llm.with_structured_output(
                    ProductSafetyAnalysis, include_raw=True)
                try:
                    res = await structured_llm.ainvoke([sys_msg, HumanMessage(content=user)])
                    raw = res.get("raw") if isinstance(res, dict) else None
                    if raw is not None:
                        self._record_anthropic_usage(
                            inp.token_tracker, raw, "coord_claude_adjudicate")
                    parsed_obj = res.get("parsed") if isinstance(res, dict) else res
                    if parsed_obj is None:
                        return {**state, "failure_type": "schema_invalid"}
                    parsed = parsed_obj.model_dump()
                    self._merge_matches(parsed, state.get("matched", {}))
                except Exception as e:
                    logger.warning("Claude adjudicate failed: %s", e)
                    return {**state, "failure_type": "api_error"}
            return {**state, "analysis": parsed}

        graph = StateGraph(GraphState)
        graph.add_node("db_match", n_db_match)
        graph.add_node("cohere_classify", n_cohere_classify)
        graph.add_node("cohere_regulatory", n_cohere_regulatory)
        graph.add_node("claude_deep_research", n_claude_deep_research)
        graph.add_node("claude_adjudicate", n_claude_adjudicate)
        graph.set_entry_point("db_match")
        graph.add_edge("db_match", "cohere_classify")
        graph.add_edge("cohere_classify", "cohere_regulatory")
        graph.add_edge("cohere_regulatory", "claude_deep_research")
        graph.add_edge("claude_deep_research", "claude_adjudicate")
        graph.add_edge("claude_adjudicate", END)
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
            logger.warning("Coordinated graph failed: %s", e)
            return AgentRunOutput(
                analysis=self._empty(inp.product_data),
                failure_type="api_error",
                notes={"models": [CLAUDE_MODEL, COHERE_MODEL]},
            )

        return AgentRunOutput(
            analysis=final.get("analysis") or self._empty(inp.product_data),
            failure_type=final.get("failure_type"),
            retry_count=0,
            notes={"models": [CLAUDE_MODEL, COHERE_MODEL]},
        )

    # ----- helpers ---------------------------------------------------------

    @staticmethod
    def _extract_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    return c.get("text", "")
        return ""

    @staticmethod
    def _record_anthropic_usage(token_tracker, resp, call_name) -> None:
        md = getattr(resp, "response_metadata", None) or {}
        usage = md.get("usage") or {}
        if not usage:
            return

        class _U:
            input_tokens = int(usage.get("input_tokens", 0) or 0)
            output_tokens = int(usage.get("output_tokens", 0) or 0)
            cache_read_input_tokens = int(usage.get("cache_read_input_tokens", 0) or 0)
            cache_creation_input_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)

        try:
            token_tracker.record_usage(
                call_name=call_name,
                model=CLAUDE_MODEL,
                usage=_U(),
            )
        except Exception as e:
            logger.debug("Could not record anthropic usage: %s", e)

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


def make_runner(**kwargs) -> CoordinatedRunner:
    from src.infrastructure.config import settings
    anthropic_key = kwargs.pop("anthropic_key", None) or settings.anthropic_api_key
    cohere_key = kwargs.pop("cohere_key", None) or settings.cohere_api_key
    if not anthropic_key or not cohere_key:
        raise RuntimeError("Both ANTHROPIC_API_KEY and COHERE_API_KEY are required")
    return CoordinatedRunner(anthropic_key=anthropic_key, cohere_key=cohere_key, **kwargs)
