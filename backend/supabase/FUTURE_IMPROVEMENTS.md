# Supabase Database - Future Improvements

## Overview

This document tracks potential database optimizations and enhancements for future implementation when scale requires them.

---

## 1. Fuzzy Matching with pg_trgm Extension

### Current State

**Matching Strategy**: Python-level fuzzy matching in `backend/src/domain/ingredient_matcher.py`
- Uses `difflib.SequenceMatcher` for similarity scoring
- Runs in application memory (not database)
- Works well for current scale (~14 allergens, ~8 PFAS compounds)

**Database Indexes**: Standard B-tree indexes only
- `idx_allergen_name` on `allergens(name)`
- `idx_pfas_name` on `pfas_compounds(name)`
- `idx_toxic_name` on `toxic_substances(name)`
- Support exact matches only

### Problem

As database grows (1000+ compounds), Python fuzzy matching will become slow:
- Must load entire database into memory
- O(n*m) comparison (n ingredients × m database entries)
- No index support = full table scan every time

### Solution: PostgreSQL Trigram Matching

**Enable pg_trgm extension** for fuzzy string matching at database level:

```sql
-- Migration: 004_add_fuzzy_matching.sql

-- Enable PostgreSQL trigram extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Add GIN indexes for trigram-based fuzzy matching
CREATE INDEX allergens_name_trgm_idx ON allergens USING GIN (name gin_trgm_ops);
CREATE INDEX allergens_synonyms_trgm_idx ON allergens USING GIN (array_to_string(synonyms, ' ') gin_trgm_ops);
CREATE INDEX allergens_alt_names_trgm_idx ON allergens USING GIN (array_to_string(alternative_names, ' ') gin_trgm_ops);

CREATE INDEX pfas_name_trgm_idx ON pfas_compounds USING GIN (name gin_trgm_ops);
CREATE INDEX pfas_common_name_trgm_idx ON pfas_compounds USING GIN (common_name gin_trgm_ops);
CREATE INDEX pfas_synonyms_trgm_idx ON pfas_compounds USING GIN (array_to_string(synonyms, ' ') gin_trgm_ops);

CREATE INDEX toxic_name_trgm_idx ON toxic_substances USING GIN (name gin_trgm_ops);
CREATE INDEX toxic_common_names_trgm_idx ON toxic_substances USING GIN (array_to_string(common_names, ' ') gin_trgm_ops);
CREATE INDEX toxic_synonyms_trgm_idx ON toxic_substances USING GIN (array_to_string(synonyms, ' ') gin_trgm_ops);

-- Set threshold for similarity matching (0.3 = 30% similar)
ALTER DATABASE postgres SET pg_trgm.similarity_threshold = 0.3;
```

### Benefits

1. **Performance**: O(log n) lookup instead of O(n*m)
2. **Accuracy**: PostgreSQL trigram matching is highly optimized
3. **Scalability**: Handles 10,000+ compounds efficiently
4. **Query Simplicity**: Use `%` operator for fuzzy matching

### Usage Example

**Current (Python)**:
```python
# Load all 1000 allergens, compare in Python
allergen_db = await db.get_all_allergens()
for ingredient in ingredients:
    for allergen in allergen_db:
        similarity = SequenceMatcher(None, ingredient, allergen['name']).ratio()
        if similarity > 0.75:
            matches.append(allergen)
```

**Future (PostgreSQL)**:
```python
# Database does fuzzy matching with index
matches = await db.fuzzy_search_allergens(ingredient)

# SQL query:
# SELECT *, similarity(name, $1) as score
# FROM allergens
# WHERE name % $1  -- Uses GIN index
# ORDER BY score DESC
# LIMIT 10
```

### Implementation Trigger

Implement when:
- Allergen database > 100 entries
- PFAS database > 50 entries
- Query latency > 200ms
- Memory usage concerns

### Estimated Impact

- **Query time**: 500ms → 50ms (10x faster)
- **Memory usage**: 100MB → 10MB (10x reduction)
- **Scalability**: Supports 10,000+ compounds

