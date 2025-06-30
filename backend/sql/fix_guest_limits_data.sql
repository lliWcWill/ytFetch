-- Fix guest limits data to ensure the get_guest_usage_summary function works correctly
-- This script ensures the guest_limits table has all required records

-- First, check if the guest_limits table exists and has the correct structure
DO $$
BEGIN
    -- Ensure the table exists with the correct structure
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'guest_limits') THEN
        RAISE NOTICE 'guest_limits table does not exist. Please run the guest_access_schema.sql first.';
    END IF;
END $$;

-- Delete any existing limits to ensure clean state
DELETE FROM guest_limits WHERE limit_type IN (
    'unofficial_transcriptions',
    'groq_transcriptions', 
    'bulk_videos',
    'daily_requests'
);

-- Insert the required guest limits
INSERT INTO guest_limits (limit_type, limit_value, description) VALUES
    ('unofficial_transcriptions', 10, 'Maximum unofficial transcriptions for guests'),
    ('groq_transcriptions', 10, 'Maximum Groq transcriptions for guests'),
    ('bulk_videos', 50, 'Maximum bulk videos for guests (one-time demo)'),
    ('daily_requests', 100, 'Maximum requests per day for guests');

-- Verify the data was inserted correctly
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count 
    FROM guest_limits 
    WHERE limit_type IN ('unofficial_transcriptions', 'groq_transcriptions', 'bulk_videos');
    
    IF v_count < 3 THEN
        RAISE EXCEPTION 'Failed to insert all required guest limits. Only % records found.', v_count;
    ELSE
        RAISE NOTICE 'Successfully inserted % guest limit records.', v_count;
    END IF;
END $$;

-- Test the get_guest_usage_summary function with a test session ID
DO $$
DECLARE
    v_result RECORD;
BEGIN
    -- Call the function with a test session ID
    SELECT * INTO v_result
    FROM get_guest_usage_summary('test-session-123')
    LIMIT 1;
    
    -- Check if limits are populated
    IF v_result.unofficial_limit IS NULL OR v_result.groq_limit IS NULL THEN
        RAISE WARNING 'Guest limits are still NULL after data insertion. Check RLS policies or function permissions.';
    ELSE
        RAISE NOTICE 'Guest usage summary test successful. Limits: unofficial=%, groq=%, bulk=%', 
            v_result.unofficial_limit, v_result.groq_limit, v_result.bulk_limit;
    END IF;
END $$;

-- Grant necessary permissions if needed
GRANT SELECT ON guest_limits TO anon, authenticated, service_role;