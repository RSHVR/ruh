-- Migration 002: Extend product_analyses table for scraping and reviews
-- Adds support for storing scraped product data and review insights

-- Add new columns to product_analyses table
ALTER TABLE product_analyses
ADD COLUMN IF NOT EXISTS scraped_product_data JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS review_insights JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS harm_score INTEGER CHECK (harm_score >= 0 AND harm_score <= 100),
ADD COLUMN IF NOT EXISTS category TEXT;

-- Add indexes for new fields
CREATE INDEX IF NOT EXISTS idx_product_analyses_category ON product_analyses(category);
CREATE INDEX IF NOT EXISTS idx_product_analyses_harm_score ON product_analyses(harm_score);

-- Add comments for documentation
COMMENT ON COLUMN product_analyses.scraped_product_data IS 'Raw scraped HTML and extracted JSON data from product page';
COMMENT ON COLUMN product_analyses.review_insights IS 'Consumer insights extracted from reviews and Q&A sections';
COMMENT ON COLUMN product_analyses.harm_score IS 'Calculated harm score (0-100, inverse of overall_score/safety score)';
COMMENT ON COLUMN product_analyses.category IS 'Product category or retailer name';