---

## 2. Full-Text Search for Ingredient Analysis

### Current State

**Search Strategy**: Substring matching with `LIKE` or `ILIKE`
- No ranking or relevance scoring
- Case-insensitive but slow
- No support for multi-word queries

### Problem

Users search for complex ingredient names:
- "sodium lauryl sulfate" vs "sodium laureth sulfate" (different chemicals!)
- "BPA free" vs "bisphenol A" (same thing)
- Typos: "parabens" vs "paraben" vs "paraben free"

### Solution: PostgreSQL Full-Text Search

```sql
-- Migration: 005_add_full_text_search.sql

-- Add tsvector columns for full-text search
ALTER TABLE allergens ADD COLUMN search_vector tsvector;
ALTER TABLE pfas_compounds ADD COLUMN search_vector tsvector;
ALTER TABLE toxic_substances ADD COLUMN search_vector tsvector;

-- Populate search vectors
UPDATE allergens SET search_vector =
  to_tsvector('english',
    COALESCE(name, '') || ' ' ||
    COALESCE(array_to_string(synonyms, ' '), '') || ' ' ||
    COALESCE(array_to_string(alternative_names, ' '), '')
  );

UPDATE pfas_compounds SET search_vector =
  to_tsvector('english',
    COALESCE(name, '') || ' ' ||
    COALESCE(common_name, '') || ' ' ||
    COALESCE(array_to_string(synonyms, ' '), '')
  );

UPDATE toxic_substances SET search_vector =
  to_tsvector('english',
    COALESCE(name, '') || ' ' ||
    COALESCE(array_to_string(common_names, ' '), '') || ' ' ||
    COALESCE(array_to_string(synonyms, ' '), '')
  );

-- Create GIN indexes for fast full-text search
CREATE INDEX allergens_search_idx ON allergens USING GIN (search_vector);
CREATE INDEX pfas_search_idx ON pfas_compounds USING GIN (search_vector);
CREATE INDEX toxic_search_idx ON toxic_substances USING GIN (search_vector);

-- Auto-update search vectors on insert/update
CREATE FUNCTION allergens_search_trigger() RETURNS trigger AS $$
BEGIN
  NEW.search_vector := to_tsvector('english',
    COALESCE(NEW.name, '') || ' ' ||
    COALESCE(array_to_string(NEW.synonyms, ' '), '') || ' ' ||
    COALESCE(array_to_string(NEW.alternative_names, ' '), '')
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER allergens_search_update BEFORE INSERT OR UPDATE
  ON allergens FOR EACH ROW EXECUTE FUNCTION allergens_search_trigger();

-- Similar triggers for pfas_compounds and toxic_substances
```

### Benefits

1. **Ranking**: Results ranked by relevance (ts_rank)
2. **Multi-word**: Handles "sodium lauryl sulfate" correctly
3. **Stemming**: "paraben" matches "parabens" automatically
4. **Performance**: GIN index = O(log n) lookups

### Usage Example

```sql
-- Search for "BPA" - matches "bisphenol A", "BPA", "bis-phenol A"
SELECT name, ts_rank(search_vector, query) as rank
FROM toxic_substances, to_tsquery('english', 'BPA') query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 10;
```

---

## 3. Materialized View for Ingredient Statistics

### Current State

**Analytics**: No aggregated statistics
- Can't see "most common allergens detected"
- Can't track "frequently found PFAS compounds"
- No trending analysis

### Problem

Running aggregate queries on `product_analyses` table is expensive:
- JSONB parsing for every row
- No caching of common queries
- Slow for analytics dashboard

### Solution: Materialized View

