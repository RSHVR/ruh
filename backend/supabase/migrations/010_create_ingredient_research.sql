-- Pre-computed ingredient research for instant lookup during product analysis
-- Run once per ingredient, use forever

CREATE TABLE ingredient_research (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity (matches source tables)
    ingredient_name TEXT NOT NULL,
    source_table TEXT NOT NULL CHECK (source_table IN ('allergens', 'pfas_compounds', 'toxic_substances')),
    source_id UUID,                     -- FK to original table
    cas_number TEXT,
    synonyms TEXT[],                    -- For matching during analysis

    -- Scientific findings
    iarc_classification TEXT,           -- 'Group 1', 'Group 2A', 'Group 2B', 'Group 3', 'Not classified'
    iarc_details TEXT,                  -- Full classification details
    ewg_score INTEGER CHECK (ewg_score >= 1 AND ewg_score <= 10),
    ewg_details TEXT,

    scientific_summary TEXT,            -- AI-synthesized summary of all findings

    -- Structured findings from research
    health_effects JSONB DEFAULT '[]',  -- [{effect, severity, evidence_level, source_url}]
    scientific_sources JSONB DEFAULT '[]', -- [{url, title, snippet, relevance_score, publication_date}]
    pubmed_studies JSONB DEFAULT '[]',  -- [{pmid, title, abstract, year, journal}]

    -- Regulatory findings
    regulatory_status JSONB DEFAULT '{}', -- {usa: {status, details}, eu: {status, details}, canada: {status, details}}
    regulatory_actions JSONB DEFAULT '[]', -- [{agency, action_type, date, details, url}]
    bans_restrictions JSONB DEFAULT '[]', -- [{jurisdiction, scope, effective_date, details}]

    -- Legal findings
    legal_summary TEXT,
    lawsuits JSONB DEFAULT '[]',        -- [{case_name, court, year, status, outcome, damages, url}]
    settlements JSONB DEFAULT '[]',     -- [{parties, year, amount, details, url}]
    class_actions JSONB DEFAULT '[]',   -- [{case_name, status, affected_products, url}]

    -- Consumer/anecdotal (from Reddit, forums)
    consumer_reports JSONB DEFAULT '[]', -- [{source, summary, sentiment, date}]

    -- Raw search data (for debugging/re-processing)
    raw_search_results JSONB DEFAULT '{}', -- {scientific: [...], legal: [...], regulatory: [...]}
    search_queries_used JSONB DEFAULT '[]', -- [{query, search_type, result_count}]

    -- Metadata
    total_sources INTEGER DEFAULT 0,
    confidence_score FLOAT DEFAULT 0.0 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    researched_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    research_version TEXT DEFAULT '1.0', -- For re-running with improved queries

    UNIQUE(ingredient_name, source_table)
);

-- Indexes for fast lookup during product analysis
CREATE INDEX idx_ingredient_research_name ON ingredient_research(ingredient_name);
CREATE INDEX idx_ingredient_research_cas ON ingredient_research(cas_number) WHERE cas_number IS NOT NULL;
CREATE INDEX idx_ingredient_research_synonyms ON ingredient_research USING GIN(synonyms);
CREATE INDEX idx_ingredient_research_source ON ingredient_research(source_table);

-- Full-text search on ingredient name and synonyms
CREATE INDEX idx_ingredient_research_fts ON ingredient_research
    USING GIN(to_tsvector('english', ingredient_name || ' ' || COALESCE(array_to_string(synonyms, ' '), '')));

-- Function to search ingredient research by name or synonym
CREATE OR REPLACE FUNCTION search_ingredient_research(search_term TEXT)
RETURNS SETOF ingredient_research AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM ingredient_research
    WHERE
        ingredient_name ILIKE '%' || search_term || '%'
        OR search_term ILIKE ANY(synonyms)
        OR cas_number = search_term
    ORDER BY
        CASE WHEN ingredient_name ILIKE search_term THEN 0 ELSE 1 END,
        ingredient_name
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE ingredient_research IS 'Pre-computed safety research for known ingredients. Populated via batch job, used for instant lookup during product analysis.';
