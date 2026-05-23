"""Wraps a SearchToolService so every search call lands in the Tracer.

Configs receive this wrapper instead of the raw service. The underlying L1/L2
cache is preserved (we delegate to the wrapped service), and the `cached` flag
on each ToolCall comes from comparing the service's pre/post usage counters.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .tracer import Tracer

logger = logging.getLogger(__name__)


class TracedSearchService:
    """Wrap a SearchToolService instance + a Tracer.

    The wrapper preserves the same ``async def search(query, search_type, ...)``
    signature so configs don't care whether they got a raw service or a wrapped
    one. Every call's latency, cached-flag, and 200-char preview is captured.
    """

    def __init__(self, inner: Any, tracer: Tracer) -> None:
        self._inner = inner
        self._tracer = tracer

    async def search(
        self,
        query: str,
        search_type: str = "general",
        force_extract: bool = False,
    ) -> str:
        # Pre-call cache-hit detection: count cached searches before+after.
        # SearchToolService keeps usage in a list; if it gained an entry with
        # provider="cache", that call was a hit.
        before_cached = self._count_cache_hits()
        started = time.perf_counter()
        error: Optional[str] = None
        result_str = ""
        try:
            result_str = await self._inner.search(
                query=query, search_type=search_type, force_extract=force_extract
            )
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            logger.warning("TracedSearchService.search failed: %s", error)
            raise
        finally:
            latency_ms = (time.perf_counter() - started) * 1000
            after_cached = self._count_cache_hits()
            cached = after_cached > before_cached
            self._tracer.record_tool_call(
                tool="web_search",
                args={"query": query, "search_type": search_type},
                latency_ms=latency_ms,
                cached=cached,
                error=error,
                result_preview=result_str if result_str else "",
            )
        return result_str

    def _count_cache_hits(self) -> int:
        log = getattr(self._inner, "_usage_log", None)
        if not log:
            return 0
        return sum(1 for u in log if getattr(u, "cached", False))

    def get_usage_summary(self):
        return self._inner.get_usage_summary()

    async def close(self) -> None:
        if hasattr(self._inner, "close"):
            await self._inner.close()
