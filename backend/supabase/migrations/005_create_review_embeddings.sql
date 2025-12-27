-- Migration 005: Create vector-enabled product reviews table
-- Uses pgvector for semantic search with Cohere embeddings

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Individual review chunks with embeddings
CREATE TABLE review_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Link to product
  url_hash TEXT NOT NULL,
  product_url TEXT NOT NULL,

  -- Review content
  review_text TEXT NOT NULL,
  review_rating INTEGER CHECK (review_rating >= 1 AND review_rating <= 5),
  reviewer_name TEXT,
  review_date TEXT,
  verified_purchase BOOLEAN DEFAULT FALSE,
  helpful_votes INTEGER DEFAULT 0,

  -- Vector embedding (Cohere embed-v4.0 = 1536 dimensions)
  embedding vector(1536),

  -- Metadata
  chunk_index INTEGER DEFAULT 0,  -- For multi-chunk reviews
  source TEXT DEFAULT 'client',   -- 'client' or 'scraper'
  page_number INTEGER DEFAULT 1,  -- Which review page it came from

  -- Timestamps
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Foreign key to product_analyses (optional, may not exist yet)
  CONSTRAINT fk_product_url_hash
    FOREIGN KEY (url_hash)
    REFERENCES product_analyses(product_url_hash)
    ON DELETE CASCADE
);

-- Indexes for fast lookups
CREATE INDEX idx_review_chunks_url_hash ON review_chunks(url_hash);
CREATE INDEX idx_review_chunks_rating ON review_chunks(review_rating);
CREATE INDEX idx_review_chunks_verified ON review_chunks(verified_purchase);

-- HNSW index for fast similarity search (cosine distance)
CREATE INDEX idx_review_chunks_embedding ON review_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Summary table for quick stats (optional, can compute from chunks)
CREATE TABLE review_summaries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  url_hash TEXT UNIQUE NOT NULL,
  product_url TEXT NOT NULL,

  -- Counts
  total_reviews INTEGER DEFAULT 0,
  pages_fetched INTEGER DEFAULT 0,

  -- Rating distribution
  rating_5_count INTEGER DEFAULT 0,
  rating_4_count INTEGER DEFAULT 0,
  rating_3_count INTEGER DEFAULT 0,
  rating_2_count INTEGER DEFAULT 0,
  rating_1_count INTEGER DEFAULT 0,

  -- Stats
  verified_ratio FLOAT DEFAULT 0.0,
  avg_rating FLOAT DEFAULT 0.0,

  -- Source
  source TEXT DEFAULT 'client',

  -- Timestamps
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_review_summaries_url_hash ON review_summaries(url_hash);

-- Function to search reviews by semantic similarity
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

-- Enable Row Level Security
-- With no policies, anon key has NO access (blocked by default)
-- service_role key bypasses RLS entirely (used by backend)
ALTER TABLE review_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_summaries ENABLE ROW LEVEL SECURITY;

-- Comments
COMMENT ON TABLE review_chunks IS 'Individual reviews with Cohere embeddings for semantic search';
COMMENT ON TABLE review_summaries IS 'Aggregated review statistics per product';
COMMENT ON FUNCTION search_reviews IS 'Semantic search across reviews using cosine similarity';
