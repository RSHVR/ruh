-- Migration 014: Feature-request board + beta credit defaults
-- Adds a public feature-request board (requests + votes) and bumps the
-- default monthly credit grant from 5 to 15 for the beta.
--
-- Idempotent + guarded throughout (safe to re-run): IF NOT EXISTS for
-- tables/columns/indexes, DO $$ ... EXCEPTION WHEN duplicate_object $$ for
-- policies. RLS enabled. Mirrors the conventions in 013_add_auth_and_credits.sql.

-- ============================================================================
-- FEATURE REQUESTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS feature_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL CHECK (char_length(title) BETWEEN 3 AND 120),
  description TEXT CHECK (char_length(description) <= 500),
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'planned', 'building', 'shipped', 'declined')),
  hidden BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite index supports the board's "non-hidden, filter by status" reads.
CREATE INDEX IF NOT EXISTS idx_feature_requests_status_hidden
  ON feature_requests(status, hidden);

-- ============================================================================
-- FEATURE VOTES (one vote per user per request)
-- ============================================================================

CREATE TABLE IF NOT EXISTS feature_votes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  feature_id UUID NOT NULL REFERENCES feature_requests(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(feature_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_feature_votes_feature ON feature_votes(feature_id);

-- ============================================================================
-- ROW-LEVEL SECURITY
-- ============================================================================

ALTER TABLE feature_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_votes ENABLE ROW LEVEL SECURITY;

-- Authenticated users can read the visible (non-hidden) board...
DO $$ BEGIN
  CREATE POLICY "Authenticated read visible features" ON feature_requests
    FOR SELECT TO authenticated USING (hidden = FALSE);
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- ...and all votes (vote tallies are public).
DO $$ BEGIN
  CREATE POLICY "Authenticated read votes" ON feature_votes
    FOR SELECT TO authenticated USING (TRUE);
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Service role manages everything (the backend uses the service key, which
-- bypasses RLS; these policies keep parity with 013 for defence in depth).
DO $$ BEGIN
  CREATE POLICY "Service manages features" ON feature_requests
    FOR ALL USING (auth.role() = 'service_role');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE POLICY "Service manages feature votes" ON feature_votes
    FOR ALL USING (auth.role() = 'service_role');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- BETA CREDIT DEFAULTS: 5 -> 15
-- ============================================================================

-- New tier rows and ledger rows default to 15 monthly credits.
ALTER TABLE user_tiers ALTER COLUMN monthly_credits SET DEFAULT 15;
ALTER TABLE credit_ledger ALTER COLUMN credits_remaining SET DEFAULT 15;

-- Same body as 013's initialize_user_credits; only the p_monthly_credits
-- default changes (5 -> 15). Call sites pass no override, so new users now
-- start with 15 credits.
CREATE OR REPLACE FUNCTION initialize_user_credits(
  p_user_id UUID,
  p_tier public.user_tier DEFAULT 'free',
  p_monthly_credits INTEGER DEFAULT 15
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  -- Create tier record
  INSERT INTO public.user_tiers (user_id, tier, monthly_credits)
  VALUES (p_user_id, p_tier, p_monthly_credits)
  ON CONFLICT (user_id) DO NOTHING;

  -- Create credit ledger
  INSERT INTO public.credit_ledger (user_id, credits_remaining)
  VALUES (p_user_id, p_monthly_credits)
  ON CONFLICT (user_id) DO NOTHING;

  -- Record initial grant
  INSERT INTO public.credit_transactions (user_id, action, amount, balance_after, note)
  VALUES (p_user_id, 'monthly_reset', p_monthly_credits, p_monthly_credits, 'Initial credit grant');
END;
$$;
