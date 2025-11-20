-- ============================================================================
-- CACHE CLEARING SCRIPTS FOR EJECT PRODUCT ANALYSES
-- ============================================================================
-- Purpose: Utility scripts to clear product analysis cache for re-testing
-- Usage: Run these in Supabase SQL Editor or via psql
-- Database: Supabase PostgreSQL
-- Date: 2025-11-20
-- ============================================================================

-- ----------------------------------------------------------------------------
-- FUNCTION 1: Clear Cache for Specific Product by URL Hash
-- ----------------------------------------------------------------------------
-- Usage: SELECT clear_product_cache('abc123...def');
-- Returns: Number of rows deleted

CREATE OR REPLACE FUNCTION clear_product_cache(url_hash_to_clear TEXT)
RETURNS INTEGER AS $$
DECLARE
    rows_deleted INTEGER;
BEGIN
    DELETE FROM product_analyses
    WHERE product_url_hash = url_hash_to_clear;

    GET DIAGNOSTICS rows_deleted = ROW_COUNT;

    RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION clear_product_cache IS 'Deletes a specific product cache entry by URL hash';

-- ----------------------------------------------------------------------------
-- FUNCTION 2: Clear Cache for Product by URL (more user-friendly)
-- ----------------------------------------------------------------------------
-- Usage: SELECT clear_product_cache_by_url('https://amazon.com/dp/B001...');
-- Returns: Number of rows deleted

CREATE OR REPLACE FUNCTION clear_product_cache_by_url(product_url_to_clear TEXT)
RETURNS INTEGER AS $$
DECLARE
    rows_deleted INTEGER;
BEGIN
    DELETE FROM product_analyses
    WHERE product_url = product_url_to_clear;

    GET DIAGNOSTICS rows_deleted = ROW_COUNT;

    RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION clear_product_cache_by_url IS 'Deletes a specific product cache entry by URL';

-- ----------------------------------------------------------------------------
-- FUNCTION 3: Clear All Cache Older Than N Days
-- ----------------------------------------------------------------------------
-- Usage: SELECT clear_old_cache(30);  -- Clear cache older than 30 days
-- Returns: Number of rows deleted

CREATE OR REPLACE FUNCTION clear_old_cache(days_old INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    rows_deleted INTEGER;
    cutoff_date TIMESTAMPTZ;
BEGIN
    cutoff_date := NOW() - (days_old || ' days')::INTERVAL;

    DELETE FROM product_analyses
    WHERE analyzed_at < cutoff_date;

    GET DIAGNOSTICS rows_deleted = ROW_COUNT;

    RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION clear_old_cache IS 'Deletes all product cache entries older than specified number of days';

-- ----------------------------------------------------------------------------
-- FUNCTION 4: Clear ALL Cache (DANGEROUS - Use for Testing Only)
-- ----------------------------------------------------------------------------
-- Usage: SELECT clear_all_cache();
-- Returns: Number of rows deleted
-- WARNING: This deletes ALL cached analyses!

CREATE OR REPLACE FUNCTION clear_all_cache()
RETURNS INTEGER AS $$
DECLARE
    rows_deleted INTEGER;
BEGIN
    DELETE FROM product_analyses;

    GET DIAGNOSTICS rows_deleted = ROW_COUNT;

    RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION clear_all_cache IS 'Deletes ALL product cache entries - USE WITH CAUTION!';

-- ----------------------------------------------------------------------------
-- FUNCTION 5: Find Product URL Hash from Partial URL Match
-- ----------------------------------------------------------------------------
-- Usage: SELECT * FROM find_product_cache('sunscreen');
-- Returns: Table of matching products with their hashes

CREATE OR REPLACE FUNCTION find_product_cache(search_term TEXT)
RETURNS TABLE (
    product_url_hash TEXT,
    product_url TEXT,
    product_name TEXT,
    brand TEXT,
    analyzed_at TIMESTAMPTZ,
    overall_score INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pa.product_url_hash,
        pa.product_url,
        pa.product_name,
        pa.brand,
        pa.analyzed_at,
        pa.overall_score
    FROM product_analyses pa
    WHERE
        pa.product_url ILIKE '%' || search_term || '%'
        OR pa.product_name ILIKE '%' || search_term || '%'
        OR pa.brand ILIKE '%' || search_term || '%'
    ORDER BY pa.analyzed_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION find_product_cache IS 'Finds product cache entries by searching URL, name, or brand';

-- ============================================================================
-- EXAMPLE USAGE SCRIPTS
-- ============================================================================

-- Example 1: Find a product's hash to clear it
-- SELECT * FROM find_product_cache('sunscreen');

-- Example 2: Clear specific product by hash
-- SELECT clear_product_cache('abc123def456...');

-- Example 3: Clear specific product by URL
-- SELECT clear_product_cache_by_url('https://amazon.com/dp/B001...');

-- Example 4: Clear cache older than 7 days
-- SELECT clear_old_cache(7);

-- Example 5: Clear ALL cache (testing only!)
-- SELECT clear_all_cache();

-- Example 6: Check how many cached products exist
-- SELECT COUNT(*) FROM product_analyses;

-- Example 7: See most recent cached products
-- SELECT product_name, brand, analyzed_at, overall_score
-- FROM product_analyses
-- ORDER BY analyzed_at DESC
-- LIMIT 10;

-- ============================================================================
-- ADMIN QUERIES FOR CACHE MANAGEMENT
-- ============================================================================

-- View cache statistics
CREATE OR REPLACE VIEW cache_statistics AS
SELECT
    COUNT(*) as total_cached_products,
    COUNT(*) FILTER (WHERE analyzed_at > NOW() - INTERVAL '1 day') as cached_today,
    COUNT(*) FILTER (WHERE analyzed_at > NOW() - INTERVAL '7 days') as cached_this_week,
    COUNT(*) FILTER (WHERE analyzed_at > NOW() - INTERVAL '30 days') as cached_this_month,
    MIN(analyzed_at) as oldest_cache_entry,
    MAX(analyzed_at) as newest_cache_entry,
    AVG(overall_score) as avg_safety_score
FROM product_analyses;

COMMENT ON VIEW cache_statistics IS 'Overview of product analysis cache statistics';

-- Query to see cache statistics
-- SELECT * FROM cache_statistics;
