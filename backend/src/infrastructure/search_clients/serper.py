"""Serper.dev search client as fallback for Tavily."""

import logging
from typing import Optional

import httpx

from .base import BaseSearchClient, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

SERPER_API_URL = "https://google.serper.dev/search"


class SerperSearchClient(BaseSearchClient):
    """Serper.dev search client - Google results at lower cost.

    Used as fallback when Tavily fails or is rate limited.
    Cost: ~$1/1000 searches (vs $8/1000 for Tavily)
    """

    def __init__(self, api_key: str) -> None:
        """Initialize the Serper client.

        Args:
            api_key: Serper API key
        """
        self._api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def search(self, query: str, search_type: str = "general") -> SearchResponse:
        """Execute a search query using Serper.dev.

        Args:
            query: The search query
            search_type: Type of search (used for result filtering, not API params)

        Returns:
            SearchResponse with results
        """
        # Truncate query if needed
        if len(query) > 400:
            query = query[:400]

        try:
            logger.info(f"Serper search: {query[:50]}... (type={search_type})")

            client = await self._get_client()
            response = await client.post(
                SERPER_API_URL,
                headers={
                    "X-API-KEY": self._api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "q": query,
                    "num": 5,  # Match Tavily's max_results
                },
            )
            response.raise_for_status()
            data = response.json()

            # Parse organic results
            results = []
            for r in data.get("organic", []):
                # Calculate a pseudo-score based on position
                position = r.get("position", 10)
                score = max(0.0, 1.0 - (position - 1) * 0.1)

                results.append(
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("link", ""),
                        content=r.get("snippet", ""),
                        score=score,
                        source="serper",
                        favicon=None,  # Serper doesn't provide favicons
                    )
                )

            logger.info(f"Serper returned {len(results)} results")

            return SearchResponse(
                query=query,
                results=results,
                response_time=0.0,  # Serper doesn't provide timing
                provider="serper",
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Serper API error: {e.response.status_code} - {e.response.text}")
            return SearchResponse(
                query=query,
                provider="serper",
                error=f"HTTP {e.response.status_code}: {e.response.text[:100]}",
            )
        except Exception as e:
            logger.error(f"Serper search failed: {e}")
            return SearchResponse(
                query=query,
                provider="serper",
                error=str(e),
            )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
