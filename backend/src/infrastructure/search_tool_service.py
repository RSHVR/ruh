"""Search tool service - orchestrates search with caching and fallback."""

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .config import settings
from .search_clients.base import SearchResponse
from .search_clients.tavily import TavilySearchClient
from .search_clients.serper import SerperSearchClient

logger = logging.getLogger(__name__)

# Pricing per search (for cost tracking)
SEARCH_PRICING = {
    "tavily": 0.008,  # $8/1000 searches (advanced depth, 2 credits)
    "tavily_extract": 0.002,  # ~$2/1000 extractions (estimate)
    "serper": 0.001,  # $1/1000 searches
    "anthropic": 0.010,  # $10/1000 searches (for comparison)
}

# Search types that benefit from full content extraction
# These often have critical data (ingredients, recall details) that snippets miss
EXTRACT_ENABLED_TYPES = {
    "manufacturer",  # Need complete ingredient/material lists
    "regulatory",    # Need full recall notices, safety alerts
}

# Configuration for extraction behavior
EXTRACT_CONFIG = {
    "extract_top_n": 2,      # Extract from top 2 URLs
    "min_score": 0.5,        # Only extract if score > 0.5
    "max_chars_per_source": 4000,  # Prevent context explosion
}


@dataclass
class SearchUsage:
    """Track search API usage."""

    provider: str
    query: str
    search_type: str
    latency_ms: float
    result_count: int
    cached: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def cost(self) -> float:
        """Calculate cost for this search."""
        if self.cached:
            return 0.0
        return SEARCH_PRICING.get(self.provider, 0.01)


class LRUCache:
    """Simple LRU cache for in-memory caching."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache if exists and not expired."""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl_seconds:
            del self._cache[key]
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, time.time())

        # Evict oldest items if over capacity
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)


