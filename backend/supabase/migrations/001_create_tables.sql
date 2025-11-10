-- Eject Database Schema
-- Migration 001: Create all core tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users table - anonymous tracking via UUID
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_active TIMESTAMPTZ,
  extension_version TEXT,

  -- Optional preferences (stored locally, synced if user opts-in)
  allergen_profile JSONB DEFAULT '[]'::jsonb,
  sensitivity_level TEXT CHECK (sensitivity_level IN ('strict', 'moderate', 'relaxed')) DEFAULT 'moderate'
);

-- 2. Product Analyses - cache of AI analysis results
CREATE TABLE product_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_url TEXT NOT NULL,
  product_url_hash TEXT UNIQUE NOT NULL,

  -- Product data
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
  analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  analysis_version TEXT,
  claude_model TEXT
);

-- Indexes for fast lookup
CREATE INDEX idx_product_url_hash ON product_analyses(product_url_hash);
CREATE INDEX idx_product_url ON product_analyses(product_url);
CREATE INDEX idx_analyzed_at ON product_analyses(analyzed_at DESC);

-- 3. User Searches - track what users searched (privacy-respecting)
CREATE TABLE user_searches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,

  product_url TEXT NOT NULL,
  product_url_hash TEXT NOT NULL,
  analysis_id UUID REFERENCES product_analyses(id),

  searched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_searches ON user_searches(user_id, searched_at DESC);
CREATE INDEX idx_user_searches_url_hash ON user_searches(product_url_hash);

-- 4. Alternative Recommendations - track what AI recommended
CREATE TABLE alternative_recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  original_analysis_id UUID REFERENCES product_analyses(id) ON DELETE CASCADE,
  alternative_product_url TEXT NOT NULL,
  alternative_product_name TEXT,

  -- Scores
  safety_score INTEGER CHECK (safety_score >= 0 AND safety_score <= 100),
  safety_improvement INTEGER,
  price DECIMAL(10,2),
  price_difference DECIMAL(10,2),

  -- Ranking
  rank INTEGER,

  -- Affiliate
  affiliate_link TEXT,
  affiliate_network TEXT,

  -- Metadata
  recommended_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_original_analysis ON alternative_recommendations(original_analysis_id);
CREATE INDEX idx_recommended_at ON alternative_recommendations(recommended_at DESC);

-- 5. User Interactions - track clicks and purchases (for optimization)
CREATE TYPE interaction_action AS ENUM ('viewed_alternatives', 'clicked_alternative', 'purchased');

CREATE TABLE user_interactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,

  search_id UUID REFERENCES user_searches(id) ON DELETE CASCADE,
  alternative_id UUID REFERENCES alternative_recommendations(id),

  action interaction_action NOT NULL,

  occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Revenue tracking (optional, privacy-respecting)
  purchase_amount DECIMAL(10,2),
  commission_earned DECIMAL(10,2)
);

CREATE INDEX idx_user_interactions ON user_interactions(user_id, occurred_at DESC);
CREATE INDEX idx_alternative_interactions ON user_interactions(alternative_id, action);

-- 6. Feedback - user ratings on analysis quality
CREATE TABLE analysis_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  analysis_id UUID REFERENCES product_analyses(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,

  helpful BOOLEAN NOT NULL,
  comment TEXT,

  submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(analysis_id, user_id)
);

CREATE INDEX idx_analysis_feedback ON analysis_feedback(analysis_id);

-- 7. Knowledge Base - allergens
CREATE TABLE allergens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  synonyms TEXT[] DEFAULT '{}',
  severity_default INTEGER CHECK (severity_default >= 1 AND severity_default <= 10),
  common_sources TEXT[] DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Knowledge Base - PFAS compounds
CREATE TABLE pfas_compounds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  cas_number TEXT UNIQUE,
  synonyms TEXT[] DEFAULT '{}',
  health_impacts TEXT[] DEFAULT '{}',
  body_effects TEXT,
  sources TEXT[] DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for knowledge base searches
CREATE INDEX idx_allergen_name ON allergens(name);
CREATE INDEX idx_pfas_name ON pfas_compounds(name);
CREATE INDEX idx_pfas_cas ON pfas_compounds(cas_number);

-- Comments for documentation
COMMENT ON TABLE users IS 'Anonymous user tracking via UUID - no PII collected';
COMMENT ON TABLE product_analyses IS 'Permanent cache of product safety analyses - de-anonymized';
COMMENT ON TABLE user_searches IS '90-day TTL tracking of user searches - anonymous UUID';
COMMENT ON TABLE alternative_recommendations IS 'Safer alternatives recommended by AI';
COMMENT ON TABLE user_interactions IS 'User interaction tracking for optimization and revenue';
COMMENT ON TABLE analysis_feedback IS 'User feedback on analysis quality';
COMMENT ON TABLE allergens IS 'Comprehensive allergen database with synonyms';
COMMENT ON TABLE pfas_compounds IS 'PFAS compounds database with health impact information';
