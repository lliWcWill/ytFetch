-- Update guest bulk video limit from 50 to 65
UPDATE guest_limits 
SET limit_value = 65,
    description = 'Maximum bulk videos for guests (one-time demo) - increased from 50'
WHERE limit_type = 'bulk_videos';

-- Verify the update
SELECT * FROM guest_limits WHERE limit_type = 'bulk_videos';