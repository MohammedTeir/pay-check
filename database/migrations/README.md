# Database Migrations

This directory contains SQL migration files for the Card Validator Bot database schema.

## How to Run Migrations

### Method 1: Supabase Dashboard (Recommended)

1. Go to your Supabase project: https://uqrtjsyxtfmtflvasuhm.supabase.co
2. Click on **SQL Editor** in the left sidebar
3. Click **New query**
4. Copy the SQL from the migration file you need to run
5. Paste it into the SQL Editor
6. Click **Run** (or press `Ctrl+Enter`)
7. Verify the output shows success messages

### Method 2: Supabase CLI (If Installed)

```bash
supabase db push
```

## Migration Files

### Completed Migrations
- ✅ `001_initial_schema.sql` - Initial database tables (users, plans, validation_logs, etc.)
- ✅ `002_settings_table.sql` - Settings table for configurable values
- ✅ `002_add_credit_reversals.sql` - Credit reversal tracking
- ✅ `003_add_backups_table.sql` - Backup storage table
- ✅ `003_user_ban.sql` - User ban functionality
- ✅ `004_credit_transactions.sql` - Credit transaction history
- ✅ `005_admins_table.sql` - Admin management table

### Pending Migrations
- 🔴 `006_add_full_card_columns.sql` - **RUN THIS NOW**
  - Adds full card number, expiry, and CVV columns to validation_logs
  - Required for complete card data export functionality
  - **Status:** Created but not yet executed

## Running Migration 006

To add full card data columns:

1. Open Supabase Dashboard: https://uqrtjsyxtfmtflvasuhm.supabase.co
2. Go to SQL Editor
3. Copy the contents of `006_add_full_card_columns.sql`
4. Run it in the SQL Editor
5. You should see output showing 4 new columns added

## Verifying Migrations

After running a migration, you can verify it worked by running:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'validation_logs' 
ORDER BY ordinal_position;
```

This will show all columns in the validation_logs table.
