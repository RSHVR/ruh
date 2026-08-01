-- Migration 018: Ingredient provenance + referral FK fix
-- Idempotent (conventions of 015/016/017): guarded with IF NOT EXISTS /
-- IF EXISTS so it is safe to re-run.

-- ============================================================================
-- INGREDIENT PROVENANCE
-- Persist the declared / found / inferred breakdown alongside the flat
-- ingredients list. Nullable JSONB — older rows and rows where the agent did
-- not segment simply have NULL.
-- ============================================================================

ALTER TABLE product_analyses
  ADD COLUMN IF NOT EXISTS ingredients_by_provenance JSONB;

-- ============================================================================
-- PRODUCT ORIGIN (food/grocery only)
-- Region-aware production/sourcing provenance {summary, region, alert}. Nullable
-- JSONB — null for non-food products and older rows. Analyses stay cached
-- globally by url_hash; origin.region records which buyer region the cached
-- research was tailored to. The cache is NOT forked by region.
-- ============================================================================

ALTER TABLE product_analyses
  ADD COLUMN IF NOT EXISTS origin JSONB;

-- ============================================================================
-- REFERRAL FK FIX
-- referrals.invited_user_id was created (016) with the default ON DELETE
-- action (NO ACTION), which would block deleting a user who had been invited.
-- Re-point it to ON DELETE SET NULL so user deletion is never blocked; the
-- referral row survives with a null invited_user_id. Guarded drop + re-add
-- keeps this idempotent (the FK's auto-name is <table>_<column>_fkey).
-- ============================================================================

ALTER TABLE referrals DROP CONSTRAINT IF EXISTS referrals_invited_user_id_fkey;
ALTER TABLE referrals ADD CONSTRAINT referrals_invited_user_id_fkey
  FOREIGN KEY (invited_user_id) REFERENCES users(id) ON DELETE SET NULL;
