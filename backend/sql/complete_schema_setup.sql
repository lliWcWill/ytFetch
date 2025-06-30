-- Complete Schema Setup for ytFetch
-- Run this entire file in Supabase SQL Editor

-- =====================================================
-- PART 1: TOKEN SYSTEM (for the new payment model)
-- =====================================================

-- User profiles table (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User token balances table
CREATE TABLE IF NOT EXISTS user_token_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    lifetime_purchased INTEGER NOT NULL DEFAULT 0,
    lifetime_spent INTEGER NOT NULL DEFAULT 0,
    last_purchase_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Token transactions table (purchase, usage, refund, bonus)
CREATE TABLE IF NOT EXISTS token_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL, -- positive for purchases/refunds, negative for usage
    type TEXT NOT NULL CHECK (type IN ('purchase', 'usage', 'refund', 'bonus')),
    description TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    stripe_session_id TEXT, -- for purchase transactions
    stripe_payment_intent TEXT, -- for purchase transactions
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for token tables
CREATE INDEX IF NOT EXISTS idx_token_transactions_user_id ON token_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_token_transactions_created_at ON token_transactions(created_at DESC);

-- =====================================================
-- PART 2: GUEST ACCESS SYSTEM
-- =====================================================

-- Guest usage tracking
CREATE TABLE IF NOT EXISTS guest_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('unofficial', 'groq', 'bulk')),
    ip_address INET,
    video_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Index for fast lookups
    INDEX idx_guest_session_method (session_id, method),
    INDEX idx_guest_created_at (created_at)
);

