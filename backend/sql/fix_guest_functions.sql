-- Fix Guest Functions for ytFetch
-- This creates the missing functions that guest_service.py expects
-- Run this SQL in Supabase SQL Editor

-- =====================================================
-- STEP 1: UPDATE GUEST USAGE TABLE STRUCTURE
-- =====================================================

-- First, check if we need to update the guest_usage table structure
-- The code expects separate columns for each usage type

-- Add missing columns if they don't exist
ALTER TABLE guest_usage 
ADD COLUMN IF NOT EXISTS session_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS ip_address INET,
ADD COLUMN IF NOT EXISTS unofficial_transcriptions INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS groq_transcriptions INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS bulk_videos_processed INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS first_use_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS last_use_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Ensure session_id is unique (required by the functions)
CREATE UNIQUE INDEX IF NOT EXISTS idx_guest_usage_session_id_unique ON guest_usage(session_id);

-- Create other required indexes
CREATE INDEX IF NOT EXISTS idx_guest_usage_ip_address ON guest_usage(ip_address);
CREATE INDEX IF NOT EXISTS idx_guest_usage_last_use ON guest_usage(last_use_at DESC);

-- =====================================================
-- STEP 2: UPDATE GUEST LIMITS TABLE STRUCTURE
-- =====================================================

