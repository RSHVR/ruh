-- 021_add_product_sku.sql
-- Persist the product SKU / model # / GTIN / MPN (best-effort, from JSON-LD or extraction).
-- Nullable TEXT; back-compat (existing rows stay NULL). A SKU is a strong variant key, so this
-- also feeds the §F family/variant no-rescan work (KB-OPTIMIZATION-PLAN). Idempotent.
--
-- DEPLOY ORDER: apply this migration to prod BEFORE deploying the code that writes `sku`.
-- store_analysis upserts the full row; an unknown `sku` column would fail the whole upsert
-- (swallowed non-fatally, so analyses would silently stop caching until the column exists).

ALTER TABLE product_analyses ADD COLUMN IF NOT EXISTS sku TEXT;

COMMENT ON COLUMN product_analyses.sku IS
  'Product SKU / model # / GTIN / MPN — best-effort from JSON-LD or extraction; NULL if unknown. Strong variant key (see KB-OPTIMIZATION-PLAN §F).';
