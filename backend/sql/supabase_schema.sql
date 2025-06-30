-- Supabase Database Schema for Bulk YouTube Downloads
-- This schema supports bulk download jobs, video tasks, user authentication,
-- real-time updates, and monetization through user tiers

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_cron";

-- =====================================================
-- USER TIERS TABLE
-- =====================================================
-- Defines different subscription tiers for monetization
CREATE TABLE IF NOT EXISTS user_tiers (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    -- Limits
    max_videos_per_job INTEGER NOT NULL DEFAULT 10,
    max_jobs_per_month INTEGER NOT NULL DEFAULT 5,
    max_concurrent_jobs INTEGER NOT NULL DEFAULT 1,
    max_video_duration_minutes INTEGER NOT NULL DEFAULT 30,
    -- Features
    priority_processing BOOLEAN DEFAULT false,
    webhook_support BOOLEAN DEFAULT false,
    api_access BOOLEAN DEFAULT false,
    -- Pricing
    price_monthly DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    price_yearly DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    -- Metadata
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default tiers
INSERT INTO user_tiers (name, display_name, description, max_videos_per_job, max_jobs_per_month, max_concurrent_jobs, max_video_duration_minutes, priority_processing, webhook_support, api_access, price_monthly, price_yearly) VALUES
('free', 'Free', 'Basic access with limited features', 5, 10, 1, 15, false, false, false, 0.00, 0.00),
('starter', 'Starter', 'Great for individuals', 25, 50, 2, 60, false, false, true, 9.99, 99.99),
('pro', 'Professional', 'For power users and small teams', 100, 200, 5, 120, true, true, true, 29.99, 299.99),
('enterprise', 'Enterprise', 'Unlimited access with premium support', 1000, 10000, 20, 360, true, true, true, 99.99, 999.99);

-- =====================================================
-- USER PROFILES TABLE
-- =====================================================
-- Extends Supabase Auth with user-specific data
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    tier_id UUID REFERENCES user_tiers(id) DEFAULT (SELECT id FROM user_tiers WHERE name = 'free'),
    -- Usage tracking
    videos_processed_this_month INTEGER DEFAULT 0,
    jobs_created_this_month INTEGER DEFAULT 0,
    total_videos_processed INTEGER DEFAULT 0,
    total_jobs_created INTEGER DEFAULT 0,
    -- Subscription info
    subscription_status VARCHAR(20) DEFAULT 'active' CHECK (subscription_status IN ('active', 'cancelled', 'suspended', 'expired')),
    subscription_expires_at TIMESTAMPTZ,
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- BULK JOBS TABLE
-- =====================================================
-- Tracks bulk download jobs for playlists/channels
CREATE TABLE IF NOT EXISTS bulk_jobs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    -- Job details
    name VARCHAR(255) NOT NULL,
    description TEXT,
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('playlist', 'channel', 'search', 'url_list')),
    source_url TEXT NOT NULL,
    source_id VARCHAR(255), -- YouTube playlist/channel ID
    -- Progress tracking
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'processing', 'completed', 'failed', 'cancelled')),
    total_videos INTEGER DEFAULT 0,
    processed_videos INTEGER DEFAULT 0,
    successful_videos INTEGER DEFAULT 0,
    failed_videos INTEGER DEFAULT 0,
    progress_percentage DECIMAL(5,2) DEFAULT 0.00,
    -- Configuration
    download_video BOOLEAN DEFAULT false,
    download_audio BOOLEAN DEFAULT true,
    generate_transcript BOOLEAN DEFAULT true,
    transcript_format VARCHAR(20) DEFAULT 'json' CHECK (transcript_format IN ('json', 'srt', 'vtt', 'txt')),
    quality VARCHAR(20) DEFAULT 'highest' CHECK (quality IN ('highest', 'high', 'medium', 'low')),
    -- Webhook configuration
    webhook_url TEXT,
    webhook_events TEXT[], -- Array of events to trigger webhook
    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    -- Timestamps
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- VIDEO TASKS TABLE
-- =====================================================
-- Individual video processing tasks
CREATE TABLE IF NOT EXISTS video_tasks (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    job_id UUID REFERENCES bulk_jobs(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    -- Video information
    video_url TEXT NOT NULL,
    video_id VARCHAR(255) NOT NULL,
    title TEXT,
    duration_seconds INTEGER,
    channel_name TEXT,
    channel_id VARCHAR(255),
    upload_date DATE,
    -- Processing status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'downloading', 'transcribing', 'completed', 'failed', 'skipped')),
    progress_percentage DECIMAL(5,2) DEFAULT 0.00,
    current_step VARCHAR(50), -- e.g., 'downloading_video', 'extracting_audio', 'generating_transcript'
    -- File storage URLs (Supabase Storage)
    video_storage_url TEXT,
    audio_storage_url TEXT,
    transcript_storage_url TEXT,
    thumbnail_url TEXT,
    -- Processing details
    file_size_bytes BIGINT,
    processing_time_seconds INTEGER,
    -- Error handling
    error_message TEXT,
    error_code VARCHAR(50),
    retry_count INTEGER DEFAULT 0,
    -- Metadata
    metadata JSONB DEFAULT '{}', -- Store additional video metadata
    -- Timestamps
    queued_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- PROCESSING LOGS TABLE