-- Ensure guest_limits table has the structure the code expects
CREATE TABLE IF NOT EXISTS guest_limits (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    limit_type VARCHAR(50) NOT NULL UNIQUE,
    limit_value INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default guest limits that match the code
INSERT INTO guest_limits (limit_type, limit_value, description) VALUES
('unofficial_transcriptions', 10, 'Maximum unofficial transcriptions for guests'),
('groq_transcriptions', 10, 'Maximum Groq transcriptions for guests'),
('bulk_videos', 50, 'Maximum bulk videos for guests (one-time demo)'),
('daily_requests', 100, 'Maximum requests per day for guests')
ON CONFLICT (limit_type) DO NOTHING;

-- =====================================================
-- STEP 3: CREATE THE MISSING FUNCTIONS
-- =====================================================

-- Function: check_guest_usage_limit
-- This is the main function that guest_service.py calls
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
BEGIN
    -- Get the limit value
    SELECT limit_value INTO v_limit
    FROM guest_limits
    WHERE limit_type = p_limit_type;
    
    IF v_limit IS NULL THEN
        -- If limit type not found, deny by default
        RETURN QUERY SELECT 
            false::BOOLEAN,
            0::INTEGER,
            0::INTEGER,
            0::INTEGER,
            'Unknown limit type'::TEXT;
        RETURN;
    END IF;
    
    -- Get current usage based on limit type
    CASE p_limit_type
        WHEN 'unofficial_transcriptions' THEN
            SELECT COALESCE(unofficial_transcriptions, 0) INTO v_current_usage
            FROM guest_usage
            WHERE session_id = p_session_id;
        WHEN 'groq_transcriptions' THEN
            SELECT COALESCE(groq_transcriptions, 0) INTO v_current_usage
            FROM guest_usage
            WHERE session_id = p_session_id;
        WHEN 'bulk_videos' THEN
            SELECT COALESCE(bulk_videos_processed, 0) INTO v_current_usage
            FROM guest_usage
            WHERE session_id = p_session_id;
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

-- Function: increment_guest_usage
-- This function increments usage counters
CREATE OR REPLACE FUNCTION increment_guest_usage(
    p_session_id VARCHAR(255),
    p_ip_address INET,
    p_usage_type VARCHAR(50),
    p_increment INTEGER DEFAULT 1
) RETURNS TABLE (
    success BOOLEAN,
    new_usage INTEGER,
    message TEXT
) AS $$
DECLARE
    v_new_usage INTEGER;
    v_success BOOLEAN := true;
    v_message TEXT := 'Usage incremented successfully';
BEGIN
    -- Insert or update guest usage record
    INSERT INTO guest_usage (session_id, ip_address, first_use_at, last_use_at, created_at, updated_at)
    VALUES (p_session_id, p_ip_address, NOW(), NOW(), NOW(), NOW())
    ON CONFLICT (session_id) DO UPDATE
    SET last_use_at = NOW(),
        updated_at = NOW(),
        ip_address = COALESCE(guest_usage.ip_address, EXCLUDED.ip_address);
    
    -- Increment the appropriate counter
    CASE p_usage_type
        WHEN 'unofficial_transcriptions' THEN
            UPDATE guest_usage
            SET unofficial_transcriptions = COALESCE(unofficial_transcriptions, 0) + p_increment,
                updated_at = NOW()
            WHERE session_id = p_session_id
            RETURNING unofficial_transcriptions INTO v_new_usage;
        WHEN 'groq_transcriptions' THEN
            UPDATE guest_usage
            SET groq_transcriptions = COALESCE(groq_transcriptions, 0) + p_increment,
                updated_at = NOW()
            WHERE session_id = p_session_id
            RETURNING groq_transcriptions INTO v_new_usage;
        WHEN 'bulk_videos' THEN
            UPDATE guest_usage
            SET bulk_videos_processed = COALESCE(bulk_videos_processed, 0) + p_increment,
                updated_at = NOW()
            WHERE session_id = p_session_id
            RETURNING bulk_videos_processed INTO v_new_usage;
        ELSE
            v_success := false;
            v_message := 'Unknown usage type';
            v_new_usage := 0;
    END CASE;
    
    RETURN QUERY SELECT v_success, v_new_usage, v_message;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: get_guest_usage_summary
-- This function returns comprehensive usage summary
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
    RETURN QUERY
    SELECT 
        gu.session_id,
        COALESCE(gu.unofficial_transcriptions, 0) as unofficial_used,
        (SELECT limit_value FROM guest_limits WHERE limit_type = 'unofficial_transcriptions') as unofficial_limit,
        GREATEST(0, (SELECT limit_value FROM guest_limits WHERE limit_type = 'unofficial_transcriptions') - COALESCE(gu.unofficial_transcriptions, 0)) as unofficial_remaining,
        COALESCE(gu.groq_transcriptions, 0) as groq_used,
        (SELECT limit_value FROM guest_limits WHERE limit_type = 'groq_transcriptions') as groq_limit,
        GREATEST(0, (SELECT limit_value FROM guest_limits WHERE limit_type = 'groq_transcriptions') - COALESCE(gu.groq_transcriptions, 0)) as groq_remaining,
        COALESCE(gu.bulk_videos_processed, 0) as bulk_used,
        (SELECT limit_value FROM guest_limits WHERE limit_type = 'bulk_videos') as bulk_limit,
        GREATEST(0, (SELECT limit_value FROM guest_limits WHERE limit_type = 'bulk_videos') - COALESCE(gu.bulk_videos_processed, 0)) as bulk_remaining,
        gu.first_use_at,
        gu.last_use_at
    FROM guest_usage gu
    WHERE gu.session_id = p_session_id;
    
    -- If no record found, return default values
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT 
            p_session_id,
            0::INTEGER,
            (SELECT limit_value FROM guest_limits WHERE limit_type = 'unofficial_transcriptions'),
            (SELECT limit_value FROM guest_limits WHERE limit_type = 'unofficial_transcriptions'),
            0::INTEGER,
            (SELECT limit_value FROM guest_limits WHERE limit_type = 'groq_transcriptions'),
            (SELECT limit_value FROM guest_limits WHERE limit_type = 'groq_transcriptions'),
            0::INTEGER,
            (SELECT limit_value FROM guest_limits WHERE limit_type = 'bulk_videos'),
            (SELECT limit_value FROM guest_limits WHERE limit_type = 'bulk_videos'),
            NULL::TIMESTAMPTZ,
            NULL::TIMESTAMPTZ;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- STEP 4: GRANT PERMISSIONS
-- =====================================================

-- Grant execute permissions to service role (used by backend)
GRANT EXECUTE ON FUNCTION check_guest_usage_limit TO service_role;
GRANT EXECUTE ON FUNCTION increment_guest_usage TO service_role;
GRANT EXECUTE ON FUNCTION get_guest_usage_summary TO service_role;

-- Grant execute permissions to anon role (for guest access)
GRANT EXECUTE ON FUNCTION check_guest_usage_limit TO anon;
GRANT EXECUTE ON FUNCTION increment_guest_usage TO anon;
GRANT EXECUTE ON FUNCTION get_guest_usage_summary TO anon;

-- =====================================================
-- STEP 5: VERIFY THE FUNCTIONS EXIST
-- =====================================================

-- Check that all functions were created successfully
SELECT 
    proname as function_name,
    pg_catalog.pg_get_function_result(oid) as returns,
    pg_catalog.pg_get_function_arguments(oid) as arguments
FROM pg_catalog.pg_proc
WHERE proname IN ('check_guest_usage_limit', 'increment_guest_usage', 'get_guest_usage_summary')
AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
ORDER BY proname;

-- Show current guest limits
SELECT * FROM guest_limits ORDER BY limit_type;