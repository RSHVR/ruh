-- Migration: Create validation logs table and helper functions
-- Purpose: Store validation logs from Claude AI misclassifications
-- Author: Backend team
-- Date: 2025-11-20

-- ============================================================================
-- 1. CREATE VALIDATION LOGS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS validation_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timestamp and type
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    log_type TEXT NOT NULL CHECK (log_type IN (
        'invalid_allergen',
        'invalid_pfas',
        'reclassified_substance',
        'validation_summary'
    )),

    -- Product information
    product_url TEXT NOT NULL,
    product_name TEXT NOT NULL,

    -- Substance information (nullable for summary type)
    substance_name TEXT,
    severity TEXT,
    confidence NUMERIC,
    category TEXT,
    cas_number TEXT,
    source TEXT,

    -- Flexible additional data stored as JSON
    details JSONB,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 2. CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

-- Index for querying by date range
CREATE INDEX idx_validation_logs_timestamp ON validation_logs(timestamp DESC);

-- Index for querying by product
CREATE INDEX idx_validation_logs_product_url ON validation_logs(product_url);

-- Index for querying by substance
CREATE INDEX idx_validation_logs_substance ON validation_logs(substance_name)
WHERE substance_name IS NOT NULL;

-- Index for querying by log type
CREATE INDEX idx_validation_logs_type ON validation_logs(log_type);

-- Composite index for common queries
CREATE INDEX idx_validation_logs_type_timestamp ON validation_logs(log_type, timestamp DESC);

-- ============================================================================
-- 3. SQL FUNCTION: Get Validation Stats by Date Range
-- ============================================================================

CREATE OR REPLACE FUNCTION get_validation_stats_by_date(
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ
)
RETURNS TABLE (
    date DATE,
    total_validations BIGINT,
    invalid_allergens BIGINT,
    invalid_pfas BIGINT,
    reclassifications BIGINT,
    unique_products BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        timestamp::DATE as date,
        COUNT(*) FILTER (WHERE log_type = 'validation_summary') as total_validations,
        COUNT(*) FILTER (WHERE log_type = 'invalid_allergen') as invalid_allergens,
        COUNT(*) FILTER (WHERE log_type = 'invalid_pfas') as invalid_pfas,
        COUNT(*) FILTER (WHERE log_type = 'reclassified_substance') as reclassifications,
        COUNT(DISTINCT product_url) as unique_products
    FROM validation_logs
    WHERE timestamp >= start_date AND timestamp <= end_date
    GROUP BY timestamp::DATE
    ORDER BY date DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. SQL FUNCTION: Get Most Flagged Substances
-- ============================================================================

CREATE OR REPLACE FUNCTION get_most_flagged_substances(
    result_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    substance_name TEXT,
    times_flagged BIGINT,
    log_type TEXT,
    avg_confidence NUMERIC,
    most_common_severity TEXT,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        vl.substance_name,
        COUNT(*) as times_flagged,
        vl.log_type,
        AVG(vl.confidence) as avg_confidence,
        MODE() WITHIN GROUP (ORDER BY vl.severity) as most_common_severity,
        MIN(vl.timestamp) as first_seen,
        MAX(vl.timestamp) as last_seen
    FROM validation_logs vl
    WHERE vl.substance_name IS NOT NULL
      AND vl.log_type IN ('invalid_allergen', 'invalid_pfas')
    GROUP BY vl.substance_name, vl.log_type
    ORDER BY times_flagged DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 5. SQL FUNCTION: Get Validation Logs by Product
-- ============================================================================

CREATE OR REPLACE FUNCTION get_validation_logs_by_product(
    search_product_url TEXT
)
RETURNS TABLE (
    id UUID,
    log_timestamp TIMESTAMPTZ,
    log_type TEXT,
    substance_name TEXT,
    severity TEXT,
    confidence NUMERIC,
    category TEXT,
    source TEXT,
    details JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        vl.id,
        vl.timestamp,
        vl.log_type,
        vl.substance_name,
        vl.severity,
        vl.confidence,
        vl.category,
        vl.source,
        vl.details
    FROM validation_logs vl
    WHERE vl.product_url = search_product_url
    ORDER BY vl.timestamp DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. SQL FUNCTION: Get Recent Validation Summary Stats
-- ============================================================================

CREATE OR REPLACE FUNCTION get_recent_validation_summary(
    days_back INTEGER DEFAULT 7
)
RETURNS TABLE (
    total_products_analyzed BIGINT,
    total_invalid_allergens BIGINT,
    total_invalid_pfas BIGINT,
    accuracy_rate NUMERIC,
    most_problematic_products JSONB
) AS $$
DECLARE
    cutoff_date TIMESTAMPTZ := NOW() - (days_back || ' days')::INTERVAL;
BEGIN
    RETURN QUERY
    SELECT
        COUNT(DISTINCT product_url) FILTER (WHERE log_type = 'validation_summary') as total_products_analyzed,
        COUNT(*) FILTER (WHERE log_type = 'invalid_allergen') as total_invalid_allergens,
        COUNT(*) FILTER (WHERE log_type = 'invalid_pfas') as total_invalid_pfas,
        CASE
            WHEN COUNT(*) FILTER (WHERE log_type = 'validation_summary') > 0 THEN
                100.0 - (
                    (COUNT(*) FILTER (WHERE log_type IN ('invalid_allergen', 'invalid_pfas'))::NUMERIC /
                     NULLIF(COUNT(*) FILTER (WHERE log_type = 'validation_summary'), 0)) * 100
                )
            ELSE 0
        END as accuracy_rate,
        jsonb_agg(jsonb_build_object(
            'product_name', product_name,
            'product_url', product_url,
            'invalid_count', invalid_count
        ) ORDER BY invalid_count DESC) FILTER (WHERE product_name IS NOT NULL) as most_problematic_products
    FROM (
        SELECT
            product_name,
            product_url,
            COUNT(*) as invalid_count
        FROM validation_logs
        WHERE timestamp >= cutoff_date
          AND log_type IN ('invalid_allergen', 'invalid_pfas')
        GROUP BY product_name, product_url
        ORDER BY invalid_count DESC
        LIMIT 10
    ) AS problematic;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. ENABLE ROW LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE validation_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Allow service role full access
CREATE POLICY "Service role has full access to validation_logs"
ON validation_logs
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Policy: Authenticated users can read (for admin dashboard)
CREATE POLICY "Authenticated users can read validation_logs"
ON validation_logs
FOR SELECT
TO authenticated
USING (true);

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE validation_logs IS 'Stores validation logs from Claude AI misclassifications for monitoring and improvement';
COMMENT ON COLUMN validation_logs.log_type IS 'Type of validation log: invalid_allergen, invalid_pfas, reclassified_substance, validation_summary';
COMMENT ON COLUMN validation_logs.details IS 'Flexible JSONB field for additional data not covered by standard columns';
COMMENT ON FUNCTION get_validation_stats_by_date IS 'Returns daily validation statistics for a date range';
COMMENT ON FUNCTION get_most_flagged_substances IS 'Returns the most frequently misclassified substances';
COMMENT ON FUNCTION get_validation_logs_by_product IS 'Returns all validation logs for a specific product URL';
COMMENT ON FUNCTION get_recent_validation_summary IS 'Returns summary statistics for recent validations';
