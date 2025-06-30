-- Treasury Schema Updates for ytFetch
-- Implements user profiles with tier and usage tracking

-- Create user_profiles table with comprehensive tier and usage tracking
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    
    -- Tier information
    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'enterprise')),
    tier_updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Stripe information
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT,
    stripe_subscription_status TEXT,
    subscription_ends_at TIMESTAMPTZ,
    
    -- Usage tracking with JSONB for flexibility
    usage_data JSONB NOT NULL DEFAULT '{
        "daily": {},
        "monthly": {},
        "all_time": {
            "videos_processed": 0,
            "jobs_created": 0,
            "transcription_minutes": 0
        }
    }'::jsonb,
    
    -- User metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Additional settings
    settings JSONB DEFAULT '{}'::jsonb
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_profiles_tier ON user_profiles(tier);
CREATE INDEX IF NOT EXISTS idx_user_profiles_stripe_customer_id ON user_profiles(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_last_activity ON user_profiles(last_activity_at);
CREATE INDEX IF NOT EXISTS idx_user_profiles_usage_data ON user_profiles USING GIN (usage_data);

-- Enable Row Level Security
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Users can only view their own profile
CREATE POLICY "Users can view own profile" ON user_profiles
    FOR SELECT USING (auth.uid() = id);

-- Users can update their own profile (limited fields)
CREATE POLICY "Users can update own profile" ON user_profiles
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Service role can do everything
CREATE POLICY "Service role has full access" ON user_profiles
    FOR ALL USING (auth.role() = 'service_role');

-- Function to increment usage counters atomically
CREATE OR REPLACE FUNCTION increment_usage_counter(
    p_user_id UUID,
    p_counter_type TEXT,
    p_increment INTEGER DEFAULT 1
) RETURNS JSONB AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
    v_month TEXT := TO_CHAR(CURRENT_DATE, 'YYYY-MM');
    v_updated_usage JSONB;
BEGIN
    -- Update usage data atomically
    UPDATE user_profiles
    SET 
        usage_data = jsonb_set(
            jsonb_set(
                jsonb_set(
                    jsonb_set(
                        usage_data,
                        ARRAY['daily', v_today::TEXT, p_counter_type],
                        to_jsonb(COALESCE((usage_data->'daily'->v_today::TEXT->>p_counter_type)::INTEGER, 0) + p_increment)
                    ),
                    ARRAY['monthly', v_month, p_counter_type],
                    to_jsonb(COALESCE((usage_data->'monthly'->v_month->>p_counter_type)::INTEGER, 0) + p_increment)
                ),
                ARRAY['all_time', p_counter_type],
                to_jsonb(COALESCE((usage_data->'all_time'->>p_counter_type)::INTEGER, 0) + p_increment)
            ),
            ARRAY['last_updated'],
            to_jsonb(NOW())
        ),
        last_activity_at = NOW(),
        updated_at = NOW()
    WHERE id = p_user_id
    RETURNING usage_data INTO v_updated_usage;
    
    -- Return the updated usage data
    RETURN v_updated_usage;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get user's current usage for a specific period
CREATE OR REPLACE FUNCTION get_user_usage(
    p_user_id UUID,
    p_period TEXT DEFAULT 'monthly'
) RETURNS TABLE (
    counter_type TEXT,
    usage_count INTEGER
) AS $$
DECLARE
    v_period_key TEXT;
BEGIN
    -- Determine the period key
    IF p_period = 'daily' THEN
        v_period_key := CURRENT_DATE::TEXT;
    ELSIF p_period = 'monthly' THEN
        v_period_key := TO_CHAR(CURRENT_DATE, 'YYYY-MM');
    ELSE
        -- For all_time, just return the all_time data
        RETURN QUERY
        SELECT 
            key::TEXT as counter_type,
            (value::TEXT)::INTEGER as usage_count
        FROM user_profiles, 
             jsonb_each(usage_data->'all_time')
        WHERE user_profiles.id = p_user_id;
        RETURN;
    END IF;
    
    -- Return usage for the specified period
    RETURN QUERY
    SELECT 
        key::TEXT as counter_type,
        (value::TEXT)::INTEGER as usage_count
    FROM user_profiles, 
         jsonb_each(usage_data->p_period->v_period_key)
    WHERE user_profiles.id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user has exceeded tier limits
CREATE OR REPLACE FUNCTION check_tier_limits(
    p_user_id UUID,
    p_limit_type TEXT,
    p_requested_count INTEGER DEFAULT 1
) RETURNS JSONB AS $$
DECLARE
    v_user_profile RECORD;
    v_tier_limits JSONB;
    v_current_usage INTEGER;
    v_limit INTEGER;
    v_month TEXT := TO_CHAR(CURRENT_DATE, 'YYYY-MM');
BEGIN
    -- Get user profile
    SELECT * INTO v_user_profile FROM user_profiles WHERE id = p_user_id;
    
    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'allowed', false,
            'reason', 'User profile not found',
            'error_code', 'profile_not_found'
        );
    END IF;
    
    -- Define tier limits
    v_tier_limits := CASE v_user_profile.tier
        WHEN 'free' THEN '{
            "videos_per_job": 5,
            "jobs_per_month": 10,
            "concurrent_jobs": 1,
            "videos_per_month": 50,
            "transcription_minutes_per_month": 300
        }'::jsonb
        WHEN 'pro' THEN '{
            "videos_per_job": 100,
            "jobs_per_month": 1000,
            "concurrent_jobs": 5,
            "videos_per_month": 10000,
            "transcription_minutes_per_month": 10000
        }'::jsonb
        WHEN 'enterprise' THEN '{
            "videos_per_job": 999999,
            "jobs_per_month": 999999,
            "concurrent_jobs": 20,
            "videos_per_month": 999999,
            "transcription_minutes_per_month": 999999
        }'::jsonb
        ELSE '{}'::jsonb
    END;
    
    -- Get the limit for the requested type
    v_limit := (v_tier_limits->>p_limit_type)::INTEGER;
    
    IF v_limit IS NULL THEN
        RETURN jsonb_build_object(
            'allowed', false,
            'reason', 'Invalid limit type',
            'error_code', 'invalid_limit_type'
        );
    END IF;
    
    -- For per-job limits, just check against the limit
    IF p_limit_type = 'videos_per_job' OR p_limit_type = 'concurrent_jobs' THEN
        IF p_requested_count > v_limit THEN
            RETURN jsonb_build_object(
                'allowed', false,
                'reason', format('Exceeds %s limit of %s for %s tier', p_limit_type, v_limit, v_user_profile.tier),
                'error_code', 'tier_limit_exceeded',
                'current_tier', v_user_profile.tier,
                'limit', v_limit,
                'requested', p_requested_count
            );
        ELSE
            RETURN jsonb_build_object(
                'allowed', true,
                'current_tier', v_user_profile.tier,
                'limit', v_limit,
                'requested', p_requested_count
            );
        END IF;
    END IF;
    
    -- For monthly limits, check current usage
    v_current_usage := COALESCE(
        (v_user_profile.usage_data->'monthly'->v_month->>
            CASE p_limit_type
                WHEN 'jobs_per_month' THEN 'jobs_created'
                WHEN 'videos_per_month' THEN 'videos_processed'
                WHEN 'transcription_minutes_per_month' THEN 'transcription_minutes'
                ELSE p_limit_type
            END
        )::INTEGER, 
        0
    );
    
    IF v_current_usage + p_requested_count > v_limit THEN
        RETURN jsonb_build_object(
            'allowed', false,
            'reason', format('Would exceed monthly %s limit', p_limit_type),
            'error_code', 'monthly_limit_exceeded',
            'current_tier', v_user_profile.tier,
            'limit', v_limit,
            'current_usage', v_current_usage,
            'requested', p_requested_count,
            'would_be', v_current_usage + p_requested_count
        );
    ELSE
        RETURN jsonb_build_object(
            'allowed', true,
            'current_tier', v_user_profile.tier,
            'limit', v_limit,
            'current_usage', v_current_usage,
            'requested', p_requested_count,
            'remaining', v_limit - v_current_usage - p_requested_count
        );
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to automatically create user profile on signup
CREATE OR REPLACE FUNCTION handle_new_user() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_profiles (id, email, tier)
    VALUES (NEW.id, NEW.email, 'free')
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger if it doesn't exist
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Create a view for easier access to user tier limits
CREATE OR REPLACE VIEW user_tier_limits AS
SELECT 
    up.id,
    up.email,
    up.tier,
    up.tier_updated_at,
    up.stripe_subscription_status,
    up.subscription_ends_at,
    CASE up.tier
        WHEN 'free' THEN 5
        WHEN 'pro' THEN 100
        WHEN 'enterprise' THEN 999999
    END as videos_per_job,
    CASE up.tier
        WHEN 'free' THEN 10
        WHEN 'pro' THEN 1000
        WHEN 'enterprise' THEN 999999
    END as jobs_per_month,
    CASE up.tier
        WHEN 'free' THEN 1
        WHEN 'pro' THEN 5
        WHEN 'enterprise' THEN 20
    END as concurrent_jobs,
    CASE up.tier
        WHEN 'free' THEN 50
        WHEN 'pro' THEN 10000
        WHEN 'enterprise' THEN 999999
    END as videos_per_month,
    CASE up.tier
        WHEN 'free' THEN 300
        WHEN 'pro' THEN 10000
        WHEN 'enterprise' THEN 999999
    END as transcription_minutes_per_month,
    COALESCE((up.usage_data->'monthly'->TO_CHAR(CURRENT_DATE, 'YYYY-MM')->>'jobs_created')::INTEGER, 0) as jobs_created_this_month,
    COALESCE((up.usage_data->'monthly'->TO_CHAR(CURRENT_DATE, 'YYYY-MM')->>'videos_processed')::INTEGER, 0) as videos_processed_this_month,
    COALESCE((up.usage_data->'monthly'->TO_CHAR(CURRENT_DATE, 'YYYY-MM')->>'transcription_minutes')::INTEGER, 0) as transcription_minutes_this_month
FROM user_profiles up;

-- Grant access to authenticated users
GRANT SELECT ON user_tier_limits TO authenticated;

-- Comments for documentation
COMMENT ON TABLE user_profiles IS 'User profiles with tier and usage tracking for the treasury system';
COMMENT ON COLUMN user_profiles.usage_data IS 'JSONB field tracking daily, monthly, and all-time usage statistics';
COMMENT ON FUNCTION increment_usage_counter IS 'Atomically increments usage counters for a user';
COMMENT ON FUNCTION check_tier_limits IS 'Checks if a user action would exceed tier limits';
COMMENT ON FUNCTION get_user_usage IS 'Returns usage statistics for a user for a specific period';