-- Guest limits configuration
CREATE TABLE IF NOT EXISTS guest_limits (
    id INTEGER PRIMARY KEY DEFAULT 1,
    unofficial_limit INTEGER DEFAULT 10,
    groq_limit INTEGER DEFAULT 10,
    bulk_limit INTEGER DEFAULT 50,
    reset_period_hours INTEGER DEFAULT 24,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default guest limits
INSERT INTO guest_limits (unofficial_limit, groq_limit, bulk_limit) 
VALUES (10, 10, 50)
ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- PART 3: ROW LEVEL SECURITY
-- =====================================================

-- Enable RLS on all new tables
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_token_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE guest_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE guest_limits ENABLE ROW LEVEL SECURITY;

-- User profiles policies
CREATE POLICY "Users can view their own profile" ON user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile" ON user_profiles
    FOR UPDATE USING (auth.uid() = id);

-- Token balances policies
CREATE POLICY "Users can view their own balance" ON user_token_balances
    FOR SELECT USING (auth.uid() = user_id);

-- Token transactions policies  
CREATE POLICY "Users can view their own transactions" ON token_transactions
    FOR SELECT USING (auth.uid() = user_id);

-- Guest tables are managed by service role only
CREATE POLICY "Service role manages guest data" ON guest_usage
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role manages guest limits" ON guest_limits
    FOR ALL USING (auth.role() = 'service_role');

-- =====================================================
-- PART 4: FUNCTIONS FOR TOKEN SYSTEM
-- =====================================================

-- Function to use tokens (atomic operation)
CREATE OR REPLACE FUNCTION use_tokens(
    p_user_id UUID,
    p_amount INTEGER,
    p_description TEXT,
    p_metadata JSONB DEFAULT '{}'
) RETURNS user_token_balances AS $$
DECLARE
    v_balance user_token_balances;
BEGIN
    -- Lock the balance row for update
    SELECT * INTO v_balance
    FROM user_token_balances
    WHERE user_id = p_user_id
    FOR UPDATE;
    
    -- Check if user has sufficient balance
    IF v_balance.balance IS NULL OR v_balance.balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient token balance';
    END IF;
    
    -- Update the balance
    UPDATE user_token_balances
    SET 
        balance = balance - p_amount,
        lifetime_spent = lifetime_spent + p_amount,
        updated_at = NOW()
    WHERE user_id = p_user_id
    RETURNING * INTO v_balance;
    
    -- Record the transaction
    INSERT INTO token_transactions (
        user_id, 
        amount, 
        type, 
        description, 
        metadata
    ) VALUES (
        p_user_id, 
        -p_amount, 
        'usage', 
        p_description, 
        p_metadata
    );
    
    RETURN v_balance;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to add tokens (for purchases, refunds, bonuses)
CREATE OR REPLACE FUNCTION add_tokens(
    p_user_id UUID,
    p_amount INTEGER,
    p_type TEXT,
    p_description TEXT,
    p_metadata JSONB DEFAULT '{}',
    p_stripe_session_id TEXT DEFAULT NULL,
    p_stripe_payment_intent TEXT DEFAULT NULL
) RETURNS user_token_balances AS $$
DECLARE
    v_balance user_token_balances;
BEGIN
    -- Ensure balance record exists
    INSERT INTO user_token_balances (user_id, balance, lifetime_purchased, lifetime_spent)
    VALUES (p_user_id, 0, 0, 0)
    ON CONFLICT (user_id) DO NOTHING;
    
    -- Lock and update the balance
    UPDATE user_token_balances
    SET 
        balance = balance + p_amount,
        lifetime_purchased = CASE 
            WHEN p_type = 'purchase' THEN lifetime_purchased + p_amount 
            ELSE lifetime_purchased 
        END,
        last_purchase_at = CASE 
            WHEN p_type = 'purchase' THEN NOW() 
            ELSE last_purchase_at 
        END,
        updated_at = NOW()
    WHERE user_id = p_user_id
    RETURNING * INTO v_balance;
    
    -- Record the transaction
    INSERT INTO token_transactions (
        user_id, 
        amount, 
        type, 
        description, 
        metadata,
        stripe_session_id,
        stripe_payment_intent
    ) VALUES (
        p_user_id, 
        p_amount, 
        p_type, 
        p_description, 
        p_metadata,
        p_stripe_session_id,
        p_stripe_payment_intent
    );
    
    RETURN v_balance;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- PART 5: AUTO-CREATE USER PROFILE ON SIGNUP
-- =====================================================

-- Trigger to auto-create user profile on signup
CREATE OR REPLACE FUNCTION handle_new_user() 
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_profiles (id, email, full_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        NEW.raw_user_meta_data->>'full_name',
        NEW.raw_user_meta_data->>'avatar_url'
    )
    ON CONFLICT (id) DO NOTHING;
    
    -- Also create initial token balance
    INSERT INTO user_token_balances (user_id, balance, lifetime_purchased, lifetime_spent)
    VALUES (NEW.id, 0, 0, 0)
    ON CONFLICT (user_id) DO NOTHING;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger for new user signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION handle_new_user();

-- =====================================================
-- PART 6: CLEAN UP OLD GUEST DATA
-- =====================================================

-- Function to clean up old guest sessions
CREATE OR REPLACE FUNCTION cleanup_old_guest_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM guest_usage 
    WHERE created_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job (if you have pg_cron extension)
-- Uncomment if pg_cron is available:
-- SELECT cron.schedule('cleanup-guest-sessions', '0 3 * * *', 'SELECT cleanup_old_guest_sessions();');

-- =====================================================
-- PART 7: GRANT PERMISSIONS
-- =====================================================

-- Grant necessary permissions to authenticated users
GRANT SELECT ON user_profiles TO authenticated;
GRANT SELECT ON user_token_balances TO authenticated;
GRANT SELECT ON token_transactions TO authenticated;
GRANT EXECUTE ON FUNCTION use_tokens TO authenticated;
GRANT EXECUTE ON FUNCTION add_tokens TO authenticated;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify all tables were created
SELECT 
    'Tables created:' as status,
    COUNT(*) as table_count
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'user_profiles', 
    'user_token_balances', 
    'token_transactions',
    'guest_usage',
    'guest_limits'
);

-- Show all tables in public schema
SELECT 
    tablename,
    CASE 
        WHEN tablename LIKE '%token%' THEN 'Token System'
        WHEN tablename LIKE '%guest%' THEN 'Guest Access'
        WHEN tablename IN ('bulk_jobs', 'video_tasks', 'user_tiers') THEN 'Bulk/Tier System'
        ELSE 'Other'
    END as system
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY system, tablename;