-- Create missing database functions for usage tracking

-- Function: increment_usage_counter
-- This function atomically increments usage counters
CREATE OR REPLACE FUNCTION increment_usage_counter(
    p_user_id UUID,
    p_counter_type TEXT,
    p_increment INTEGER DEFAULT 1
) RETURNS TABLE (
    success BOOLEAN,
    new_value INTEGER,
    monthly_limit INTEGER,
    remaining INTEGER
) AS $$
DECLARE
    v_tier_id UUID;
    v_current_value INTEGER;
    v_limit INTEGER;
    v_column_name TEXT;
    v_limit_column TEXT;
BEGIN
    -- Map counter type to column names
    CASE p_counter_type
        WHEN 'videos_processed' THEN
            v_column_name := 'videos_processed_this_month';
            v_limit_column := 'monthly_videos';
        WHEN 'jobs_created' THEN
            v_column_name := 'jobs_created_this_month';
            v_limit_column := 'monthly_jobs';
        WHEN 'transcription_minutes' THEN
            v_column_name := 'transcription_minutes_this_month';
            v_limit_column := 'monthly_transcription_minutes';
        ELSE
            RAISE EXCEPTION 'Unknown counter type: %', p_counter_type;
    END CASE;
    
    -- Get user's tier and current usage
    EXECUTE format('SELECT tier_id, %I FROM user_profiles WHERE id = $1', v_column_name)
    INTO v_tier_id, v_current_value
    USING p_user_id;
    
    -- Get tier limit
    EXECUTE format('SELECT %I FROM tiers WHERE id = $1', v_limit_column)
    INTO v_limit
    USING v_tier_id;
    
    -- Check if increment would exceed limit
    IF v_current_value + p_increment > v_limit THEN
        RETURN QUERY SELECT 
            false::BOOLEAN,
            v_current_value,
            v_limit,
            GREATEST(0, v_limit - v_current_value);
        RETURN;
    END IF;
    
    -- Perform the increment
    EXECUTE format('UPDATE user_profiles SET %I = %I + $1 WHERE id = $2', v_column_name, v_column_name)
    USING p_increment, p_user_id;
    
    -- Return success with new values
    RETURN QUERY SELECT 
        true::BOOLEAN,
        v_current_value + p_increment,
        v_limit,
        v_limit - (v_current_value + p_increment);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function: get_user_usage_summary
-- Returns comprehensive usage information for a user
CREATE OR REPLACE FUNCTION get_user_usage_summary(p_user_id UUID)
RETURNS TABLE (
    tier_name TEXT,
    tier_display_name TEXT,
    videos_used INTEGER,
    videos_limit INTEGER,
    videos_remaining INTEGER,
    jobs_used INTEGER,
    jobs_limit INTEGER,
    jobs_remaining INTEGER,
    minutes_used INTEGER,
    minutes_limit INTEGER,
    minutes_remaining INTEGER,
    reset_date TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.name,
        t.display_name,
        COALESCE(up.videos_processed_this_month, 0),
        t.monthly_videos,
        GREATEST(0, t.monthly_videos - COALESCE(up.videos_processed_this_month, 0)),
        COALESCE(up.jobs_created_this_month, 0),
        t.monthly_jobs,
        GREATEST(0, t.monthly_jobs - COALESCE(up.jobs_created_this_month, 0)),
        COALESCE(up.transcription_minutes_this_month, 0),
        t.monthly_transcription_minutes,
        GREATEST(0, t.monthly_transcription_minutes - COALESCE(up.transcription_minutes_this_month, 0)),
        up.last_usage_reset_at
    FROM user_profiles up
    JOIN tiers t ON up.tier_id = t.id
    WHERE up.id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permissions
GRANT EXECUTE ON FUNCTION increment_usage_counter TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION get_user_usage_summary TO service_role, authenticated;

-- Test the functions
SELECT * FROM get_user_usage_summary('17a939d6-bc4d-4225-afbc-bf22ac626dd7');