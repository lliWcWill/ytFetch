-- Add missing columns to user_profiles table for compatibility
-- This allows the usage_service to work with the current schema

-- Check current columns
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_profiles' 
AND table_schema = 'public'
ORDER BY ordinal_position;

-- Add missing columns if they don't exist
ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS tier_id UUID,
ADD COLUMN IF NOT EXISTS usage_data JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT,
ADD COLUMN IF NOT EXISTS videos_processed_this_month INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS jobs_created_this_month INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS transcription_minutes_this_month INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_usage_reset_at TIMESTAMPTZ DEFAULT NOW();

-- Create or update the tiers table
CREATE TABLE IF NOT EXISTS tiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    monthly_videos INTEGER NOT NULL,
    monthly_jobs INTEGER NOT NULL,
    monthly_transcription_minutes INTEGER NOT NULL,
    price_monthly DECIMAL(10, 2),
    price_yearly DECIMAL(10, 2),
    features JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default tiers if they don't exist
INSERT INTO tiers (name, display_name, monthly_videos, monthly_jobs, monthly_transcription_minutes, price_monthly, price_yearly, features)
VALUES 
    ('free', 'Free', 20, 20, 60, 0, 0, '["10 unofficial transcriptions/month", "10 Groq transcriptions/month", "Basic support"]'),
    ('pro', 'Pro', 200, 200, 600, 19, 190, '["200 videos/month", "600 minutes transcription", "Priority support", "All export formats"]'),
    ('unlimited', 'Unlimited', 999999, 999999, 999999, 49, 490, '["Unlimited videos", "Unlimited transcription", "Premium support", "API access"]')
ON CONFLICT (name) DO NOTHING;

-- Get the free tier ID
DO $$
DECLARE
    free_tier_id UUID;
BEGIN
    SELECT id INTO free_tier_id FROM tiers WHERE name = 'free';
    
    -- Update all user profiles to have the free tier by default
    UPDATE user_profiles 
    SET tier_id = free_tier_id 
    WHERE tier_id IS NULL;
END $$;

-- Add foreign key constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'user_profiles_tier_id_fkey' 
        AND table_name = 'user_profiles'
    ) THEN
        ALTER TABLE user_profiles 
        ADD CONSTRAINT user_profiles_tier_id_fkey 
        FOREIGN KEY (tier_id) REFERENCES tiers(id);
    END IF;
END $$;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_profiles_tier_id ON user_profiles(tier_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_stripe_customer_id ON user_profiles(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- Verify the changes
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_profiles' 
AND table_schema = 'public'
ORDER BY ordinal_position;