-- Create a simpler bulk_jobs table that matches what the API expects

-- Drop the existing table if you want to start fresh (BE CAREFUL - this will delete data!)
-- DROP TABLE IF EXISTS video_tasks CASCADE;
-- DROP TABLE IF EXISTS bulk_jobs CASCADE;

-- Create the simplified bulk_jobs table
CREATE TABLE IF NOT EXISTS bulk_jobs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL, -- Can be a real user ID or guest UUID
    source_url TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    total_videos INTEGER DEFAULT 0,
    completed_videos INTEGER DEFAULT 0,
    failed_videos INTEGER DEFAULT 0,
    transcript_method VARCHAR(20) DEFAULT 'unofficial',
    output_format VARCHAR(20) DEFAULT 'txt',
    user_tier VARCHAR(20) DEFAULT 'free',
    webhook_url TEXT,
    zip_file_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Create video_tasks table if it doesn't exist
CREATE TABLE IF NOT EXISTS video_tasks (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    job_id UUID REFERENCES bulk_jobs(id) ON DELETE CASCADE NOT NULL,
    user_id UUID NOT NULL,
    video_id VARCHAR(255) NOT NULL,
    title TEXT,
    video_url TEXT NOT NULL,
    duration INTEGER,
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_user_id ON bulk_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_status ON bulk_jobs(status);
CREATE INDEX IF NOT EXISTS idx_video_tasks_job_id ON video_tasks(job_id);
CREATE INDEX IF NOT EXISTS idx_video_tasks_status ON video_tasks(status);

-- Grant permissions (adjust based on your needs)
GRANT ALL ON bulk_jobs TO postgres, authenticated, anon;
GRANT ALL ON video_tasks TO postgres, authenticated, anon;

-- Enable RLS if needed
-- ALTER TABLE bulk_jobs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE video_tasks ENABLE ROW LEVEL SECURITY;