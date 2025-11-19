-- ============================================================================
-- COMPREHENSIVE DATABASE DROP SCRIPT
-- WARNING: This will delete ALL data and objects in your Supabase database!
-- ============================================================================
-- Use this to reset your database to a clean state before running migrations
--
-- Total Objects: 63
--   - 1 Extension (uuid-ossp)
--   - 1 Custom Type (interaction_action)
--   - 9 Tables
--   - 27 Indexes (auto-dropped with CASCADE)
--   - 6 Functions
--   - 20 RLS Policies
-- ============================================================================

-- ============================================================================
-- STEP 1: Drop all RLS policies (must be dropped before tables)
-- ============================================================================

-- Users table policies (4)
DROP POLICY IF EXISTS "Users can read own data" ON users;
DROP POLICY IF EXISTS "Users can insert own data" ON users;
DROP POLICY IF EXISTS "Users can update own data" ON users;
DROP POLICY IF EXISTS "Service role can manage users" ON users;

-- Product analyses policies (3)
DROP POLICY IF EXISTS "Anyone can read product analyses" ON product_analyses;
DROP POLICY IF EXISTS "Service role can insert analyses" ON product_analyses;
DROP POLICY IF EXISTS "Service role can update analyses" ON product_analyses;

-- User searches policies (2)
DROP POLICY IF EXISTS "Users can read own searches" ON user_searches;
DROP POLICY IF EXISTS "Service role can manage searches" ON user_searches;

-- Alternative recommendations policies (2)
DROP POLICY IF EXISTS "Anyone can read alternatives" ON alternative_recommendations;
DROP POLICY IF EXISTS "Service role can manage alternatives" ON alternative_recommendations;

-- User interactions policies (2)
DROP POLICY IF EXISTS "Users can read own interactions" ON user_interactions;
DROP POLICY IF EXISTS "Service role can manage interactions" ON user_interactions;

-- Analysis feedback policies (3)
DROP POLICY IF EXISTS "Anyone can read feedback" ON analysis_feedback;
DROP POLICY IF EXISTS "Users can insert own feedback" ON analysis_feedback;
DROP POLICY IF EXISTS "Service role can manage feedback" ON analysis_feedback;

-- Knowledge base policies (4)
DROP POLICY IF EXISTS "Anyone can read allergens" ON allergens;
DROP POLICY IF EXISTS "Service role can manage allergens" ON allergens;
DROP POLICY IF EXISTS "Anyone can read pfas" ON pfas_compounds;
DROP POLICY IF EXISTS "Service role can manage pfas" ON pfas_compounds;

-- ============================================================================
-- STEP 2: Drop all functions (6 total)
-- ============================================================================

DROP FUNCTION IF EXISTS set_current_user_id(UUID) CASCADE;
DROP FUNCTION IF EXISTS search_allergen(TEXT) CASCADE;
DROP FUNCTION IF EXISTS search_pfas(TEXT) CASCADE;
DROP FUNCTION IF EXISTS search_toxic_substance(TEXT) CASCADE;
DROP FUNCTION IF EXISTS find_precursors(TEXT) CASCADE;
DROP FUNCTION IF EXISTS find_metabolites(TEXT) CASCADE;

-- ============================================================================
-- STEP 3: Drop all tables (9 total - respecting foreign key dependencies)
-- ============================================================================

-- Drop dependent tables first (those with foreign keys to other tables)
DROP TABLE IF EXISTS analysis_feedback CASCADE;
DROP TABLE IF EXISTS user_interactions CASCADE;
DROP TABLE IF EXISTS alternative_recommendations CASCADE;
DROP TABLE IF EXISTS user_searches CASCADE;

-- Drop main application tables
DROP TABLE IF EXISTS product_analyses CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Drop knowledge base tables (no dependencies)
DROP TABLE IF EXISTS allergens CASCADE;
DROP TABLE IF EXISTS pfas_compounds CASCADE;
DROP TABLE IF EXISTS toxic_substances CASCADE;

-- ============================================================================
-- STEP 4: Drop custom types (1 total)
-- ============================================================================

DROP TYPE IF EXISTS interaction_action CASCADE;

-- ============================================================================
-- STEP 5: Drop extensions
-- ============================================================================

-- Note: uuid-ossp is commonly used by other tables/apps in Supabase
-- Only drop if you're absolutely sure nothing else needs it
DROP EXTENSION IF EXISTS "uuid-ossp" CASCADE;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check if any tables remain
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename NOT LIKE 'pg_%'
  AND tablename NOT LIKE 'sql_%';

-- Check if custom type remains
SELECT typname FROM pg_type WHERE typname = 'interaction_action';

-- Check if extension remains
SELECT extname FROM pg_extension WHERE extname = 'uuid-ossp';

-- Expected results:
--   - Tables query: 0 rows (all dropped)
--   - Type query: 0 rows (dropped)
--   - Extension query: 0 rows (dropped)
