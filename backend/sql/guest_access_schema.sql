-- Guest Access Schema Updates for ytFetch
-- Adds support for guest access with usage limits

-- =====================================================
-- UPDATE USER PROFILES TABLE
-- =====================================================
-- Add guest usage tracking columns to user_profiles
ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS is_guest BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS guest_usage_data JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- Create index for guest users
CREATE INDEX IF NOT EXISTS idx_user_profiles_is_guest ON user_profiles(is_guest);

-- =====================================================
-- GUEST USAGE TRACKING TABLE
-- =====================================================
-- Track guest usage by IP/session for rate limiting
CREATE TABLE IF NOT EXISTS guest_usage (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    ip_address INET,
    -- Usage counters
    unofficial_transcriptions INTEGER DEFAULT 0,
    groq_transcriptions INTEGER DEFAULT 0,
    bulk_videos_processed INTEGER DEFAULT 0,
    -- Timestamps
    first_use_at TIMESTAMPTZ DEFAULT NOW(),
    last_use_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for guest usage
CREATE INDEX IF NOT EXISTS idx_guest_usage_session_id ON guest_usage(session_id);
CREATE INDEX IF NOT EXISTS idx_guest_usage_ip_address ON guest_usage(ip_address);
CREATE INDEX IF NOT EXISTS idx_guest_usage_last_use ON guest_usage(last_use_at DESC);

-- =====================================================
-- GUEST USAGE LIMITS
-- =====================================================
-- Define guest usage limits
CREATE TABLE IF NOT EXISTS guest_limits (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    limit_type VARCHAR(50) NOT NULL UNIQUE,
    limit_value INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default guest limits
INSERT INTO guest_limits (limit_type, limit_value, description) VALUES
('unofficial_transcriptions', 10, 'Maximum unofficial transcriptions for guests'),
('groq_transcriptions', 10, 'Maximum Groq transcriptions for guests'),
('bulk_videos', 50, 'Maximum bulk videos for guests (one-time demo)'),
('daily_requests', 100, 'Maximum requests per day for guests')
ON CONFLICT (limit_type) DO NOTHING;

-- =====================================================
-- FUNCTIONS FOR GUEST ACCESS
-- =====================================================

-- Function to check guest usage limits
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
$$ LANGUAGE plpgsql;

-- Function to increment guest usage
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
    INSERT INTO guest_usage (session_id, ip_address)
    VALUES (p_session_id, p_ip_address)
    ON CONFLICT (session_id) DO UPDATE
    SET last_use_at = NOW(),
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
$$ LANGUAGE plpgsql;

-- Function to get guest usage summary
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
$$ LANGUAGE plpgsql;

-- =====================================================
-- UPDATE TIER CONFIGURATION
-- =====================================================
-- Update user_profiles to use new tier structure
ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS tier VARCHAR(50) DEFAULT 'free';

-- Migrate existing tier_id to tier name
UPDATE user_profiles up
SET tier = COALESCE(
    (SELECT name FROM user_tiers WHERE id = up.tier_id),
    'free'
)
WHERE tier IS NULL OR tier = '';

-- Update usage_data structure to match the new format
UPDATE user_profiles
SET usage_data = jsonb_build_object(
    'monthly', jsonb_build_object(
        to_char(NOW(), 'YYYY-MM'), jsonb_build_object(
            'videos_processed', COALESCE(videos_processed_this_month, 0),
            'jobs_created', COALESCE(jobs_created_this_month, 0),
            'transcription_minutes', 0
        )
    ),
    'all_time', jsonb_build_object(
        'videos_processed', COALESCE(total_videos_processed, 0),
        'jobs_created', COALESCE(total_jobs_created, 0),
        'transcription_minutes', 0
    )
)
WHERE usage_data IS NULL OR usage_data = '{}';

-- =====================================================
-- UPDATED CHECK_TIER_LIMITS FUNCTION
-- =====================================================
-- Update the check_tier_limits function to handle guests
CREATE OR REPLACE FUNCTION check_tier_limits(
    p_user_id UUID,
    p_limit_type VARCHAR(50),
    p_requested_count INTEGER DEFAULT 1
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
DECLARE
    v_tier VARCHAR(50);
    v_limit INTEGER;
    v_current_usage INTEGER;
    v_allowed BOOLEAN;
    v_would_be INTEGER;
    v_remaining INTEGER;
    v_reason TEXT;
    v_error_code VARCHAR(50);
    v_current_month VARCHAR(7);
BEGIN
    -- Get current month
    v_current_month := to_char(NOW(), 'YYYY-MM');
    
    -- Get user's tier
    SELECT tier INTO v_tier
    FROM user_profiles
    WHERE id = p_user_id;
    
    -- Default to free tier if not found
    v_tier := COALESCE(v_tier, 'free');
    
    -- Get limit based on tier and type
    CASE v_tier
        WHEN 'free' THEN
            CASE p_limit_type
                WHEN 'videos_per_job' THEN v_limit := 5;
                WHEN 'jobs_per_month' THEN v_limit := 10;
                WHEN 'videos_per_month' THEN v_limit := 50;
                WHEN 'transcription_minutes_per_month' THEN v_limit := 300;
                ELSE v_limit := 0;
            END CASE;
        WHEN 'pro' THEN
            CASE p_limit_type
                WHEN 'videos_per_job' THEN v_limit := 100;
                WHEN 'jobs_per_month' THEN v_limit := 1000;
                WHEN 'videos_per_month' THEN v_limit := 10000;
                WHEN 'transcription_minutes_per_month' THEN v_limit := 10000;
                ELSE v_limit := 0;
            END CASE;
        WHEN 'enterprise' THEN
            v_limit := 999999; -- Effectively unlimited
        ELSE
            v_limit := 0;
    END CASE;
    
    -- Get current usage from usage_data JSONB
    IF p_limit_type IN ('jobs_per_month', 'videos_per_month', 'transcription_minutes_per_month') THEN
        -- Monthly limits
        SELECT 
            COALESCE(
                (usage_data->'monthly'->v_current_month->>
                    CASE p_limit_type
                        WHEN 'jobs_per_month' THEN 'jobs_created'
                        WHEN 'videos_per_month' THEN 'videos_processed'
                        WHEN 'transcription_minutes_per_month' THEN 'transcription_minutes'
                    END
                )::INTEGER,
                0
            ) INTO v_current_usage
        FROM user_profiles
        WHERE id = p_user_id;
    ELSE
        -- Per-job limits don't have current usage
        v_current_usage := 0;
    END IF;
    
    -- Calculate would-be usage
    v_would_be := v_current_usage + p_requested_count;
    v_allowed := v_would_be <= v_limit;
    v_remaining := GREATEST(0, v_limit - v_current_usage);
    
    -- Set reason and error code
    IF v_allowed THEN
        v_reason := 'Within tier limits';
        v_error_code := NULL;
    ELSE
        v_reason := format('Would exceed %s tier limit of %s', v_tier, v_limit);
        v_error_code := 'tier_limit_exceeded';
    END IF;
    
    RETURN QUERY SELECT 
        v_allowed,
        v_tier,
        v_limit,
        v_current_usage,
        p_requested_count,
        v_would_be,
        v_remaining,
        v_reason,
        v_error_code;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- CLEANUP OLD COLUMNS (Run after migration is verified)
-- =====================================================
-- These can be run after verifying the migration worked:
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS videos_processed_this_month;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS jobs_created_this_month;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS total_videos_processed;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS total_jobs_created;
-- ALTER TABLE user_profiles DROP COLUMN IF EXISTS tier_id;