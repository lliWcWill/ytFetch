-- Fix the ambiguous column reference in get_guest_usage_summary function
-- and ensure guest bulk job limits work correctly

-- Drop the existing function to recreate it
DROP FUNCTION IF EXISTS get_guest_usage_summary(VARCHAR(255));

-- Recreate the function with properly qualified column names
CREATE OR REPLACE FUNCTION get_guest_usage_summary(p_session_id VARCHAR(255))
RETURNS TABLE (
    session_id VARCHAR(255),
    unofficial_used INTEGER,
    unofficial_limit INTEGER,
    unofficial_remaining INTEGER,
    groq_used INTEGER,
    groq_limit INTEGER,
    groq_remaining INTEGER,
    bulk_used INTEGER,
    bulk_limit INTEGER,
    bulk_remaining INTEGER,
    first_use_at TIMESTAMPTZ,
    last_use_at TIMESTAMPTZ
) AS $$
BEGIN
    -- First try to get existing usage
    RETURN QUERY
    SELECT 
        gu.session_id::VARCHAR(255),
        COALESCE(gu.unofficial_transcriptions, 0)::INTEGER as unofficial_used,
        COALESCE(gl1.limit_value, 10)::INTEGER as unofficial_limit,
        GREATEST(0, COALESCE(gl1.limit_value, 10) - COALESCE(gu.unofficial_transcriptions, 0))::INTEGER as unofficial_remaining,
        COALESCE(gu.groq_transcriptions, 0)::INTEGER as groq_used,
        COALESCE(gl2.limit_value, 10)::INTEGER as groq_limit,
        GREATEST(0, COALESCE(gl2.limit_value, 10) - COALESCE(gu.groq_transcriptions, 0))::INTEGER as groq_remaining,
        COALESCE(gu.bulk_videos_processed, 0)::INTEGER as bulk_used,
        COALESCE(gl3.limit_value, 50)::INTEGER as bulk_limit,
        GREATEST(0, COALESCE(gl3.limit_value, 50) - COALESCE(gu.bulk_videos_processed, 0))::INTEGER as bulk_remaining,
        gu.first_use_at,
        gu.last_use_at
    FROM guest_usage gu
    LEFT JOIN guest_limits gl1 ON gl1.limit_type = 'unofficial_transcriptions'
    LEFT JOIN guest_limits gl2 ON gl2.limit_type = 'groq_transcriptions'
    LEFT JOIN guest_limits gl3 ON gl3.limit_type = 'bulk_videos'
    WHERE gu.session_id = p_session_id;
    
    -- If no record found, return default values
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT 
            p_session_id::VARCHAR(255),
            0::INTEGER as unofficial_used,
            COALESCE((SELECT limit_value FROM guest_limits WHERE limit_type = 'unofficial_transcriptions'), 10)::INTEGER as unofficial_limit,
            COALESCE((SELECT limit_value FROM guest_limits WHERE limit_type = 'unofficial_transcriptions'), 10)::INTEGER as unofficial_remaining,
            0::INTEGER as groq_used,
            COALESCE((SELECT limit_value FROM guest_limits WHERE limit_type = 'groq_transcriptions'), 10)::INTEGER as groq_limit,
            COALESCE((SELECT limit_value FROM guest_limits WHERE limit_type = 'groq_transcriptions'), 10)::INTEGER as groq_remaining,
            0::INTEGER as bulk_used,
            COALESCE((SELECT limit_value FROM guest_limits WHERE limit_type = 'bulk_videos'), 50)::INTEGER as bulk_limit,
            COALESCE((SELECT limit_value FROM guest_limits WHERE limit_type = 'bulk_videos'), 50)::INTEGER as bulk_remaining,
            NULL::TIMESTAMPTZ as first_use_at,
            NULL::TIMESTAMPTZ as last_use_at;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Also fix the check_guest_usage_limit function to ensure it works correctly for bulk jobs
DROP FUNCTION IF EXISTS check_guest_usage_limit(VARCHAR(255), VARCHAR(50), INTEGER);

CREATE OR REPLACE FUNCTION check_guest_usage_limit(
    p_session_id VARCHAR(255),
    p_limit_type VARCHAR(50),
    p_requested_count INTEGER DEFAULT 1
) RETURNS TABLE (
    allowed BOOLEAN,
    current_usage INTEGER,
    limit_value INTEGER,
    remaining INTEGER,
    message TEXT
) AS $$
DECLARE
    v_current_usage INTEGER;
    v_limit INTEGER;
    v_allowed BOOLEAN;
    v_remaining INTEGER;
    v_message TEXT;
    v_bulk_jobs_today INTEGER;
