-- Migration: Add token tracking columns to product_analyses
-- Tracks Claude API token usage and costs for each analysis

-- Add token tracking columns to product_analyses table
ALTER TABLE product_analyses
ADD COLUMN IF NOT EXISTS total_input_tokens INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_output_tokens INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_tokens INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_cost_usd DECIMAL(10, 6) DEFAULT 0,
ADD COLUMN IF NOT EXISTS api_call_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS token_usage_details JSONB DEFAULT '[]'::jsonb;

-- Add comments for documentation
COMMENT ON COLUMN product_analyses.total_input_tokens IS 'Total input tokens used across all Claude API calls for this analysis';
COMMENT ON COLUMN product_analyses.total_output_tokens IS 'Total output tokens used across all Claude API calls for this analysis';
COMMENT ON COLUMN product_analyses.total_tokens IS 'Total tokens (input + output) used for this analysis';
COMMENT ON COLUMN product_analyses.total_cost_usd IS 'Estimated cost in USD for this analysis based on Claude API pricing';
COMMENT ON COLUMN product_analyses.api_call_count IS 'Number of Claude API calls made for this analysis';
COMMENT ON COLUMN product_analyses.token_usage_details IS 'Detailed breakdown of token usage per API call (JSON array)';

-- Create index for cost analysis queries
CREATE INDEX IF NOT EXISTS idx_product_analyses_cost ON product_analyses(total_cost_usd);
CREATE INDEX IF NOT EXISTS idx_product_analyses_tokens ON product_analyses(total_tokens);
