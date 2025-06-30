-- Fix bulk_jobs table schema by adding missing columns
ALTER TABLE bulk_jobs 
ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}',
ADD COLUMN IF NOT EXISTS webhook_url text,
ADD COLUMN IF NOT EXISTS max_videos integer,
ADD COLUMN IF NOT EXISTS retry_settings jsonb DEFAULT '{"max_retries": 3, "retry_delay": 10}';

-- Verify the changes
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'bulk_jobs'
ORDER BY ordinal_position;