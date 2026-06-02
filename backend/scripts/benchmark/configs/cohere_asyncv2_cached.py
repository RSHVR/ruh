"""Config #2: cohere.AsyncClientV2 + ToolV2 + response_format json_schema.

"Caching" here is a provider gap — Cohere does not support prompt caching.
We use the ``documents`` parameter for the KB (Cohere's grounding mechanism)
and keep the static prompt at a fixed position so prefix bytes are stable,
but we report ``supports_caching=False`` and ``cache_*_tokens=0`` truthfully.

A tool-use loop is implemented manually: in V2 the model returns
``tool_calls`` on the message, we execute them, append ``tool`` messages,
and re-call. After the tool loop ends we make one final formatting call
asking for ``response_format=json_schema`` if the SDK supports it.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .base import AgentRunInput, AgentRunOutput, BaseAgentRunner
from .prompts import base_prompt, build_kb_block, build_user_message
from .tool_schemas import COHERE_TOOLS

logger = logging.getLogger(__name__)

# LangSmith @traceable so each Cohere turn nests under the run's root trace.
# Cohere has no official wrapper (unlike wrap_anthropic), so we trace the chat
# call ourselves. Falls back to a no-op decorator if langsmith is unavailable.
try:
    from langsmith import traceable as _traceable
except Exception:  # pragma: no cover
    def _traceable(*_a, **_k):
        def _deco(fn):
            return fn
        return _deco

MODEL_ID = "command-a-03-2025"
MAX_TOOL_ITERATIONS = 10


def _safety_json_schema() -> Dict[str, Any]:
    """Minimal json_schema for the final formatting call.

    The full ProductSafetyAnalysis pydantic model exists in
    backend/src/domain/extraction_schemas.py; we mirror its top-level shape.
    """
    return {
        "type": "object",
        "properties": {
            "product_name": {"type": "string"},
            "brand": {"type": "string"},
            "retailer": {"type": "string"},
            "ingredients": {"type": "array", "items": {"type": "string"}},
            "allergens_detected": {"type": "array"},
            "pfas_detected": {"type": "array"},
            "other_concerns": {"type": "array"},
            "research_sources": {"type": "array"},
            "confidence": {"type": "number"},
        },
        "required": ["allergens_detected", "pfas_detected", "other_concerns", "confidence"],
    }


class CohereAsyncV2Runner(BaseAgentRunner):
    name = "cohere_asyncv2_cached"
    supports_caching = False

    def __init__(self, api_key: str, temperature: float = 0.3) -> None:
        super().__init__()
        try:
            from cohere import AsyncClientV2  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "cohere>=5.13 required for config 'cohere_asyncv2_cached'"
            ) from e
        self._client = AsyncClientV2(api_key=api_key)
        self._temperature = temperature

    async def run(self, inp: AgentRunInput) -> AgentRunOutput:
        from ..traced_search import TracedSearchService
        traced = TracedSearchService(inp.search_service, inp.tracer)

        # Build the static-then-KB system prompt.
        # We keep the static body first so configs that DO support caching
        # see the same byte layout.
        with self._record_phase(inp.tracer, "build_prompt"):
            kb_block = build_kb_block(inp.allergen_db, inp.pfas_db, inp.allergen_profile)
            system_text = base_prompt("cohere") + "\n" + kb_block
            user_text = build_user_message(inp.product_data, inp.product_url)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ]

        retry_count = 0
        failure: Optional[str] = None
        final_text: str = ""

        # Traced chat: each turn becomes an LLM child run in LangSmith. `messages`
        # is logged as the input (what the model saw), resp as the output (its
        # reasoning + tool_calls).
        @_traceable(run_type="llm", name="cohere_chat")
        async def _chat(messages: List[Dict[str, Any]]):
            return await self._client.chat(
                model=MODEL_ID,
                messages=messages,
                tools=COHERE_TOOLS,
                temperature=self._temperature,
            )

        with self._record_phase(inp.tracer, "tool_loop"):
            for iteration in range(MAX_TOOL_ITERATIONS):
                t0 = time.perf_counter()
                try:
                    resp = await _chat(messages)
                except Exception as e:
                    logger.warning("cohere chat failed: %s", e)
                    failure = "api_error"
                    break
                latency = (time.perf_counter() - t0) * 1000

                # Record token usage (no cache fields on Cohere)
                usage = getattr(resp, "usage", None)
                billed = getattr(usage, "billed_units", None) if usage else None
                if billed:
                    self._record_cohere_usage(
                        inp.token_tracker, billed, call_name=f"cohere_iter{iteration}"
                    )

                msg = resp.message
                tool_calls = getattr(msg, "tool_calls", None) or []
                if not tool_calls:
                    # Final response from the tool loop.
                    final_text = self._extract_text(msg)
                    break

                # Echo the assistant message back, then execute each tool call.
                messages.append(self._assistant_to_dict(msg))

                for tc in tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    if name == "web_search":
                        try:
                            tool_result = await traced.search(
                                query=args.get("query", ""),
                                search_type=args.get("search_type", "general"),
                            )
                        except Exception as e:
                            tool_result = json.dumps({"error": str(e)})
                    elif name == "lookup_ingredient_research":
                        tool_result = self._lookup_local(inp.supabase_client, args.get("ingredient", ""))
                    else:
                        tool_result = json.dumps({"error": f"unknown tool {name}"})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    })
            else:
                failure = "max_iterations"

        # Final formatting pass (always, even after a non-tool stop) so the
        # output is strict json_schema. Cohere V2 supports response_format on
        # the chat call; if structured output is incompatible with the
        # mid-loop tool calls, we do a second standalone call here.
        analysis: Dict[str, Any] = {}
        if not failure:
            with self._record_phase(inp.tracer, "final_format"):
                analysis = await self._final_format(messages, inp.token_tracker, final_text)
                if not analysis:
                    failure = "schema_invalid"

        return AgentRunOutput(
            analysis=analysis or self._empty_analysis(inp.product_data),
            failure_type=failure,
            retry_count=retry_count,
            notes={"model": MODEL_ID, "iterations": iteration + 1 if 'iteration' in locals() else 0},
        )

    # ----- helpers ---------------------------------------------------------

    def _record_cohere_usage(self, token_tracker: Any, billed: Any, call_name: str) -> None:
        # Cohere's billed_units is { input_tokens, output_tokens, ... }
        try:
            class _U:
                input_tokens = int(getattr(billed, "input_tokens", 0) or 0)
                output_tokens = int(getattr(billed, "output_tokens", 0) or 0)

            token_tracker.record_usage(
                call_name=call_name,
                model=MODEL_ID,
                usage=_U(),
                estimated_input=None,
            )
        except Exception as e:
            logger.debug("Could not record Cohere usage: %s", e)

    def _extract_text(self, msg: Any) -> str:
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for c in content:
                t = getattr(c, "text", None) or (c.get("text") if isinstance(c, dict) else None)
                if t:
                    parts.append(t)
            return "\n".join(parts)
        return ""

    def _assistant_to_dict(self, msg: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {"role": "assistant"}
        text = self._extract_text(msg)
        if text:
            out["content"] = text
        tcs = getattr(msg, "tool_calls", None)
        if tcs:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tcs
            ]
        return out

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

    async def _final_format(
        self, messages: List[Dict[str, Any]], token_tracker: Any, fallback_text: str
    ) -> Dict[str, Any]:
        """Final pass asking for json_schema. Try response_format first; if
        the SDK rejects it (e.g. when the conversation contains tool calls),
        fall back to parsing the loop's final assistant text.
        """
        if fallback_text:
            parsed = self._safe_json_parse(fallback_text)
            if parsed:
                return parsed

        try:
            resp = await self._client.chat(
                model=MODEL_ID,
                messages=messages + [
                    {
                        "role": "user",
                        "content": "Return ONLY the final JSON object matching the schema. No tool calls.",
                    }
                ],
                response_format={
                    "type": "json_object",
                    "schema": _safety_json_schema(),
                },
                temperature=0.0,
            )
            usage = getattr(resp, "usage", None)
            billed = getattr(usage, "billed_units", None) if usage else None
            if billed:
                self._record_cohere_usage(token_tracker, billed, call_name="cohere_final_format")
            text = self._extract_text(resp.message)
            return self._safe_json_parse(text) or {}
        except Exception as e:
            logger.warning("Cohere final format call failed: %s", e)
            return {}

    @staticmethod
    def _safe_json_parse(text: str) -> Dict[str, Any]:
        if not text:
            return {}
        s = text.strip()
        if s.startswith("```"):
            # ```json or ``` block
            s = s.split("\n", 1)[1] if "\n" in s else s
            if s.endswith("```"):
                s = s[:-3]
        start = s.find("{")
        end = s.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            return json.loads(s[start: end + 1])
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _empty_analysis(product_data: Dict[str, Any]) -> Dict[str, Any]:
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


def make_runner(**kwargs) -> CohereAsyncV2Runner:
    from src.infrastructure.config import settings
    api_key = kwargs.pop("api_key", None) or settings.cohere_api_key
    if not api_key:
        raise RuntimeError("COHERE_API_KEY not set")
    return CohereAsyncV2Runner(api_key=api_key, **kwargs)
