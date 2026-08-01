"""Unified Product Safety Agent with feature flag routing.

This module provides a unified interface for product safety analysis that
routes between two implementations based on configuration:

1. LangGraph Agent (Cohere + Claude Haiku): ~40-50% cheaper
   - Uses Cohere Command R+ for research and analysis
   - Uses Claude Haiku for adversarial verification
   - Enabled via `use_langgraph_agent=True` in settings

2. Claude Agent (Claude Sonnet): Original implementation
   - Uses Claude Sonnet 4.5 for all operations
   - Default fallback for stability

The routing is transparent to callers - both implementations share the
same interface (analyze_extracted_product, analyze_product).
"""

import logging
from typing import Any, Dict, List, Optional

from .config import settings
from .token_tracker import TokenTracker
from .search_tool_service import SearchToolService

logger = logging.getLogger(__name__)


class ProductSafetyAgentWrapper:
    """Unified wrapper that routes to LangGraph or Claude agent based on config.

    This class provides a single interface for product safety analysis,
    abstracting away the implementation choice. It supports:

    - Feature flag routing (use_langgraph_agent)
    - Graceful fallback to Claude if LangGraph fails
    - Consistent interface regardless of backend

    Usage:
        agent = ProductSafetyAgentWrapper(token_tracker=tracker)
        result = await agent.analyze_extracted_product(product_data, url, ...)
    """

    def __init__(
        self,
        token_tracker: Optional[TokenTracker] = None,
        search_service: Optional[SearchToolService] = None,
        supabase_client: Any = None,
    ):
        """Initialize the safety agent wrapper.

        Args:
            token_tracker: Token usage tracker (shared across both implementations)
            search_service: Search service for web searches
            supabase_client: Supabase client for database operations
        """
        self.token_tracker = token_tracker or TokenTracker()
        self.search_service = search_service
        self.supabase_client = supabase_client

        # Check which implementation to use
        self.use_langgraph = settings.use_langgraph_agent and settings.cohere_api_key

        # Lazy-initialized agents
        self._langgraph_agent = None
        self._claude_agent = None

        if self.use_langgraph:
            logger.info("🚀 SafetyAgent: LangGraph mode enabled (Cohere + Claude Haiku)")
        else:
            logger.info("🔷 SafetyAgent: Claude mode (Claude Sonnet)")

    def _get_langgraph_agent(self):
        """Lazily initialize LangGraph agent."""
        if self._langgraph_agent is None:
            from .langgraph_agent import LangGraphSafetyAgent

            self._langgraph_agent = LangGraphSafetyAgent(
                token_tracker=self.token_tracker,
                search_service=self.search_service,
                supabase_client=self.supabase_client,
            )
        return self._langgraph_agent

    def _get_claude_agent(self):
        """Lazily initialize Claude agent."""
        if self._claude_agent is None:
            from .claude_agent import ProductSafetyAgent

            self._claude_agent = ProductSafetyAgent(
                token_tracker=self.token_tracker,
                search_service=self.search_service,
                supabase_client=self.supabase_client,
            )
        return self._claude_agent

    async def analyze_extracted_product(
        self,
        product_data: Dict[str, Any],
        product_url: str,
        allergen_profile: List[str] = None,
        pfas_database: List[Dict[str, Any]] = None,
        allergen_database: List[Dict[str, Any]] = None,
        user_region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze product that was already extracted from HTML.

        This is the primary analysis method, called when we have pre-extracted
        product data from the scraper.

        Args:
            product_data: Structured product data from ClaudeQueryService
            product_url: Original product URL
            allergen_profile: User's allergen concerns
            pfas_database: PFAS compounds knowledge base
            allergen_database: Allergens knowledge base

        Returns:
            Safety analysis dictionary with allergens, PFAS, concerns
        """
        if self.use_langgraph:
            try:
                logger.info("📊 Using LangGraph agent for analysis")
                agent = self._get_langgraph_agent()
                return await agent.analyze_extracted_product(
                    product_data=product_data,
                    product_url=product_url,
                    allergen_profile=allergen_profile,
                    pfas_database=pfas_database,
                    allergen_database=allergen_database,
                )
            except Exception as e:
                logger.error(f"❌ LangGraph agent failed: {e}")
                logger.info("🔄 Falling back to Claude agent")
                # Fall through to Claude agent

        # Use Claude agent (either by config or fallback)
        logger.info("📊 Using Claude agent for analysis")
        agent = self._get_claude_agent()
        return await agent.analyze_extracted_product(
            product_data=product_data,
            product_url=product_url,
            allergen_profile=allergen_profile,
            pfas_database=pfas_database,
            allergen_database=allergen_database,
            user_region=user_region,
        )

    async def analyze_product(
        self,
        product_url: str,
        allergen_profile: List[str] = None,
        pfas_database: List[Dict[str, Any]] = None,
        allergen_database: List[Dict[str, Any]] = None,
        user_region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze product directly from URL (fallback when scraping fails).

        This method is used when we don't have pre-extracted product data
        and need to fetch/analyze the product page directly.

        Note: LangGraph agent doesn't support direct URL analysis yet,
        so this always uses the Claude agent.

        Args:
            product_url: Product URL to analyze
            allergen_profile: User's allergen concerns
            pfas_database: PFAS compounds knowledge base
            allergen_database: Allergens knowledge base

        Returns:
            Safety analysis dictionary
        """
        # Direct URL analysis uses Claude agent (has web_fetch capability)
        logger.info("📊 Using Claude agent for direct URL analysis")
        agent = self._get_claude_agent()
        return await agent.analyze_product(
            product_url=product_url,
            allergen_profile=allergen_profile,
            pfas_database=pfas_database,
            allergen_database=allergen_database,
            user_region=user_region,
        )

    async def find_alternatives(
        self,
        product_analysis: Dict[str, Any],
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Find safer alternative products.

        Placeholder for Phase 4 implementation.

        Args:
            product_analysis: Analysis of the original product
            max_results: Maximum number of alternatives to return

        Returns:
            List of alternative product suggestions
        """
        # Both agents delegate to Claude for this (not implemented yet)
        agent = self._get_claude_agent()
        return await agent.find_alternatives(product_analysis, max_results)

    async def close(self) -> None:
        """Cleanup resources for both agents."""
        if self._langgraph_agent is not None:
            await self._langgraph_agent.close()

        if self._claude_agent is not None:
            await self._claude_agent.close()


# Convenience alias for backward compatibility
SafetyAgent = ProductSafetyAgentWrapper
