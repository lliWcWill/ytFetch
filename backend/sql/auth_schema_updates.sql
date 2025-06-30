-- Authentication Schema Updates for ytFetch
-- These ALTER statements formalize user ownership relationships and ensure proper foreign key constraints
-- Execute these after the main schema is deployed

-- =====================================================
-- FOREIGN KEY CONSTRAINT UPDATES
-- =====================================================

-- Ensure all user_id fields have proper foreign key constraints
-- These should already exist from the main schema, but we're adding them explicitly for security

-- Add foreign key constraint to bulk_jobs.user_id if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'bulk_jobs_user_id_fkey' 
        AND table_name = 'bulk_jobs'
    ) THEN
        ALTER TABLE bulk_jobs 
        ADD CONSTRAINT bulk_jobs_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add foreign key constraint to video_tasks.user_id if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'video_tasks_user_id_fkey' 
        AND table_name = 'video_tasks'
    ) THEN
        ALTER TABLE video_tasks 
        ADD CONSTRAINT video_tasks_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add foreign key constraint to processing_logs.user_id if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'processing_logs_user_id_fkey' 
        AND table_name = 'processing_logs'
    ) THEN
        ALTER TABLE processing_logs 
        ADD CONSTRAINT processing_logs_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add foreign key constraint to webhook_logs.user_id if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'webhook_logs_user_id_fkey' 
        AND table_name = 'webhook_logs'
    ) THEN
        ALTER TABLE webhook_logs 
        ADD CONSTRAINT webhook_logs_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- =====================================================
-- ADDITIONAL SECURITY INDEXES
-- =====================================================

