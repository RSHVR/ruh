-- Migration 006: Enable Row Level Security on all tables
-- With no policies, anon key has NO access (blocked by default)
-- service_role key bypasses RLS entirely (used by backend)

-- Reference data tables
ALTER TABLE allergens ENABLE ROW LEVEL SECURITY;
ALTER TABLE pfas_compounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE toxic_substances ENABLE ROW LEVEL SECURITY;

-- Core analysis tables
ALTER TABLE product_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE alternative_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_feedback ENABLE ROW LEVEL SECURITY;

-- User tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_searches ENABLE ROW LEVEL SECURITY;

-- System tables
-- Note: cache_statistics is a VIEW, not a table (views don't support RLS)
ALTER TABLE validation_logs ENABLE ROW LEVEL SECURITY;
