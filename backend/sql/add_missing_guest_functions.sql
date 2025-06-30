-- Add missing guest usage functions
-- Run this in Supabase SQL Editor

-- Function to get guest usage summary
CREATE OR REPLACE FUNCTION get_guest_usage_summary(p_session_id TEXT)
RETURNS TABLE (
    unofficial_count BIGINT,
    groq_count BIGINT,
    bulk_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) FILTER (WHERE method = 'unofficial') as unofficial_count,
        COUNT(*) FILTER (WHERE method = 'groq') as groq_count,
        COUNT(*) FILTER (WHERE method = 'bulk') as bulk_count
    FROM guest_usage
    WHERE session_id = p_session_id
    AND created_at > NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if guest can use a method
CREATE OR REPLACE FUNCTION check_guest_limit(
    p_session_id TEXT,
    p_method TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    v_count INTEGER;
    v_limit INTEGER;
BEGIN
    -- Get current usage count
    SELECT COUNT(*)
    INTO v_count
    FROM guest_usage
    WHERE session_id = p_session_id
    AND method = p_method
    AND created_at > NOW() - INTERVAL '24 hours';
    
    -- Get limit for this method
    SELECT CASE p_method
        WHEN 'unofficial' THEN unofficial_limit
        WHEN 'groq' THEN groq_limit
        WHEN 'bulk' THEN bulk_limit
        ELSE 0
    END
    INTO v_limit
    FROM guest_limits
    WHERE id = 1;
    
    -- Return true if under limit
    RETURN v_count < v_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to record guest usage
CREATE OR REPLACE FUNCTION record_guest_usage(
    p_session_id TEXT,
    p_method TEXT,
    p_ip_address INET DEFAULT NULL,
    p_video_url TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO guest_usage (session_id, method, ip_address, video_url)
    VALUES (p_session_id, p_method, p_ip_address, p_video_url);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permissions to anon role (for guest access)
GRANT EXECUTE ON FUNCTION get_guest_usage_summary TO anon;
GRANT EXECUTE ON FUNCTION check_guest_limit TO anon;
GRANT EXECUTE ON FUNCTION record_guest_usage TO anon;

-- Verify functions were created
SELECT 
    proname as function_name,
    pg_catalog.pg_get_function_result(oid) as returns
FROM pg_catalog.pg_proc
WHERE proname IN ('get_guest_usage_summary', 'check_guest_limit', 'record_guest_usage')
AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');