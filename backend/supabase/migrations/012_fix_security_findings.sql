-- ============================================================================
-- Migration 012: Fix Supabase security findings (BUG-9)
-- Date: 2026-02-08
-- Source: Supabase Database Linter security/performance advisors
-- Ref: backend/docs/BUGS_2026-02-08.md — BUG-9
-- ============================================================================
-- This migration addresses:
--   9a: Replace USING(true) RLS policies with service_role-only access
--   9b: Recreate cache_statistics view as SECURITY INVOKER
--   9c: Set search_path on all 18 public functions
--   9d: Add service_role RLS policies to 11 unprotected tables
--   9e: Move extensions to dedicated schema (uuid-ossp, vector)
--   9f: Drop unused indexes, add missing FK indexes
-- ============================================================================

BEGIN;

-- ============================================================================
-- 9a: Fix overly permissive RLS policies (USING(true) → service_role only)
-- ============================================================================

-- extracted_content: drop permissive policy, add service_role-only
DROP POLICY IF EXISTS "Allow all operations on extracted_content" ON public.extracted_content;
CREATE POLICY "service_role_only" ON public.extracted_content
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ingredient_research: drop permissive policy, restrict to service_role
-- Migration 010 created this table but never enabled RLS, so the policy below
-- would be dormant (table exposed via the API). Enable RLS here to enforce it.
ALTER TABLE public.ingredient_research ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_access" ON public.ingredient_research;
CREATE POLICY "service_role_only" ON public.ingredient_research
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- search_cache: drop permissive policy, restrict to service_role
DROP POLICY IF EXISTS "service_role_all_access" ON public.search_cache;
CREATE POLICY "service_role_only" ON public.search_cache
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- ============================================================================
-- 9b: Recreate cache_statistics view as SECURITY INVOKER
-- ============================================================================

DROP VIEW IF EXISTS public.cache_statistics;
CREATE VIEW public.cache_statistics
WITH (security_invoker = true)
AS
SELECT
    count(*) AS total_cached_products,
    count(*) FILTER (WHERE analyzed_at > (now() - '1 day'::interval)) AS cached_today,
    count(*) FILTER (WHERE analyzed_at > (now() - '7 days'::interval)) AS cached_this_week,
    count(*) FILTER (WHERE analyzed_at > (now() - '30 days'::interval)) AS cached_this_month,
    min(analyzed_at) AS oldest_cache_entry,
    max(analyzed_at) AS newest_cache_entry,
    avg(overall_score) AS avg_safety_score
FROM public.product_analyses;


-- ============================================================================
-- 9c: Fix mutable search_path on all 18 functions
-- ============================================================================
-- Recreate each function with SET search_path = '' to prevent
-- search path injection attacks.

CREATE OR REPLACE FUNCTION public.search_allergen(search_term text)
RETURNS TABLE(allergen_id uuid, allergen_name text, severity integer, allergen_type text)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
  RETURN QUERY
  SELECT id, name, severity_default, a.allergen_type
  FROM public.allergens a
  WHERE
    LOWER(a.name) = LOWER(search_term) OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(a.synonyms))) OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(a.alternative_names)));
END;
$function$;

CREATE OR REPLACE FUNCTION public.search_pfas(search_term text)
RETURNS TABLE(pfas_id uuid, pfas_name text, cas text, effects text, regulatory_status text)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
  RETURN QUERY
  SELECT id, name, cas_number, body_effects, regulatory_status_canada
  FROM public.pfas_compounds
  WHERE
    LOWER(name) LIKE '%' || LOWER(search_term) || '%' OR
    cas_number = search_term OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(synonyms)));
END;
$function$;

CREATE OR REPLACE FUNCTION public.search_toxic_substance(search_term text)
RETURNS TABLE(substance_id uuid, substance_name text, cas text, category text, effects text)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
  RETURN QUERY
  SELECT id, name, cas_number, substance_category, body_effects
  FROM public.toxic_substances
  WHERE
    LOWER(name) LIKE '%' || LOWER(search_term) || '%' OR
    cas_number = search_term OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(synonyms))) OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(common_names)));
END;
$function$;

