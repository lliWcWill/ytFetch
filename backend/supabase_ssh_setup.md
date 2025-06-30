# Supabase Database Connection Guide

## Option 1: Direct psql Connection

1. **Get your database credentials** from Supabase Dashboard:
   - Go to Settings → Database
   - Look for "Connection string" section
   - You'll see something like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```

2. **Connect using psql**:
   ```bash
   psql "postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require"
   ```

3. **Run the schema**:
   ```bash
   # Once connected, run:
   \i /path/to/complete_schema_setup.sql
   
   # Or copy/paste the SQL directly
   ```

## Option 2: Using Supabase CLI

1. **Install Supabase CLI**:
   ```bash
   npm install -g supabase
   ```

2. **Login and link project**:
   ```bash
   supabase login
   supabase link --project-ref [YOUR-PROJECT-REF]
   ```

3. **Run migrations**:
   ```bash
   supabase db push complete_schema_setup.sql
   ```

## Checking What's Already There

Once connected, run these commands:

```sql
-- List all tables
\dt

-- See table details
\d user_profiles
\d bulk_jobs
\d user_token_balances

-- Check if tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```

## Your Current Setup

Based on what you sent, you have:
- ✅ `user_tiers` table (for free/pro/enterprise)
- ✅ `bulk_jobs` table
- ✅ `video_tasks` table
- ✅ `processing_logs` table

You still need:
- ❌ `user_profiles` table
- ❌ `user_token_balances` table  
- ❌ `token_transactions` table
- ❌ `guest_usage` table
- ❌ `guest_limits` table

The `complete_schema_setup.sql` will add these missing tables without affecting your existing ones.