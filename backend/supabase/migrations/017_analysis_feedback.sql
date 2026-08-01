-- Migration 017: Analysis feedback
-- Stores every thumbs-up / thumbs-down / bug-report a user submits on an
-- analysis, optionally with reason badges and/or a free-text comment.
--
-- No unique constraint — multiple submissions per user/analysis are allowed;
-- abuse is handled by API rate limiting, not the schema.
--
-- Idempotent + guarded (safe to re-run): IF NOT EXISTS for tables/indexes,
-- DO $$ ... EXCEPTION WHEN duplicate_object $$ for policies. RLS enabled.
-- Mirrors the conventions in 016_referrals.sql / 013_add_auth_and_credits.sql.

-- ============================================================================
-- LEGACY CLEANUP
-- Migration 001 created an analysis_feedback table with a different shape
-- (analysis_id + helpful BOOLEAN) that never shipped a feature and holds no
-- data in prod. If that legacy shape is present AND empty, replace it; if it
-- somehow has rows, fail loudly rather than dropping silently.
-- ============================================================================

DO $$
DECLARE
  v_rows BIGINT;
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'analysis_feedback'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'analysis_feedback'
      AND column_name = 'url_hash'
  ) THEN
    EXECUTE 'SELECT COUNT(*) FROM public.analysis_feedback' INTO v_rows;
    IF v_rows > 0 THEN
      RAISE EXCEPTION 'Legacy analysis_feedback table has % rows — refusing to drop; migrate manually', v_rows;
    END IF;
    DROP TABLE public.analysis_feedback CASCADE;
  END IF;
END $$;

-- ============================================================================
-- ANALYSIS FEEDBACK
-- ============================================================================

CREATE TABLE IF NOT EXISTS analysis_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  url_hash TEXT NOT NULL,
  rating TEXT NOT NULL CHECK (rating IN ('up', 'down', 'bug')),
  reasons TEXT[] NOT NULL DEFAULT '{}',
  comment TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Per-analysis reads (aggregate a product's feedback).
CREATE INDEX IF NOT EXISTS idx_analysis_feedback_url_hash
  ON analysis_feedback(url_hash);

-- Per-user reads (a user's own submissions, newest first).
CREATE INDEX IF NOT EXISTS idx_analysis_feedback_user_created
  ON analysis_feedback(user_id, created_at);

-- ============================================================================
-- ROW-LEVEL SECURITY
-- ============================================================================

ALTER TABLE analysis_feedback ENABLE ROW LEVEL SECURITY;

-- Authenticated users can read their own submissions. The
-- users.auth_id = auth.uid() join mirrors the ownership pattern from 013.
DO $$ BEGIN
  CREATE POLICY "Users read own feedback" ON analysis_feedback
    FOR SELECT TO authenticated USING (
      user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Service role manages everything (the backend uses the service key, which
-- bypasses RLS; this policy keeps parity with 013/016 for defence in depth).
DO $$ BEGIN
  CREATE POLICY "Service manages feedback" ON analysis_feedback
    FOR ALL USING (auth.role() = 'service_role');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;