CREATE OR REPLACE FUNCTION public.search_reviews(
    query_embedding vector,
    match_url_hash text DEFAULT NULL,
    match_threshold double precision DEFAULT 0.5,
    match_count integer DEFAULT 10
)
-- NOTE: return shape must match migration 008 (adds helpful_votes + reviewer_name),
-- otherwise CREATE OR REPLACE fails (42P13) and 008's added fields are silently lost.
RETURNS TABLE(id uuid, url_hash text, review_text text, review_rating integer, verified_purchase boolean, helpful_votes integer, reviewer_name text, similarity double precision)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
  RETURN QUERY
  SELECT
    rc.id,
    rc.url_hash,
    rc.review_text,
    rc.review_rating,
    rc.verified_purchase,
    rc.helpful_votes,
    rc.reviewer_name,
    1 - (rc.embedding <=> query_embedding) AS similarity
  FROM public.review_chunks rc
  WHERE
    (match_url_hash IS NULL OR rc.url_hash = match_url_hash)
    AND rc.embedding IS NOT NULL
    AND 1 - (rc.embedding <=> query_embedding) > match_threshold
  ORDER BY rc.embedding <=> query_embedding
  LIMIT match_count;
END;
$function$;

CREATE OR REPLACE FUNCTION public.search_ingredient_research(search_term text)
RETURNS SETOF public.ingredient_research
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
    RETURN QUERY
    SELECT * FROM public.ingredient_research
    WHERE
        ingredient_name ILIKE '%' || search_term || '%'
        OR search_term ILIKE ANY(synonyms)
        OR cas_number = search_term
    ORDER BY
        CASE WHEN ingredient_name ILIKE search_term THEN 0 ELSE 1 END,
        ingredient_name
    LIMIT 5;
END;
$function$;

CREATE OR REPLACE FUNCTION public.find_precursors(substance_name text)
RETURNS TABLE(precursor_name text, transformation_pathway text, source_table text)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
  RETURN QUERY
  SELECT name, p.transformation_pathway, 'pfas_compounds'::TEXT
  FROM public.pfas_compounds p
  WHERE substance_name = ANY(p.metabolites) AND p.is_precursor = TRUE
  UNION
  SELECT name, t.transformation_pathway, 'toxic_substances'::TEXT
  FROM public.toxic_substances t
  WHERE substance_name = ANY(t.metabolites) AND t.is_precursor = TRUE;
END;
$function$;

CREATE OR REPLACE FUNCTION public.find_metabolites(substance_name text)
RETURNS TABLE(metabolite_name text, transformation_pathway text, source_table text)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
  RETURN QUERY
  SELECT name, p.transformation_pathway, 'pfas_compounds'::TEXT
  FROM public.pfas_compounds p
  WHERE substance_name = ANY(p.parent_compounds) AND p.is_metabolite = TRUE
  UNION
  SELECT name, t.transformation_pathway, 'toxic_substances'::TEXT
  FROM public.toxic_substances t
  WHERE substance_name = ANY(t.parent_compounds) AND t.is_metabolite = TRUE;
END;
$function$;

CREATE OR REPLACE FUNCTION public.find_product_cache(search_term text)
RETURNS TABLE(product_url_hash text, product_url text, product_name text, brand text, analyzed_at timestamp with time zone, overall_score integer)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
    RETURN QUERY
    SELECT
        pa.product_url_hash,
        pa.product_url,
        pa.product_name,
        pa.brand,
        pa.analyzed_at,
        pa.overall_score
    FROM public.product_analyses pa
    WHERE
        pa.product_url ILIKE '%' || search_term || '%'
        OR pa.product_name ILIKE '%' || search_term || '%'
        OR pa.brand ILIKE '%' || search_term || '%'
    ORDER BY pa.analyzed_at DESC;
END;
$function$;

CREATE OR REPLACE FUNCTION public.clear_all_cache()
RETURNS integer
LANGUAGE plpgsql
SET search_path = ''
AS $function$
DECLARE
    rows_deleted INTEGER;
BEGIN
    DELETE FROM public.product_analyses;
    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN rows_deleted;
END;
$function$;

CREATE OR REPLACE FUNCTION public.clear_product_cache(url_hash_to_clear text)
RETURNS integer
LANGUAGE plpgsql
SET search_path = ''
AS $function$
DECLARE
    rows_deleted INTEGER;
BEGIN
    DELETE FROM public.product_analyses
    WHERE product_url_hash = url_hash_to_clear;
    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN rows_deleted;
END;
$function$;

