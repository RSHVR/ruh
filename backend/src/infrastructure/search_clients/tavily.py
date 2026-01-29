"""Tavily search client for AI-optimized web search and content extraction."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from tavily import AsyncTavilyClient

from .base import BaseSearchClient, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    """Content extracted from a URL."""

    url: str
    raw_content: str
    content_length: int = 0
    failed: bool = False
    error: Optional[str] = None

    def __post_init__(self):
        self.content_length = len(self.raw_content)


@dataclass
class ExtractResponse:
    """Response from Tavily extract API."""

    results: List[ExtractedContent] = field(default_factory=list)
    failed_results: List[ExtractedContent] = field(default_factory=list)
    response_time: float = 0.0

    def format_for_claude(self, max_chars_per_source: int = 3000) -> str:
        """Format extracted content for Claude tool_result.

        Args:
            max_chars_per_source: Max chars to include per source (prevents context explosion)
        """
        if not self.results:
            return "No content could be extracted from the URLs."

        output = []
        for item in self.results:
            content = item.raw_content[:max_chars_per_source]
            if len(item.raw_content) > max_chars_per_source:
                content += f"\n... [truncated, {item.content_length} total chars]"

            output.append(f"**Source:** {item.url}")
            output.append(f"**Content ({item.content_length} chars):**")
            output.append(content)
            output.append("---")

        if self.failed_results:
            output.append(f"\n⚠️ Failed to extract from {len(self.failed_results)} URL(s)")

        return "\n".join(output)

# Domain filters by search type (supports wildcards like *.gov)
DOMAIN_FILTERS: Dict[str, List[str]] = {
    "regulatory": ["*.gov", "healthcanada.gc.ca"],
    "scientific": [
        "pubmed.ncbi.nlm.nih.gov",
        "nih.gov",
        "iarc.who.int",
        "arxiv.org",
        "*.edu",
    ],
    "ingredient": [
        # Per-ingredient safety research - comprehensive scientific sources
        "pubmed.ncbi.nlm.nih.gov",
        "nih.gov",
        "iarc.who.int",
        "epa.gov",
        "cdc.gov",
        "ewg.org",  # Environmental Working Group - ingredient safety ratings
        "cosmetic-ingredient-review.org",  # CIR - cosmetic ingredient assessments
        "incidecoder.com",  # Ingredient decoder with research links
        "*.edu",
    ],
    "manufacturer": [],  # No filter - allow any manufacturer site
    "legal": ["uscourts.gov", "reuters.com", "nytimes.com", "wsj.com"],
    "consumer": ["reddit.com", "makeupalley.com"],  # Real user experiences
    "general": [],
}

# Domains to exclude by search type
# Consumer searches ALLOW Reddit for real user experiences
EXCLUDED_DOMAINS_DEFAULT = ["reddit.com", "quora.com", "pinterest.com", "medium.com"]
EXCLUDED_DOMAINS_CONSUMER = ["quora.com", "pinterest.com", "medium.com"]  # Only Reddit allowed


class TavilySearchClient(BaseSearchClient):
    """Tavily search client using AsyncTavilyClient for parallel queries.

    Best practices from Tavily skill docs:
    - Query length: Keep under 400 characters
    - include_answer=False: Since we use Claude for synthesis
    - chunks_per_source=3: Controls context size (max 500 chars per chunk)
    - Wildcard domains: Use *.gov instead of listing each .gov domain
    - AsyncTavilyClient: For parallel queries in agentic workflows
    """

    def __init__(self, api_key: str) -> None:
        """Initialize the Tavily client.

        Args:
            api_key: Tavily API key (format: tvly-...)
        """
        self.client = AsyncTavilyClient(api_key=api_key)
        self._api_key = api_key

    async def search(self, query: str, search_type: str = "general") -> SearchResponse:
        """Execute a search query using Tavily.

        Args:
            query: The search query (will be truncated to 400 chars)
            search_type: Type of search for domain filtering.
                Options: "manufacturer", "regulatory", "scientific", "legal", "general"

        Returns:
            SearchResponse with results
        """
        # Truncate query to 400 chars (Tavily best practice)
        if len(query) > 400:
            logger.warning(f"Query truncated from {len(query)} to 400 chars")
            query = query[:400]

        # Get domain filters for this search type
        include_domains = DOMAIN_FILTERS.get(search_type, [])

        # Consumer searches allow Reddit/Quora; others exclude them
        exclude_domains = (
            EXCLUDED_DOMAINS_CONSUMER if search_type == "consumer"
            else EXCLUDED_DOMAINS_DEFAULT
        )

        try:
            logger.info(f"Tavily search: {query[:50]}... (type={search_type})")

            response = await self.client.search(
                query=query,
                search_depth="advanced",  # Highest relevance, returns chunks (2 credits)
                max_results=5,
                chunks_per_source=3,  # Control token size (1-5, requires advanced depth)
                include_answer=False,  # Don't use - we have Claude for synthesis
                include_raw_content=False,  # Just content snippets, not full page
                include_domains=include_domains if include_domains else None,
                exclude_domains=exclude_domains,
                timeout=30,
            )

            # Parse results
            results = []
            for r in response.get("results", []):
                results.append(
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        content=r.get("content", ""),
                        score=r.get("score", 0.0),
                        source="tavily",
                        favicon=r.get("favicon"),
                    )
                )

            logger.info(
                f"Tavily returned {len(results)} results in {response.get('response_time', 0):.2f}s"
            )

            return SearchResponse(
                query=query,
                results=results,
                response_time=response.get("response_time", 0.0),
                request_id=response.get("request_id"),
                provider="tavily",
            )

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            # Re-raise specific errors for proper handling in service layer
            raise

    async def extract(
        self,
        urls: List[str],
        query: Optional[str] = None,
        chunks_per_source: int = 3,
        extract_depth: str = "advanced",
    ) -> ExtractResponse:
        """Extract full content from URLs using Tavily Extract API.

        Best practices from Tavily docs:
        - Use query + chunks_per_source to get relevant chunks instead of full page
        - extract_depth="advanced" for JS-heavy pages (FDA.gov, manufacturer sites)
        - Max 20 URLs per request
        - Fallback: if basic fails, retry with advanced

        Args:
            urls: List of URLs to extract (max 20)
            query: Optional query to rerank chunks by relevance
            chunks_per_source: Chunks per source (1-5, max 500 chars each). Only with query.
            extract_depth: "basic" or "advanced" (for JS-rendered pages)

        Returns:
            ExtractResponse with extracted content
        """
        if not urls:
            return ExtractResponse()

        # Limit to 20 URLs (Tavily limit)
        if len(urls) > 20:
            logger.warning(f"Truncating {len(urls)} URLs to 20 (Tavily limit)")
            urls = urls[:20]

        try:
            logger.info(f"Tavily extract: {len(urls)} URLs (depth={extract_depth})")

            # Build extract params
            params: Dict[str, any] = {
                "urls": urls,
                "extract_depth": extract_depth,
                "timeout": 60.0,  # Higher timeout for extraction
            }

            # Only add query params if query is provided
            if query:
                params["query"] = query[:400]  # Truncate query
                params["chunks_per_source"] = chunks_per_source

            response = await self.client.extract(**params)

            # Parse successful extractions
            results = []
            for r in response.get("results", []):
                results.append(
                    ExtractedContent(
                        url=r.get("url", ""),
                        raw_content=r.get("raw_content", ""),
                    )
                )

            # Parse failed extractions
            failed_results = []
            for f in response.get("failed_results", []):
                failed_results.append(
                    ExtractedContent(
                        url=f.get("url", ""),
                        raw_content="",
                        failed=True,
                        error=f.get("error", "Unknown error"),
                    )
                )

            logger.info(
                f"Tavily extracted {len(results)} URLs successfully, "
                f"{len(failed_results)} failed"
            )

            return ExtractResponse(
                results=results,
                failed_results=failed_results,
                response_time=response.get("response_time", 0.0),
            )

        except Exception as e:
            logger.error(f"Tavily extract failed: {e}")
            # Return all URLs as failed
            return ExtractResponse(
                failed_results=[
                    ExtractedContent(url=url, raw_content="", failed=True, error=str(e))
                    for url in urls
                ]
            )

    async def search_and_extract(
        self,
        query: str,
        search_type: str = "general",
        extract_top_n: int = 2,
        min_score: float = 0.5,
    ) -> str:
        """Search and extract full content from top results.

        Two-step pattern recommended by Tavily docs:
        1. Search to find relevant URLs
        2. Filter by score > threshold
        3. Extract full content from top N URLs

        Args:
            query: Search query
            search_type: Type of search for domain filtering
            extract_top_n: Number of top URLs to extract (default 2)
            min_score: Minimum relevance score to consider (default 0.5)

        Returns:
            Formatted string with search results + extracted content
        """
        # Step 1: Search
        search_response = await self.search(query, search_type)

        if not search_response.results:
            return "No search results found."

        # Step 2: Filter by score and get top URLs
        high_quality_results = [
            r for r in search_response.results if r.score >= min_score
        ]

        if not high_quality_results:
            # Fall back to search-only results
            logger.info("No results above score threshold, using search snippets only")
            return search_response.format_for_claude()

        # Step 3: Extract from top N URLs
        urls_to_extract = [r.url for r in high_quality_results[:extract_top_n]]

        logger.info(f"Extracting content from {len(urls_to_extract)} top URLs")
        extract_response = await self.extract(
            urls=urls_to_extract,
            query=query,  # Rerank extracted chunks by query relevance
            chunks_per_source=3,
            extract_depth="advanced",  # Better for .gov and manufacturer sites
        )

        # Step 4: Combine search overview + extracted details
        output = []

        # Add search overview (all results with snippets)
        output.append("## Search Results Overview")
        output.append(search_response.format_for_claude())

        # Add extracted full content
        if extract_response.results:
            output.append("\n## Extracted Full Content")
            output.append(extract_response.format_for_claude(max_chars_per_source=4000))

        return "\n".join(output)

    async def search_consumer_verified(
        self,
        product_name: str,
        brand: str,
        other_brand_products: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> str:
        """Search for consumer reviews with product-specific verification.

        This method:
        1. Searches Reddit for product reviews/reactions
        2. Extracts full content from top results
        3. Filters for posts specifically about THIS product
        4. Flags posts that mention multiple products (uncertain attribution)

        Args:
            product_name: Full product name (e.g., "Heartleaf Pore Control Cleansing Oil")
            brand: Brand name (e.g., "ANUA")
            other_brand_products: Other products from same brand to check for conflation
                                  (e.g., ["toner", "serum", "essence"])
            max_results: Max results to return after filtering

        Returns:
            Formatted string with verified consumer reports
        """
        other_brand_products = other_brand_products or ["toner", "serum", "essence", "cream", "moisturizer"]

        # Build search query focused on reactions/reviews
        query = f"{brand} {product_name} review reaction allergy breakout reddit"

        logger.info(f"Consumer search (verified): {query[:50]}...")

        # Step 1: Search Reddit
        search_response = await self.search(query, search_type="consumer")

        if not search_response.results:
            return "No consumer reviews found."

        # Step 2: Extract full content from top results
        urls = [r.url for r in search_response.results[:6]]  # Get more, filter down

        try:
            extract_response = await self.extract(
                urls=urls,
                extract_depth="advanced",
            )
        except Exception as e:
            logger.warning(f"Extraction failed, using search snippets: {e}")
            return search_response.format_for_claude()

        if not extract_response.results:
            return search_response.format_for_claude()

        # Step 3: Analyze and filter each post
        verified_posts = []
        conflated_posts = []
        product_keywords = product_name.lower().split()

        for item in extract_response.results:
            content_lower = item.raw_content.lower()
            url = item.url

            # Check if post mentions the target product
            mentions_target = any(kw in content_lower for kw in product_keywords)

            if not mentions_target:
                continue  # Skip posts that don't mention our product

            # Check for conflation with other products
            conflated_products = []
            for other_product in other_brand_products:
                # Check if they mention other products AND it's not part of our product name
                if other_product.lower() in content_lower and other_product.lower() not in product_name.lower():
                    conflated_products.append(other_product)

            # Extract username if available
            username = "unknown"
            if "/user/" in item.raw_content:
                try:
                    start = item.raw_content.find("/user/") + 6
                    end = item.raw_content.find("/", start) if "/" in item.raw_content[start:start+50] else start + 30
                    if end == -1:
                        end = start + 30
                    username = item.raw_content[start:end].split(")")[0].split("]")[0].strip()
                except:
                    pass

            # Categorize the post
            post_info = {
                "url": url,
                "username": username,
                "content_preview": item.raw_content[:500],
                "conflated_with": conflated_products,
            }

            if conflated_products:
                conflated_posts.append(post_info)
            else:
                verified_posts.append(post_info)

        # Step 4: Format output
        output = []
        output.append(f"## Consumer Reports for {brand} {product_name}")
        output.append("")

        if verified_posts:
            output.append(f"### ✅ Verified Product-Specific Reports ({len(verified_posts)})")
            output.append("*These posts specifically discuss this product without mentioning other brand products*")
            output.append("")

            for post in verified_posts[:max_results]:
                output.append(f"**User: u/{post['username']}** ([source]({post['url']}))")
                output.append(f"> {post['content_preview'][:300]}...")
                output.append("")

        if conflated_posts:
            output.append(f"### ⚠️ Uncertain Attribution ({len(conflated_posts)})")
            output.append("*These users also mentioned other products - cannot isolate which caused reaction*")
            output.append("")

            for post in conflated_posts[:3]:  # Limit uncertain ones
                other = ", ".join(post["conflated_with"])
                output.append(f"**User: u/{post['username']}** - also used: {other}")
                output.append(f"  [source]({post['url']})")
                output.append("")

        if not verified_posts and not conflated_posts:
            output.append("No relevant consumer reports found for this specific product.")

        # Summary stats
        output.append("---")
        output.append(f"**Summary:** {len(verified_posts)} verified reports, {len(conflated_posts)} uncertain attribution")

        return "\n".join(output)

    async def close(self) -> None:
        """Close the Tavily client (no-op for Tavily SDK)."""
        # Tavily SDK doesn't require explicit cleanup
        pass
