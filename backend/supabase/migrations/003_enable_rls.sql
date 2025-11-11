-- Eject Database Schema
-- Migration 003: Enable Row Level Security (RLS)

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE alternative_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE allergens ENABLE ROW LEVEL SECURITY;
ALTER TABLE pfas_compounds ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- USERS TABLE POLICIES
-- ============================================================================

-- Users can read their own data
CREATE POLICY "Users can read own data"
  ON users
  FOR SELECT
  USING (auth.uid() = id OR id = (current_setting('app.current_user_id', true))::uuid);

-- Users can insert their own record
CREATE POLICY "Users can insert own data"
  ON users
  FOR INSERT
  WITH CHECK (auth.uid() = id OR id = (current_setting('app.current_user_id', true))::uuid);

-- Users can update their own data
CREATE POLICY "Users can update own data"
  ON users
  FOR UPDATE
  USING (auth.uid() = id OR id = (current_setting('app.current_user_id', true))::uuid);

-- Service role (backend) can manage all users
CREATE POLICY "Service role can manage users"
  ON users
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- PRODUCT_ANALYSES TABLE POLICIES (PUBLIC READ, SERVICE WRITE)
-- ============================================================================

-- Anyone can read product analyses (de-anonymized, public safety data)
CREATE POLICY "Anyone can read product analyses"
  ON product_analyses
  FOR SELECT
  USING (true);

-- Only service role can insert/update product analyses
CREATE POLICY "Service role can insert analyses"
  ON product_analyses
  FOR INSERT
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can update analyses"
  ON product_analyses
  FOR UPDATE
  USING (auth.role() = 'service_role');

-- ============================================================================
-- USER_SEARCHES TABLE POLICIES (PRIVATE)
-- ============================================================================

-- Users can only read their own searches
CREATE POLICY "Users can read own searches"
  ON user_searches
  FOR SELECT
  USING (
    auth.uid() = user_id OR
    user_id = (current_setting('app.current_user_id', true))::uuid
  );

-- Service role can manage searches
CREATE POLICY "Service role can manage searches"
  ON user_searches
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- ALTERNATIVE_RECOMMENDATIONS TABLE POLICIES (PUBLIC READ)
-- ============================================================================

-- Anyone can read alternatives (tied to public product analyses)
CREATE POLICY "Anyone can read alternatives"
  ON alternative_recommendations
  FOR SELECT
  USING (true);

-- Only service role can insert/update alternatives
CREATE POLICY "Service role can manage alternatives"
  ON alternative_recommendations
  FOR INSERT
  WITH CHECK (auth.role() = 'service_role');

-- ============================================================================
-- USER_INTERACTIONS TABLE POLICIES (PRIVATE)
-- ============================================================================

-- Users can only read their own interactions
CREATE POLICY "Users can read own interactions"
  ON user_interactions
  FOR SELECT
  USING (
    auth.uid() = user_id OR
    user_id = (current_setting('app.current_user_id', true))::uuid
  );

-- Service role can manage interactions
CREATE POLICY "Service role can manage interactions"
  ON user_interactions
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- ANALYSIS_FEEDBACK TABLE POLICIES
-- ============================================================================

-- Users can read feedback on any analysis (for transparency)
CREATE POLICY "Anyone can read feedback"
  ON analysis_feedback
  FOR SELECT
  USING (true);

-- Users can insert their own feedback
CREATE POLICY "Users can insert own feedback"
  ON analysis_feedback
  FOR INSERT
  WITH CHECK (
    auth.uid() = user_id OR
    user_id = (current_setting('app.current_user_id', true))::uuid
  );

-- Service role can manage feedback
CREATE POLICY "Service role can manage feedback"
  ON analysis_feedback
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- KNOWLEDGE BASE POLICIES (PUBLIC READ-ONLY)
-- ============================================================================

-- Anyone can read allergens (public knowledge base)
CREATE POLICY "Anyone can read allergens"
  ON allergens
  FOR SELECT
  USING (true);

-- Only service role can update allergens
CREATE POLICY "Service role can manage allergens"
  ON allergens
  FOR ALL
  USING (auth.role() = 'service_role');

-- Anyone can read PFAS compounds (public knowledge base)
CREATE POLICY "Anyone can read pfas"
  ON pfas_compounds
  FOR SELECT
  USING (true);

-- Only service role can update PFAS compounds
CREATE POLICY "Service role can manage pfas"
  ON pfas_compounds
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- HELPER FUNCTION: Set current user ID for backend queries
-- ============================================================================

-- This function allows the backend to impersonate a user for RLS checks
-- Usage: SELECT set_current_user_id('user-uuid-here');
CREATE OR REPLACE FUNCTION set_current_user_id(user_uuid UUID)
RETURNS void AS $$
BEGIN
  PERFORM set_config('app.current_user_id', user_uuid::text, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION set_current_user_id IS 'Set user context for RLS policies (backend use only)';

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON POLICY "Anyone can read product analyses" ON product_analyses IS
  'Product safety data is de-anonymized and public for transparency';

COMMENT ON POLICY "Users can read own searches" ON user_searches IS
  'User searches are private - only accessible by that user';

COMMENT ON POLICY "Anyone can read allergens" ON allergens IS
  'Knowledge base is public for transparency and education';

COMMENT ON POLICY "Anyone can read pfas" ON pfas_compounds IS
  'PFAS health data is public for transparency and education';
