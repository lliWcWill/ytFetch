-- Fix schema cache issue and ensure bulk_jobs table has all required columns

-- First, let's check what columns exist
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'bulk_jobs'
ORDER BY ordinal_position;

-- Notify PostgREST to reload schema cache
NOTIFY pgrst, 'reload schema';

-- Alternative: You may need to restart the PostgREST service or 
-- clear the schema cache through Supabase dashboard