-- Migration: 002_settings_table
-- Allows admins to manage settings (crypto addresses, etc.) from the bot.

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed with default values (admins can change these via bot)
INSERT INTO settings (key, value)
VALUES
    ('crypto_address_usdt', ''),
    ('crypto_address_btc', ''),
    ('admin_contact', '@admin')
ON CONFLICT (key) DO NOTHING;
