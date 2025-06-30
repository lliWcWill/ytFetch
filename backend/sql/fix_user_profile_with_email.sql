-- Fix User Profile Creation with Email
-- This handles the NOT NULL constraint on email column

-- First, get the user's email from auth.users
DO $$
DECLARE
    user_email TEXT;
    user_exists BOOLEAN;
    profile_exists BOOLEAN;
BEGIN
    -- Check if profile already exists
    SELECT EXISTS (
        SELECT 1 FROM user_profiles 
        WHERE id = '17a939d6-bc4d-4225-afbc-bf22ac626dd7'
    ) INTO profile_exists;
    
    IF NOT profile_exists THEN
        -- Get user's email from auth.users
        SELECT email INTO user_email
        FROM auth.users 
        WHERE id = '17a939d6-bc4d-4225-afbc-bf22ac626dd7';
        
        IF user_email IS NOT NULL THEN
            -- Insert profile with email
            INSERT INTO public.user_profiles (id, email, full_name, avatar_url)
            VALUES (
                '17a939d6-bc4d-4225-afbc-bf22ac626dd7',
                user_email,
                '',  -- empty string for full_name
                ''   -- empty string for avatar_url
            );
            
            RAISE NOTICE 'Created profile for user % with email %', '17a939d6-bc4d-4225-afbc-bf22ac626dd7', user_email;
        ELSE
            RAISE NOTICE 'User not found in auth.users';
        END IF;
    ELSE
        RAISE NOTICE 'Profile already exists for user 17a939d6-bc4d-4225-afbc-bf22ac626dd7';
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
END $$;

-- Update the trigger function to handle email properly
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Insert profile with email from auth.users
    INSERT INTO public.user_profiles (id, email, full_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
        COALESCE(NEW.raw_user_meta_data->>'avatar_url', '')
    );
    
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

-- Ensure the trigger exists
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- Grant necessary permissions
GRANT EXECUTE ON FUNCTION public.handle_new_user() TO service_role;

-- Verify the profile was created
SELECT * FROM user_profiles WHERE id = '17a939d6-bc4d-4225-afbc-bf22ac626dd7';