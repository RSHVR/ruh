# Custom Web Search Implementation

Replaces Anthropic's native `web_search_20250305` tool with a custom implementation using **Tavily** (primary) and **Serper.dev** (fallback).

## Why Custom Search?

| Provider          | Cost per 1000 searches | Features                                           |
| ----------------- | ---------------------- | -------------------------------------------------- |
| Anthropic native  | $10.00                 | Basic search                                       |
| **Tavily**        | $8.00                  | AI-optimized, domain filtering, content extraction |
| Serper (fallback) | $1.00                  | Google results                                     |

**With caching enabled, expect 40-50% cost reduction.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ProductSafetyAgent                           │
│                    (claude_agent.py)                            │
│  • Custom web_search tool definition                            │
│  • Manual tool execution loop                                   │
│  • Native web_fetch still handled by Anthropic                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              SearchToolService (search_tool_service.py)         │
│  • L1: In-memory LRU cache (1hr TTL, 1000 entries)             │
│  • L2: Supabase cache (24hr TTL) [optional]                    │
│  • Auto-extract for manufacturer/regulatory searches            │
│  • Fallback chain: Cache → Tavily → Serper → Empty             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌─────────────────────────┐    ┌─────────────────────────┐
│   TavilySearchClient    │    │   SerperSearchClient    │
│   • search()            │    │   • search()            │
│   • extract()           │    │   (fallback only)       │
│   • search_and_extract()│    └─────────────────────────┘
│   • search_consumer_    │
│     verified()          │
└─────────────────────────┘
```

---

## Configuration

### Environment Variables

```bash
# .env
TAVILY_API_KEY=tvly-...           # Required for custom search
SERPER_API_KEY=...                # Optional fallback
USE_CUSTOM_SEARCH=true            # Feature flag (default: true)
SEARCH_CACHE_TTL_HOURS=24         # Cache expiration
```

### Feature Flag

In `config.py`:

```python
use_custom_search: bool = True  # Set to False to use Anthropic native
```

---

## Search Types

| Type           | Domain Filter                        | Extraction | Required                  | Use Case                            |
| -------------- | ------------------------------------ | ---------- | ------------------------- | ----------------------------------- |
| `manufacturer` | None (any)                           | ✅ Yes     | If ingredients incomplete | Full ingredient lists, MSDS         |
| `regulatory`   | `*.gov`, Health Canada               | ✅ Yes     | ✅ Yes                    | FDA recalls, safety alerts          |
| `ingredient`   | PubMed, NIH, IARC, EPA, EWG, `*.edu` | ❌ No      | ✅ Yes (per-ingredient)   | Individual chemical safety research |
| `scientific`   | PubMed, NIH, IARC, `*.edu`           | ❌ No      | Optional                  | General research studies            |
| `legal`        | Courts, Reuters, NYT, WSJ            | ❌ No      | ✅ Yes                    | Lawsuits, settlements               |
| `consumer`     | Reddit only                          | ❌ No      | ✅ Yes                    | Real user experiences, reactions    |
| `general`      | None                                 | ❌ No      | Optional                  | Fallback searches                   |

### Per-Ingredient Research (NEW)

The `ingredient` search type is specifically designed for researching individual chemicals:

```python
# Example queries for per-ingredient research
"Phenoxyethanol toxicity studies"
"Butylated Hydroxytoluene BHT IARC classification"
"Fragrance phthalates endocrine disruptor"
"PEG-40 hydrogenated castor oil contamination"
```

**Priority ingredients to research:**

- Preservatives (phenoxyethanol, parabens, formaldehyde releasers)
- Antioxidants (BHT, BHA)
- Fragrance/parfum (phthalates concern)
- Surfactants with "PEG" or "-eth" (1,4-dioxane contamination)
- Colorants/dyes (FD&C, CI numbers)
- Any unrecognized chemical names

### Domain Filtering

```python
# Excluded from all searches (except consumer)
EXCLUDED_DOMAINS_DEFAULT = ["reddit.com", "quora.com", "pinterest.com", "medium.com"]