-- =====================================================
-- Detailed logging for debugging and monitoring
CREATE TABLE IF NOT EXISTS processing_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    task_id UUID REFERENCES video_tasks(id) ON DELETE CASCADE,
    job_id UUID REFERENCES bulk_jobs(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    -- Log details
    log_level VARCHAR(20) NOT NULL CHECK (log_level IN ('debug', 'info', 'warning', 'error', 'critical')),
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- WEBHOOKS LOG TABLE
-- =====================================================
-- Track webhook deliveries and retries
CREATE TABLE IF NOT EXISTS webhook_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    job_id UUID REFERENCES bulk_jobs(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    -- Webhook details
    webhook_url TEXT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    -- Delivery status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'success', 'failed', 'retrying')),
    http_status_code INTEGER,
    response_body TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    -- Timestamps
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Bulk jobs indexes
CREATE INDEX idx_bulk_jobs_user_id ON bulk_jobs(user_id);
CREATE INDEX idx_bulk_jobs_status ON bulk_jobs(status);
CREATE INDEX idx_bulk_jobs_created_at ON bulk_jobs(created_at DESC);
CREATE INDEX idx_bulk_jobs_user_status ON bulk_jobs(user_id, status);

-- Video tasks indexes
CREATE INDEX idx_video_tasks_job_id ON video_tasks(job_id);
CREATE INDEX idx_video_tasks_user_id ON video_tasks(user_id);
CREATE INDEX idx_video_tasks_status ON video_tasks(status);
CREATE INDEX idx_video_tasks_video_id ON video_tasks(video_id);
CREATE INDEX idx_video_tasks_created_at ON video_tasks(created_at DESC);
CREATE INDEX idx_video_tasks_job_status ON video_tasks(job_id, status);

-- Processing logs indexes
CREATE INDEX idx_processing_logs_task_id ON processing_logs(task_id);
CREATE INDEX idx_processing_logs_job_id ON processing_logs(job_id);
CREATE INDEX idx_processing_logs_created_at ON processing_logs(created_at DESC);

-- User profiles indexes
CREATE INDEX idx_user_profiles_tier_id ON user_profiles(tier_id);
CREATE INDEX idx_user_profiles_subscription_status ON user_profiles(subscription_status);

-- =====================================================
-- FUNCTIONS AND TRIGGERS
-- =====================================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply timestamp update triggers
CREATE TRIGGER update_bulk_jobs_updated_at BEFORE UPDATE ON bulk_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_video_tasks_updated_at BEFORE UPDATE ON video_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_tiers_updated_at BEFORE UPDATE ON user_tiers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to automatically update job progress
CREATE OR REPLACE FUNCTION update_job_progress()
RETURNS TRIGGER AS $$
DECLARE
    v_total_videos INTEGER;
    v_processed_videos INTEGER;
    v_successful_videos INTEGER;
    v_failed_videos INTEGER;
    v_progress DECIMAL(5,2);
    v_all_completed BOOLEAN;
