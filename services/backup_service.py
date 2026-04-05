"""
Backup & Export Service — automated database backups and data export.
"""

import json
import csv
import io
import logging
from datetime import datetime
from typing import Optional

from database.supabase_client import get_supabase
from utils.formatters import escape_md

logger = logging.getLogger(__name__)

# Tables to backup
BACKUP_TABLES = [
    "users",
    "plans",
    "stripe_accounts",
    "validation_logs",
    "admin_logs",
    "credit_transactions",
    "card_cooldowns",
]


async def create_backup(
    tables: Optional[list[str]] = None,
    include_deleted: bool = False,
) -> dict:
    """
    Create a full database backup.
    
    Args:
        tables: List of tables to backup (default: all)
        include_deleted: Include soft-deleted records
    
    Returns:
        Backup metadata
    """
    if tables is None:
        tables = BACKUP_TABLES
    
    sb = get_supabase()
    backup_data = {}
    total_records = 0
    
    for table in tables:
        try:
            response = sb.table(table).select("*").execute()
            backup_data[table] = response.data
            record_count = len(response.data)
            total_records += record_count
            logger.info(f"Backed up {table}: {record_count} records")
        except Exception as e:
            logger.error(f"Failed to backup {table}: {e}")
            backup_data[table] = []
    
    # Create backup metadata
    backup_id = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    metadata = {
        "backup_id": backup_id,
        "created_at": datetime.utcnow().isoformat(),
        "table_count": len(tables),
        "total_records": total_records,
        "tables": {
            table: len(records) for table, records in backup_data.items()
        },
        "version": "1.0",
    }
    
    # Store backup in database
    try:
        sb.table("backups").insert({
            "backup_id": backup_id,
            "metadata": metadata,
            "data": backup_data,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
        logger.info(f"Backup stored: {backup_id}")
    except Exception as e:
        logger.warning(f"Failed to store backup in database: {e}")
        # Return backup data anyway for manual save
    
    return metadata


async def list_backups(limit: int = 20) -> list[dict]:
    """List recent backups."""
    try:
        sb = get_supabase()
        response = (
            sb.table("backups")
            .select("backup_id, metadata, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
        return []


async def export_table_to_json(
    table: str,
    limit: int = 1000,
    filters: Optional[dict] = None,
) -> str:
    """
    Export table data to JSON format.
    
    Args:
        table: Table name
        limit: Max records to export
        filters: Optional filters (e.g., {"user_id": 123})
    
    Returns:
        JSON string
    """
    try:
        sb = get_supabase()
        query = sb.table(table).select("*")
        
        # Apply filters
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        response = query.limit(limit).execute()
        
        # Format JSON
        export_data = {
            "table": table,
            "exported_at": datetime.utcnow().isoformat(),
            "record_count": len(response.data),
            "data": response.data,
        }
        
        return json.dumps(export_data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to export {table} to JSON: {e}")
        return json.dumps({"error": str(e)})


async def export_table_to_csv(
    table: str,
    limit: int = 1000,
    filters: Optional[dict] = None,
) -> str:
    """
    Export table data to CSV format.
    
    Args:
        table: Table name
        limit: Max records to export
        filters: Optional filters
    
    Returns:
        CSV string
    """
    try:
        sb = get_supabase()
        query = sb.table(table).select("*")
        
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        response = query.limit(limit).execute()
        
        if not response.data:
            return "No data found"
        
        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=response.data[0].keys())
        writer.writeheader()
        writer.writerows(response.data)
        
        return output.getvalue()
    except Exception as e:
        logger.error(f"Failed to export {table} to CSV: {e}")
        return f"Error: {str(e)}"


async def export_user_data(telegram_id: int) -> dict:
    """
    Export all data for a specific user (GDPR compliance).
    
    Returns:
        Dict with all user data in multiple formats
    """
    from models.user import User
    from models.validation_log import ValidationLog
    from models.credit_transaction import CreditTransaction
    
    user = User.get_by_telegram_id(telegram_id)
    if not user:
        return {"error": "User not found"}
    
    # Get user's data
    validation_logs = ValidationLog.get_by_user(telegram_id, limit=1000)
    credit_txns = CreditTransaction.get_by_user(telegram_id, limit=1000)
    
    return {
        "user": user.to_dict(),
        "validation_logs": [log.to_dict() for log in validation_logs],
        "credit_transactions": [txn.to_dict() for txn in credit_txns],
        "exported_at": datetime.utcnow().isoformat(),
    }


async def cleanup_old_backups(keep_days: int = 30) -> int:
    """
    Delete backups older than specified days.
    
    Returns:
        Number of backups deleted
    """
    try:
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=keep_days)
        sb = get_supabase()
        
        # Find old backups
        response = (
            sb.table("backups")
            .select("id")
            .lt("created_at", cutoff.isoformat())
            .execute()
        )
        
        if not response.data:
            return 0
        
        # Delete old backups
        deleted = len(response.data)
        sb.table("backups").delete().lt("created_at", cutoff.isoformat()).execute()
        
        logger.info(f"Cleaned up {deleted} old backups (>{keep_days} days)")
        return deleted
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {e}")
        return 0


async def restore_backup(backup_id: str) -> dict:
    """
    Restore data from a backup.
    WARNING: This will overwrite existing data!
    
    Args:
        backup_id: Backup ID to restore
    
    Returns:
        Restore result metadata
    """
    try:
        sb = get_supabase()
        
        # Get backup data
        response = sb.table("backups").select("*").eq("backup_id", backup_id).execute()
        if not response.data:
            return {"success": False, "error": "Backup not found"}
        
        backup = response.data[0]
        data = backup.get("data", {})
        
        restored_tables = 0
        restored_records = 0
        errors = []
        
        # Restore each table
        for table_name, records in data.items():
            try:
                if not records:
                    continue
                
                # Delete existing data (careful!)
                # sb.table(table_name).delete().neq("id", 0).execute()
                
                # Insert backup data
                # Note: This is simplified - production should handle conflicts
                for record in records:
                    # Remove id to let DB generate new one (or use upsert)
                    record_copy = {k: v for k, v in record.items() if k != "id"}
                    sb.table(table_name).insert(record_copy).execute()
                    restored_records += 1
                
                restored_tables += 1
                logger.info(f"Restored {table_name}: {len(records)} records")
            except Exception as e:
                error_msg = f"Failed to restore {table_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return {
            "success": len(errors) == 0,
            "backup_id": backup_id,
            "restored_tables": restored_tables,
            "restored_records": restored_records,
            "errors": errors,
            "restored_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}")
        return {"success": False, "error": str(e)}


def format_backup_summary(backups: list[dict]) -> str:
    """Format backup list for Telegram message."""
    if not backups:
        return "📭 *No backups found*"
    
    lines = ["💾 *Database Backups*\n"]
    
    for i, backup in enumerate(backups[:10], 1):
        metadata = backup.get("metadata", {})
        created = backup.get("created_at", "Unknown")[:19].replace("T", " ")
        total_records = metadata.get("total_records", 0)
        backup_id = backup.get("backup_id", "Unknown")
        
        lines.append(
            f"*{i}\\.* `{backup_id}`\n"
            f"   📅 {escape_md(created)}\n"
            f"   📊 {total_records} records\n"
        )
    
    return "\n".join(lines)
