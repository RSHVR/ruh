# Supabase Migrations

## Overview

SQL migration files for Supabase PostgreSQL database schema and seed data. These are the **active** migration files used in production (not the legacy files in `../../migrations/`).

---

## Migration Files

### 001_create_tables.sql
**Purpose**: Create all database tables (9 tables)

**Tables Created**:
1. `product_analyses` - Product analysis cache
2. `users` - Anonymous user tracking
3. `user_searches` - Search history
4. `allergens` - Allergen knowledge base
5. `pfas_compounds` - PFAS chemicals database
6. `toxic_substances` - Other harmful substances
7. `alternative_recommendations` - Safer product suggestions
8. `user_interactions` - Click/purchase tracking
9. `analysis_feedback` - User feedback

**Key Features**:
- UUID primary keys
- Timestamp columns (created_at, updated_at)
- Foreign key relationships
- JSON columns for complex data
- Text search indexes

### 002_extend_product_analyses.sql
**Purpose**: Extend product_analyses table with additional columns

**Columns Added**:
- Additional metadata fields
- Enhanced analysis data storage
- Performance optimization indexes

**Why separate migration?**:
- Schema evolution after initial deployment
- Keeps 001 migration clean and simple
- Allows incremental schema updates

### 002_seed_allergens_pfas.sql
**Purpose**: Populate allergen and PFAS knowledge base

**Data Seeded**:

**Allergens** (14 major allergens):
- Peanuts (high severity)
- Tree nuts (high severity)
- Shellfish (high severity)
- Fish (high severity)
- Milk (moderate severity)
- Eggs (moderate severity)
- Wheat/Gluten (moderate severity)
- Soy (moderate severity)
- Sesame (moderate severity)
- Sulfites (moderate severity)
- And others...

**PFAS Compounds** (8 major compounds):
- PFOA (Perfluorooctanoic acid) - Health effects: liver damage, cancer risk
- PFOS (Perfluorooctanesulfonic acid) - Health effects: immune system, thyroid
- GenX (replacement PFAS) - Health effects: similar to PFOA
- PFNA, PFBS, PFHxS, etc.

**Why seed data?**:
- Claude uses this knowledge base for detection
- Provides consistency in analysis
- Reference data for harm score calculation

### 003_enable_rls.sql
**Purpose**: Enable Row Level Security policies

**Policies Enabled**:

**Public read access**:
- `allergens` - Anyone can read allergen data
- `pfas_compounds` - Anyone can read PFAS data
- `toxic_substances` - Anyone can read substance data

**Authenticated access**:
- `product_analyses` - API key required for write
- `user_searches` - User-scoped access
- `user_interactions` - User-scoped access
- `analysis_feedback` - User-scoped access

**Security Benefits**:
- Database-level authorization
- Prevents unauthorized writes
- Row-level access control for user data
- Public knowledge base, private user data

---

## SQL Schema Highlights

### product_analyses Table

```sql
CREATE TABLE product_analyses (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  url_hash VARCHAR(64) UNIQUE NOT NULL,
  product_url TEXT NOT NULL,
  product_name TEXT,
  brand TEXT,
  retailer TEXT,
  overall_score INTEGER,
  allergens_detected JSONB,
  pfas_detected JSONB,
  other_concerns JSONB,
  confidence FLOAT,
  analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_url_hash ON product_analyses(url_hash);
CREATE INDEX idx_analyzed_at ON product_analyses(analyzed_at);
```

**Key Design Decisions**:
- `url_hash` - Unique index for fast cache lookups
- `JSONB` - Flexible storage for arrays of allergens/PFAS
- `confidence` - Float (0.0-1.0) for analysis quality
- `analyzed_at` - Separate from `created_at` for re-analysis tracking

### allergens Table

```sql
CREATE TABLE allergens (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(100) UNIQUE NOT NULL,
  severity VARCHAR(20) CHECK (severity IN ('low', 'moderate', 'high')),
  description TEXT,
  health_effects TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Severity Levels**:
- `low` - Minor reactions (5 points)
- `moderate` - Common allergens (15 points)
- `high` - Severe/anaphylactic risk (30 points)

### pfas_compounds Table

```sql
CREATE TABLE pfas_compounds (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(100) UNIQUE NOT NULL,
  chemical_formula VARCHAR(50),
  health_effects TEXT,
  regulatory_status TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**All PFAS score**: 40 points (consistently high harm)

---

## Migration Execution Order

```
1. 001_create_tables.sql          (creates schema)
    ↓
2. 002_extend_product_analyses.sql (adds columns)
    ↓
3. 002_seed_allergens_pfas.sql    (populates data)
    ↓
4. 003_enable_rls.sql             (security policies)
```

**Critical**: Must run in this exact order.

---

## File-Level Relationships

```
migrations/
  ├─ 001_create_tables.sql
  ├─ 002_extend_product_analyses.sql
  ├─ 002_seed_allergens_pfas.sql
  └─ 003_enable_rls.sql

Applied to:
  - Supabase PostgreSQL database

Used by:
  - src/infrastructure/database.py (queries tables)
  - src/domain/harm_calculator.py (uses allergen severity)
  - src/infrastructure/claude_agent.py (references PFAS knowledge)
```

---

## Differences from Legacy Migrations

**Legacy** (`../../migrations/`):
- 2 files
- 8 tables (missing `toxic_substances`)
- Older schema design
- No RLS policies
- Different seed data format

**Current** (`./`):
- 4 files
- 9 tables (comprehensive)
- Enhanced schema with indexes
- RLS security enabled
- Production-ready seed data

**Status**: Legacy migrations are **BLOAT** and should not be used.

---

## Related Documentation

- [Supabase Directory](../CLAUDE.md) - Parent directory overview
- [Database Service](../../src/infrastructure/CLAUDE.md) - Client implementation
- [Legacy Migrations](../../migrations/CLAUDE.md) - **Deprecated** old files

---

Last Updated: 2025-11-18
