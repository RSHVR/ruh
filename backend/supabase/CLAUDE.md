# Supabase Database

## Overview

Supabase PostgreSQL database configuration and migrations for the Eject backend. Manages product analyses cache, user tracking, allergen/PFAS knowledge base, and analytics.

---

## Database Schema Overview

### Tables (9 total)

**Core Tables**:
1. `product_analyses` - Cached product analysis results (permanent storage)
2. `allergens` - Allergen knowledge base
3. `pfas_compounds` - PFAS chemical compounds with health effects
4. `toxic_substances` - Other harmful substances database

**User Tracking**:
5. `users` - Anonymous user tracking (UUID, no PII)
6. `user_searches` - Search history (90-day TTL)
7. `user_interactions` - Click/purchase tracking

**Features**:
8. `alternative_recommendations` - Safer product alternatives
9. `analysis_feedback` - User feedback on analyses

---

## Directory Structure

```
/backend/supabase/
├── README.md              # Supabase setup documentation
└── migrations/            # SQL migration files → [migrations/CLAUDE.md](./migrations/CLAUDE.md)
    ├── 001_create_tables.sql           # Create all 9 tables
    ├── 002_extend_product_analyses.sql # Add columns to product_analyses
    ├── 002_seed_allergens_pfas.sql     # Seed allergen and PFAS data
    └── 003_enable_rls.sql              # Enable Row Level Security policies
```

---

## Database Architecture

### Caching Strategy

**product_analyses table**:
- Permanent storage (no automatic expiration)
- Keyed by `url_hash` (SHA256 of product URL)
- Upsert on new analyses (updates if URL exists)
- Enables instant responses for repeated requests

**Why permanent?**:
- Product formulations change infrequently
- Analysis is expensive (AI API costs)
- Cache hit rate improves over time
- Manual purge available if needed

### Privacy Design

**users table**:
- Stores UUID only (generated client-side)
- No PII (name, email, IP address)
- Enables analytics without compromising privacy

**user_searches table**:
- 90-day TTL (automatic cleanup)
- Links to user UUID
- Tracks search patterns for improvements

### Knowledge Base

**allergens table**:
- Common allergens (peanuts, shellfish, etc.)
- Severity levels (low, moderate, high)
- Health effects descriptions

**pfas_compounds table**:
- Known PFAS chemicals (PFOA, PFOS, GenX, etc.)
- Health effects and regulatory status
- Used by Claude for detection

**toxic_substances table**:
- Other harmful chemicals
- Toxicity levels
- Regulatory information

---

## Row Level Security (RLS)

**Enabled in**: `migrations/003_enable_rls.sql`

**Policies**:
- Public read access to knowledge base (allergens, pfas_compounds)
- Authenticated write access for analyses
- User-scoped access for user_searches and interactions

**Benefits**:
- Security by default
- API key enforcement at database level
- Prevents unauthorized data access

---

## File-Level Relationships

```
supabase/
  └── migrations/
       ├─ 001_create_tables.sql       (creates schema)
       ├─ 002_extend_product_analyses.sql (adds columns)
       ├─ 002_seed_allergens_pfas.sql (populates knowledge base)
       └─ 003_enable_rls.sql          (security policies)

Used by:
  - src/infrastructure/database.py (Supabase client)
  - src/api/routes/analyze.py (via database.py)
```

---

## Connection Details

**Environment Variables** (in `.env`):
- `SUPABASE_URL` - Project URL (e.g., `https://xxx.supabase.co`)
- `SUPABASE_KEY` - Service role key or anon key

**Client Initialization** (in `src/infrastructure/database.py`):
```python
from supabase import create_client
client = create_client(settings.supabase_url, settings.supabase_key)
```

---

## Migration Management

### Running Migrations

**Using Supabase CLI**:
```bash
supabase db push
```

**Manual execution**:
```bash
psql $DATABASE_URL -f migrations/001_create_tables.sql
psql $DATABASE_URL -f migrations/002_extend_product_analyses.sql
psql $DATABASE_URL -f migrations/002_seed_allergens_pfas.sql
psql $DATABASE_URL -f migrations/003_enable_rls.sql
```

### Migration Order

1. `001_create_tables.sql` - Must run first (creates all tables)
2. `002_extend_product_analyses.sql` - Extends product_analyses table
3. `002_seed_allergens_pfas.sql` - Populates knowledge base
4. `003_enable_rls.sql` - Enables security policies

---

## Related Documentation

- [Backend Overview](../CLAUDE.md) - Backend directory overview
- [Migrations](./migrations/CLAUDE.md) - Detailed migration file documentation
- [Database Service](../src/infrastructure/CLAUDE.md) - Database client implementation
- [Legacy Migrations](../migrations/CLAUDE.md) - **Deprecated** old migrations

---

Last Updated: 2025-11-18
