-- Add missing columns to bulk_jobs table

-- Add user_tier column
ALTER TABLE bulk_jobs 
ADD COLUMN IF NOT EXISTS user_tier VARCHAR(20) DEFAULT 'free';

-- Add transcript_method column (the API uses this instead of generate_transcript boolean)
ALTER TABLE bulk_jobs 
ADD COLUMN IF NOT EXISTS transcript_method VARCHAR(20) DEFAULT 'unofficial' 
CHECK (transcript_method IN ('unofficial', 'groq', 'openai'));

-- Add output_format column (separate from transcript_format for API compatibility)
ALTER TABLE bulk_jobs 
ADD COLUMN IF NOT EXISTS output_format VARCHAR(20) DEFAULT 'txt' 
CHECK (output_format IN ('txt', 'srt', 'vtt', 'json'));

-- Update existing rows to have sensible defaults
UPDATE bulk_jobs 
SET 
    user_tier = 'free',
    transcript_method = CASE 
        WHEN generate_transcript = true THEN 'unofficial'
        ELSE 'unofficial'
    END,
    output_format = COALESCE(transcript_format, 'txt')
WHERE user_tier IS NULL OR transcript_method IS NULL OR output_format IS NULL;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_user_tier ON bulk_jobs(user_tier);
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_transcript_method ON bulk_jobs(transcript_method);