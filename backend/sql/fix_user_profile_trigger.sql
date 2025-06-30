-- Fix User Profile Creation Trigger for ytFetch
-- This ensures new users get a profile created automatically on signup

-- First, let's check the current table structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'user_profiles' 
AND table_schema = 'public'
ORDER BY ordinal_position;

-- Drop the existing trigger and function to recreate them
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_new_user();

-- Create a function that works with the current table structure
-- This version only inserts fields that exist in the table
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    default_tier_id UUID;
    tier_exists BOOLEAN;
    has_email_column BOOLEAN;
    has_tier_column BOOLEAN;
BEGIN
    -- Check which columns exist in user_profiles
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_profiles' 
        AND column_name = 'email'
        AND table_schema = 'public'
    ) INTO has_email_column;
    
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_profiles' 
        AND column_name = 'tier_id'
        AND table_schema = 'public'
    ) INTO has_tier_column;

    -- Handle tier-based system if tier_id column exists
    IF has_tier_column THEN
        -- Check if tiers table exists
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'tiers' 
            AND table_schema = 'public'
        ) INTO tier_exists;
        
        IF tier_exists THEN
            -- Get the default 'free' tier ID
            SELECT id INTO default_tier_id 
            FROM tiers 
            WHERE name = 'free' 
            LIMIT 1;
        END IF;
        
        -- Insert with tier_id
        INSERT INTO public.user_profiles (id, tier_id)
        VALUES (NEW.id, COALESCE(default_tier_id, NULL));
    ELSIF has_email_column THEN
        -- Insert with email-based structure
        INSERT INTO public.user_profiles (id, email, full_name, avatar_url)
        VALUES (
            NEW.id,
            NEW.email,
            COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
            COALESCE(NEW.raw_user_meta_data->>'avatar_url', '')
        );
    ELSE
        -- Minimal insert with just ID
        INSERT INTO public.user_profiles (id)
        VALUES (NEW.id);
    END IF;
    
    -- Also create token balance entry if table exists
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'user_token_balances' 
        AND table_schema = 'public'
    ) THEN
        INSERT INTO public.user_token_balances (user_id, balance)
        VALUES (NEW.id, 0)
        ON CONFLICT (user_id) DO NOTHING;
    END IF;
    
    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        -- Log the error but don't fail the signup
        RAISE LOG 'Error in handle_new_user: %', SQLERRM;
        RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Recreate the trigger
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- Grant necessary permissions
GRANT EXECUTE ON FUNCTION public.handle_new_user() TO service_role;

-- Fix existing user who doesn't have a profile
-- Insert profile for user 17a939d6-bc4d-4225-afbc-bf22ac626dd7
DO $$
DECLARE
    user_exists BOOLEAN;
    profile_exists BOOLEAN;
    default_tier_id UUID;
    has_tier_column BOOLEAN;
BEGIN
    -- Check if user exists
    SELECT EXISTS (
        SELECT 1 FROM auth.users 
        WHERE id = '17a939d6-bc4d-4225-afbc-bf22ac626dd7'
    ) INTO user_exists;
    
    -- Check if profile exists
    SELECT EXISTS (
        SELECT 1 FROM user_profiles 
        WHERE id = '17a939d6-bc4d-4225-afbc-bf22ac626dd7'
    ) INTO profile_exists;
    
    -- Check if tier_id column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_profiles' 
        AND column_name = 'tier_id'
        AND table_schema = 'public'
    ) INTO has_tier_column;
    
    IF user_exists AND NOT profile_exists THEN
        IF has_tier_column THEN
            -- Get free tier ID
            SELECT id INTO default_tier_id 
            FROM tiers 
            WHERE name = 'free' 
            LIMIT 1;
            
            -- Insert with tier
            INSERT INTO public.user_profiles (id, tier_id)
            VALUES ('17a939d6-bc4d-4225-afbc-bf22ac626dd7', default_tier_id);
        ELSE
            -- Insert minimal profile
            INSERT INTO public.user_profiles (id)
            VALUES ('17a939d6-bc4d-4225-afbc-bf22ac626dd7');
        END IF;
        
        -- Also create token balance if needed
        IF EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'user_token_balances' 
            AND table_schema = 'public'
        ) THEN
            INSERT INTO public.user_token_balances (user_id, balance)
            VALUES ('17a939d6-bc4d-4225-afbc-bf22ac626dd7', 0)
            ON CONFLICT (user_id) DO NOTHING;
        END IF;
        
        RAISE NOTICE 'Created profile for user 17a939d6-bc4d-4225-afbc-bf22ac626dd7';
    ELSIF profile_exists THEN
        RAISE NOTICE 'Profile already exists for user 17a939d6-bc4d-4225-afbc-bf22ac626dd7';
    ELSE
        RAISE NOTICE 'User 17a939d6-bc4d-4225-afbc-bf22ac626dd7 not found in auth.users';
    END IF;
END $$;

-- Test the function
SELECT * FROM user_profiles WHERE id = '17a939d6-bc4d-4225-afbc-bf22ac626dd7';