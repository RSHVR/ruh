"""Custom web content extraction service (simplified).

Primary tool: Trafilatura (fetching + content extraction)
Fallback: Playwright (only for JS-heavy sites like EWG, EPA)

Cost savings: $0 vs $0.002/extraction with Tavily
"""

import asyncio
import hashlib
import logging
import re
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlparse

import trafilatura
from playwright.async_api import Browser, async_playwright

from src.infrastructure.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    """Extracted content from a web page."""

    url: str
    title: Optional[str] = None
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # Extraction info
    extractor: str = "trafilatura"
    js_rendered: bool = False
    extraction_time_ms: int = 0
    content_length: int = 0

    def __post_init__(self) -> None:
        if self.text and not self.content_length:
            self.content_length = len(self.text)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "url": self.url,
            "title": self.title,
            "text_content": self.text,
            "metadata": self.metadata,
            "extractor_used": self.extractor,
            "js_rendered": self.js_rendered,
            "extraction_time_ms": self.extraction_time_ms,
            "content_length": self.content_length,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExtractedContent":
        """Create from dictionary."""
        return cls(
            url=data["url"],
            title=data.get("title"),
            text=data.get("text_content", ""),
            metadata=data.get("metadata", {}),
            extractor=data.get("extractor_used", "trafilatura"),
            js_rendered=data.get("js_rendered", False),
            extraction_time_ms=data.get("extraction_time_ms", 0),
            content_length=data.get("content_length", 0),
        )


class LRUCache:
    """Simple LRU cache with TTL."""

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[ExtractedContent, datetime]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[ExtractedContent]:
        async with self._lock:
            if key not in self._cache:
                return None
            content, timestamp = self._cache[key]
            if datetime.utcnow() - timestamp > timedelta(seconds=self.ttl_seconds):
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return content

    async def set(self, key: str, value: ExtractedContent) -> None:
        async with self._lock:
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (value, datetime.utcnow())


class PlaywrightPool:
    """Lazy-initialized Playwright browser pool for JS rendering."""

    def __init__(self, pool_size: int = 2):
        self.pool_size = pool_size
        self._browsers: list[Browser] = []
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._playwright = None
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            logger.info(f"Initializing Playwright pool ({self.pool_size} browsers)")
            self._playwright = await async_playwright().start()
            self._semaphore = asyncio.Semaphore(self.pool_size)
            for _ in range(self.pool_size):
                browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
                )
                self._browsers.append(browser)
            self._initialized = True

    async def get_html(self, url: str, timeout_ms: int = 30000) -> str:
        """Fetch URL with JS rendering."""
        await self._ensure_initialized()
        async with self._semaphore:  # type: ignore
            browser = self._browsers[hash(url) % len(self._browsers)]
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            )
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                await asyncio.sleep(1)  # Let JS settle
                return await page.content()
            finally:
                await context.close()

    async def close(self) -> None:
        for browser in self._browsers:
            await browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False


