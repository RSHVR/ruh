-- Migration 008: Update search_reviews RPC to return more fields
-- Adds helpful_votes and reviewer_name for better review analysis

-- Drop and recreate the function with additional return fields
CREATE OR REPLACE FUNCTION search_reviews(
  query_embedding vector(1536),
  match_url_hash TEXT DEFAULT NULL,
  match_threshold FLOAT DEFAULT 0.5,
  match_count INT DEFAULT 10
)
RETURNS TABLE (
  id UUID,
  url_hash TEXT,
  review_text TEXT,
  review_rating INTEGER,
  verified_purchase BOOLEAN,
  helpful_votes INTEGER,
  reviewer_name TEXT,
  similarity FLOAT
)
LANGUAGE plpgsql
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
    1 - (rc.embedding <=> query_embedding) AS similarity
  FROM review_chunks rc
  WHERE
    (match_url_hash IS NULL OR rc.url_hash = match_url_hash)
    AND rc.embedding IS NOT NULL
    AND 1 - (rc.embedding <=> query_embedding) > match_threshold
  ORDER BY rc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_reviews IS 'Semantic search across reviews using cosine similarity - returns full review data';
