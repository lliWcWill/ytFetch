-- Create tables for token system
-- Run this in Supabase SQL editor

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

-- Token transactions table
CREATE TABLE IF NOT EXISTS token_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('purchase', 'usage', 'refund', 'bonus')),
    description TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_token_transactions_user_id ON token_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_token_transactions_created_at ON token_transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_transactions_type ON token_transactions(type);

-- Enable Row Level Security
ALTER TABLE user_token_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_transactions ENABLE ROW LEVEL SECURITY;

-- RLS Policies for user_token_balances
-- Users can only see their own balance
CREATE POLICY "Users can view own token balance" ON user_token_balances
    FOR SELECT USING (auth.uid() = user_id);

-- Only service role can update balances
CREATE POLICY "Service role can manage token balances" ON user_token_balances
    FOR ALL USING (auth.jwt()->>'role' = 'service_role');

-- RLS Policies for token_transactions
-- Users can only see their own transactions
CREATE POLICY "Users can view own transactions" ON token_transactions
    FOR SELECT USING (auth.uid() = user_id);

-- Only service role can create transactions
CREATE POLICY "Service role can create transactions" ON token_transactions
    FOR INSERT WITH CHECK (auth.jwt()->>'role' = 'service_role');

-- Function to use tokens (called when starting a transcription)
CREATE OR REPLACE FUNCTION use_tokens(
    p_user_id UUID,
    p_amount INTEGER,
    p_description TEXT,
    p_metadata JSONB DEFAULT '{}'
) RETURNS TABLE (
    success BOOLEAN,
    balance INTEGER,
    message TEXT
) AS $$
DECLARE
    v_current_balance INTEGER;
    v_new_balance INTEGER;
BEGIN
    -- Get current balance with row lock
    SELECT balance INTO v_current_balance
    FROM user_token_balances
    WHERE user_id = p_user_id
    FOR UPDATE;
    
    -- Check if user has enough tokens
    IF v_current_balance IS NULL OR v_current_balance < p_amount THEN
        RETURN QUERY SELECT 
            false::BOOLEAN,
            COALESCE(v_current_balance, 0),
            'Insufficient token balance'::TEXT;
        RETURN;
    END IF;
    
    -- Deduct tokens
    v_new_balance := v_current_balance - p_amount;
    
    UPDATE user_token_balances
    SET balance = v_new_balance,
        lifetime_spent = lifetime_spent + p_amount,
        updated_at = NOW()
    WHERE user_id = p_user_id;
    
    -- Record transaction
    INSERT INTO token_transactions (user_id, amount, type, description, metadata)
    VALUES (p_user_id, -p_amount, 'usage', p_description, p_metadata);
    
    RETURN QUERY SELECT 
        true::BOOLEAN,
        v_new_balance,
        'Tokens deducted successfully'::TEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION use_tokens TO service_role, authenticated;

-- Create initial balance for existing user
INSERT INTO user_token_balances (user_id, balance, lifetime_purchased, lifetime_spent)
VALUES ('17a939d6-bc4d-4225-afbc-bf22ac626dd7', 0, 0, 0)
ON CONFLICT (user_id) DO NOTHING;