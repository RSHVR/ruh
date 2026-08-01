-- Migration 019: Hybrid review search (lexical BM25-class + existing semantic)
--
-- The review RAG (get_health_relevant_reviews -> search_reviews, migration 008)
-- is purely semantic/pgvector. Embeddings can rank an exact term ("PFOA",
-- "benzene", "formaldehyde", "rash", "hives") low, so a hard lexical match could
-- be missed. This adds native Postgres full-text search over review_chunks
-- (migration 005) and a lexical RPC; the service fuses it with the semantic RPC
-- via Reciprocal Rank Fusion, then Cohere rerank stays the final stage.
--
-- Supabase hosted Postgres has no paradedb/pg_search, so we use the closest
-- native scorer: a GIN-indexed tsvector + websearch_to_tsquery + ts_rank_cd.
-- Idempotent (re-runnable), following the conventions of migrations 015-018.

-- 1. Generated tsvector column over the review text.
--    to_tsvector('english', review_text) is the IMMUTABLE 2-arg form (the config
--    is resolved at definition time), which is required for a STORED generated
--    column. Supabase (PG 15+) supports generated columns; if a target ever runs
--    PG < 12 this would need a trigger-maintained column instead.
ALTER TABLE review_chunks
  ADD COLUMN IF NOT EXISTS review_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', review_text)) STORED;

-- 2. GIN index for fast full-text matching.
CREATE INDEX IF NOT EXISTS idx_review_chunks_tsv
  ON review_chunks USING gin (review_tsv);

-- 3. Lexical search RPC — mirrors search_reviews' filters/return shape (minus the
--    embedding), returns a ts_rank_cd relevance score instead of cosine
--    similarity. websearch_to_tsquery tolerates arbitrary user text (never raises
--    on punctuation/operators), so passing raw health-concern queries is safe.
--    SECURITY DEFINER + empty search_path per the SQL-function convention
--    (migration 013); the table is schema-qualified accordingly.
CREATE OR REPLACE FUNCTION search_reviews_lexical(
  p_query TEXT,
  p_url_hash TEXT DEFAULT NULL,
  p_limit INT DEFAULT 10
)
RETURNS TABLE (
  id UUID,
  url_hash TEXT,
  review_text TEXT,
  review_rating INTEGER,
  verified_purchase BOOLEAN,
  helpful_votes INTEGER,
  reviewer_name TEXT,
  lexical_rank FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  RETURN QUERY
  SELECT
    rc.id,
    rc.url_hash,
    rc.review_text,
    rc.review_rating,
    rc.verified_purchase,
    rc.helpful_votes,
    rc.reviewer_name,
    ts_rank_cd(rc.review_tsv, websearch_to_tsquery('english', p_query))::float AS lexical_rank
  FROM public.review_chunks rc
  WHERE
    (p_url_hash IS NULL OR rc.url_hash = p_url_hash)
    AND rc.review_tsv @@ websearch_to_tsquery('english', p_query)
  ORDER BY lexical_rank DESC
  LIMIT p_limit;
END;
$$;

COMMENT ON COLUMN review_chunks.review_tsv IS
  'Generated english tsvector over review_text for lexical (full-text) search.';
COMMENT ON FUNCTION search_reviews_lexical IS
  'Lexical (BM25-class) review search via ts_rank_cd; fused with search_reviews (semantic) by RRF in the app layer.';