BEGIN
    -- Get video task statistics for the job
    SELECT 
        COUNT(*),
        COUNT(*) FILTER (WHERE status IN ('completed', 'failed', 'skipped')),
        COUNT(*) FILTER (WHERE status = 'completed'),
        COUNT(*) FILTER (WHERE status = 'failed')
    INTO 
        v_total_videos,
        v_processed_videos,
        v_successful_videos,
        v_failed_videos
    FROM video_tasks
    WHERE job_id = COALESCE(NEW.job_id, OLD.job_id);
    
    -- Calculate progress percentage
    IF v_total_videos > 0 THEN
        v_progress := (v_processed_videos::DECIMAL / v_total_videos) * 100;
    ELSE
        v_progress := 0;
    END IF;
    
    -- Check if all videos are processed
    v_all_completed := v_processed_videos = v_total_videos AND v_total_videos > 0;
    
    -- Update the bulk job
    UPDATE bulk_jobs
    SET 
        total_videos = v_total_videos,
        processed_videos = v_processed_videos,
        successful_videos = v_successful_videos,
        failed_videos = v_failed_videos,
        progress_percentage = v_progress,
        status = CASE 
            WHEN v_all_completed AND v_failed_videos = 0 THEN 'completed'
            WHEN v_all_completed AND v_failed_videos > 0 THEN 'completed'
            WHEN status = 'cancelled' THEN 'cancelled'
            WHEN v_processed_videos > 0 THEN 'processing'
            ELSE status
        END,
        completed_at = CASE 
            WHEN v_all_completed THEN NOW()
            ELSE completed_at
        END
    WHERE id = COALESCE(NEW.job_id, OLD.job_id);
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update job progress when video tasks change
CREATE TRIGGER update_job_progress_on_task_change
AFTER INSERT OR UPDATE OR DELETE ON video_tasks
    FOR EACH ROW EXECUTE FUNCTION update_job_progress();

-- Function to create user profile on signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_profiles (id, tier_id)
    VALUES (NEW.id, (SELECT id FROM user_tiers WHERE name = 'free'));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to create profile for new users
CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Function to reset monthly usage counters
CREATE OR REPLACE FUNCTION reset_monthly_usage()
RETURNS void AS $$
BEGIN
    UPDATE user_profiles
    SET 
        videos_processed_this_month = 0,
        jobs_created_this_month = 0
    WHERE subscription_status = 'active';
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE bulk_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_logs ENABLE ROW LEVEL SECURITY;

-- User profiles policies
CREATE POLICY "Users can view own profile" ON user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON user_profiles
    FOR UPDATE USING (auth.uid() = id);

-- Bulk jobs policies
CREATE POLICY "Users can view own jobs" ON bulk_jobs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own jobs" ON bulk_jobs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own jobs" ON bulk_jobs
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own jobs" ON bulk_jobs
    FOR DELETE USING (auth.uid() = user_id);

-- Video tasks policies
CREATE POLICY "Users can view own tasks" ON video_tasks
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own tasks" ON video_tasks
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own tasks" ON video_tasks
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own tasks" ON video_tasks
    FOR DELETE USING (auth.uid() = user_id);

-- Processing logs policies
CREATE POLICY "Users can view own logs" ON processing_logs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own logs" ON processing_logs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Webhook logs policies
CREATE POLICY "Users can view own webhook logs" ON webhook_logs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own webhook logs" ON webhook_logs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- =====================================================
-- VIEWS FOR EASIER QUERYING
-- =====================================================

-- Job summary view
CREATE OR REPLACE VIEW job_summaries AS
SELECT 
    j.id,
    j.user_id,
    j.name,
    j.source_type,
    j.status,
    j.total_videos,
    j.processed_videos,
    j.successful_videos,
    j.failed_videos,
    j.progress_percentage,
    j.created_at,
    j.completed_at,
    u.tier_id,
    t.name as tier_name,
    t.display_name as tier_display_name
