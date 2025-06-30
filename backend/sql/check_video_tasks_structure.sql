-- Check the structure of video_tasks table
\d video_tasks

-- Check column names
SELECT column_name, ordinal_position, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'video_tasks' 
ORDER BY ordinal_position;