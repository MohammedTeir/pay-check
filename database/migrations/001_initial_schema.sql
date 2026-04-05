-- Migration: 001_initial_schema
-- Run this in Supabase SQL Editor to create all required tables

-- ============================================================
-- USERS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    credits INTEGER DEFAULT 0,
    plan_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);

-- ============================================================
-- PLANS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS plans (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    crypto_price_usd NUMERIC(10,2) NOT NULL,
    credits INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- STRIPE ACCOUNTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS stripe_accounts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label TEXT UNIQUE NOT NULL,
    secret_key_encrypted TEXT NOT NULL,
    is_active BOOLEAN DEFAULT false,
    daily_count INTEGER DEFAULT 0,
    daily_reset_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- VALIDATION LOGS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS validation_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    card_bin TEXT NOT NULL,
    last4 TEXT NOT NULL,
    card_hash TEXT NOT NULL,
    amount_cents INTEGER DEFAULT 50,
    stripe_pi_id TEXT,
    status TEXT NOT NULL,
    decline_code TEXT,
    stripe_account_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_validation_user FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
    CONSTRAINT fk_stripe_account FOREIGN KEY (stripe_account_id) REFERENCES stripe_accounts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_validation_logs_user_id ON validation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_validation_logs_card_hash ON validation_logs(card_hash);
CREATE INDEX IF NOT EXISTS idx_validation_logs_created ON validation_logs(created_at);

-- ============================================================
-- CARD COOLDOWNS TABLE (24h duplicate prevention)
-- ============================================================
CREATE TABLE IF NOT EXISTS card_cooldowns (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    card_hash TEXT NOT NULL,
    validated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_card_cooldowns_hash ON card_cooldowns(card_hash);
CREATE INDEX IF NOT EXISTS idx_card_cooldowns_expires ON card_cooldowns(expires_at);

-- ============================================================
-- ADMIN AUDIT LOG TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    admin_id BIGINT NOT NULL,
    admin_username TEXT,
    action TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_logs_admin_id ON admin_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_created ON admin_logs(created_at);

-- ============================================================
-- FOREIGN KEY: users.plan_id -> plans.id
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_user_plan'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT fk_user_plan
            FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE SET NULL;
    END IF;
END $$;

-- ============================================================
-- FUNCTION: Auto-cleanup expired card cooldowns
-- ============================================================
CREATE OR REPLACE FUNCTION cleanup_expired_cooldowns()
RETURNS void AS $$
BEGIN
    DELETE FROM card_cooldowns WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- FUNCTION: Reset daily Stripe counter (call via cron or manually)
-- ============================================================
CREATE OR REPLACE FUNCTION reset_stripe_daily_counters()
RETURNS void AS $$
BEGIN
    UPDATE stripe_accounts
    SET daily_count = 0, daily_reset_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- SEED DATA: Default plan (optional, admin can override)
-- ============================================================
INSERT INTO plans (name, crypto_price_usd, credits, is_active)
VALUES
    ('Basic', 20.00, 500, true),
    ('Pro', 50.00, 1500, true),
    ('Premium', 100.00, 3500, true)
ON CONFLICT (name) DO NOTHING;