class SearchToolService:
    """Orchestrates search with caching, fallback, and cost tracking.

    Architecture:
    - L1: In-memory LRU cache (1000 entries, 1hr TTL)
    - L2: Supabase search_cache table (24hr TTL)
    - Fallback: Tavily → Serper → Stale Cache → Empty
    """

    def __init__(
        self,
        supabase_client: Optional[Any] = None,
        tavily_api_key: Optional[str] = None,
        serper_api_key: Optional[str] = None,
    ) -> None:
        """Initialize the search service.

        Args:
            supabase_client: Supabase client for L2 cache
            tavily_api_key: Tavily API key (falls back to settings)
            serper_api_key: Serper API key (falls back to settings)
        """
        self._supabase = supabase_client
        self._memory_cache = LRUCache(max_size=1000, ttl_seconds=3600)  # 1hr TTL

        # Initialize search clients
        tavily_key = tavily_api_key or settings.tavily_api_key
        serper_key = serper_api_key or settings.serper_api_key

        self._tavily: Optional[TavilySearchClient] = None
        self._serper: Optional[SerperSearchClient] = None

        if tavily_key:
            self._tavily = TavilySearchClient(api_key=tavily_key)
            logger.info("Tavily search client initialized")
        else:
            logger.warning("Tavily API key not configured")

        if serper_key:
            self._serper = SerperSearchClient(api_key=serper_key)
            logger.info("Serper search client initialized (fallback)")
        else:
            logger.warning("Serper API key not configured (no fallback)")

        # Usage tracking
        self._usage_log: List[SearchUsage] = []

    def _generate_cache_key(self, query: str, search_type: str) -> str:
        """Generate deterministic cache key from query and search type."""
        # Normalize query: lowercase, remove extra whitespace
        normalized = " ".join(query.lower().split())
        key_string = f"{search_type}:{normalized}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    async def _get_from_supabase_cache(self, cache_key: str) -> Optional[SearchResponse]:
        """Get from Supabase L2 cache if available and not expired."""
        if not self._supabase:
            return None

        try:
            response = self._supabase.table("search_cache").select("*").eq(
                "query_hash", cache_key
            ).execute()

            if response.data:
                cached = response.data[0]
                expires_at = datetime.fromisoformat(
                    cached["expires_at"].replace("Z", "+00:00")
                )

                if datetime.now(timezone.utc) < expires_at:
                    # Cache hit - parse stored results
                    results_data = cached.get("results", {})
                    return SearchResponse(
                        query=results_data.get("query", ""),
                        results=[],  # We only need the formatted output
                        provider=cached.get("provider", "cache"),
                    )

            return None
        except Exception as e:
            logger.warning(f"Supabase cache read failed: {e}")
            return None

    async def _store_in_supabase_cache(
        self,
        cache_key: str,
        search_type: str,
        response: SearchResponse,
    ) -> None:
        """Store result in Supabase L2 cache."""
        if not self._supabase:
            return

        try:
            ttl_hours = settings.search_cache_ttl_hours
            expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

            cache_data = {
                "query_hash": cache_key,
                "search_type": search_type,
                "provider": response.provider,
                "results": {
                    "query": response.query,
                    "formatted": response.format_for_claude(),
                    "result_count": len(response.results),
                },
                "expires_at": expires_at.isoformat(),
            }

            self._supabase.table("search_cache").upsert(
                cache_data, on_conflict="query_hash,search_type"
            ).execute()

            logger.debug(f"Stored in Supabase cache: {cache_key[:16]}...")
        except Exception as e:
            logger.warning(f"Supabase cache write failed: {e}")

    async def search(
        self,
        query: str,
        search_type: str = "general",
        force_extract: bool = False,
    ) -> str:
        """Execute a search with caching, fallback, and optional extraction.

        For search types in EXTRACT_ENABLED_TYPES (manufacturer, regulatory),
        this will automatically extract full content from top URLs to get
        complete ingredient lists, recall details, etc.

        Args:
            query: The search query
            search_type: Type of search (manufacturer, regulatory, scientific, legal, general)
            force_extract: Force extraction even for non-enabled search types

        Returns:
            Formatted search results for Claude tool_result
        """
        start_time = time.time()

        # Determine if we should use extraction
        use_extraction = (
            self._tavily is not None
            and (search_type in EXTRACT_ENABLED_TYPES or force_extract)
        )

        # Use different cache key for extracted vs non-extracted results
        cache_suffix = "_extracted" if use_extraction else ""
        cache_key = self._generate_cache_key(query, search_type) + cache_suffix

        # 1. Check in-memory L1 cache
        cached = self._memory_cache.get(cache_key)
        if cached:
            logger.info(f"L1 cache HIT: {query[:50]}...{' (extracted)' if use_extraction else ''}")
            self._log_usage("cache", query, search_type, 0, 0, cached=True)
            return cached

        # 2. Check Supabase L2 cache
        supabase_cached = await self._get_from_supabase_cache(cache_key)
        if supabase_cached:
            formatted = supabase_cached.format_for_claude() if supabase_cached.results else ""
            if formatted:
                logger.info(f"L2 cache HIT: {query[:50]}...")
                self._memory_cache.set(cache_key, formatted)  # Promote to L1
                self._log_usage("cache", query, search_type, 0, 0, cached=True)
                return formatted

        # 3. Try Tavily (primary) - with or without extraction
        if self._tavily:
            try:
                if use_extraction:
                    # Enhanced search with content extraction
                    formatted = await self._tavily.search_and_extract(
                        query=query,
                        search_type=search_type,
                        extract_top_n=EXTRACT_CONFIG["extract_top_n"],
                        min_score=EXTRACT_CONFIG["min_score"],
                    )
                    provider = "tavily+extract"
                    # Log both search and extract costs
                    self._log_usage(
                        "tavily", query, search_type, 0, 0, cached=False
                    )
                    self._log_usage(
                        "tavily_extract", query, search_type, 0,
                        EXTRACT_CONFIG["extract_top_n"], cached=False
                    )
                else:
                    # Standard search (snippets only)
                    response = await self._tavily.search(query, search_type)
                    formatted = response.format_for_claude()
                    provider = "tavily"

                    latency_ms = (time.time() - start_time) * 1000
                    self._log_usage(
                        provider, query, search_type, latency_ms, len(response.results)
                    )

                # Cache the result
                self._memory_cache.set(cache_key, formatted)
                # Note: For extracted results, we store the full formatted output
                # This is fine since we're caching the final output, not the raw response

                return formatted

            except Exception as e:
                logger.warning(f"Tavily failed: {e}, trying Serper fallback...")

        # 4. Try Serper (fallback) - no extraction support
        if self._serper:
            try:
                response = await self._serper.search(query, search_type)
                formatted = response.format_for_claude()

                # Cache even Serper results
                self._memory_cache.set(cache_key, formatted)

                latency_ms = (time.time() - start_time) * 1000
                self._log_usage(
                    "serper", query, search_type, latency_ms, len(response.results)
                )
                return formatted

            except Exception as e:
                logger.error(f"Serper also failed: {e}")

        # 5. No results available
        logger.error(f"All search providers failed for: {query[:50]}...")
        return "Search unavailable. Please try again later."

    async def search_parallel(
        self, queries: List[tuple[str, str]]
    ) -> List[str]:
        """Execute multiple searches in parallel.

        Args:
            queries: List of (query, search_type) tuples

        Returns:
            List of formatted search results in same order
        """
        tasks = [self.search(q, st) for q, st in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error strings
        return [
            r if isinstance(r, str) else f"Search error: {r}"
            for r in results
        ]

    def _log_usage(
        self,
        provider: str,
        query: str,
        search_type: str,
        latency_ms: float,
        result_count: int,
        cached: bool = False,
    ) -> None:
        """Log search usage for cost tracking."""
        usage = SearchUsage(
            provider=provider,
            query=query[:100],  # Truncate for storage
            search_type=search_type,
            latency_ms=latency_ms,
            result_count=result_count,
            cached=cached,
        )
        self._usage_log.append(usage)

        if not cached:
            logger.info(
                f"Search: {provider} | {search_type} | {latency_ms:.0f}ms | "
                f"{result_count} results | ${usage.cost:.4f}"
            )

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get summary of search usage for this session."""
        if not self._usage_log:
            return {"total_searches": 0, "total_cost": 0.0}

        total_cost = sum(u.cost for u in self._usage_log)
        by_provider = {}
        for u in self._usage_log:
            if u.provider not in by_provider:
                by_provider[u.provider] = {"count": 0, "cost": 0.0}
            by_provider[u.provider]["count"] += 1
            by_provider[u.provider]["cost"] += u.cost

        cache_hits = sum(1 for u in self._usage_log if u.cached)

        return {
            "total_searches": len(self._usage_log),
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hits / len(self._usage_log) if self._usage_log else 0,
            "total_cost": total_cost,
            "by_provider": by_provider,
        }

    def clear_usage_log(self) -> None:
        """Clear the usage log (call at end of analysis)."""
        self._usage_log.clear()

    async def close(self) -> None:
        """Close all search clients."""
        if self._tavily:
            await self._tavily.close()
        if self._serper:
            await self._serper.close()
