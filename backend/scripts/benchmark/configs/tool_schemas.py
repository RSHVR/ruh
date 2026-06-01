"""Canonical tool schemas + cross-framework converters.

The Anthropic-style schemas are the source of truth (lifted from
``backend/src/infrastructure/claude_agent.py:20-87``). Converters produce
Cohere ToolV2 dicts and LangChain ``@tool`` callables from the same source
so all five configs see byte-identical tool descriptions — a fairness
requirement.

LangChain ``@tool`` callables need a runtime that actually executes the
search. ``make_langchain_tools(...)`` wires them to a ``SearchToolService``
instance and an optional Supabase client; the returned callables are
``BaseTool``-compatible and can be passed to ``create_react_agent``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Anthropic schemas (source of truth)
# ---------------------------------------------------------------------------

LOOKUP_INGREDIENT_RESEARCH_TOOL: Dict[str, Any] = {
    "name": "lookup_ingredient_research",
    "description": (
        "Look up pre-computed research for an ingredient from the database.\n\n"
        "WARNING: This database may be incomplete or empty. ALWAYS use web_search\n"
        "for ingredient research first. Only use this tool as a supplementary check\n"
        "AFTER you have already searched for the ingredient via web_search.\n\n"
        "Args:\n"
        "    ingredient: Ingredient name to look up\n\n"
        "Returns:\n"
        "    JSON string with research findings or not found message"
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "ingredient": {
                "type": "string",
                "description": "Ingredient name to look up",
            },
        },
        "required": ["ingredient"],
        "additionalProperties": False,
    },
}

CUSTOM_WEB_SEARCH_TOOL: Dict[str, Any] = {
    "name": "web_search",
    "description": (
        "Search the web for product safety information.\n\n"
        "Use this tool to find:\n"
        "- Manufacturer official ingredient/material lists and MSDS sheets\n"
        "- FDA/EPA/CPSC recalls and safety alerts\n"
        "- Per-ingredient scientific studies, IARC classifications, and toxicity data\n"
        "- Class action lawsuits and consumer complaints\n\n"
        "SEARCH TYPES:\n"
        '- "manufacturer": Official product pages, MSDS, ingredient lists\n'
        '- "regulatory": FDA.gov, Health Canada, EPA recalls and warnings\n'
        '- "ingredient": Per-ingredient safety research (PubMed, NIH, IARC, EPA, EWG)\n'
        '- "scientific": General scientific studies and research papers\n'
        '- "legal": Class action lawsuits, court records, settlements\n'
        '- "consumer": Reddit user experiences and reactions\n'
        '- "general": No domain filter\n\n'
        "IMPORTANT: For products with multiple ingredients, use search_type=\"ingredient\" to research\n"
        "individual ingredients like \"[ingredient name] toxicity\" or \"[ingredient name] IARC classification\".\n\n"
        "Results are filtered to credible sources based on search_type."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (keep under 400 characters)",
            },
            "search_type": {
                "type": "string",
                "enum": [
                    "manufacturer",
                    "regulatory",
                    "ingredient",
                    "scientific",
                    "legal",
                    "consumer",
                    "general",
                ],
                "description": "Type of search. Use 'ingredient' for per-ingredient safety research.",
            },
        },
        "required": ["query", "search_type"],
        "additionalProperties": False,
    },
}


ANTHROPIC_TOOLS: List[Dict[str, Any]] = [CUSTOM_WEB_SEARCH_TOOL, LOOKUP_INGREDIENT_RESEARCH_TOOL]


# ---------------------------------------------------------------------------
# Cohere ToolV2 schema converter
# ---------------------------------------------------------------------------

def to_cohere_tool(anthropic_tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an Anthropic tool dict to Cohere ToolV2 shape.

    Cohere expects:
        {
            "type": "function",
            "function": {
                "name": str,
                "description": str,
                "parameters": {json-schema-object},
            },
        }
    """
    return {
        "type": "function",
        "function": {
            "name": anthropic_tool["name"],
            "description": anthropic_tool["description"],
            "parameters": anthropic_tool["input_schema"],
        },
    }


COHERE_TOOLS: List[Dict[str, Any]] = [to_cohere_tool(t) for t in ANTHROPIC_TOOLS]


# ---------------------------------------------------------------------------
# LangChain @tool factory (returns BaseTool-compatible callables)
# ---------------------------------------------------------------------------

def make_langchain_tools(
    search_service: Any,
    supabase_client: Any = None,
) -> List[Any]:
    """Build LangChain tools bound to a SearchToolService + optional Supabase.

    Lazy-imports langchain_core so importing this module doesn't require
    langchain to be installed (matters for the Cohere-V2 config which doesn't
    use LangChain at all).
    """
    from langchain_core.tools import tool

    @tool
    async def web_search(query: str, search_type: str = "general") -> str:
        """Search the web for product safety information.

        Args:
            query: Search query (keep under 400 characters).
            search_type: One of manufacturer, regulatory, ingredient,
                scientific, legal, consumer, general.

        Returns:
            JSON string with search results.
        """
        if not search_service:
            return json.dumps({"error": "Search service not available", "results": []})

        # Async tool: under create_react_agent.ainvoke(), LangGraph awaits this on
        # the live event loop, so we await the async search service directly. A
        # *sync* tool gets offloaded to a worker thread with no event loop, where
        # asyncio.get_event_loop() raises "no current event loop in thread" — the
        # bug that silently broke every LangGraph search.
        try:
            result_str = await search_service.search(
                query=query, search_type=search_type
            )
            return json.dumps({
                "search_type": search_type,
                "query": query,
                "results": (result_str or "")[:2000],
            })
        except Exception as e:
            logger.warning("web_search tool failed: %s", e)
            return json.dumps({"error": str(e), "results": ""})

    @tool
    async def lookup_ingredient_research(ingredient: str) -> str:
        """Look up pre-computed research for an ingredient.

        WARNING: This database may be incomplete or empty. ALWAYS use web_search
        for ingredient research first. Use this only as a supplementary check.

        Args:
            ingredient: Ingredient name to look up.
        """
        if not supabase_client:
            return json.dumps({
                "ingredient": ingredient,
                "found": False,
                "reason": "Database not available",
            })
        try:
            # supabase-py is sync; run it off the event loop to avoid blocking.
            result = await asyncio.to_thread(
                lambda: (
                    supabase_client.table("ingredient_research")
                    .select("*")
                    .ilike("ingredient_name", f"%{ingredient}%")
                    .limit(1)
                    .execute()
                )
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
            return json.dumps(
                {"ingredient": ingredient, "found": False, "error": str(e)}
            )

    return [web_search, lookup_ingredient_research]


__all__ = [
    "LOOKUP_INGREDIENT_RESEARCH_TOOL",
    "CUSTOM_WEB_SEARCH_TOOL",
    "ANTHROPIC_TOOLS",
    "COHERE_TOOLS",
    "to_cohere_tool",
    "make_langchain_tools",
]