BEGIN
    -- Get the limit value
    SELECT gl.limit_value INTO v_limit
    FROM guest_limits gl
    WHERE gl.limit_type = p_limit_type;
    
    -- Use default limits if not found
    IF v_limit IS NULL THEN
        CASE p_limit_type
            WHEN 'unofficial_transcriptions' THEN v_limit := 10;
            WHEN 'groq_transcriptions' THEN v_limit := 10;
            WHEN 'bulk_videos' THEN v_limit := 50;
            ELSE v_limit := 0;
        END CASE;
    END IF;
    
    -- Special handling for bulk jobs - check daily limit
    IF p_limit_type = 'bulk_videos' THEN
        -- For bulk jobs, guests get 1 job per day, not based on video count
        -- Check if they've already created a bulk job today
        SELECT COUNT(*)::INTEGER INTO v_bulk_jobs_today
        FROM bulk_jobs bj
        WHERE bj.user_id IN (
            SELECT CAST(uuid_generate_v5('6ba7b810-9dad-11d1-80b4-00c04fd430c8'::uuid, 'guest_' || p_session_id) AS TEXT)
        )
        AND bj.created_at >= CURRENT_DATE
        AND bj.created_at < CURRENT_DATE + INTERVAL '1 day';
        
        IF v_bulk_jobs_today > 0 THEN
            -- Already created a bulk job today
            RETURN QUERY SELECT 
                false::BOOLEAN,
                1::INTEGER,  -- current usage (jobs today)
                1::INTEGER,  -- limit (1 job per day)
                0::INTEGER,  -- remaining
                'Guests are limited to 1 bulk job per day. Please sign in for unlimited access.'::TEXT;
            RETURN;
        ELSE
            -- Haven't created a bulk job today, allow it
            RETURN QUERY SELECT 
                true::BOOLEAN,
                0::INTEGER,  -- current usage
                1::INTEGER,  -- limit
                1::INTEGER,  -- remaining
                'Bulk job allowed for today'::TEXT;
            RETURN;
        END IF;
    END IF;
    
    -- Get current usage based on limit type (for non-bulk jobs)
    CASE p_limit_type
        WHEN 'unofficial_transcriptions' THEN
            SELECT COALESCE(gu.unofficial_transcriptions, 0) INTO v_current_usage
            FROM guest_usage gu
            WHERE gu.session_id = p_session_id;
        WHEN 'groq_transcriptions' THEN
            SELECT COALESCE(gu.groq_transcriptions, 0) INTO v_current_usage
            FROM guest_usage gu
            WHERE gu.session_id = p_session_id;
        ELSE
            v_current_usage := 0;
    END CASE;
    
    -- Handle null (new guest)
    v_current_usage := COALESCE(v_current_usage, 0);
    
    -- Check if allowed
    v_allowed := (v_current_usage + p_requested_count) <= v_limit;
    v_remaining := GREATEST(0, v_limit - v_current_usage);
    
    -- Set appropriate message
    IF v_allowed THEN
        v_message := 'Usage within limits';
    ELSE
        v_message := format('Guest limit reached: %s/%s %s used', v_current_usage, v_limit, p_limit_type);
    END IF;
    
    RETURN QUERY SELECT 
        v_allowed,
        v_current_usage,
        v_limit,
        v_remaining,
        v_message;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permissions
GRANT EXECUTE ON FUNCTION get_guest_usage_summary TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION check_guest_usage_limit TO anon, authenticated, service_role;

-- Ensure guest_limits table has correct data
INSERT INTO guest_limits (limit_type, limit_value, description) VALUES
    ('unofficial_transcriptions', 10, 'Maximum unofficial transcriptions for guests'),
    ('groq_transcriptions', 10, 'Maximum Groq transcriptions for guests'),
    ('bulk_videos', 50, 'Maximum bulk videos for guests (one-time demo)'),
    ('daily_requests', 100, 'Maximum requests per day for guests')
ON CONFLICT (limit_type) DO UPDATE
SET limit_value = EXCLUDED.limit_value,
    description = EXCLUDED.description;

-- Test the functions
SELECT 'Testing get_guest_usage_summary:' as test;
SELECT * FROM get_guest_usage_summary('faae54c2-56da-4c5e-a15e-1343b7ccfbf8');

SELECT 'Testing check_guest_usage_limit for bulk jobs:' as test;
SELECT * FROM check_guest_usage_limit('faae54c2-56da-4c5e-a15e-1343b7ccfbf8', 'bulk_videos', 60);