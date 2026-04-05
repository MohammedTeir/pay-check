-- Migration: 003_add_backups_table
-- Adds backup storage table for automated backups

-- ============================================================
-- BACKUPS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS backups (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    backup_id TEXT UNIQUE NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_backups_backup_id ON backups(backup_id);
CREATE INDEX IF NOT EXISTS idx_backups_created_at ON backups(created_at);

-- Comment for documentation
COMMENT ON TABLE backups IS 'Stores automated database backups';
COMMENT ON COLUMN backups.backup_id IS 'Unique backup identifier (e.g., backup_20260405_123456)';
COMMENT ON COLUMN backups.metadata IS 'Backup metadata (table counts, timestamps)';
COMMENT ON COLUMN backups.data IS 'Actual backup data (JSON)';
COMMENT ON COLUMN backups.created_at IS 'Backup creation timestamp';

-- ============================================================
-- ROW LEVEL SECURITY (optional but recommended)
-- ============================================================

-- Enable RLS
ALTER TABLE backups ENABLE ROW LEVEL SECURITY;

-- Only service role can manage backups (handled by backend)
-- No user-facing access needed
