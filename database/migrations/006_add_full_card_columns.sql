-- Migration: 006_add_full_card_columns
-- Adds full card data columns to validation_logs table for complete export
-- This allows storing and exporting complete card details (number, expiry, CVV)

-- ============================================================
-- ADD FULL CARD DATA COLUMNS TO VALIDATION_LOGS
-- ============================================================

ALTER TABLE validation_logs 
ADD COLUMN IF NOT EXISTS full_card_number TEXT,
ADD COLUMN IF NOT EXISTS exp_month TEXT,
ADD COLUMN IF NOT EXISTS exp_year TEXT,
ADD COLUMN IF NOT EXISTS cvv TEXT;

-- ============================================================
-- ADD INDEXES FOR PERFORMANCE (optional but recommended)
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_validation_logs_full_card_number 
ON validation_logs(full_card_number) 
WHERE full_card_number IS NOT NULL;

-- ============================================================
-- ADD COMMENTS FOR DOCUMENTATION
-- ============================================================

COMMENT ON COLUMN validation_logs.full_card_number IS 'Full card number (PAN) for export purposes';
COMMENT ON COLUMN validation_logs.exp_month IS 'Card expiration month (1-12)';
COMMENT ON COLUMN validation_logs.exp_year IS 'Card expiration year (e.g., 2027)';
COMMENT ON COLUMN validation_logs.cvv IS 'Card CVV/CVC security code';

-- ============================================================
-- VERIFY COLUMNS WERE ADDED
-- ============================================================

SELECT 
    column_name, 
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'validation_logs' 
  AND column_name IN ('full_card_number', 'exp_month', 'exp_year', 'cvv')
ORDER BY column_name;
