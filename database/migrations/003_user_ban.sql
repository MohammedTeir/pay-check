-- Migration 003: Add is_banned column to users table
-- Adds soft-delete/suspension capability

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT false;
CREATE INDEX IF NOT EXISTS idx_users_is_banned ON users(is_banned);

COMMENT ON COLUMN users.is_banned IS 'Whether the user is banned from using the bot';