class ExtractionService:
    """Simplified extraction service using Trafilatura as primary tool.

    Architecture:
    1. Try Trafilatura first (handles 90% of sites)
    2. Fall back to Playwright only for JS-heavy sites (EWG, EPA)
    3. Cache results in L1 (memory) and L2 (Supabase)
    """

    # Sites that ACTUALLY need JS rendering (verified by audit)
    JS_REQUIRED_DOMAINS = [
        "ewg.org",
        "epa.gov",
    ]

    # Cache TTL: 30 days
    CACHE_TTL_SECONDS = 30 * 24 * 60 * 60

    # Minimum content threshold - below this, try Playwright
    MIN_CONTENT_CHARS = 500

    def __init__(
        self,
        supabase_client: Any = None,
        use_cache: bool = True,
        playwright_pool_size: int = 2,
    ):
        self.supabase = supabase_client
        self.use_cache = use_cache
        self._l1_cache = LRUCache(max_size=500, ttl_seconds=3600)
        self._playwright = PlaywrightPool(pool_size=playwright_pool_size)

        self._stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "trafilatura_extractions": 0,
            "playwright_extractions": 0,
            "errors": 0,
        }

    def _get_cache_key(self, url: str) -> str:
        normalized = url.lower().strip().rstrip("/")
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _needs_js(self, url: str) -> bool:
        return any(domain in url for domain in self.JS_REQUIRED_DOMAINS)

    def _extract_metadata(self, html: str, url: str) -> dict[str, Any]:
        """Extract metadata using Trafilatura + regex for structured fields."""
        meta = trafilatura.extract_metadata(html)
        result = {}

        if meta:
            if meta.title:
                # Clean title (remove " - PubMed" suffix etc)
                result["title"] = re.sub(r"\s*-\s*(PubMed|PMC).*$", "", meta.title)
            if meta.author:
                result["author"] = meta.author
            if meta.date:
                result["date"] = meta.date
            if meta.sitename:
                result["sitename"] = meta.sitename
            if meta.description:
                result["description"] = meta.description

        # Extract structured IDs from URL or content
        if "pubmed" in url or "pmc" in url:
            # PMID from URL
            pmid_match = re.search(r"pubmed[./](\d+)", url)
            if pmid_match:
                result["pmid"] = pmid_match.group(1)

            # PMC ID from URL
            pmc_match = re.search(r"PMC(\d+)", url)
            if pmc_match:
                result["pmc_id"] = f"PMC{pmc_match.group(1)}"

        return result

    async def _get_from_l2_cache(self, cache_key: str) -> Optional[ExtractedContent]:
        if not self.supabase:
            return None
        try:
            response = (
                self.supabase.table("extracted_content")
                .select("*")
                .eq("url_hash", cache_key)
                .gt("expires_at", datetime.utcnow().isoformat())
                .limit(1)
                .execute()
            )
            if response.data:
                self._stats["l2_hits"] += 1
                return ExtractedContent.from_dict(response.data[0])
        except Exception as e:
            logger.warning(f"L2 cache lookup failed: {e}")
        return None

    async def _store_in_l2_cache(
        self, cache_key: str, url: str, content: ExtractedContent
    ) -> None:
        if not self.supabase:
            return
        try:
            domain = urlparse(url).netloc
            expires_at = datetime.utcnow() + timedelta(seconds=self.CACHE_TTL_SECONDS)
            data = {
                "url": url,
                "url_hash": cache_key,
                "domain": domain,
                "expires_at": expires_at.isoformat(),
                **content.to_dict(),
            }
            self.supabase.table("extracted_content").upsert(
                data, on_conflict="url_hash"
            ).execute()
        except Exception as e:
            logger.warning(f"L2 cache store failed: {e}")

    async def extract(
        self,
        url: str,
        force_js: bool = False,
        skip_cache: bool = False,
    ) -> ExtractedContent:
        """Extract content from URL.

        Args:
            url: URL to extract
            force_js: Force Playwright rendering
            skip_cache: Bypass cache

        Returns:
            ExtractedContent with text and metadata
        """
        cache_key = self._get_cache_key(url)

        # Check caches
        if self.use_cache and not skip_cache:
            cached = await self._l1_cache.get(cache_key)
            if cached:
                self._stats["l1_hits"] += 1
                return cached

            cached = await self._get_from_l2_cache(cache_key)
            if cached:
                await self._l1_cache.set(cache_key, cached)
                return cached

        start_time = time.time()
        js_rendered = False
        html = None
        text = None

        # Step 1: Try Trafilatura first (unless force_js or known JS site)
        if not force_js and not self._needs_js(url):
            try:
                html = trafilatura.fetch_url(url)
                if html:
                    text = trafilatura.extract(
                        html,
                        include_tables=True,
                        include_links=True,
                        favor_recall=True,
                    )
                    self._stats["trafilatura_extractions"] += 1
            except Exception as e:
                logger.warning(f"Trafilatura failed for {url}: {e}")

        # Step 2: If content is too short, try Playwright
        if not text or len(text) < self.MIN_CONTENT_CHARS:
            try:
                logger.info(f"Using Playwright for {url} (trafilatura got {len(text) if text else 0} chars)")
                html = await self._playwright.get_html(url)
                text = trafilatura.extract(
                    html,
                    include_tables=True,
                    include_links=True,
                    favor_recall=True,
                )
                js_rendered = True
                self._stats["playwright_extractions"] += 1
            except Exception as e:
                logger.error(f"Playwright failed for {url}: {e}")
                self._stats["errors"] += 1
                if not text:
                    raise

        # Extract metadata
        metadata = self._extract_metadata(html, url) if html else {}
        title = metadata.pop("title", None)

        extraction_time_ms = int((time.time() - start_time) * 1000)

        content = ExtractedContent(
            url=url,
            title=title,
            text=text or "",
            metadata=metadata,
            extractor="playwright" if js_rendered else "trafilatura",
            js_rendered=js_rendered,
            extraction_time_ms=extraction_time_ms,
        )

        # Cache
        if self.use_cache:
            await self._l1_cache.set(cache_key, content)
            await self._store_in_l2_cache(cache_key, url, content)

        logger.info(
            f"Extracted {content.content_length:,} chars from {url} "
            f"in {extraction_time_ms}ms (js={js_rendered})"
        )

        return content

    async def extract_batch(
        self,
        urls: list[str],
        max_concurrent: int = 5,
    ) -> list[tuple[str, Optional[ExtractedContent], Optional[str]]]:
        """Extract from multiple URLs concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_one(url: str):
            async with semaphore:
                try:
                    content = await self.extract(url)
                    return (url, content, None)
                except Exception as e:
                    return (url, None, str(e))

        return list(await asyncio.gather(*[extract_one(url) for url in urls]))

    def get_stats(self) -> dict[str, Any]:
        total = (
            self._stats["l1_hits"]
            + self._stats["l2_hits"]
            + self._stats["trafilatura_extractions"]
            + self._stats["playwright_extractions"]
        )
        return {
            **self._stats,
            "cache_hit_rate": (
                (self._stats["l1_hits"] + self._stats["l2_hits"]) / max(1, total)
            ),
        }

    async def close(self) -> None:
        await self._playwright.close()
        logger.info(f"ExtractionService closed. Stats: {self.get_stats()}")


@asynccontextmanager
async def extraction_service_context(supabase_client: Any = None):
    """Context manager for ExtractionService."""
    service = ExtractionService(supabase_client=supabase_client)
    try:
        yield service
    finally:
        await service.close()
