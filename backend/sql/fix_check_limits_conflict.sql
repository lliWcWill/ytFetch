-- First, drop the existing functions to avoid conflicts
DROP FUNCTION IF EXISTS check_user_limits(uuid, varchar, integer, boolean, varchar);
DROP FUNCTION IF EXISTS check_tier_limits(varchar, integer, uuid);

-- Create a simple check_tier_limits function for the token-based system
CREATE OR REPLACE FUNCTION check_tier_limits(
    p_limit_type VARCHAR(50),
    p_requested_count INTEGER,
    p_user_id UUID
)
RETURNS TABLE (
    allowed BOOLEAN,
    current_tier VARCHAR(50),
    limit_value INTEGER,
    current_usage INTEGER,
    requested INTEGER,
    would_be INTEGER,
    remaining INTEGER,
    reason TEXT,
    error_code VARCHAR(50)
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- In token-based system, authenticated users have no tier limits
    -- They only pay for what they use
    RETURN QUERY
    SELECT 
        TRUE::BOOLEAN as allowed,
        'token_based'::VARCHAR(50) as current_tier,
        999999::INTEGER as limit_value,  -- Effectively unlimited
        0::INTEGER as current_usage,
        p_requested_count as requested,
        p_requested_count as would_be,
        999999::INTEGER as remaining,
        'Token-based system - pay per use'::TEXT as reason,
        NULL::VARCHAR(50) as error_code;
END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION check_tier_limits TO authenticated;
GRANT EXECUTE ON FUNCTION check_tier_limits TO service_role;

-- Test the function
SELECT * FROM check_tier_limits('bulk_jobs', 1, auth.uid());