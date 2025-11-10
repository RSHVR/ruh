# Eject Supabase Database Setup

This directory contains the database schema and migrations for the Eject product safety analysis platform.

## Database Schema Overview

### Core Tables

1. **users** - Anonymous user tracking (no PII)
2. **product_analyses** - Cached AI product safety analyses
3. **user_searches** - User search history (90-day TTL)
4. **alternative_recommendations** - AI-recommended safer alternatives
5. **user_interactions** - Click/purchase tracking for optimization
6. **analysis_feedback** - User ratings on analysis quality
7. **allergens** - Knowledge base of common allergens
8. **pfas_compounds** - PFAS compounds database

## Running Migrations

### Option 1: Using Supabase CLI

1. Install Supabase CLI:
```bash
npm install -g supabase
```

2. Link to your project:
```bash
supabase link --project-ref vslnwiugfuvquiaafxgh
```

3. Run migrations:
```bash
supabase db push
```

### Option 2: Using Supabase Dashboard

1. Go to https://vslnwiugfuvquiaafxgh.supabase.co/project/vslnwiugfuvquiaafxgh/editor
2. Click on "SQL Editor"
3. Copy and paste the contents of each migration file in order:
   - `001_create_tables.sql`
   - `002_seed_allergens_pfas.sql`
4. Click "Run" for each migration

### Option 3: Using psql

```bash
psql postgresql://postgres:[YOUR-PASSWORD]@db.vslnwiugfuvquiaafxgh.supabase.co:5432/postgres \
  -f migrations/001_create_tables.sql

psql postgresql://postgres:[YOUR-PASSWORD]@db.vslnwiugfuvquiaafxgh.supabase.co:5432/postgres \
  -f migrations/002_seed_allergens_pfas.sql
```

## Verification

After running migrations, verify the setup:

```sql
-- Check tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public';

-- Check allergen count (should be 16)
SELECT COUNT(*) FROM allergens;

-- Check PFAS compound count (should be 8)
SELECT COUNT(*) FROM pfas_compounds;

-- Test allergen search function
SELECT * FROM search_allergen('milk');

-- Test PFAS search function
SELECT * FROM search_pfas('PFOA');
```

## Database Functions

### `search_allergen(search_term TEXT)`
Searches allergens by name or synonym. Returns matching allergens with severity scores.

**Example:**
```sql
SELECT * FROM search_allergen('dairy');  -- Returns 'Milk' allergen
SELECT * FROM search_allergen('gluten'); -- Returns 'Wheat' allergen
```

### `search_pfas(search_term TEXT)`
Searches PFAS compounds by name, CAS number, or synonym. Returns compound details with health effects.

**Example:**
```sql
SELECT * FROM search_pfas('PFOA');      -- Returns PFOA details
SELECT * FROM search_pfas('335-67-1');  -- Search by CAS number
SELECT * FROM search_pfas('teflon');    -- Search by synonym
```

## Environment Setup

Update your backend `.env` or Secret Manager with:

```bash
SUPABASE_URL=https://vslnwiugfuvquiaafxgh.supabase.co
SUPABASE_KEY=<your-anon-key>  # Get from Supabase dashboard
```

## Privacy & Data Retention

- **User data**: Auto-delete after 90 days (GDPR compliant)
- **Product analyses**: Permanent (de-anonymized, no user linkage)
- **No PII**: Users tracked only by anonymous UUID
- **Consent required**: For any data sharing or analytics

## Next Steps

After running migrations:

1. ✅ Run setup-secrets.sh to add Supabase API key to Secret Manager
2. ✅ Deploy backend with updated secrets
3. ✅ Test API with `/api/analyze` endpoint
4. ✅ Verify database queries work correctly

## Troubleshooting

**Error: "relation already exists"**
- Tables already created. Use `DROP TABLE` carefully or create new migration to alter existing tables.

**Error: "function search_allergen does not exist"**
- Run migration 002 which creates the search functions.

**Can't connect to database**
- Verify your Supabase project is active
- Check your connection string and credentials
- Ensure your IP is allowed (Supabase allows all by default)

## Schema Diagram

```
users
  ↓
user_searches → product_analyses → alternative_recommendations
  ↓                                        ↓
user_interactions                   user_interactions
  ↓
analysis_feedback

allergens (knowledge base)
pfas_compounds (knowledge base)
```
