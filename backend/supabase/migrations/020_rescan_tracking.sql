-- Migration 020: Inconclusive-rescan tracking
-- Inconclusive cached analyses (no content / rock-bottom confidence / garbage
-- extraction) are treated as stale and re-analyzed on the next visit and by a
-- scheduled sweep, bounded by MAX_RESCANS (3) in src/domain/quality.py.
-- Idempotent (conventions of 015-018).

ALTER TABLE product_analyses
  ADD COLUMN IF NOT EXISTS rescan_count INTEGER NOT NULL DEFAULT 0;