# Consumer searches allow Reddit
EXCLUDED_DOMAINS_CONSUMER = ["quora.com", "pinterest.com", "medium.com"]
```

---

## Content Extraction

For `manufacturer` and `regulatory` search types, the system automatically:

1. **Searches** for relevant URLs
2. **Filters** by relevance score (> 0.5)
3. **Extracts** full content from top 2 URLs
4. **Returns** combined snippets + extracted content

This provides ~2.5x more content for Claude to analyze (8K chars vs 3K).

### Configuration

```python
EXTRACT_CONFIG = {
    "extract_top_n": 2,           # Extract from top 2 URLs
    "min_score": 0.5,             # Minimum relevance score
    "max_chars_per_source": 4000, # Prevent context explosion
}
```

---

## Consumer Search Verification

The `search_consumer_verified()` method filters Reddit posts for product-specific attribution:

```python
result = await tavily_client.search_consumer_verified(
    product_name='Heartleaf Pore Control Cleansing Oil',
    brand='ANUA',
    other_brand_products=['toner', 'serum', 'essence', 'cream'],
)
```

### Output Categories

| Category         | Meaning                                                   |
| ---------------- | --------------------------------------------------------- |
| ✅ **Verified**  | Post only mentions the target product                     |
| ⚠️ **Uncertain** | User also used other brand products - can't isolate cause |

This prevents false attribution when users try multiple products from the same brand.

---

## Caching

### Two-Tier Cache

1. **L1: In-Memory LRU** (1 hour TTL, 1000 entries)
   - Fastest access
   - Per-process cache
   - Evicts least recently used

2. **L2: Supabase** (24 hour TTL)
   - Persistent across restarts
   - Shared across instances
   - Requires `search_cache` table

### Cache Key Generation

```python
# Normalized: lowercase, whitespace collapsed
key = sha256(f"{search_type}:{normalized_query}")[:32]

# Extracted results use different key
key_extracted = key + "_extracted"
```

### Supabase Migration

```sql
-- Run: supabase db push
-- File: supabase/migrations/009_create_search_cache.sql

CREATE TABLE search_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash VARCHAR(64) NOT NULL,
    search_type VARCHAR(32) NOT NULL,
    provider VARCHAR(32) NOT NULL,
    results JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE(query_hash, search_type)
);

CREATE INDEX idx_search_cache_expires ON search_cache(expires_at);
```

---

## Cost Tracking

### Token + Search Unified Tracking

```python
from src.infrastructure.token_tracker import TokenTracker

tracker = TokenTracker()
tracker.start_analysis("url_hash")

# ... Claude API calls and searches ...

summary = tracker.finish_analysis()
# Returns: tokens, searches, cache hits, total cost
```

### Pricing Constants

```python
SEARCH_PRICING = {
    "tavily": 0.008,        # $8/1000 searches
    "tavily_extract": 0.002, # $2/1000 extractions
    "serper": 0.001,        # $1/1000 searches
    "anthropic": 0.010,     # $10/1000 (for comparison)
    "cache": 0.0,           # Free
}
```

---

## Manual Tool Loop

The custom search uses a manual tool execution loop:

```python
# In claude_agent.py

while iteration < max_iterations:
    response = client.messages.create(
        model=self.model,
        tools=[CUSTOM_WEB_SEARCH_TOOL, native_web_fetch],
        ...
    )

    if response.stop_reason == "tool_use":
        # Find our custom web_search requests
        tool_uses = [b for b in response.content if b.name == "web_search"]

        # Execute via Tavily/Serper
        results = await asyncio.gather(*[
            search_service.search(t.input["query"], t.input["search_type"])
            for t in tool_uses
        ])

        # Send results back to Claude
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
    else:
        break  # Claude is done
```

---

## API Reference

### SearchToolService

```python
class SearchToolService:
    def __init__(
        self,
        supabase_client: Optional[Any] = None,  # For L2 cache
        tavily_api_key: Optional[str] = None,
        serper_api_key: Optional[str] = None,
    )

    async def search(
        self,
        query: str,
        search_type: str = "general",
        force_extract: bool = False,
    ) -> str:
        """Returns formatted search results for Claude."""

    def get_usage_summary(self) -> Dict[str, Any]:
        """Returns search costs and cache hit rate."""

    async def close(self) -> None:
        """Cleanup resources."""
