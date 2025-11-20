# Supabase Database Reset Guide

**For**: Hosted Supabase (Cloud)
**Method**: SQL Script Execution
**Danger Level**: ⚠️ **DESTRUCTIVE** - All data will be lost!

---

## Overview

This guide walks you through completely dropping all tables in your hosted Supabase database and re-running migrations from scratch.

**When to use this**:
- Schema got messed up and you want a clean slate
- Migration files changed and you need to re-apply them
- Testing database setup process
- Preparing for a fresh deployment

**⚠️ WARNING**: This will **permanently delete ALL data** in your database. Only do this if you're okay losing all cached product analyses, user data, and knowledge base entries.

---

## Prerequisites

✅ Access to Supabase Dashboard (https://supabase.com/dashboard)
✅ Your Supabase project URL and credentials
✅ Backup of any critical data (if needed)

---

## Step-by-Step Instructions

### Step 1: Access Supabase SQL Editor

1. Go to https://supabase.com/dashboard
2. Select your project (the Eject project)
3. Click on **"SQL Editor"** in the left sidebar
4. Click **"New query"** button

---

### Step 2: Drop All Tables

1. Open the file: `backend/supabase/migrations/000_drop_all.sql`
2. Copy the entire contents
3. Paste into Supabase SQL Editor
4. Click **"Run"** button (or press Cmd/Ctrl + Enter)

**What this does**:
- Drops all 9 tables (users, product_analyses, allergens, pfas_compounds, etc.)
- Drops custom SQL functions (search_allergen, search_pfas)
- Uses CASCADE to handle foreign key dependencies
- Leaves uuid-ossp extension (commonly used, safe to keep)

**Expected output**:
```
DROP TABLE
DROP TABLE
DROP TABLE
...
(Multiple "DROP TABLE" messages)
```

**Verify tables are dropped**:
The script includes a verification query at the end. You should see:
- **0 rows returned** = Success! All tables dropped
- **Some rows returned** = Those tables still exist, may need manual intervention

---

### Step 3: Run Migration 001 - Create Tables

1. Open the file: `backend/supabase/migrations/001_create_tables.sql`
2. Copy the entire contents
3. Paste into Supabase SQL Editor (new query)
4. Click **"Run"**

**What this creates**:
- 9 tables: users, product_analyses, user_searches, allergens, pfas_compounds, toxic_substances, alternative_recommendations, user_interactions, analysis_feedback
- Indexes for fast lookups
- UUID extension

**Expected output**:
```
CREATE EXTENSION
CREATE TABLE
CREATE TABLE
...
CREATE INDEX
```

**Verify tables created**:
Go to **"Table Editor"** in left sidebar. You should see all 9 tables listed.

---

### Step 4: Run Migration 002 - Extend Product Analyses

1. Open the file: `backend/supabase/migrations/002_extend_product_analyses.sql`
2. Copy the entire contents
3. Paste into Supabase SQL Editor (new query)
4. Click **"Run"**

**What this does**:
- Adds additional columns to product_analyses table
- Adds indexes for performance

**Expected output**:
```
ALTER TABLE
CREATE INDEX
```

---

### Step 5: Run Migration 002 - Seed Allergens and PFAS

1. Open the file: `backend/supabase/migrations/002_seed_allergens_pfas.sql`
2. Copy the entire contents
3. Paste into Supabase SQL Editor (new query)
4. Click **"Run"**

**What this does**:
- Inserts 14 major allergens (peanuts, shellfish, milk, etc.)
- Inserts 8 PFAS compounds (PFOA, PFOS, GenX, etc.)

**Expected output**:
```
INSERT 0 14
INSERT 0 8
```

**Verify seed data**:
- Go to **"Table Editor"** → **allergens** → Should see 14 rows
- Go to **"Table Editor"** → **pfas_compounds** → Should see 8 rows

---

### Step 6: Run Migration 003 - Enable Row Level Security

1. Open the file: `backend/supabase/migrations/003_enable_rls.sql`
2. Copy the entire contents
3. Paste into Supabase SQL Editor (new query)
4. Click **"Run"**

**What this does**:
- Enables Row Level Security (RLS) on all tables
- Sets up policies for public read access (knowledge base)
- Sets up policies for authenticated access (user data)

**Expected output**:
```
ALTER TABLE
CREATE POLICY
CREATE POLICY
...
```

**Verify RLS enabled**:
- Go to **"Authentication"** → **"Policies"**
- You should see policies for allergens, pfas_compounds, product_analyses, etc.

---

### Step 7: Verify Database Setup

Run this verification query in SQL Editor:

```sql
-- Check all tables exist
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- Check allergen count
SELECT COUNT(*) as allergen_count FROM allergens;

-- Check PFAS count
SELECT COUNT(*) as pfas_count FROM pfas_compounds;

-- Check RLS is enabled
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND rowsecurity = true;
```

**Expected results**:
- **9 tables** listed (allergens, alternative_recommendations, analysis_feedback, pfas_compounds, product_analyses, toxic_substances, user_interactions, user_searches, users)
- **allergen_count**: 14
- **pfas_count**: 8
- **RLS enabled** on all 9 tables

---

## Alternative Method: Using psql Command Line

If you prefer command line (requires PostgreSQL client installed):

### 1. Get Database Connection String

1. Go to Supabase Dashboard → **"Settings"** → **"Database"**
2. Scroll to **"Connection string"** section
3. Copy the **"Connection string"** (URI format)
4. Replace `[YOUR-PASSWORD]` with your actual database password

**Format**:
```
postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### 2. Run Migrations via psql

```bash
# Navigate to your project
cd /Users/arshveergahir/Desktop/GitHub\ Repos/Eject/backend

# Drop all tables
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres" \
  -f supabase/migrations/000_drop_all.sql

# Run migration 001
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres" \
  -f supabase/migrations/001_create_tables.sql

# Run migration 002 (extend)
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres" \
  -f supabase/migrations/002_extend_product_analyses.sql

# Run migration 002 (seed)
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres" \
  -f supabase/migrations/002_seed_allergens_pfas.sql

# Run migration 003 (RLS)
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres" \
  -f supabase/migrations/003_enable_rls.sql
```

---

## Using Supabase CLI (Recommended for Future)

If you want to use Supabase CLI for easier migration management:

### 1. Install Supabase CLI

```bash
# macOS
brew install supabase/tap/supabase

# Or npm
npm install -g supabase
```

### 2. Link Your Project

```bash
cd /Users/arshveergahir/Desktop/GitHub\ Repos/Eject/backend

# Login to Supabase
supabase login

# Link to your project
supabase link --project-ref [YOUR-PROJECT-REF]
```

### 3. Reset Database

```bash
# This will drop ALL data and re-run migrations
supabase db reset --linked
```

**Advantage**: Supabase CLI tracks which migrations have been run and only applies new ones.

---

## Troubleshooting

### Error: "table does not exist"
**Solution**: Ignore this during drop phase - it means table was already dropped or never existed

### Error: "relation already exists"
**Solution**: Tables weren't fully dropped. Re-run `000_drop_all.sql`

### Error: "permission denied"
**Solution**: Make sure you're connected as the `postgres` user (superuser)

### Error: "foreign key constraint violation"
**Solution**: The `CASCADE` in drop statements should handle this. If not, manually drop tables in reverse order:
1. analysis_feedback
2. user_interactions
3. alternative_recommendations
4. user_searches
5. product_analyses
6. toxic_substances
7. pfas_compounds
8. allergens
9. users

### Seed data not appearing
**Solution**: Check that migration 001 completed successfully. Seed migration depends on tables existing.

---

## Post-Reset Checklist

After resetting database:

- [ ] All 9 tables created successfully
- [ ] 14 allergens seeded
- [ ] 8 PFAS compounds seeded
- [ ] RLS enabled on all tables
- [ ] Backend API can connect to database
- [ ] Test product analysis endpoint: `POST /api/analyze`
- [ ] Verify caching works (run same analysis twice)

---

## Files Created

This guide references these files:

1. ✅ `backend/supabase/migrations/000_drop_all.sql` - **NEW** - Drops all tables
2. ✅ `backend/supabase/migrations/001_create_tables.sql` - Creates schema
3. ✅ `backend/supabase/migrations/002_extend_product_analyses.sql` - Extends tables
4. ✅ `backend/supabase/migrations/002_seed_allergens_pfas.sql` - Seeds data
5. ✅ `backend/supabase/migrations/003_enable_rls.sql` - Security policies

---

## Migration Order Summary

```
000_drop_all.sql              ← Drop everything (DESTRUCTIVE)
    ↓
001_create_tables.sql         ← Create all 9 tables
    ↓
002_extend_product_analyses.sql ← Add extra columns
    ↓
002_seed_allergens_pfas.sql   ← Insert knowledge base data
    ↓
003_enable_rls.sql            ← Enable security policies
```

**Total time**: ~2-5 minutes (depending on dashboard loading)

---

## Safety Tips

1. **Backup First**: If you have any critical data, export tables before dropping
2. **Test Environment**: Try this on a test/staging project first
3. **Double Check**: Make sure you're in the correct Supabase project
4. **Version Control**: All migration files are in git, so you can always recover
5. **Read Output**: Check SQL output for errors after each migration

---

## Need Help?

- **Supabase Docs**: https://supabase.com/docs/guides/database
- **SQL Editor Guide**: https://supabase.com/docs/guides/database/sql-editor
- **Migrations Guide**: https://supabase.com/docs/guides/cli/local-development#database-migrations

---

**Created**: 2025-11-19
**For**: Eject Project - Hosted Supabase Database Reset