```sql
-- Migration: 006_add_statistics_views.sql

-- Materialized view for allergen detection frequency
CREATE MATERIALIZED VIEW allergen_statistics AS
SELECT
  a.name,
  COUNT(DISTINCT pa.id) as detection_count,
  AVG((pa.confidence * 100)::INTEGER) as avg_confidence,
  MAX(pa.analyzed_at) as last_detected
FROM allergens a
LEFT JOIN product_analyses pa ON pa.allergens_detected @> jsonb_build_array(jsonb_build_object('name', a.name))
GROUP BY a.name
ORDER BY detection_count DESC;

-- Materialized view for PFAS detection frequency
CREATE MATERIALIZED VIEW pfas_statistics AS
SELECT
  p.name,
  p.cas_number,
  COUNT(DISTINCT pa.id) as detection_count,
  AVG((pa.confidence * 100)::INTEGER) as avg_confidence,
  MAX(pa.analyzed_at) as last_detected
FROM pfas_compounds p
LEFT JOIN product_analyses pa ON pa.pfas_detected @> jsonb_build_array(jsonb_build_object('name', p.name))
GROUP BY p.name, p.cas_number
ORDER BY detection_count DESC;

-- Indexes on materialized views
CREATE INDEX allergen_stats_count_idx ON allergen_statistics(detection_count DESC);
CREATE INDEX pfas_stats_count_idx ON pfas_statistics(detection_count DESC);

-- Refresh function (call periodically via cron)
CREATE OR REPLACE FUNCTION refresh_statistics() RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY allergen_statistics;
  REFRESH MATERIALIZED VIEW CONCURRENTLY pfas_statistics;
END;
$$ LANGUAGE plpgsql;
```

### Benefits

1. **Fast Analytics**: Pre-computed statistics
2. **Dashboard Ready**: No heavy queries on main tables
3. **Historical Trends**: Track detection patterns over time

### Refresh Strategy

```sql
-- Refresh every hour via pg_cron
SELECT cron.schedule('refresh-stats', '0 * * * *', 'SELECT refresh_statistics()');
```

---

## 4. Partitioning for product_analyses Table

### Current State

**Table Size**: Single table for all analyses
- Will grow unbounded over time
- Slow queries as table grows
- Difficult to archive old data

### Problem

After 1 year of operation:
- 1M+ product analyses
- 10GB+ table size
- Query performance degrades
- Backup/restore becomes slow

### Solution: Time-Based Partitioning

```sql
-- Migration: 007_partition_product_analyses.sql

-- Convert product_analyses to partitioned table
ALTER TABLE product_analyses RENAME TO product_analyses_old;

CREATE TABLE product_analyses (
  id UUID DEFAULT gen_random_uuid(),
  product_url TEXT NOT NULL,
  product_url_hash TEXT NOT NULL,
  product_name TEXT,
  brand TEXT,
  overall_score INTEGER,
  allergens_detected JSONB DEFAULT '[]'::jsonb,
  pfas_detected JSONB DEFAULT '[]'::jsonb,
  other_concerns JSONB DEFAULT '[]'::jsonb,
  confidence INTEGER,
  analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (analyzed_at);

-- Create partitions for each month
CREATE TABLE product_analyses_2025_01 PARTITION OF product_analyses
  FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE product_analyses_2025_02 PARTITION OF product_analyses
  FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Auto-create future partitions (via pg_partman or custom function)
CREATE OR REPLACE FUNCTION create_monthly_partitions() RETURNS void AS $$
DECLARE
  start_date DATE;
  end_date DATE;
  partition_name TEXT;
BEGIN
  FOR i IN 0..11 LOOP
    start_date := date_trunc('month', CURRENT_DATE + (i || ' months')::INTERVAL);
    end_date := start_date + '1 month'::INTERVAL;
    partition_name := 'product_analyses_' || to_char(start_date, 'YYYY_MM');

    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS %I PARTITION OF product_analyses FOR VALUES FROM (%L) TO (%L)',
      partition_name, start_date, end_date
    );
  END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Schedule monthly partition creation
SELECT cron.schedule('create-partitions', '0 0 1 * *', 'SELECT create_monthly_partitions()');

-- Migrate old data
INSERT INTO product_analyses SELECT * FROM product_analyses_old;
DROP TABLE product_analyses_old;
```

### Benefits

