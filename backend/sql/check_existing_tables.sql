-- Check what tables already exist in your database
SELECT 
    schemaname,
    tablename 
FROM 
    pg_tables 
WHERE 
    schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY 
    schemaname, 
    tablename;

-- Check if specific tables we need exist
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'user_profiles'
) as user_profiles_exists,
EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'user_token_balances'
) as token_balances_exists,
EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'bulk_jobs'
) as bulk_jobs_exists,
EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'guest_usage'
) as guest_usage_exists;