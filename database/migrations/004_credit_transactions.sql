-- Migration 004: Credit transaction ledger
-- Tracks every credit change for auditing

CREATE TABLE IF NOT EXISTS credit_transactions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    balance_after INTEGER NOT NULL,
    admin_id BIGINT,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_transaction_user FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_created ON credit_transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_reason ON credit_transactions(reason);

COMMENT ON TABLE credit_transactions IS 'Audit trail for all credit changes';
COMMENT ON COLUMN credit_transactions.amount IS 'Positive = added, Negative = deducted';
COMMENT ON COLUMN credit_transactions.reason IS 'Reason code: validation, admin_add, admin_reset, plan_assign, plan_purchase, admin_grant';
