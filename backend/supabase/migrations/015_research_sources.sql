-- Migration 015: persist agent research citations per analysis
-- The research agent already returns research_sources [{type, url, finding}]
-- in its structured output; this column stops the route from dropping them.
-- Idempotent.

ALTER TABLE product_analyses
  ADD COLUMN IF NOT EXISTS research_sources JSONB NOT NULL DEFAULT '[]'::jsonb;