CREATE OR REPLACE FUNCTION public.clear_product_cache_by_url(product_url_to_clear text)
RETURNS integer
LANGUAGE plpgsql
SET search_path = ''
AS $function$
DECLARE
    rows_deleted INTEGER;
BEGIN
    DELETE FROM public.product_analyses
    WHERE product_url = product_url_to_clear;
    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN rows_deleted;
END;
$function$;

CREATE OR REPLACE FUNCTION public.clear_old_cache(days_old integer DEFAULT 30)
RETURNS integer
LANGUAGE plpgsql
SET search_path = ''
AS $function$
DECLARE
    rows_deleted INTEGER;
    cutoff_date TIMESTAMPTZ;
BEGIN
    cutoff_date := NOW() - (days_old || ' days')::INTERVAL;
    DELETE FROM public.product_analyses
    WHERE analyzed_at < cutoff_date;
    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN rows_deleted;
END;
$function$;

CREATE OR REPLACE FUNCTION public.cleanup_expired_search_cache()
RETURNS integer
LANGUAGE plpgsql
SET search_path = ''
AS $function$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM public.search_cache
    WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$function$;

CREATE OR REPLACE FUNCTION public.cleanup_expired_extractions()
RETURNS integer
LANGUAGE plpgsql
SET search_path = ''
AS $function$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM public.extracted_content
    WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_recent_validation_summary(days_back integer DEFAULT 7)
RETURNS TABLE(total_products_analyzed bigint, total_invalid_allergens bigint, total_invalid_pfas bigint, accuracy_rate numeric, most_problematic_products jsonb)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
DECLARE
    cutoff_date TIMESTAMPTZ := NOW() - (days_back || ' days')::INTERVAL;
BEGIN
    RETURN QUERY
    SELECT
        COUNT(DISTINCT product_url) FILTER (WHERE log_type = 'validation_summary') as total_products_analyzed,
        COUNT(*) FILTER (WHERE log_type = 'invalid_allergen') as total_invalid_allergens,
        COUNT(*) FILTER (WHERE log_type = 'invalid_pfas') as total_invalid_pfas,
        CASE
            WHEN COUNT(*) FILTER (WHERE log_type = 'validation_summary') > 0 THEN
                100.0 - (
                    (COUNT(*) FILTER (WHERE log_type IN ('invalid_allergen', 'invalid_pfas'))::NUMERIC /
                     NULLIF(COUNT(*) FILTER (WHERE log_type = 'validation_summary'), 0)) * 100
                )
            ELSE 0
        END as accuracy_rate,
        jsonb_agg(jsonb_build_object(
            'product_name', product_name,
            'product_url', product_url,
            'invalid_count', invalid_count
        ) ORDER BY invalid_count DESC) FILTER (WHERE product_name IS NOT NULL) as most_problematic_products
    FROM (
        SELECT
            vl.product_name,
            vl.product_url,
            COUNT(*) as invalid_count
        FROM public.validation_logs vl
        WHERE vl.timestamp >= cutoff_date
          AND vl.log_type IN ('invalid_allergen', 'invalid_pfas')
        GROUP BY vl.product_name, vl.product_url
        ORDER BY invalid_count DESC
        LIMIT 10
    ) AS problematic;
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_validation_stats_by_date(start_date timestamp with time zone, end_date timestamp with time zone)
RETURNS TABLE(date date, total_validations bigint, invalid_allergens bigint, invalid_pfas bigint, reclassifications bigint, unique_products bigint)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
    RETURN QUERY
    SELECT
        vl.timestamp::DATE as date,
        COUNT(*) FILTER (WHERE vl.log_type = 'validation_summary') as total_validations,
        COUNT(*) FILTER (WHERE vl.log_type = 'invalid_allergen') as invalid_allergens,
        COUNT(*) FILTER (WHERE vl.log_type = 'invalid_pfas') as invalid_pfas,
        COUNT(*) FILTER (WHERE vl.log_type = 'reclassified_substance') as reclassifications,
        COUNT(DISTINCT vl.product_url) as unique_products
    FROM public.validation_logs vl
    WHERE vl.timestamp >= start_date AND vl.timestamp <= end_date
    GROUP BY vl.timestamp::DATE
    ORDER BY date DESC;
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_validation_logs_by_product(search_product_url text)
RETURNS TABLE(id uuid, log_timestamp timestamp with time zone, log_type text, substance_name text, severity text, confidence numeric, category text, source text, details jsonb)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
    RETURN QUERY
    SELECT
        vl.id,
        vl.timestamp,
        vl.log_type,
        vl.substance_name,
        vl.severity,
        vl.confidence,
        vl.category,
        vl.source,
        vl.details
    FROM public.validation_logs vl
    WHERE vl.product_url = search_product_url
    ORDER BY vl.timestamp DESC;
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_most_flagged_substances(result_limit integer DEFAULT 20)
RETURNS TABLE(substance_name text, times_flagged bigint, log_type text, avg_confidence numeric, most_common_severity text, first_seen timestamp with time zone, last_seen timestamp with time zone)
LANGUAGE plpgsql
SET search_path = ''
AS $function$
BEGIN
    RETURN QUERY
    SELECT
        vl.substance_name,
        COUNT(*) as times_flagged,
        vl.log_type,
        AVG(vl.confidence) as avg_confidence,
        MODE() WITHIN GROUP (ORDER BY vl.severity) as most_common_severity,
        MIN(vl.timestamp) as first_seen,
        MAX(vl.timestamp) as last_seen
    FROM public.validation_logs vl
    WHERE vl.substance_name IS NOT NULL
      AND vl.log_type IN ('invalid_allergen', 'invalid_pfas')
    GROUP BY vl.substance_name, vl.log_type
    ORDER BY times_flagged DESC
    LIMIT result_limit;
