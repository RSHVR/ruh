-- Migration 013: Add authentication and credit system
-- Adds Supabase Auth integration, user tiers, credit ledger, and unlock tracking

-- ============================================================================
-- EXTEND users TABLE (link to Supabase Auth)
-- ============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_id UUID UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider TEXT;

CREATE INDEX IF NOT EXISTS idx_users_auth_id ON users(auth_id);

-- ============================================================================
-- USER TIERS
-- ============================================================================

DO $$ BEGIN
  CREATE TYPE user_tier AS ENUM ('free', 'basic', 'middle', 'unlimited');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS user_tiers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tier user_tier NOT NULL DEFAULT 'free',
  monthly_credits INTEGER NOT NULL DEFAULT 5,
  tier_set_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  set_by TEXT NOT NULL DEFAULT 'system',
  UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_tiers_user_id ON user_tiers(user_id);

-- ============================================================================
-- CREDIT LEDGER (server-authoritative balance, one active row per user)
-- ============================================================================

CREATE TABLE IF NOT EXISTS credit_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  credits_remaining INTEGER NOT NULL DEFAULT 5,
  cycle_start TIMESTAMPTZ NOT NULL DEFAULT date_trunc('month', NOW()),
  cycle_end TIMESTAMPTZ NOT NULL DEFAULT date_trunc('month', NOW()) + INTERVAL '1 month',
  last_deducted_at TIMESTAMPTZ,
  total_used_this_cycle INTEGER NOT NULL DEFAULT 0,
  UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_id ON credit_ledger(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_cycle ON credit_ledger(cycle_end);

-- ============================================================================
-- CREDIT TRANSACTIONS (audit trail)
-- ============================================================================

DO $$ BEGIN
  CREATE TYPE credit_action AS ENUM (
    'monthly_reset',
    'detail_view',
    'admin_grant',
    'tier_change',
    'refund'
  );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS credit_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  action credit_action NOT NULL,
  amount INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  analysis_url_hash TEXT,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_user ON credit_transactions(user_id, created_at DESC);

-- ============================================================================
-- UNLOCKED ANALYSES (prevents double-charging)
-- ============================================================================

CREATE TABLE IF NOT EXISTS unlocked_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  url_hash TEXT NOT NULL,
  unlocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, url_hash)
);

CREATE INDEX IF NOT EXISTS idx_unlocked_analyses_lookup ON unlocked_analyses(user_id, url_hash);

-- ============================================================================
-- ROW-LEVEL SECURITY
-- ============================================================================

ALTER TABLE user_tiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE unlocked_analyses ENABLE ROW LEVEL SECURITY;

-- Users can read their own rows
CREATE POLICY "Users read own tier" ON user_tiers
  FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
  );

CREATE POLICY "Users read own credits" ON credit_ledger
  FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
  );

CREATE POLICY "Users read own transactions" ON credit_transactions
  FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
  );

CREATE POLICY "Users read own unlocks" ON unlocked_analyses
  FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
  );

-- Service role can manage all
CREATE POLICY "Service manages tiers" ON user_tiers
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service manages credits" ON credit_ledger
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service manages transactions" ON credit_transactions
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service manages unlocks" ON unlocked_analyses
  FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- RPC: Atomic credit deduction
-- ============================================================================

CREATE OR REPLACE FUNCTION deduct_credit(
  p_user_id UUID,
  p_url_hash TEXT
) RETURNS TABLE(
  success BOOLEAN,
  credits_remaining INTEGER,
  already_unlocked BOOLEAN,
  is_unlimited BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_tier public.user_tier;
  v_credits INTEGER;
  v_already BOOLEAN;
BEGIN
  -- Check tier
  SELECT ut.tier INTO v_tier
  FROM public.user_tiers ut WHERE ut.user_id = p_user_id;

  -- Unlimited: always succeeds, no deduction
  IF v_tier = 'unlimited' THEN
    RETURN QUERY SELECT TRUE, -1, FALSE, TRUE;
    RETURN;
  END IF;

  -- Check if already unlocked
  SELECT EXISTS(
    SELECT 1 FROM public.unlocked_analyses ua
    WHERE ua.user_id = p_user_id AND ua.url_hash = p_url_hash
  ) INTO v_already;

  IF v_already THEN
    SELECT cl.credits_remaining INTO v_credits
    FROM public.credit_ledger cl WHERE cl.user_id = p_user_id;
    RETURN QUERY SELECT TRUE, COALESCE(v_credits, 0), TRUE, FALSE;
    RETURN;
  END IF;

  -- Deduct credit atomically (row lock via UPDATE ... RETURNING)
  UPDATE public.credit_ledger cl
  SET credits_remaining = cl.credits_remaining - 1,
      total_used_this_cycle = cl.total_used_this_cycle + 1,
      last_deducted_at = NOW()
  WHERE cl.user_id = p_user_id
    AND cl.credits_remaining > 0
    AND cl.cycle_end > NOW()
  RETURNING cl.credits_remaining INTO v_credits;

  IF v_credits IS NOT NULL THEN
    -- Record transaction
    INSERT INTO public.credit_transactions (user_id, action, amount, balance_after, analysis_url_hash)
    VALUES (p_user_id, 'detail_view', -1, v_credits, p_url_hash);

    -- Record unlock
    INSERT INTO public.unlocked_analyses (user_id, url_hash)
    VALUES (p_user_id, p_url_hash);

    RETURN QUERY SELECT TRUE, v_credits, FALSE, FALSE;
  ELSE
    -- No credits or expired cycle
    SELECT cl.credits_remaining INTO v_credits
    FROM public.credit_ledger cl WHERE cl.user_id = p_user_id;
    RETURN QUERY SELECT FALSE, COALESCE(v_credits, 0), FALSE, FALSE;
  END IF;
END;
$$;

-- ============================================================================
-- RPC: Monthly credit reset (call via pg_cron or scheduled task)
-- ============================================================================

CREATE OR REPLACE FUNCTION reset_monthly_credits()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  affected INTEGER;
BEGIN
  UPDATE public.credit_ledger cl
  SET credits_remaining = ut.monthly_credits,
      total_used_this_cycle = 0,
      cycle_start = date_trunc('month', NOW()),
      cycle_end = date_trunc('month', NOW()) + INTERVAL '1 month'
  FROM public.user_tiers ut
  WHERE cl.user_id = ut.user_id
    AND cl.cycle_end <= NOW()
    AND ut.tier != 'unlimited';

  GET DIAGNOSTICS affected = ROW_COUNT;

  -- Log resets as transactions
  INSERT INTO public.credit_transactions (user_id, action, amount, balance_after, note)
  SELECT cl.user_id, 'monthly_reset', ut.monthly_credits, cl.credits_remaining, 'Automatic monthly reset'
  FROM public.credit_ledger cl
  JOIN public.user_tiers ut ON cl.user_id = ut.user_id
  WHERE cl.cycle_start = date_trunc('month', NOW())
    AND ut.tier != 'unlimited';

  RETURN affected;
END;
$$;

-- ============================================================================
-- RPC: Initialize new user with tier and credits
-- ============================================================================

CREATE OR REPLACE FUNCTION initialize_user_credits(
  p_user_id UUID,
  p_tier public.user_tier DEFAULT 'free',
  p_monthly_credits INTEGER DEFAULT 5
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
