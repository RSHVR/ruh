-- Migration 016: Referral program
-- Users invite friends by email; when an invited email signs up AND completes
-- their first analysis, the referrer earns +10 credits (max 5 credited
-- referrals per referrer). Unlimited invites are stored; no self-referral;
-- only the earliest inviter of a given email is credited.
--
-- Idempotent + guarded throughout (safe to re-run): IF NOT EXISTS for
-- tables/indexes, DO $$ ... EXCEPTION WHEN duplicate_object $$ for policies.
-- RLS enabled. Mirrors the conventions in 014_feature_requests.sql /
-- 013_add_auth_and_credits.sql.

-- ============================================================================
-- REFERRALS (one row per referrer -> invited email)
-- ============================================================================

CREATE TABLE IF NOT EXISTS referrals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  referrer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  invited_email TEXT NOT NULL,            -- stored lowercased by the service
  invited_user_id UUID REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'invited'
    CHECK (status IN ('invited', 'signed_up', 'credited')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  credited_at TIMESTAMPTZ,
  UNIQUE(referrer_user_id, invited_email)
);

-- Conversion lookups join on the invited email (across all referrers).
CREATE INDEX IF NOT EXISTS idx_referrals_invited_email
  ON referrals(invited_email);

-- The board/summary reads filter a referrer's rows by status.
CREATE INDEX IF NOT EXISTS idx_referrals_referrer_status
  ON referrals(referrer_user_id, status);

-- ============================================================================
-- ROW-LEVEL SECURITY
-- ============================================================================

ALTER TABLE referrals ENABLE ROW LEVEL SECURITY;

-- Authenticated users can read their own invites (as the referrer). The
-- users.auth_id = auth.uid() join mirrors the ownership pattern from 013.
DO $$ BEGIN
  CREATE POLICY "Users read own referrals" ON referrals
    FOR SELECT TO authenticated USING (
      referrer_user_id IN (SELECT id FROM users WHERE auth_id = auth.uid())
    );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Service role manages everything (the backend uses the service key, which
-- bypasses RLS; this policy keeps parity with 013/014 for defence in depth).
DO $$ BEGIN
  CREATE POLICY "Service manages referrals" ON referrals
    FOR ALL USING (auth.role() = 'service_role');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- RPC: Process a referral conversion for a user who completed their first
--      qualifying analysis. Idempotent — safe to call on every analysis.
-- ============================================================================

CREATE OR REPLACE FUNCTION process_referral_conversion(p_user_id UUID)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_email          TEXT;
  v_referral       public.referrals%ROWTYPE;
  v_credited_count INTEGER;
  v_new_balance    INTEGER;
  v_result         INTEGER := 0;
BEGIN
  -- Resolve the converting user's email (normalized lowercase).
  SELECT lower(u.email) INTO v_email
  FROM public.users u
  WHERE u.id = p_user_id;

  IF v_email IS NULL THEN
    RETURN 0;
  END IF;

  -- Earliest outstanding invite for this email, excluding any self-invite.
  SELECT r.* INTO v_referral
  FROM public.referrals r
  WHERE r.invited_email = v_email
    AND r.status = 'invited'
    AND r.referrer_user_id <> p_user_id
  ORDER BY r.created_at ASC
  LIMIT 1;

  -- No outstanding invite -> nothing to do (idempotent no-op).
  IF NOT FOUND THEN
    RETURN 0;
  END IF;

  -- How many referrals has this referrer already been credited for?
  SELECT COUNT(*) INTO v_credited_count
  FROM public.referrals r
  WHERE r.referrer_user_id = v_referral.referrer_user_id
    AND r.status = 'credited';

  IF v_credited_count < 5 THEN
    -- Under the cap: credit the referral, grant +10, log the transaction.
    UPDATE public.referrals
    SET status = 'credited',
        invited_user_id = p_user_id,
        credited_at = NOW()
    WHERE id = v_referral.id;

    UPDATE public.credit_ledger
    SET credits_remaining = credits_remaining + 10
    WHERE user_id = v_referral.referrer_user_id
    RETURNING credits_remaining INTO v_new_balance;

    -- Record the grant (guard against a missing ledger row, which would make
    -- balance_after NULL and violate its NOT NULL constraint).
    IF v_new_balance IS NOT NULL THEN
      INSERT INTO public.credit_transactions
        (user_id, action, amount, balance_after, note)
      VALUES
        (v_referral.referrer_user_id, 'admin_grant', 10, v_new_balance,
         'Referral reward');
    END IF;

    v_result := 1;
  ELSE
    -- Referrer at the cap: track the signup but do not credit.
    UPDATE public.referrals
    SET status = 'signed_up',
        invited_user_id = p_user_id
    WHERE id = v_referral.id;

    v_result := 0;
  END IF;

  -- Any OTHER outstanding invites for this same email lose the race — mark them
  -- signed_up (tracked, uncredited) and stamp the now-known invited user.
  UPDATE public.referrals
  SET status = 'signed_up',
      invited_user_id = p_user_id
  WHERE invited_email = v_email
    AND status = 'invited'
    AND id <> v_referral.id;

  RETURN v_result;
END;
$$;