1. **Query Performance**: Partition pruning = faster queries
2. **Archive Strategy**: Drop old partitions easily
3. **Maintenance**: Vacuum/analyze per partition (faster)
4. **Backup/Restore**: Partition-level backups

### Partition Retention Policy

```sql
-- Drop partitions older than 2 years
CREATE OR REPLACE FUNCTION drop_old_partitions() RETURNS void AS $$
DECLARE
  partition_name TEXT;
BEGIN
  FOR partition_name IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename LIKE 'product_analyses_%'
    AND tablename < 'product_analyses_' || to_char(CURRENT_DATE - '2 years'::INTERVAL, 'YYYY_MM')
  LOOP
    EXECUTE 'DROP TABLE IF EXISTS ' || partition_name;
  END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Run monthly
SELECT cron.schedule('drop-old-partitions', '0 0 1 * *', 'SELECT drop_old_partitions()');
```

---

## 5. JSONB Indexing for Nested Queries

### Current State

**JSONB Columns**: `allergens_detected`, `pfas_detected`, `other_concerns`
- No indexes on JSONB content
- Full scan for queries like "find all products with peanuts"

### Problem

Queries filtering by allergen/PFAS name are slow:

```sql
-- Slow query (full table scan)
SELECT * FROM product_analyses
WHERE allergens_detected @> '[{"name": "Peanuts"}]';
```

### Solution: GIN Indexes on JSONB

```sql
-- Migration: 008_add_jsonb_indexes.sql

-- Create GIN indexes for containment queries (@>)
CREATE INDEX allergens_detected_gin_idx ON product_analyses USING GIN (allergens_detected jsonb_path_ops);
CREATE INDEX pfas_detected_gin_idx ON product_analyses USING GIN (pfas_detected jsonb_path_ops);
CREATE INDEX other_concerns_gin_idx ON product_analyses USING GIN (other_concerns jsonb_path_ops);

-- Create indexes for specific JSONB paths
CREATE INDEX allergens_name_idx ON product_analyses USING GIN ((allergens_detected -> 'name'));
CREATE INDEX pfas_name_idx ON product_analyses USING GIN ((pfas_detected -> 'name'));
```

### Benefits

1. **Fast JSONB Queries**: O(log n) instead of O(n)
2. **Containment Checks**: `@>` operator uses index
3. **Path Queries**: Directly query nested JSON fields

### Usage Example

```sql
-- Fast query (uses GIN index)
SELECT product_name, brand, analyzed_at
FROM product_analyses
WHERE allergens_detected @> '[{"name": "Peanuts"}]'
ORDER BY analyzed_at DESC
LIMIT 100;
```

---

## Implementation Priority

| Priority | Feature | Trigger | Estimated Effort |
|----------|---------|---------|------------------|
| **High** | Fuzzy Matching (pg_trgm) | > 100 compounds | 2 hours |
| **Medium** | JSONB Indexes | > 10,000 analyses | 1 hour |
| **Medium** | Full-Text Search | User feature request | 4 hours |
| **Low** | Materialized Views | Analytics dashboard | 3 hours |
| **Low** | Table Partitioning | > 1M analyses | 6 hours |

---

## Monitoring Triggers

Set up alerts to know when to implement these improvements:

```sql
-- Query to check database size
SELECT
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Query to check row counts
SELECT
  'allergens' as table_name, COUNT(*) as row_count FROM allergens
UNION ALL
SELECT 'pfas_compounds', COUNT(*) FROM pfas_compounds
UNION ALL
SELECT 'toxic_substances', COUNT(*) FROM toxic_substances
UNION ALL
SELECT 'product_analyses', COUNT(*) FROM product_analyses;

-- Query to check average query time
SELECT
  query,
  calls,
  mean_exec_time,
  max_exec_time
FROM pg_stat_statements
WHERE query LIKE '%product_analyses%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

## Notes

- All improvements are **backwards compatible** - existing code will continue to work
- Migrations can be applied incrementally without downtime
- GIN indexes add ~30% storage overhead but provide 10-100x query speedup
- Test migrations on staging database before production deployment

---

Last Updated: 2025-11-19