END;
$function$;


-- ============================================================================
-- 9d: Add service_role RLS policies to 11 tables with RLS enabled but no policies
-- ============================================================================
-- These tables currently block ALL access (including service_role via PostgREST).
-- Add explicit service_role policies so the backend can operate correctly.

-- allergens (knowledge base — read-heavy)
CREATE POLICY "service_role_all" ON public.allergens FOR ALL TO service_role USING (true) WITH CHECK (true);

-- pfas_compounds (knowledge base — read-heavy)
CREATE POLICY "service_role_all" ON public.pfas_compounds FOR ALL TO service_role USING (true) WITH CHECK (true);

-- toxic_substances (knowledge base — read-heavy)
CREATE POLICY "service_role_all" ON public.toxic_substances FOR ALL TO service_role USING (true) WITH CHECK (true);

-- product_analyses (main cache — read/write)
CREATE POLICY "service_role_all" ON public.product_analyses FOR ALL TO service_role USING (true) WITH CHECK (true);

-- users (user tracking)
CREATE POLICY "service_role_all" ON public.users FOR ALL TO service_role USING (true) WITH CHECK (true);

-- user_searches (search logs)
CREATE POLICY "service_role_all" ON public.user_searches FOR ALL TO service_role USING (true) WITH CHECK (true);

-- review_chunks (review embeddings)
CREATE POLICY "service_role_all" ON public.review_chunks FOR ALL TO service_role USING (true) WITH CHECK (true);

-- review_summaries (review stats)
CREATE POLICY "service_role_all" ON public.review_summaries FOR ALL TO service_role USING (true) WITH CHECK (true);

-- alternative_recommendations (safer alternatives)
CREATE POLICY "service_role_all" ON public.alternative_recommendations FOR ALL TO service_role USING (true) WITH CHECK (true);

-- user_interactions (interaction tracking)
CREATE POLICY "service_role_all" ON public.user_interactions FOR ALL TO service_role USING (true) WITH CHECK (true);

-- analysis_feedback (user feedback)
CREATE POLICY "service_role_all" ON public.analysis_feedback FOR ALL TO service_role USING (true) WITH CHECK (true);

-- validation_logs (already has rows but should also have explicit policy)
-- Postgres does not support IF NOT EXISTS on CREATE POLICY; bare CREATE matches the sibling policies above.
CREATE POLICY "service_role_all" ON public.validation_logs FOR ALL TO service_role USING (true) WITH CHECK (true);


-- ============================================================================
-- 9e: Move extensions to dedicated schema
-- ============================================================================
-- NOTE: This can break existing references. Supabase recommends using the
-- extensions schema. After moving, functions using uuid_generate_v4() or
-- vector types will resolve via search_path. The default Supabase search_path
-- includes 'extensions' so this should be transparent.

CREATE SCHEMA IF NOT EXISTS extensions;

