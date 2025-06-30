-- Diagnostic script to identify why guest usage API returns null limits

-- 1. Check if guest_limits table exists and has data
SELECT 'Checking guest_limits table...' as step;
SELECT COUNT(*) as guest_limits_count, 
       COUNT(*) FILTER (WHERE limit_type = 'unofficial_transcriptions') as unofficial_count,
       COUNT(*) FILTER (WHERE limit_type = 'groq_transcriptions') as groq_count,
       COUNT(*) FILTER (WHERE limit_type = 'bulk_videos') as bulk_count
FROM guest_limits;

-- 2. Show the actual guest_limits data
SELECT 'Guest limits data:' as step;
SELECT * FROM guest_limits ORDER BY limit_type;

-- 3. Test the database function directly
SELECT 'Testing get_guest_usage_summary function...' as step;
SELECT * FROM get_guest_usage_summary('test-session-123');

-- 4. Check if there are any RLS policies on guest_limits
SELECT 'Checking RLS policies on guest_limits...' as step;
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies 
WHERE tablename = 'guest_limits';

-- 5. Check table permissions
SELECT 'Checking table permissions...' as step;
SELECT 
    grantee, 
    privilege_type 
FROM information_schema.role_table_grants 
WHERE table_name = 'guest_limits';

-- 6. Test individual subqueries from the function
SELECT 'Testing individual limit queries...' as step;
SELECT 
    'unofficial' as type,
    (SELECT limit_value FROM guest_limits WHERE limit_type = 'unofficial_transcriptions') as limit_value
UNION ALL
SELECT 
    'groq' as type,
    (SELECT limit_value FROM guest_limits WHERE limit_type = 'groq_transcriptions') as limit_value
UNION ALL
SELECT 
    'bulk' as type,
    (SELECT limit_value FROM guest_limits WHERE limit_type = 'bulk_videos') as limit_value;

-- 7. Check if the function has SECURITY DEFINER
SELECT 'Checking function security settings...' as step;
SELECT 
    proname,
    prosecdef as is_security_definer,
    proowner::regrole as owner
FROM pg_proc
WHERE proname = 'get_guest_usage_summary';