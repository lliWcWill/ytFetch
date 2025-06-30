-- Token-based payment system schema

-- User profiles table (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User token balances
CREATE TABLE IF NOT EXISTS user_token_balances (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    lifetime_purchased INTEGER NOT NULL DEFAULT 0,
    lifetime_spent INTEGER NOT NULL DEFAULT 0,
    last_purchase_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Token transactions
CREATE TABLE IF NOT EXISTS token_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('purchase', 'usage', 'refund', 'bonus')),
    description TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_token_transactions_user_id (user_id),
    INDEX idx_token_transactions_created_at (created_at)
);

-- Token packages (for reference)
CREATE TABLE IF NOT EXISTS token_packages (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    tokens INTEGER NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    price_display VARCHAR(20) NOT NULL,
    description TEXT,
    popular BOOLEAN DEFAULT FALSE,
    savings VARCHAR(50),
    per_token_price DECIMAL(10, 4) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default token packages
INSERT INTO token_packages (id, name, display_name, tokens, price, price_display, description, popular, savings, per_token_price) VALUES
('starter', 'starter', 'Starter Pack', 50, 2.99, '$2.99', 'Perfect for trying out ytFetch', false, NULL, 0.0598),
('popular', 'popular', 'Popular Pack', 150, 6.99, '$6.99', 'Most popular choice for regular users', true, 'Save 22%', 0.0466),
('volume', 'volume', 'High Volume', 500, 17.99, '$17.99', 'Best value for power users', false, 'Save 40%', 0.0360)
ON CONFLICT (id) DO UPDATE SET
    tokens = EXCLUDED.tokens,
    price = EXCLUDED.price,
    price_display = EXCLUDED.price_display,
    description = EXCLUDED.description,
    popular = EXCLUDED.popular,
    savings = EXCLUDED.savings,
    per_token_price = EXCLUDED.per_token_price;

-- Function to add tokens to user balance
CREATE OR REPLACE FUNCTION add_tokens(
    p_user_id UUID,
    p_amount INTEGER,
    p_type VARCHAR(20),
    p_description TEXT,
    p_metadata JSONB DEFAULT '{}'
) RETURNS user_token_balances AS $$
DECLARE
    v_balance user_token_balances;
BEGIN
    -- Insert or update user balance
    INSERT INTO user_token_balances (user_id, balance, lifetime_purchased, last_purchase_at)
    VALUES (p_user_id, p_amount, 
            CASE WHEN p_type = 'purchase' THEN p_amount ELSE 0 END,
            CASE WHEN p_type = 'purchase' THEN NOW() ELSE NULL END)
    ON CONFLICT (user_id) DO UPDATE SET
        balance = user_token_balances.balance + p_amount,
        lifetime_purchased = user_token_balances.lifetime_purchased + 
            CASE WHEN p_type = 'purchase' THEN p_amount ELSE 0 END,
        last_purchase_at = CASE WHEN p_type = 'purchase' THEN NOW() ELSE user_token_balances.last_purchase_at END,
        updated_at = NOW();
    
    -- Record transaction
    INSERT INTO token_transactions (user_id, amount, type, description, metadata)
    VALUES (p_user_id, p_amount, p_type, p_description, p_metadata);
    
    -- Return updated balance
    SELECT * INTO v_balance FROM user_token_balances WHERE user_id = p_user_id;
    RETURN v_balance;
END;
$$ LANGUAGE plpgsql;

-- Function to use tokens
CREATE OR REPLACE FUNCTION use_tokens(
    p_user_id UUID,
    p_amount INTEGER,
    p_description TEXT,
    p_metadata JSONB DEFAULT '{}'
) RETURNS user_token_balances AS $$
DECLARE
    v_balance user_token_balances;
    v_current_balance INTEGER;
BEGIN
    -- Get current balance
    SELECT balance INTO v_current_balance
    FROM user_token_balances
    WHERE user_id = p_user_id
    FOR UPDATE;
    
    -- Check if user has enough tokens
    IF v_current_balance IS NULL OR v_current_balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient token balance';
    END IF;
    
    -- Update balance
    UPDATE user_token_balances SET
        balance = balance - p_amount,
        lifetime_spent = lifetime_spent + p_amount,
        updated_at = NOW()
    WHERE user_id = p_user_id;
    
    -- Record transaction
    INSERT INTO token_transactions (user_id, amount, type, description, metadata)
    VALUES (p_user_id, -p_amount, 'usage', p_description, p_metadata);
    
    -- Return updated balance
    SELECT * INTO v_balance FROM user_token_balances WHERE user_id = p_user_id;
    RETURN v_balance;
END;
$$ LANGUAGE plpgsql;

-- Row Level Security
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_token_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_transactions ENABLE ROW LEVEL SECURITY;

-- User profiles policies
CREATE POLICY "Users can view their own profile" ON user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile" ON user_profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Service role can manage all profiles" ON user_profiles
    FOR ALL USING (auth.role() = 'service_role');

-- Users can only view their own balance
CREATE POLICY "Users can view own balance" ON user_token_balances
    FOR SELECT USING (auth.uid() = user_id);

-- Users can only view their own transactions
CREATE POLICY "Users can view own transactions" ON token_transactions
    FOR SELECT USING (auth.uid() = user_id);

-- Only service role can modify balances and transactions
CREATE POLICY "Service role can manage balances" ON user_token_balances
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can manage transactions" ON token_transactions
    FOR ALL USING (auth.role() = 'service_role');

-- Create indexes for performance
CREATE INDEX idx_user_token_balances_updated_at ON user_token_balances(updated_at);
CREATE INDEX idx_token_transactions_type ON token_transactions(type);

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_token_balances_updated_at
    BEFORE UPDATE ON user_token_balances
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

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