-- Move uuid-ossp (gen_random_uuid() from pg_crypto is preferred, but uuid-ossp
-- may be referenced by existing default values)
ALTER EXTENSION "uuid-ossp" SET SCHEMA extensions;

-- Move pgvector
ALTER EXTENSION vector SET SCHEMA extensions;


-- ============================================================================
-- 9f: Drop unused indexes (44 total — never been hit)
-- ============================================================================

-- validation_logs (5 unused indexes)
DROP INDEX IF EXISTS public.idx_validation_logs_timestamp;
DROP INDEX IF EXISTS public.idx_validation_logs_product_url;
DROP INDEX IF EXISTS public.idx_validation_logs_substance;
DROP INDEX IF EXISTS public.idx_validation_logs_type;
DROP INDEX IF EXISTS public.idx_validation_logs_type_timestamp;

-- review_chunks (4 unused indexes)
DROP INDEX IF EXISTS public.idx_review_chunks_url_hash;
DROP INDEX IF EXISTS public.idx_review_chunks_rating;
DROP INDEX IF EXISTS public.idx_review_chunks_verified;
DROP INDEX IF EXISTS public.idx_review_chunks_embedding;

-- review_summaries (1 unused index)
DROP INDEX IF EXISTS public.idx_review_summaries_url_hash;

-- extracted_content (3 unused indexes)
DROP INDEX IF EXISTS public.idx_extracted_content_domain;
DROP INDEX IF EXISTS public.idx_extracted_content_expires;
DROP INDEX IF EXISTS public.idx_extracted_content_extractor;

-- search_cache (2 unused indexes)
DROP INDEX IF EXISTS public.idx_search_cache_expires;
DROP INDEX IF EXISTS public.idx_search_cache_provider;

-- product_analyses (5 unused indexes)
DROP INDEX IF EXISTS public.idx_product_analyses_cost;
DROP INDEX IF EXISTS public.idx_product_analyses_tokens;
DROP INDEX IF EXISTS public.idx_product_analyses_category;
DROP INDEX IF EXISTS public.idx_product_analyses_harm_score;
DROP INDEX IF EXISTS public.idx_product_url;

-- ingredient_research (5 unused indexes)
DROP INDEX IF EXISTS public.idx_ingredient_research_name;
DROP INDEX IF EXISTS public.idx_ingredient_research_cas;
DROP INDEX IF EXISTS public.idx_ingredient_research_synonyms;
DROP INDEX IF EXISTS public.idx_ingredient_research_source;
DROP INDEX IF EXISTS public.idx_ingredient_research_fts;

-- pfas_compounds (4 unused indexes)
DROP INDEX IF EXISTS public.idx_pfas_cas;
DROP INDEX IF EXISTS public.idx_pfas_category;
DROP INDEX IF EXISTS public.idx_pfas_precursor;
DROP INDEX IF EXISTS public.idx_pfas_parent;

-- toxic_substances (4 unused indexes)
DROP INDEX IF EXISTS public.idx_toxic_cas;
DROP INDEX IF EXISTS public.idx_toxic_category;
DROP INDEX IF EXISTS public.idx_toxic_precursor;
DROP INDEX IF EXISTS public.idx_toxic_parent;

-- alternative_recommendations (2 unused indexes)
DROP INDEX IF EXISTS public.idx_original_analysis;
DROP INDEX IF EXISTS public.idx_recommended_at;

-- user_interactions (2 unused indexes)
DROP INDEX IF EXISTS public.idx_user_interactions;
DROP INDEX IF EXISTS public.idx_alternative_interactions;

-- analysis_feedback (1 unused index)
DROP INDEX IF EXISTS public.idx_analysis_feedback;

-- allergens (1 unused index)
DROP INDEX IF EXISTS public.idx_allergen_type;

-- user_searches (1 unused index)
DROP INDEX IF EXISTS public.idx_user_searches_url_hash;


-- ============================================================================
-- 9f: Add missing indexes on foreign keys
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_analysis_feedback_user_id
    ON public.analysis_feedback (user_id);

CREATE INDEX IF NOT EXISTS idx_user_interactions_search_id
    ON public.user_interactions (search_id);

CREATE INDEX IF NOT EXISTS idx_user_searches_analysis_id
    ON public.user_searches (analysis_id);


COMMIT;
