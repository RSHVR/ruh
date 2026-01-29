"""Token tracking service for Claude API usage.

Provides:
- Pre-request token counting
- Post-request usage tracking
- Cost calculation
- Aggregate tracking per analysis session
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from anthropic import Anthropic

from .config import settings

logger = logging.getLogger(__name__)


# Claude Sonnet 4.5 pricing (per 1M tokens)
PRICING = {
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,   # $3 per 1M input tokens
        "output": 15.00,  # $15 per 1M output tokens
    },
    # Add other models as needed
    "claude-sonnet-4-20250514": {
        "input": 3.00,
        "output": 15.00,
    },
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 3.00, "output": 15.00}

# Web search pricing (per search)
SEARCH_PRICING = {
    "tavily": 0.008,     # $8/1000 searches (advanced mode, 2 credits)
    "serper": 0.001,     # $1/1000 searches
    "anthropic": 0.010,  # $10/1000 searches (native web_search_20250305)
    "cache": 0.0,        # Free (cached result)
}


@dataclass
class TokenUsage:
    """Token usage for a single API call."""

    call_name: str  # e.g., "product_extraction", "review_insights", "agent_analysis"
    model: str
    input_tokens: int
    output_tokens: int
    input_tokens_estimated: Optional[int] = None  # Pre-request estimate
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def input_cost(self) -> float:
        """Cost for input tokens in USD."""
        pricing = PRICING.get(self.model, DEFAULT_PRICING)
        return (self.input_tokens / 1_000_000) * pricing["input"]

    @property
    def output_cost(self) -> float:
        """Cost for output tokens in USD."""
        pricing = PRICING.get(self.model, DEFAULT_PRICING)
        return (self.output_tokens / 1_000_000) * pricing["output"]

    @property
    def total_cost(self) -> float:
        """Total cost in USD."""
        return self.input_cost + self.output_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "call_name": self.call_name,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "input_tokens_estimated": self.input_tokens_estimated,
            "total_tokens": self.total_tokens,
            "input_cost_usd": round(self.input_cost, 6),
            "output_cost_usd": round(self.output_cost, 6),
            "total_cost_usd": round(self.total_cost, 6),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SearchUsage:
    """Track a single web search API call."""

    provider: str  # "tavily", "serper", "anthropic", or "cache"
    query: str
    search_type: str  # "manufacturer", "regulatory", "scientific", "legal", "general"
    result_count: int
    latency_ms: float
    cached: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def cost(self) -> float:
        """Calculate cost for this search."""
        if self.cached:
            return 0.0
        return SEARCH_PRICING.get(self.provider, 0.01)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "provider": self.provider,
            "query": self.query[:100],  # Truncate for storage
            "search_type": self.search_type,
            "result_count": self.result_count,
            "latency_ms": round(self.latency_ms, 2),
            "cached": self.cached,
            "cost_usd": round(self.cost, 6),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AnalysisTokenSummary:
    """Aggregated token and search usage for an entire analysis."""

    url_hash: str
    calls: List[TokenUsage] = field(default_factory=list)
    searches: List[SearchUsage] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens across all calls."""
        return sum(call.input_tokens for call in self.calls)

    @property
    def total_output_tokens(self) -> int:
        """Total output tokens across all calls."""
        return sum(call.output_tokens for call in self.calls)

    @property
    def total_tokens(self) -> int:
        """Total tokens across all calls."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def token_cost(self) -> float:
        """Total token cost in USD across all calls."""
        return sum(call.total_cost for call in self.calls)

    @property
    def search_cost(self) -> float:
        """Total search cost in USD across all searches."""
        return sum(search.cost for search in self.searches)

    @property
    def total_cost(self) -> float:
        """Total cost (tokens + searches) in USD."""
        return self.token_cost + self.search_cost

    @property
    def call_count(self) -> int:
        """Number of Claude API calls made."""
        return len(self.calls)

    @property
    def search_count(self) -> int:
        """Number of web searches performed."""
        return len(self.searches)

    @property
    def search_cache_hits(self) -> int:
        """Number of cached search results used."""
        return sum(1 for s in self.searches if s.cached)

    @property
    def search_cache_hit_rate(self) -> float:
        """Cache hit rate for searches (0-1)."""
        if not self.searches:
            return 0.0
        return self.search_cache_hits / len(self.searches)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "url_hash": self.url_hash,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "token_cost_usd": round(self.token_cost, 6),
            "search_cost_usd": round(self.search_cost, 6),
            "total_cost_usd": round(self.total_cost, 6),
            "call_count": self.call_count,
            "search_count": self.search_count,
            "search_cache_hits": self.search_cache_hits,
            "calls": [call.to_dict() for call in self.calls],
            "searches": [search.to_dict() for search in self.searches],
        }

    def log_summary(self):
        """Log a formatted summary of token and search usage."""
        logger.info("=" * 60)
        logger.info("💰 USAGE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"   URL Hash: {self.url_hash[:16]}...")
        logger.info(f"   Claude API Calls: {self.call_count}")
        logger.info(f"   Web Searches: {self.search_count}")
        logger.info("-" * 60)

        # Token usage breakdown
        if self.calls:
            logger.info("   📊 CLAUDE API USAGE")
            for call in self.calls:
                logger.info(f"      • {call.call_name}")
                logger.info(f"        Input:  {call.input_tokens:,} tokens (${call.input_cost:.4f})")
                logger.info(f"        Output: {call.output_tokens:,} tokens (${call.output_cost:.4f})")
                logger.info(f"        Total:  {call.total_tokens:,} tokens (${call.total_cost:.4f})")

        # Search usage breakdown
        if self.searches:
            logger.info("-" * 60)
            logger.info("   🔍 WEB SEARCH USAGE")
            by_provider: Dict[str, Dict[str, Any]] = {}
            for search in self.searches:
                if search.provider not in by_provider:
                    by_provider[search.provider] = {"count": 0, "cost": 0.0, "cached": 0}
                by_provider[search.provider]["count"] += 1
                by_provider[search.provider]["cost"] += search.cost
                if search.cached:
                    by_provider[search.provider]["cached"] += 1

            for provider, stats in by_provider.items():
                cache_info = f" ({stats['cached']} cached)" if stats['cached'] else ""
                logger.info(f"      • {provider}: {stats['count']} searches{cache_info} (${stats['cost']:.4f})")

        logger.info("-" * 60)
        logger.info("   📈 TOTALS")
        logger.info(f"      Tokens:  {self.total_tokens:,} (${self.token_cost:.4f})")
        if self.searches:
            logger.info(f"      Searches: {self.search_count} ({self.search_cache_hit_rate:.0%} cached) (${self.search_cost:.4f})")
        logger.info(f"      TOTAL:   ${self.total_cost:.4f} USD")
        logger.info("=" * 60)


class TokenTracker:
    """Service for tracking Claude API token usage.

    Usage:
        tracker = TokenTracker()

        # Start tracking for an analysis
        tracker.start_analysis("abc123")

        # Before API call - count tokens (optional)
        estimated = tracker.count_tokens(model, system, messages)

        # After API call - record usage
        tracker.record_usage("product_extraction", model, response.usage)

        # Get summary
        summary = tracker.get_summary()
        summary.log_summary()
    """

    def __init__(self):
        """Initialize token tracker."""
        self.client: Optional[Anthropic] = None
        self._current_analysis: Optional[AnalysisTokenSummary] = None

    def _init_client(self):
        """Initialize Anthropic client lazily."""
        if self.client is None:
            self.client = Anthropic(api_key=settings.anthropic_api_key)

    def start_analysis(self, url_hash: str):
        """Start tracking a new analysis.

        Args:
            url_hash: Product URL hash to track
        """
        self._current_analysis = AnalysisTokenSummary(url_hash=url_hash)
        logger.info(f"🔢 Token tracking started for {url_hash[:16]}...")

    def count_tokens(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """Count tokens before sending a request.

        Uses the Anthropic count_tokens API to estimate input tokens.

        Args:
            model: Model name
            messages: List of message dicts
            system: Optional system prompt
            tools: Optional list of tool definitions

        Returns:
            Estimated input token count
        """
        self._init_client()

        try:
            params: Dict[str, Any] = {
                "model": model,
                "messages": messages,
            }

            if system:
                params["system"] = system

            if tools:
                params["tools"] = tools

            response = self.client.messages.count_tokens(**params)
            estimated_tokens = response.input_tokens

            logger.info(f"🔢 Pre-request estimate: {estimated_tokens:,} input tokens")
            return estimated_tokens

        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            return 0

    def record_usage(
        self,
        call_name: str,
        model: str,
        usage: Any,  # anthropic.types.Usage
        estimated_input: Optional[int] = None,
    ) -> TokenUsage:
        """Record token usage from an API response.

        Args:
            call_name: Name of the API call (e.g., "product_extraction")
            model: Model used
            usage: Usage object from API response
            estimated_input: Optional pre-request estimate

        Returns:
            TokenUsage object
        """
        token_usage = TokenUsage(
            call_name=call_name,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            input_tokens_estimated=estimated_input,
        )

        # Log detailed usage
        self._log_usage(token_usage)

        # Add to current analysis if tracking
        if self._current_analysis:
            self._current_analysis.calls.append(token_usage)

        return token_usage

    def _log_usage(self, usage: TokenUsage):
        """Log formatted token usage."""
        logger.info("-" * 50)
        logger.info(f"💰 TOKEN USAGE: {usage.call_name}")
        logger.info("-" * 50)

        if usage.input_tokens_estimated:
            diff = usage.input_tokens - usage.input_tokens_estimated
            diff_pct = (diff / usage.input_tokens_estimated) * 100 if usage.input_tokens_estimated else 0
            logger.info(f"   Estimated:  {usage.input_tokens_estimated:,} tokens")
            logger.info(f"   Actual:     {usage.input_tokens:,} tokens ({diff:+,}, {diff_pct:+.1f}%)")
        else:
            logger.info(f"   Input:      {usage.input_tokens:,} tokens")

        logger.info(f"   Output:     {usage.output_tokens:,} tokens")
        logger.info(f"   Total:      {usage.total_tokens:,} tokens")
        logger.info("-" * 50)
        logger.info(f"   Input cost:  ${usage.input_cost:.4f}")
        logger.info(f"   Output cost: ${usage.output_cost:.4f}")
        logger.info(f"   Total cost:  ${usage.total_cost:.4f}")
        logger.info("-" * 50)

    def record_search(
        self,
        provider: str,
        query: str,
        search_type: str,
        result_count: int,
        latency_ms: float,
        cached: bool = False,
    ) -> SearchUsage:
        """Record a web search for cost tracking.

        Args:
            provider: Search provider ("tavily", "serper", "anthropic", "cache")
            query: The search query
            search_type: Type of search performed
            result_count: Number of results returned
            latency_ms: Search latency in milliseconds
            cached: Whether this was a cache hit

        Returns:
            SearchUsage object
        """
        search_usage = SearchUsage(
            provider=provider,
            query=query,
            search_type=search_type,
            result_count=result_count,
            latency_ms=latency_ms,
            cached=cached,
        )

        # Log the search
        if cached:
            logger.debug(f"🔍 Search (cached): {query[:50]}...")
        else:
            logger.info(
                f"🔍 Search [{provider}]: {query[:50]}... | "
                f"{result_count} results | {latency_ms:.0f}ms | ${search_usage.cost:.4f}"
            )

        # Add to current analysis if tracking
        if self._current_analysis:
            self._current_analysis.searches.append(search_usage)

        return search_usage

    def record_search_from_service(self, usage_summary: Dict[str, Any]) -> None:
        """Record search usage from SearchToolService summary.

        This is called at the end of an analysis to merge search costs
        from the SearchToolService into the token tracker.

        Args:
            usage_summary: Dict from SearchToolService.get_usage_summary()
        """
        if not self._current_analysis:
            return

        # Log the merged summary
        total_searches = usage_summary.get("total_searches", 0)
        cache_hits = usage_summary.get("cache_hits", 0)
        total_cost = usage_summary.get("total_cost", 0.0)

        if total_searches > 0:
            logger.info(
                f"🔍 Search summary merged: {total_searches} searches, "
                f"{cache_hits} cached, ${total_cost:.4f}"
            )

    def get_summary(self) -> Optional[AnalysisTokenSummary]:
        """Get the current analysis summary.

        Returns:
            AnalysisTokenSummary or None if no analysis is being tracked
        """
        return self._current_analysis

    def finish_analysis(self) -> Optional[AnalysisTokenSummary]:
        """Finish tracking and return the summary.

        Returns:
            Final AnalysisTokenSummary
        """
        summary = self._current_analysis
        if summary:
            summary.log_summary()
        self._current_analysis = None
        return summary


# Global instance for convenience
token_tracker = TokenTracker()
