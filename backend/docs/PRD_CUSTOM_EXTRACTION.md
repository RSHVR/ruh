# PRD: Custom Web Content Extraction Service

## Problem Statement

Currently relying on Tavily's extract API ($0.002/extraction) for fetching full page content during ingredient research. At scale:

- Initial batch: 785 extractions = $1.57
- Per product analysis: 5-10 extractions = $0.01-0.02
- Monthly at 1000 analyses: ~$150-200 in extraction costs alone

Additionally, Tavily extraction:

- Is a black box (no control over what's extracted)
- May miss structured data (tables, ingredient lists)
- Has rate limits we don't control
- Adds external dependency for critical functionality

---

## Goals

1. **Eliminate extraction costs** - $0 vs $0.002/call
2. **Improve extraction quality** - Custom logic for scientific sources (PubMed, FDA, EWG)
3. **Full control** - Cache aggressively, retry logic, no external rate limits
4. **JS rendering** - Handle modern SPAs and JS-heavy government sites

---

## Non-Goals

- Building a general-purpose web scraper
- Bypassing anti-bot measures (we target public scientific/regulatory sites)
- Real-time extraction during user requests (batch pre-computation is fine being slower)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ExtractionService                                │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  PlaywrightPool │  │  Trafilatura    │  │  SourceExtractors   │  │
│  │  (JS Rendering) │  │  (Generic)      │  │  (Site-Specific)    │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘  │
│           │                    │                      │              │
│           └────────────────────┴──────────────────────┘              │
│                                │                                     │
│                    ┌───────────▼───────────┐                        │
│                    │   ExtractionCache     │                        │
│                    │   (Supabase + LRU)    │                        │
│                    └───────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Components

#### 1. PlaywrightPool

Manages a pool of browser instances for JS rendering.

```python
class PlaywrightPool:
    """Pool of Playwright browser instances for concurrent extraction."""

    def __init__(self, pool_size: int = 3):
        self.pool_size = pool_size
        self.browsers: List[Browser] = []

    async def get_rendered_html(self, url: str, wait_for: str = None) -> str:
        """Fetch URL and return fully rendered HTML."""
        # - Acquire browser from pool
        # - Navigate to URL
        # - Wait for network idle or specific selector
        # - Return page.content()
        # - Release browser back to pool
```

#### 2. Trafilatura Extractor

Generic content extraction for most sites.

```python
class TrafilaturaExtractor:
    """Generic content extraction using Trafilatura."""

    def extract(self, html: str, url: str) -> ExtractedContent:
        """Extract main content from HTML."""
        text = trafilatura.extract(
            html,
            include_tables=True,
            include_links=True,
            include_images=False,
            favor_recall=True,  # Get more content, even if noisy
        )
        return ExtractedContent(
            url=url,
            text=text,
            tables=self._extract_tables(html),
            metadata=trafilatura.extract_metadata(html),
        )
```

#### 3. Source-Specific Extractors

Custom extractors for high-value sources with known structure.

| Source      | Custom Logic                                          |
| ----------- | ----------------------------------------------------- |
| **PubMed**  | Extract title, abstract, authors, PMID, MeSH terms    |
| **FDA.gov** | Extract recall notices, warning letters, drug labels  |
| **EPA.gov** | Extract chemical assessments, toxicity data           |
| **EWG.org** | Extract ingredient scores, hazard ratings             |
| **IARC**    | Extract monograph classifications, evidence summaries |
| **NIH/NLM** | Extract study summaries, compound data                |

```python
class PubMedExtractor(BaseExtractor):
    """Extract structured data from PubMed articles."""

    PATTERNS = {
        "pmid": r"PMID:\s*(\d+)",
        "title": "h1.heading-title",
        "abstract": "div.abstract-content",
        "authors": "div.authors-list",
    }

    def extract(self, html: str, url: str) -> PubMedArticle:
        soup = BeautifulSoup(html, "lxml")
        return PubMedArticle(
            pmid=self._extract_pmid(soup),
            title=self._extract_title(soup),
            abstract=self._extract_abstract(soup),
            authors=self._extract_authors(soup),
            mesh_terms=self._extract_mesh_terms(soup),
        )
```

#### 4. Extraction Cache

Two-tier caching to avoid re-fetching.

```python
class ExtractionCache:
    """Cache extracted content in memory and Supabase."""

    # L1: In-memory LRU (1 hour TTL, 500 entries)
    # L2: Supabase extracted_content table (30 day TTL)

    async def get(self, url: str) -> Optional[ExtractedContent]:
        # Check L1 → Check L2 → Return None

    async def set(self, url: str, content: ExtractedContent) -> None:
        # Store in L1 and L2
```

#### 5. ExtractionService (Orchestrator)

Main entry point that routes to appropriate extractor.

```python
class ExtractionService:
    """Orchestrates content extraction from URLs."""

    # Route by domain
    EXTRACTORS = {
        "pubmed.ncbi.nlm.nih.gov": PubMedExtractor,
        "fda.gov": FDAExtractor,
        "epa.gov": EPAExtractor,
        "ewg.org": EWGExtractor,
        "iarc.who.int": IARCExtractor,
    }

    async def extract(self, url: str, use_js: bool = None) -> ExtractedContent:
        """Extract content from URL.

        Args:
            url: URL to extract
            use_js: Force JS rendering (auto-detected if None)

        Returns:
            ExtractedContent with text, tables, metadata
        """
        # 1. Check cache
        cached = await self.cache.get(url)
        if cached:
            return cached

        # 2. Determine if JS rendering needed
        needs_js = use_js if use_js is not None else self._needs_js(url)

        # 3. Fetch HTML
        if needs_js:
            html = await self.playwright_pool.get_rendered_html(url)
        else:
            html = await self._fetch_simple(url)

        # 4. Route to appropriate extractor
        domain = urlparse(url).netloc
        extractor = self.EXTRACTORS.get(domain, self.trafilatura)

        # 5. Extract and cache
        content = extractor.extract(html, url)
        await self.cache.set(url, content)

        return content

    def _needs_js(self, url: str) -> bool:
        """Determine if URL needs JS rendering."""
        JS_REQUIRED_DOMAINS = [
            "fda.gov",
            "epa.gov",
            "ewg.org",
        ]
        return any(d in url for d in JS_REQUIRED_DOMAINS)
```

---

## Database Schema

```sql
-- New table for caching extracted content
CREATE TABLE extracted_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    url TEXT NOT NULL UNIQUE,
    url_hash VARCHAR(64) NOT NULL,  -- For faster lookups
    domain TEXT NOT NULL,           -- For analytics

    -- Extracted data
    title TEXT,
    text_content TEXT,              -- Main extracted text
    tables JSONB DEFAULT '[]',      -- Extracted tables
    metadata JSONB DEFAULT '{}',    -- Author, date, etc.
    structured_data JSONB,          -- Source-specific (PMID, scores, etc.)

    -- Extraction metadata
    extractor_used TEXT,            -- trafilatura, pubmed, fda, etc.
    js_rendered BOOLEAN DEFAULT FALSE,
    extraction_time_ms INTEGER,
    content_length INTEGER,

    -- Cache management
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT idx_extracted_content_url_hash UNIQUE(url_hash)
);

CREATE INDEX idx_extracted_content_domain ON extracted_content(domain);
CREATE INDEX idx_extracted_content_expires ON extracted_content(expires_at);
```

---

## Data Models

```python
@dataclass
class ExtractedContent:
    """Generic extracted content."""
    url: str
    title: Optional[str]
    text: str
    tables: List[Dict[str, Any]]  # [{headers: [...], rows: [[...]]}]
    metadata: Dict[str, Any]      # {author, date, source, etc.}
    structured_data: Optional[Dict[str, Any]]  # Source-specific

    extractor: str
    js_rendered: bool
    extraction_time_ms: int
    content_length: int

@dataclass
class PubMedArticle(ExtractedContent):
    """PubMed-specific extraction."""
    pmid: str
    authors: List[str]
    journal: str
    publication_date: str
    abstract: str
    mesh_terms: List[str]
    doi: Optional[str]

@dataclass
class FDADocument(ExtractedContent):
    """FDA-specific extraction."""
    document_type: str  # recall, warning_letter, drug_label
    product_name: Optional[str]
    company: Optional[str]
    issue_date: Optional[str]
    hazard_classification: Optional[str]
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Day 1)

- [ ] Create `extraction_service.py` with basic structure
- [ ] Implement `PlaywrightPool` for JS rendering
- [ ] Implement `TrafilaturaExtractor` for generic extraction
- [ ] Add extraction cache (L1 memory + L2 Supabase)
- [ ] Create database migration for `extracted_content` table

### Phase 2: Source-Specific Extractors (Day 2)

- [ ] `PubMedExtractor` - Scientific articles
- [ ] `FDAExtractor` - Recalls, warnings, drug labels
- [ ] `EPAExtractor` - Chemical assessments
- [ ] `EWGExtractor` - Ingredient safety scores
- [ ] `IARCExtractor` - Carcinogen classifications

### Phase 3: Integration (Day 3)

- [ ] Update `IngredientResearchService` to use `ExtractionService`
- [ ] Update `SearchToolService` to use custom extraction
- [ ] Add fallback to Tavily extract if custom fails
- [ ] Performance testing and optimization

### Phase 4: Monitoring & Iteration (Ongoing)

- [ ] Track extraction success rates by domain
- [ ] Add new source-specific extractors as needed
- [ ] Tune JS rendering timeouts and selectors

---

## Success Metrics

| Metric                   | Target                        |
| ------------------------ | ----------------------------- |
| Extraction cost          | $0 (vs $0.002/call)           |
| Extraction success rate  | >95%                          |
| Average extraction time  | <5s (JS), <1s (simple)        |
| Cache hit rate           | >60% after warmup             |
| PubMed data completeness | PMID, title, abstract in >99% |
| FDA data completeness    | Document type, date in >95%   |

---

## Risks & Mitigations

| Risk                      | Mitigation                                                              |
| ------------------------- | ----------------------------------------------------------------------- |
| Sites block Playwright    | Use realistic user agents, rate limiting, residential proxies if needed |
| Site structure changes    | Monitor extraction failures, alert on >5% failure rate                  |
| Playwright resource usage | Pool size limits, browser recycling, timeout enforcement                |
| Slow batch processing     | Parallel extraction (pool of 3-5 browsers), overnight runs              |

---

## Dependencies

```toml
# Add to pyproject.toml
"trafilatura>=1.6.0",
"playwright>=1.40.0",  # Already installed
"lxml>=5.0.0",         # Already installed (for BeautifulSoup)
```

---

## Cost Comparison

| Scenario                 | Tavily Extract | Custom Extraction |
| ------------------------ | -------------- | ----------------- |
| Initial batch (785 URLs) | $1.57          | $0                |
| Per analysis (5 URLs)    | $0.01          | $0                |
| Monthly (1000 analyses)  | $50            | $0                |
| Annual                   | $600           | $0                |

**Savings: $600/year** + full control over extraction quality.

---

## Open Questions

1. **Rate limiting strategy** - How aggressive can we be with government sites?
2. **Proxy needs** - Do any critical sources block cloud IPs?
3. **Storage costs** - How much will Supabase storage cost for cached content?
4. **Fallback behavior** - When custom extraction fails, use Tavily or skip?