```

### TavilySearchClient

```python
class TavilySearchClient:
    async def search(
        self,
        query: str,
        search_type: str = "general",
    ) -> SearchResponse:
        """Basic search with domain filtering."""

    async def extract(
        self,
        urls: List[str],
        query: Optional[str] = None,
        chunks_per_source: int = 3,
        extract_depth: str = "advanced",
    ) -> ExtractResponse:
        """Extract full content from URLs."""

    async def search_and_extract(
        self,
        query: str,
        search_type: str = "general",
        extract_top_n: int = 2,
        min_score: float = 0.5,
    ) -> str:
        """Combined search + extraction."""

    async def search_consumer_verified(
        self,
        product_name: str,
        brand: str,
        other_brand_products: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> str:
        """Reddit search with product-specific verification."""
```

---

## Files Reference

| File                            | Purpose                           |
| ------------------------------- | --------------------------------- |
| `config.py`                     | Feature flag, API keys, cache TTL |
| `search_tool_service.py`        | Orchestrator with caching         |
| `search_clients/tavily.py`      | Tavily client with extract        |
| `search_clients/serper.py`      | Serper fallback client            |
| `search_clients/base.py`        | Abstract base, dataclasses        |
| `claude_agent.py`               | Custom tool + manual loop         |
| `token_tracker.py`              | Unified cost tracking             |
| `supabase/migrations/009_*.sql` | Cache table migration             |

---

## Example Usage

```python
import asyncio
from src.infrastructure.claude_agent import ProductSafetyAgent
from src.infrastructure.search_tool_service import SearchToolService
from src.infrastructure.token_tracker import TokenTracker

async def analyze_product(url: str):
    tracker = TokenTracker()
    tracker.start_analysis("test")

    search_service = SearchToolService(supabase_client=None)

    agent = ProductSafetyAgent(
        token_tracker=tracker,
        search_service=search_service,
    )

    result = await agent.analyze_product(
        product_url=url,
        allergen_profile=["Fragrance"],
        pfas_database=[...],
        allergen_database=[...],
    )

    summary = tracker.finish_analysis()
    print(f"Total cost: ${summary.total_cost:.4f}")

    await agent.close()
    return result

asyncio.run(analyze_product("https://amazon.ca/..."))
```

---

## Troubleshooting

### "Tavily API key not configured"

Add `TAVILY_API_KEY=tvly-...` to `.env`

### "Serper API key not configured (no fallback)"

Optional - add `SERPER_API_KEY=...` for fallback

### Token counting errors for web_fetch

Normal - the beta `web_fetch_20250910` tool isn't supported by token counting API. Actual calls work fine.

### Low cache hit rate

- Check `SEARCH_CACHE_TTL_HOURS` setting
- Ensure Supabase client is passed for L2 cache
- Similar queries may have different normalized forms

---

## Cost Comparison Example

**Analysis of 1 product (comprehensive - ~10 searches):**

- 1 manufacturer search (if needed)
- 1 regulatory search
- 4 per-ingredient searches (avg)
- 1 legal search
- 1 consumer search
- - 2 extraction calls for manufacturer/regulatory

| Provider           | Cost   |
| ------------------ | ------ |
| Anthropic native   | $0.100 |
| Tavily (no cache)  | $0.084 |
| Tavily (40% cache) | $0.050 |

**Monthly at 1000 analyses:**

| Provider           | Monthly Cost |
| ------------------ | ------------ |
| Anthropic native   | $100.00      |
| Tavily (no cache)  | $84.00       |
| Tavily (40% cache) | **$50.00**   |

Savings: **50%** with caching enabled.

**Note:** Per-ingredient searches are highly cacheable - "Phenoxyethanol toxicity" is the same query regardless of which product contains it. Over time, cache hit rate improves as common ingredients are researched.
