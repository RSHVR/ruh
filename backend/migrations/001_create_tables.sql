-- Migration: Create all Eject database tables
-- Description: Initial schema for product safety analysis
-- Date: 2025-11-10

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table - anonymous tracking via UUID
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP,
    extension_version TEXT,
    allergen_profile JSONB DEFAULT '[]'::jsonb,
    sensitivity_level TEXT CHECK (sensitivity_level IN ('strict', 'moderate', 'relaxed'))
);

-- Product Analyses - permanent storage of AI analysis results
CREATE TABLE IF NOT EXISTS product_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_url TEXT NOT NULL,
    product_url_hash TEXT UNIQUE NOT NULL,
    product_name TEXT,
    brand TEXT,
    retailer TEXT,
    ingredients TEXT[],

    -- Analysis results
    overall_score INTEGER CHECK (overall_score >= 0 AND overall_score <= 100),
    allergens_detected JSONB DEFAULT '[]'::jsonb,
    pfas_detected JSONB DEFAULT '[]'::jsonb,
    other_concerns JSONB DEFAULT '[]'::jsonb,
    confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),

    -- Metadata
    analyzed_at TIMESTAMP DEFAULT NOW(),
    analysis_version TEXT,
    claude_model TEXT,

    -- Indexes for fast lookup
    CONSTRAINT product_analyses_pkey PRIMARY KEY (id)
);

-- Create indexes on product_analyses
CREATE INDEX idx_url_hash ON product_analyses(product_url_hash);
CREATE INDEX idx_product_url ON product_analyses(product_url);

-- User Searches - track what users searched (with TTL)
CREATE TABLE IF NOT EXISTS user_searches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    product_url TEXT NOT NULL,
    product_url_hash TEXT NOT NULL,
    analysis_id UUID REFERENCES product_analyses(id),
    searched_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '90 days')
);

-- Create indexes on user_searches
CREATE INDEX idx_user_searches ON user_searches(user_id, searched_at DESC);
CREATE INDEX idx_user_searches_url_hash ON user_searches(product_url_hash);
CREATE INDEX idx_user_searches_expires ON user_searches(expires_at);

-- Alternative Recommendations - track what AI recommended
CREATE TABLE IF NOT EXISTS alternative_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    original_analysis_id UUID REFERENCES product_analyses(id),
    alternative_product_url TEXT NOT NULL,
    alternative_product_name TEXT,

    -- Scores
    safety_score INTEGER CHECK (safety_score >= 0 AND safety_score <= 100),
    safety_improvement INTEGER,
    price NUMERIC(10,2),
    price_difference NUMERIC(10,2),

    -- Ranking
    rank INTEGER CHECK (rank >= 1 AND rank <= 5),

    -- Affiliate
    affiliate_link TEXT,
    affiliate_network TEXT,

    -- Metadata
    recommended_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_original_analysis ON alternative_recommendations(original_analysis_id);

-- User Interactions - track clicks and purchases
CREATE TABLE IF NOT EXISTS user_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    search_id UUID REFERENCES user_searches(id),
    alternative_id UUID REFERENCES alternative_recommendations(id),
    action TEXT CHECK (action IN ('viewed_alternatives', 'clicked_alternative', 'purchased')),
    occurred_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '90 days'),

    -- Revenue tracking (optional)
    purchase_amount NUMERIC(10,2),
    commission_earned NUMERIC(10,2)
);

CREATE INDEX idx_user_interactions ON user_interactions(user_id, occurred_at DESC);
CREATE INDEX idx_alternative_interactions ON user_interactions(alternative_id, action);
CREATE INDEX idx_user_interactions_expires ON user_interactions(expires_at);

-- Feedback - user ratings on analysis quality
CREATE TABLE IF NOT EXISTS analysis_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID REFERENCES product_analyses(id),
    user_id UUID REFERENCES users(id),
    helpful BOOLEAN NOT NULL,
    comment TEXT,
    submitted_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(analysis_id, user_id)
);

CREATE INDEX idx_analysis_feedback ON analysis_feedback(analysis_id);

-- Knowledge Base - allergens
CREATE TABLE IF NOT EXISTS allergens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    synonyms TEXT[],
    severity_default INTEGER CHECK (severity_default >= 1 AND severity_default <= 10),
    common_sources TEXT[],
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Knowledge Base - PFAS compounds
CREATE TABLE IF NOT EXISTS pfas_compounds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    cas_number TEXT UNIQUE,
    synonyms TEXT[],
    health_impacts TEXT[],
    body_effects TEXT,
    sources TEXT[],
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create function to automatically clean up expired data
CREATE OR REPLACE FUNCTION delete_expired_user_data()
RETURNS void AS $$
BEGIN
    DELETE FROM user_searches WHERE expires_at < NOW();
    DELETE FROM user_interactions WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Create scheduled job to run cleanup (requires pg_cron extension)
-- This can be set up in Supabase dashboard or run manually
COMMENT ON FUNCTION delete_expired_user_data() IS 'Deletes expired user-linked data (searches and interactions older than 90 days)';
