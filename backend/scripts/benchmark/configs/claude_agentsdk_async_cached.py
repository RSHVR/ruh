"""Config #1: claude_agent_sdk.ClaudeSDKClient + AsyncAnthropic + 1hr cache.

Three cache breakpoints:
  1. End of the ``tools`` array
  2. End of the static system block (STATIC_BASE_PROMPT)
  3. End of the KB block (build_kb_block output)

Each marked with ``cache_control={"type":"ephemeral","ttl":"1h"}``. We attach
``extra_headers={"anthropic-beta": "extended-cache-ttl-2025-04-11"}`` to opt
into the 1hr TTL beta.

A PreToolUse-style hook enforces a per-run web_search budget (default 6).
Implementation note: the ``claude_agent_sdk`` Python SDK API surface has
been evolving; the imports below are best-effort against the public package
as of the planning cutoff and should be verified at install time.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import AgentRunInput, AgentRunOutput, BaseAgentRunner
from .prompts import STATIC_BASE_PROMPT, build_kb_block, build_user_message
from .tool_schemas import ANTHROPIC_TOOLS

logger = logging.getLogger(__name__)

MODEL_ID = "claude-sonnet-4-5-20250929"
CACHE_TTL = "1h"
CACHE_BETA = "extended-cache-ttl-2025-04-11"

DEFAULT_SEARCH_BUDGET = 6
MAX_TOOL_ITERATIONS = 12


def _tools_with_cache() -> List[Dict[str, Any]]:
    """Apply a cache breakpoint at the END of the tools array."""
    tools = [dict(t) for t in ANTHROPIC_TOOLS]
    # Cache breakpoint goes on the LAST tool; covers all prior tools.
    tools[-1] = dict(tools[-1])
    tools[-1]["cache_control"] = {"type": "ephemeral", "ttl": CACHE_TTL}
    return tools


def _system_blocks(allergen_db, pfas_db, allergen_profile) -> List[Dict[str, Any]]:
    """Two cached blocks: static body, then KB block."""
    kb_block = build_kb_block(allergen_db, pfas_db, allergen_profile)
    return [
        {
            "type": "text",
            "text": STATIC_BASE_PROMPT,
            "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL},
        },
        {
            "type": "text",
            "text": kb_block,
            "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL},
        },
    ]


class ClaudeAgentSDKRunner(BaseAgentRunner):
    name = "claude_agentsdk_async_cached"
    supports_caching = True

    def __init__(
        self,
        api_key: str,
        temperature: float = 0.3,
        search_budget: int = DEFAULT_SEARCH_BUDGET,
    ) -> None:
        super().__init__()
        from anthropic import AsyncAnthropic
        self._client = AsyncAnthropic(api_key=api_key)
        self._temperature = temperature
        self._search_budget = search_budget

    async def run(self, inp: AgentRunInput) -> AgentRunOutput:
        from ..traced_search import TracedSearchService
        traced = TracedSearchService(inp.search_service, inp.tracer)

        with self._record_phase(inp.tracer, "build_prompt"):
            system = _system_blocks(inp.allergen_db, inp.pfas_db, inp.allergen_profile)
            tools = _tools_with_cache()
            user_text = build_user_message(inp.product_data, inp.product_url)

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": user_text},
        ]
        searches_used = 0
        retry_count = 0
        failure: Optional[str] = None

        with self._record_phase(inp.tracer, "tool_loop"):
            for iteration in range(MAX_TOOL_ITERATIONS):
                try:
                    resp = await self._client.messages.create(
                        model=MODEL_ID,
                        max_tokens=4096,
                        temperature=self._temperature,
                        system=system,
                        messages=messages,
                        tools=tools,
                        tool_choice={"type": "auto"},
                        extra_headers={"anthropic-beta": CACHE_BETA},
                    )
                except Exception as e:
                    logger.warning("Anthropic create failed (iter %s): %s", iteration, e)
                    failure = "api_error"
                    break

                inp.token_tracker.record_usage(
                    call_name=f"claude_sdk_iter{iteration}",
                    model=MODEL_ID,
                    usage=resp.usage,
                    estimated_input=None,
                )

                if resp.stop_reason != "tool_use":
                    # Done.
                    text = self._extract_text(resp)
                    analysis = self._safe_json_parse(text)
                    if not analysis:
                        failure = "schema_invalid"
                    return AgentRunOutput(
                        analysis=analysis or self._empty(inp.product_data),
                        failure_type=failure,
                        retry_count=retry_count,
                        notes={"model": MODEL_ID, "iterations": iteration + 1,
                               "searches_used": searches_used},
                    )

                tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
                if not tool_uses:
                    failure = "no_tool_blocks"
                    break

                messages.append({"role": "assistant", "content": resp.content})
                tool_results: List[Dict[str, Any]] = []
                for tu in tool_uses:
                    if tu.name == "web_search":
                        # Hook: enforce search budget.
                        if searches_used >= self._search_budget:
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tu.id,
                                "content": json.dumps({
                                    "error": "search_budget_exhausted",
                                    "searches_used": searches_used,
                                    "limit": self._search_budget,
                                }),
                            })
                            continue
                        searches_used += 1
                        query = tu.input.get("query", "")
                        search_type = tu.input.get("search_type", "general")
                        try:
                            content = await traced.search(query=query, search_type=search_type)
                        except Exception as e:
                            content = json.dumps({"error": str(e)})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": content,
                        })
                    elif tu.name == "lookup_ingredient_research":
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": self._lookup_local(
                                inp.supabase_client, tu.input.get("ingredient", "")
                            ),
                        })
                    else:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": json.dumps({"error": f"unknown tool {tu.name}"}),
                        })
                messages.append({"role": "user", "content": tool_results})
            else:
                failure = "max_iterations"

        return AgentRunOutput(
            analysis=self._empty(inp.product_data),
            failure_type=failure,
            retry_count=retry_count,
            notes={"model": MODEL_ID, "searches_used": searches_used},
        )

    # ----- helpers ---------------------------------------------------------

    @staticmethod
    def _extract_text(resp: Any) -> str:
        parts = []
        for b in resp.content:
            t = getattr(b, "text", None)
            if t:
                parts.append(t)
        return "\n".join(parts)

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

    def _lookup_local(self, supabase_client: Any, ingredient: str) -> str:
        if not supabase_client:
            return json.dumps({"ingredient": ingredient, "found": False, "reason": "no db"})
        try:
            result = (
                supabase_client.table("ingredient_research")
                .select("*")
                .ilike("ingredient_name", f"%{ingredient}%")
                .limit(1)
                .execute()
            )
            if result.data:
                data = result.data[0]
                return json.dumps({
                    "ingredient": ingredient,
                    "found": True,
                    "safety_summary": data.get("safety_summary", ""),
                    "concerns": data.get("concerns", []),
                    "sources": data.get("sources", []),
                })
            return json.dumps({"ingredient": ingredient, "found": False})
        except Exception as e:
            return json.dumps({"ingredient": ingredient, "found": False, "error": str(e)})

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


def make_runner(**kwargs) -> ClaudeAgentSDKRunner:
    from src.infrastructure.config import settings
    api_key = kwargs.pop("api_key", None) or settings.anthropic_api_key
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return ClaudeAgentSDKRunner(api_key=api_key, **kwargs)
