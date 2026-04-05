-- Migration: 002_add_credit_reversals
-- Adds reversal tracking columns to credit_transactions table

-- ============================================================
-- ADD REVERSAL COLUMNS TO CREDIT_TRANSACTIONS
-- ============================================================

-- Add reversed flag
ALTER TABLE credit_transactions 
ADD COLUMN IF NOT EXISTS reversed BOOLEAN DEFAULT false;

-- Add reversed_by admin ID
ALTER TABLE credit_transactions 
ADD COLUMN IF NOT EXISTS reversed_by BIGINT;

-- Add reversal reason
ALTER TABLE credit_transactions 
ADD COLUMN IF NOT EXISTS reversal_reason TEXT;

-- Add reversal timestamp
ALTER TABLE credit_transactions 
ADD COLUMN IF NOT EXISTS reversed_at TIMESTAMPTZ;

-- Create index for faster reversal queries
CREATE INDEX IF NOT EXISTS idx_credit_transactions_reversed 
ON credit_transactions(reversed);

-- Create index for reversal admin tracking
CREATE INDEX IF NOT EXISTS idx_credit_transactions_reversed_by 
ON credit_transactions(reversed_by);

-- Add comment for documentation
COMMENT ON COLUMN credit_transactions.reversed IS 'Whether this transaction has been reversed';
COMMENT ON COLUMN credit_transactions.reversed_by IS 'Admin ID who performed the reversal';
COMMENT ON COLUMN credit_transactions.reversal_reason IS 'Reason for the reversal';
COMMENT ON COLUMN credit_transactions.reversed_at IS 'Timestamp of the reversal';
