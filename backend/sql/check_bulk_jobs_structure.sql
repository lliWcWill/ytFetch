-- Check the structure of bulk_jobs table
\d bulk_jobs

-- Check column order
SELECT column_name, ordinal_position, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'bulk_jobs' 
ORDER BY ordinal_position;