FROM bulk_jobs j
JOIN user_profiles u ON j.user_id = u.id
JOIN user_tiers t ON u.tier_id = t.id;

-- =====================================================
-- STORED PROCEDURES
-- =====================================================

-- Procedure to check user limits before creating a job
CREATE OR REPLACE FUNCTION check_user_limits(p_user_id UUID, p_video_count INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    v_tier_id UUID;
    v_max_videos_per_job INTEGER;
    v_max_jobs_per_month INTEGER;
    v_max_concurrent_jobs INTEGER;
    v_jobs_this_month INTEGER;
    v_active_jobs INTEGER;
BEGIN
    -- Get user's tier and limits
    SELECT 
        up.tier_id,
        ut.max_videos_per_job,
        ut.max_jobs_per_month,
        ut.max_concurrent_jobs,
        up.jobs_created_this_month
    INTO 
        v_tier_id,
        v_max_videos_per_job,
        v_max_jobs_per_month,
        v_max_concurrent_jobs,
        v_jobs_this_month
    FROM user_profiles up
    JOIN user_tiers ut ON up.tier_id = ut.id
    WHERE up.id = p_user_id;
    
    -- Count active jobs
    SELECT COUNT(*)
    INTO v_active_jobs
    FROM bulk_jobs
    WHERE user_id = p_user_id
    AND status IN ('pending', 'queued', 'processing');
    
    -- Check limits
    IF p_video_count > v_max_videos_per_job THEN
        RAISE EXCEPTION 'Video count exceeds tier limit of % videos per job', v_max_videos_per_job;
    END IF;
    
    IF v_jobs_this_month >= v_max_jobs_per_month THEN
        RAISE EXCEPTION 'Monthly job limit of % reached', v_max_jobs_per_month;
    END IF;
    
    IF v_active_jobs >= v_max_concurrent_jobs THEN
        RAISE EXCEPTION 'Concurrent job limit of % reached', v_max_concurrent_jobs;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- REALTIME SUBSCRIPTIONS SETUP
-- =====================================================

-- Enable realtime for job status updates
ALTER PUBLICATION supabase_realtime ADD TABLE bulk_jobs;
ALTER PUBLICATION supabase_realtime ADD TABLE video_tasks;

-- =====================================================
-- SCHEDULED JOBS (using pg_cron)
-- =====================================================

-- Schedule monthly usage reset (runs at midnight on the 1st of each month)
SELECT cron.schedule(
    'reset-monthly-usage',
    '0 0 1 * *',
    'SELECT reset_monthly_usage();'
);

-- =====================================================
-- SAMPLE QUERIES FOR COMMON OPERATIONS
-- =====================================================

/*
-- Create a new bulk job
INSERT INTO bulk_jobs (user_id, name, source_type, source_url, source_id)
VALUES (auth.uid(), 'My Playlist', 'playlist', 'https://youtube.com/playlist?list=...', 'PLxxxxxxx')
RETURNING *;

-- Add video tasks for a job
INSERT INTO video_tasks (job_id, user_id, video_url, video_id)
VALUES 
    ('job-uuid', auth.uid(), 'https://youtube.com/watch?v=xxx1', 'xxx1'),
    ('job-uuid', auth.uid(), 'https://youtube.com/watch?v=xxx2', 'xxx2');

-- Get job progress with tasks
SELECT 
    j.*,
    ARRAY_AGG(
        JSON_BUILD_OBJECT(
            'id', t.id,
            'video_id', t.video_id,
            'title', t.title,
            'status', t.status,
            'progress', t.progress_percentage
        ) ORDER BY t.created_at
    ) as tasks
FROM bulk_jobs j
LEFT JOIN video_tasks t ON j.id = t.job_id
WHERE j.user_id = auth.uid()
GROUP BY j.id;

-- Subscribe to real-time updates for a job
-- Use Supabase client: 
-- supabase.from('bulk_jobs').on('UPDATE', payload => {...}).subscribe()
*/