-- Migration: Create search_cache table for caching web search results
-- This enables L2 caching for Tavily/Serper search results
-- TTL-based expiration with 24hr default

-- Create the search_cache table
CREATE TABLE IF NOT EXISTS search_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash VARCHAR(64) NOT NULL,          -- SHA256 of normalized query (first 32 chars)
    search_type VARCHAR(32) NOT NULL,          -- manufacturer, regulatory, scientific, legal, general
    provider VARCHAR(32) NOT NULL,             -- tavily, serper
    results JSONB NOT NULL,                    -- Cached search results
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,           -- TTL-based expiration
    UNIQUE(query_hash, search_type)
);

-- Index for efficient cache lookups
CREATE INDEX IF NOT EXISTS idx_search_cache_query
    ON search_cache(query_hash, search_type);

-- Index for cache expiration cleanup
CREATE INDEX IF NOT EXISTS idx_search_cache_expires
    ON search_cache(expires_at);

-- Index for provider analytics
CREATE INDEX IF NOT EXISTS idx_search_cache_provider
    ON search_cache(provider);

-- Add comment for documentation
COMMENT ON TABLE search_cache IS 'L2 cache for Tavily/Serper web search results. Reduces API costs by caching common queries.';
COMMENT ON COLUMN search_cache.query_hash IS 'SHA256 hash of normalized query + search_type (first 32 chars)';
COMMENT ON COLUMN search_cache.search_type IS 'Type of search: manufacturer, regulatory, scientific, legal, general';
COMMENT ON COLUMN search_cache.provider IS 'Search provider: tavily or serper';
COMMENT ON COLUMN search_cache.results IS 'Cached search results including formatted output for Claude';
COMMENT ON COLUMN search_cache.expires_at IS 'Cache expiration time (default 24 hours from creation)';

-- Enable RLS (Row Level Security)
ALTER TABLE search_cache ENABLE ROW LEVEL SECURITY;

-- Create policy for service role access (backend only)
CREATE POLICY "service_role_all_access" ON search_cache
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Function to clean up expired cache entries (can be called periodically)
CREATE OR REPLACE FUNCTION cleanup_expired_search_cache()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM search_cache
    WHERE expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

COMMENT ON FUNCTION cleanup_expired_search_cache IS 'Removes expired search cache entries. Can be called periodically via cron or manually.';