-- Add indexes to optimize authentication queries
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_user_id_status_created 
ON bulk_jobs(user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_video_tasks_user_id_job_id 
ON video_tasks(user_id, job_id);

CREATE INDEX IF NOT EXISTS idx_processing_logs_user_id_created 
ON processing_logs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_profiles_id_tier 
ON user_profiles(id, tier_id);

-- =====================================================
-- ENHANCED ROW LEVEL SECURITY POLICIES
-- =====================================================

-- Drop existing policies if they exist and recreate with enhanced security
DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can view own jobs" ON bulk_jobs;
DROP POLICY IF EXISTS "Users can create own jobs" ON bulk_jobs;
DROP POLICY IF EXISTS "Users can update own jobs" ON bulk_jobs;
DROP POLICY IF EXISTS "Users can delete own jobs" ON bulk_jobs;
DROP POLICY IF EXISTS "Users can view own tasks" ON video_tasks;
DROP POLICY IF EXISTS "Users can create own tasks" ON video_tasks;
DROP POLICY IF EXISTS "Users can update own tasks" ON video_tasks;
DROP POLICY IF EXISTS "Users can delete own tasks" ON video_tasks;
DROP POLICY IF EXISTS "Users can view own logs" ON processing_logs;
DROP POLICY IF EXISTS "Users can create own logs" ON processing_logs;
DROP POLICY IF EXISTS "Users can view own webhook logs" ON webhook_logs;
DROP POLICY IF EXISTS "Users can create own webhook logs" ON webhook_logs;

-- Enhanced user profiles policies with better security
CREATE POLICY "Users can view own profile" ON user_profiles
    FOR SELECT 
    USING (auth.uid() = id AND auth.uid() IS NOT NULL);

CREATE POLICY "Users can update own profile" ON user_profiles
    FOR UPDATE 
    USING (auth.uid() = id AND auth.uid() IS NOT NULL)
    WITH CHECK (auth.uid() = id AND auth.uid() IS NOT NULL);

-- Service role can manage all profiles for admin operations
CREATE POLICY "Service role can manage profiles" ON user_profiles
    FOR ALL 
    USING (auth.jwt() ->> 'role' = 'service_role')
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

-- Enhanced bulk jobs policies
CREATE POLICY "Users can view own jobs" ON bulk_jobs
    FOR SELECT 
    USING (auth.uid() = user_id AND auth.uid() IS NOT NULL);

CREATE POLICY "Users can create own jobs" ON bulk_jobs
    FOR INSERT 
    WITH CHECK (auth.uid() = user_id AND auth.uid() IS NOT NULL);

CREATE POLICY "Users can update own jobs" ON bulk_jobs
    FOR UPDATE 
    USING (auth.uid() = user_id AND auth.uid() IS NOT NULL)
    WITH CHECK (auth.uid() = user_id AND auth.uid() IS NOT NULL);

CREATE POLICY "Users can delete own jobs" ON bulk_jobs
    FOR DELETE 
    USING (auth.uid() = user_id AND auth.uid() IS NOT NULL);

-- Service role can manage all jobs for system operations
CREATE POLICY "Service role can manage jobs" ON bulk_jobs
    FOR ALL 
    USING (auth.jwt() ->> 'role' = 'service_role')
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

-- Enhanced video tasks policies
CREATE POLICY "Users can view own tasks" ON video_tasks
    FOR SELECT 
    USING (auth.uid() = user_id AND auth.uid() IS NOT NULL);

CREATE POLICY "Users can create own tasks" ON video_tasks
    FOR INSERT 
    WITH CHECK (auth.uid() = user_id AND auth.uid() IS NOT NULL);

CREATE POLICY "Users can update own tasks" ON video_tasks
    FOR UPDATE 
    USING (auth.uid() = user_id AND auth.uid() IS NOT NULL)
    WITH CHECK (auth.uid() = user_id AND auth.uid() IS NOT NULL);

CREATE POLICY "Users can delete own tasks" ON video_tasks
    FOR DELETE 
    USING (auth.uid() = user_id AND auth.uid() IS NOT NULL);

-- Service role can manage all tasks for processing operations
CREATE POLICY "Service role can manage tasks" ON video_tasks
    FOR ALL 
    USING (auth.jwt() ->> 'role' = 'service_role')
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

-- Enhanced processing logs policies
CREATE POLICY "Users can view own logs" ON processing_logs
    FOR SELECT 
    USING (auth.uid() = user_id AND auth.uid() IS NOT NULL);

CREATE POLICY "Users can create own logs" ON processing_logs
    FOR INSERT 
    WITH CHECK (auth.uid() = user_id AND auth.uid() IS NOT NULL);

-- Service role can manage all logs for debugging
CREATE POLICY "Service role can manage logs" ON processing_logs
    FOR ALL 
    USING (auth.jwt() ->> 'role' = 'service_role')
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

-- Enhanced webhook logs policies
CREATE POLICY "Users can view own webhook logs" ON webhook_logs
    FOR SELECT 
    USING (auth.uid() = user_id AND auth.uid() IS NOT NULL);

CREATE POLICY "Users can create own webhook logs" ON webhook_logs
    FOR INSERT 
    WITH CHECK (auth.uid() = user_id AND auth.uid() IS NOT NULL);

-- Service role can manage all webhook logs for system operations
CREATE POLICY "Service role can manage webhook logs" ON webhook_logs
    FOR ALL 
    USING (auth.jwt() ->> 'role' = 'service_role')
    WITH CHECK (auth.jwt() ->> 'role' = 'service_role');

-- =====================================================
-- USER TIER READ ACCESS
-- =====================================================

-- Allow authenticated users to read user tier information
-- This is needed for the frontend to display tier limits
CREATE POLICY "Authenticated users can view tiers" ON user_tiers
    FOR SELECT 
    USING (auth.role() = 'authenticated');

-- =====================================================
-- ENHANCED SECURITY FUNCTIONS
-- =====================================================

-- Function to check if user can access a specific job
CREATE OR REPLACE FUNCTION user_can_access_job(job_uuid UUID)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check if user owns the job or has service role
    RETURN EXISTS (
        SELECT 1 FROM bulk_jobs 
        WHERE id = job_uuid 
        AND (user_id = auth.uid() OR auth.jwt() ->> 'role' = 'service_role')
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user can access a specific task
CREATE OR REPLACE FUNCTION user_can_access_task(task_uuid UUID)
RETURNS BOOLEAN AS $$
BEGIN
    -- Check if user owns the task or has service role
    RETURN EXISTS (
        SELECT 1 FROM video_tasks 
        WHERE id = task_uuid 
        AND (user_id = auth.uid() OR auth.jwt() ->> 'role' = 'service_role')
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get user's current tier limits
CREATE OR REPLACE FUNCTION get_user_tier_limits(user_uuid UUID DEFAULT auth.uid())
RETURNS TABLE (
    tier_name VARCHAR(50),
    max_videos_per_job INTEGER,
    max_jobs_per_month INTEGER,
    max_concurrent_jobs INTEGER,
    max_video_duration_minutes INTEGER,
    priority_processing BOOLEAN,
    webhook_support BOOLEAN,
    api_access BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ut.name,
        ut.max_videos_per_job,
        ut.max_jobs_per_month,
        ut.max_concurrent_jobs,
        ut.max_video_duration_minutes,
        ut.priority_processing,
        ut.webhook_support,
        ut.api_access
    FROM user_profiles up
    JOIN user_tiers ut ON up.tier_id = ut.id
    WHERE up.id = user_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check user's current usage against limits
CREATE OR REPLACE FUNCTION check_user_limits(
    user_uuid UUID DEFAULT auth.uid(),
    requested_videos INTEGER DEFAULT 0
)
RETURNS TABLE (
    within_limits BOOLEAN,
    videos_this_month INTEGER,
    jobs_this_month INTEGER,
    active_jobs INTEGER,
    tier_max_videos INTEGER,
    tier_max_jobs INTEGER,
    tier_max_concurrent INTEGER
) AS $$
DECLARE
    v_profile RECORD;
    v_tier RECORD;
    v_active_jobs INTEGER;
BEGIN
    -- Get user profile and tier
    SELECT up.*, ut.* INTO v_profile, v_tier
    FROM user_profiles up
    JOIN user_tiers ut ON up.tier_id = ut.id
    WHERE up.id = user_uuid;
    
    -- Count active jobs
    SELECT COUNT(*) INTO v_active_jobs
    FROM bulk_jobs
    WHERE user_id = user_uuid
    AND status IN ('pending', 'queued', 'processing');
    
    -- Return check results
    RETURN QUERY SELECT
        (requested_videos <= v_tier.max_videos_per_job AND
         v_profile.jobs_created_this_month < v_tier.max_jobs_per_month AND
         v_active_jobs < v_tier.max_concurrent_jobs) as within_limits,
        v_profile.videos_processed_this_month,
        v_profile.jobs_created_this_month,
        v_active_jobs,
        v_tier.max_videos_per_job,
        v_tier.max_jobs_per_month,
        v_tier.max_concurrent_jobs;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- AUDIT AND MONITORING
-- =====================================================

-- Create audit log table for security monitoring
CREATE TABLE IF NOT EXISTS auth_audit_log (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for audit log queries
CREATE INDEX IF NOT EXISTS idx_auth_audit_log_user_created 
ON auth_audit_log(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_audit_log_action_created 
ON auth_audit_log(action, created_at DESC);

-- Function to log authentication events
CREATE OR REPLACE FUNCTION log_auth_event(
    p_user_id UUID,
    p_action VARCHAR(100),
    p_resource_type VARCHAR(50) DEFAULT NULL,
    p_resource_id VARCHAR(255) DEFAULT NULL,
    p_success BOOLEAN DEFAULT true,
    p_error_message TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'
)
RETURNS UUID AS $$
DECLARE
    v_log_id UUID;
BEGIN
    INSERT INTO auth_audit_log (
        user_id, action, resource_type, resource_id, 
        success, error_message, metadata
    ) VALUES (
        p_user_id, p_action, p_resource_type, p_resource_id,
        p_success, p_error_message, p_metadata
    ) RETURNING id INTO v_log_id;
    
    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Enable RLS on audit log
ALTER TABLE auth_audit_log ENABLE ROW LEVEL SECURITY;

-- Only service role can read audit logs (for security monitoring)
CREATE POLICY "Service role can view audit logs" ON auth_audit_log
    FOR SELECT 
    USING (auth.jwt() ->> 'role' = 'service_role');

-- Anyone can create audit logs (for logging purposes)
CREATE POLICY "System can create audit logs" ON auth_audit_log
    FOR INSERT 
    WITH CHECK (true);

-- =====================================================
-- REFRESH REALTIME SUBSCRIPTIONS
-- =====================================================

-- Ensure realtime is enabled for the new audit table
ALTER PUBLICATION supabase_realtime ADD TABLE auth_audit_log;

COMMENT ON TABLE auth_audit_log IS 'Audit log for authentication and authorization events';
COMMENT ON FUNCTION get_user_tier_limits IS 'Get current user tier limits and features';
COMMENT ON FUNCTION check_user_limits IS 'Check if user is within their subscription limits';
COMMENT ON FUNCTION user_can_access_job IS 'Check if user can access a specific bulk job';
COMMENT ON FUNCTION user_can_access_task IS 'Check if user can access a specific video task';