-- Cache for extracted web content (replaces Tavily extract API)
-- Saves $0.002 per extraction = ~$600/year at scale

CREATE TABLE extracted_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- URL identification
    url TEXT NOT NULL,
    url_hash VARCHAR(64) NOT NULL,  -- SHA256 for fast lookups
    domain TEXT NOT NULL,           -- For analytics and cleanup

    -- Extracted data
    title TEXT,
    text_content TEXT,              -- Main extracted text
    tables JSONB DEFAULT '[]',      -- Extracted tables as [{headers: [], rows: [[]]}]
    metadata JSONB DEFAULT '{}',    -- Author, date, description, etc.
    structured_data JSONB,          -- Source-specific data (PMID, scores, etc.)

    -- Extraction metadata
    extractor_used TEXT,            -- trafilatura, pubmed, fda, etc.
    js_rendered BOOLEAN DEFAULT FALSE,
    extraction_time_ms INTEGER,
    content_length INTEGER,

    -- Cache management
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT extracted_content_url_hash_unique UNIQUE(url_hash)
);

-- Indexes for efficient lookups
CREATE INDEX idx_extracted_content_url_hash ON extracted_content(url_hash);
CREATE INDEX idx_extracted_content_domain ON extracted_content(domain);
CREATE INDEX idx_extracted_content_expires ON extracted_content(expires_at);
CREATE INDEX idx_extracted_content_extractor ON extracted_content(extractor_used);

-- Function to clean up expired cache entries (run periodically)
CREATE OR REPLACE FUNCTION cleanup_expired_extractions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM extracted_content
    WHERE expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- RLS policies (same pattern as other tables)
ALTER TABLE extracted_content ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all operations on extracted_content"
    ON extracted_content
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE extracted_content IS 'Cache for extracted web content. Replaces Tavily extract API. TTL: 30 days.';
COMMENT ON COLUMN extracted_content.url_hash IS 'SHA256 hash of normalized URL for fast lookups';
COMMENT ON COLUMN extracted_content.structured_data IS 'Source-specific structured data (e.g., PMID, MeSH terms for PubMed)';
COMMENT ON COLUMN extracted_content.extractor_used IS 'Which extractor was used: trafilatura (generic), pubmed, fda, epa, ewg, iarc';
