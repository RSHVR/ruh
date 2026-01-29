"""Abstract base class for search clients."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    url: str
    content: str
    score: float
    source: str  # "tavily" or "serper"
    favicon: Optional[str] = None


@dataclass
class SearchResponse:
    """Response from a search query."""

    query: str
    results: List[SearchResult] = field(default_factory=list)
    response_time: float = 0.0
    request_id: Optional[str] = None
    provider: str = ""
    error: Optional[str] = None

    def format_for_claude(self) -> str:
        """Format search results for Claude tool_result.

        Filters by score > 0.5 and formats as readable text.
        """
        if self.error:
            return f"Search error: {self.error}"

        if not self.results:
            return "No relevant results found."

        output = []
        for r in self.results:
            # Only include high-relevance results (score > 0.5)
            if r.score < 0.5:
                continue
            output.append(f"**{r.title}** ({r.url})")
            output.append(f"Relevance: {r.score:.0%}")
            # Limit content to 500 chars per result
            content = r.content[:500] if r.content else ""
            output.append(content)
            output.append("---")

        return "\n".join(output) if output else "No high-relevance results found."


class BaseSearchClient(ABC):
    """Abstract base class for search clients."""

    @abstractmethod
    async def search(self, query: str, search_type: str = "general") -> SearchResponse:
        """Execute a search query.

        Args:
            query: The search query (should be under 400 chars)
            search_type: Type of search for domain filtering.
                Options: "manufacturer", "regulatory", "scientific", "legal", "general"

        Returns:
            SearchResponse with results
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections."""
        pass
