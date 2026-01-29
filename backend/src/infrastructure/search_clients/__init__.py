"""Search clients for web search functionality."""

from .base import BaseSearchClient, SearchResult
from .tavily import TavilySearchClient
from .serper import SerperSearchClient

__all__ = [
    "BaseSearchClient",
    "SearchResult",
    "TavilySearchClient",
    "SerperSearchClient",
]
