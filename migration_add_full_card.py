"""
Migration script to add full card data columns to validation_logs table.

IMPORTANT: You must run this SQL directly in your Supabase Dashboard:
1. Go to https://uqrtjsyxtfmtflvasuhm.supabase.co
2. Navigate to SQL Editor
3. Copy and paste the SQL below and run it
"""

MIGRATION_SQL = """
-- Add full card data columns to validation_logs table
ALTER TABLE validation_logs 
ADD COLUMN IF NOT EXISTS full_card_number TEXT,
ADD COLUMN IF NOT EXISTS exp_month TEXT,
ADD COLUMN IF NOT EXISTS exp_year TEXT,
ADD COLUMN IF NOT EXISTS cvv TEXT;

-- Verify the columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'validation_logs' 
AND column_name IN ('full_card_number', 'exp_month', 'exp_year', 'cvv')
ORDER BY column_name;
"""

if __name__ == "__main__":
    print("=" * 70)
    print("MIGRATION: Add Full Card Data Columns")
    print("=" * 70)
    print()
    print("Please run the following SQL in your Supabase Dashboard:")
    print("1. Go to: https://uqrtjsyxtfmtflvasuhm.supabase.co")
    print("2. Click on 'SQL Editor' in the left sidebar")
    print("3. Create a new query and paste the SQL below")
    print("4. Click 'Run' to execute the migration")
    print()
    print("=" * 70)
    print("SQL TO COPY AND RUN:")
    print("=" * 70)
    print(MIGRATION_SQL)
    print("=" * 70)
