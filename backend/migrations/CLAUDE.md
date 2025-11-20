# Legacy Migrations

## ⚠️ BLOAT WARNING: Superseded by Supabase Migrations

This directory is **BLOAT** - it contains legacy SQL migration files that have been superseded by the Supabase migrations in `../supabase/migrations/`.

---

## Overview

This directory contains the original database migration files created before migrating to Supabase's migration system. These files are **outdated** and should not be used.

---

## Directory Structure

```
/backend/migrations/
├── 001_create_tables.sql         # ⚠️ OUTDATED schema (missing tables and columns)
└── 002_seed_knowledge_base.sql   # ⚠️ LEGACY seed data
```

---

## Evidence of Bloat

### Comparison with Active Migrations

**Legacy** (`./migrations/001_create_tables.sql`):
- Creates 8 tables
- Missing `toxic_substances` table
- Older column definitions
- Not aligned with current schema

**Active** (`../supabase/migrations/001_create_tables.sql`):
- Creates 9 tables (includes `toxic_substances`)
- Enhanced column definitions
- Current production schema
- Row Level Security policies

### Migration System Superseded

**Old System**: Manual SQL files in `./migrations/`
**New System**: Supabase CLI migrations in `../supabase/migrations/`

The Supabase system provides:
- Version control integration
- Automatic schema diffing
- Rollback capabilities
- RLS policy management

---

## Files Description

### 001_create_tables.sql
**Status**: ⚠️ **BLOAT - Outdated**

**Content**: SQL DDL for creating database tables

**Issues**:
- Missing `toxic_substances` table
- Older schema design
- Not used in production

### 002_seed_knowledge_base.sql
**Status**: ⚠️ **BLOAT - Legacy**

**Content**: INSERT statements for allergens and PFAS compounds

**Issues**:
- Superseded by `../supabase/migrations/002_seed_allergens_pfas.sql`
- Different data format
- Not used in production

---

## Correct Location for Migrations

Active migrations are in: **`../supabase/migrations/`**

See: [../supabase/migrations/CLAUDE.md](../supabase/migrations/CLAUDE.md)

---

## Related Documentation

- [Backend Overview](../CLAUDE.md) - Backend directory overview
- [Supabase Migrations](../supabase/migrations/CLAUDE.md) - **Active migration files**
- [Database Service](../src/infrastructure/CLAUDE.md) - Database client implementation

---

Last Updated: 2025-11-18
