-- Reset interrupted bulk job back to pending status
-- This allows the job to be restarted via the API

-- First, check the current state
SELECT id, status, total_videos, completed_videos, failed_videos 
FROM bulk_jobs 
WHERE id = 'd50af6ca-37e4-44e1-988e-48e9768c4d04';

-- Reset the job to pending (only if it's in processing state)
UPDATE bulk_jobs 
SET status = 'pending',
    updated_at = NOW()
WHERE id = 'd50af6ca-37e4-44e1-988e-48e9768c4d04'
  AND status = 'processing';

-- Verify the update
SELECT id, status, total_videos, completed_videos, failed_videos 
FROM bulk_jobs 
WHERE id = 'd50af6ca-37e4-44e1-988e-48e9768c4d04';