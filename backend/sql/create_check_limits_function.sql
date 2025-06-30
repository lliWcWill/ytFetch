-- Create a unified function to check limits for both guests and authenticated users
-- This replaces the missing check_tier_limits function

-- First, ensure the guest_limits table has bulk job limits
INSERT INTO guest_limits (limit_type, limit_value, description) 
VALUES ('bulk_jobs', 1, 'Maximum bulk jobs per day for guests')
ON CONFLICT (limit_type) DO UPDATE SET limit_value = 1;

-- Function to check limits for both guest and authenticated users
CREATE OR REPLACE FUNCTION check_user_limits(
    p_user_id UUID,
    p_limit_type VARCHAR(50),
    p_requested_count INTEGER DEFAULT 1,
    p_is_guest BOOLEAN DEFAULT FALSE,
    p_session_id VARCHAR(255) DEFAULT NULL
) RETURNS TABLE (
    allowed BOOLEAN,
    current_usage INTEGER,
    limit_value INTEGER,
    remaining INTEGER,
    message TEXT,
    requires_tokens BOOLEAN
) AS $$
DECLARE
    v_allowed BOOLEAN;
    v_current_usage INTEGER;
    v_limit INTEGER;
    v_remaining INTEGER;
    v_message TEXT;
    v_requires_tokens BOOLEAN := FALSE;
BEGIN
    -- Handle guest users
    IF p_is_guest AND p_session_id IS NOT NULL THEN
        -- For guests, check guest limits
        IF p_limit_type = 'bulk_jobs' THEN
            -- Check daily bulk job limit for guests
            SELECT COUNT(*) INTO v_current_usage
            FROM bulk_jobs
            WHERE user_id = p_user_id
            AND created_at >= CURRENT_DATE;
            
            SELECT limit_value INTO v_limit
            FROM guest_limits
            WHERE limit_type = 'bulk_jobs';
            
            v_limit := COALESCE(v_limit, 1); -- Default to 1 bulk job per day
        ELSE
            -- Use existing guest usage check
            SELECT 
                current_usage,
                limit_value
            INTO 
                v_current_usage,
                v_limit
            FROM check_guest_usage_limit(p_session_id, p_limit_type, p_requested_count);
        END IF;
        
        v_allowed := (v_current_usage + p_requested_count) <= v_limit;
        v_remaining := GREATEST(0, v_limit - v_current_usage);
        
        IF v_allowed THEN
            v_message := 'Within guest limits';
        ELSE
            v_message := format('Guest limit reached: %s/%s used. Please sign in to continue.', v_current_usage, v_limit);
        END IF;
    ELSE
        -- For authenticated users in token-based system
        -- No tier limits apply - only token balance matters
        v_allowed := TRUE;
        v_current_usage := 0;
        v_limit := 999999; -- Effectively unlimited
        v_remaining := 999999;
        v_message := 'Token-based system - no tier limits';
        v_requires_tokens := TRUE;
        
        -- Log for debugging
        RAISE NOTICE 'Authenticated user % - token-based system, no tier limits', p_user_id;
    END IF;
    
    RETURN QUERY SELECT 
        v_allowed,
        v_current_usage,
        v_limit,
        v_remaining,
        v_message,
        v_requires_tokens;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create a wrapper function with the old name for compatibility
CREATE OR REPLACE FUNCTION check_tier_limits(
    p_limit_type VARCHAR(50),
    p_requested_count INTEGER,
    p_user_id UUID
) RETURNS TABLE (
    allowed BOOLEAN,
    current_tier VARCHAR(50),
    limit_value INTEGER,
    current_usage INTEGER,
    requested INTEGER,
    would_be INTEGER,
    remaining INTEGER,
    reason TEXT,
    error_code VARCHAR(50)
) AS $$
BEGIN
    -- Call the new unified function
    RETURN QUERY
    SELECT 
        allowed,
        'token_based'::VARCHAR(50) as current_tier,
        limit_value,
        current_usage,
        p_requested_count as requested,
        current_usage + p_requested_count as would_be,
        remaining,
        message as reason,
        CASE WHEN NOT allowed THEN 'limit_exceeded'::VARCHAR(50) ELSE NULL::VARCHAR(50) END as error_code
    FROM check_user_limits(p_user_id, p_limit_type, p_requested_count, FALSE, NULL);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permissions
GRANT EXECUTE ON FUNCTION check_user_limits TO service_role, authenticated, anon;
GRANT EXECUTE ON FUNCTION check_tier_limits TO service_role, authenticated, anon;

-- Test the function
SELECT * FROM check_tier_limits('videos_per_job', 10, '17a939d6-bc4d-4225-afbc-bf22ac626dd7'::UUID);