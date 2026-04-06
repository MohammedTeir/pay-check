"""
Export service — user-facing validation history export.
"""

import csv
import io
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from models.user import User
from models.validation_log import ValidationLog
from models.credit_transaction import CreditTransaction
from utils.formatters import escape_md

logger = logging.getLogger(__name__)

# Auto-delete exports after 24 hours (privacy)
EXPORT_RETENTION_HOURS = 24


async def export_user_history_to_json(telegram_id: int, limit: int = 500) -> Optional[str]:
    """
    Export user's validation history to JSON.
    
    Returns:
        File path or None if failed
    """
    try:
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        validation_logs = ValidationLog.get_by_user(telegram_id, limit=limit)
        
        export_data = {
            "user": {
                "telegram_id": user.telegram_id,
                "username": user.username,
                "credits": user.credits,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "validation_history": [
                {
                    "id": log.id,
                    "card_number": log.full_card_number or f"{log.card_bin}****{log.last4}",
                    "exp_month": log.exp_month or "",
                    "exp_year": log.exp_year or "",
                    "cvv": log.cvv or "",
                    "status": log.status,
                    "decline_code": log.decline_code,
                    "stripe_pi_id": log.stripe_pi_id,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in validation_logs
            ],
            "exported_at": datetime.utcnow().isoformat(),
            "total_validations": len(validation_logs),
        }
        
        # Save file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"validation_history_{telegram_id}_{timestamp}.json"
        filepath = os.path.join("exports", filename)
        
        os.makedirs("exports", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Created validation history export: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to export validation history to JSON: {e}", exc_info=True)
        return None


async def export_user_history_to_csv(telegram_id: int, limit: int = 500) -> Optional[str]:
    """
    Export user's validation history to CSV.
    
    Returns:
        File path or None if failed
    """
    try:
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        validation_logs = ValidationLog.get_by_user(telegram_id, limit=limit)
        
        if not validation_logs:
            return None
        
        # Create CSV
        output = io.StringIO()
        fieldnames = [
            "id", "card_number", "exp_month", "exp_year", "cvv",
            "status", "decline_code", "stripe_pi_id", "created_at"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)

        writer.writeheader()
        for log in validation_logs:
            writer.writerow({
                "id": log.id,
                "card_number": log.full_card_number or f"{log.card_bin}****{log.last4}",
                "exp_month": log.exp_month or "",
                "exp_year": log.exp_year or "",
                "cvv": log.cvv or "",
                "status": log.status,
                "decline_code": log.decline_code or "",
                "stripe_pi_id": log.stripe_pi_id or "",
                "created_at": log.created_at.isoformat() if log.created_at else "",
            })
        
        # Save file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"validation_history_{telegram_id}_{timestamp}.csv"
        filepath = os.path.join("exports", filename)
        
        os.makedirs("exports", exist_ok=True)
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.write(output.getvalue())
        
        logger.info(f"Created validation history CSV export: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to export validation history to CSV: {e}", exc_info=True)
        return None


async def export_user_history_to_text(telegram_id: int, limit: int = 100) -> Optional[str]:
    """
    Export user's validation history to formatted text.
    
    Returns:
        File path or None if failed
    """
    try:
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        validation_logs = ValidationLog.get_by_user(telegram_id, limit=limit)
        
        if not validation_logs:
            return None
        
        # Create formatted text
        lines = [
            f"Validation History Export",
            f"User: {user.username or user.telegram_id}",
            f"Telegram ID: {user.telegram_id}",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Total Validations: {len(validation_logs)}",
            f"{'='*60}",
            f"",
        ]
        
        for i, log in enumerate(validation_logs, 1):
            created = log.created_at.strftime("%Y-%m-%d %H:%M") if log.created_at else "Unknown"
            card_number = log.full_card_number or f"{log.card_bin}******{log.last4}"
            exp_month = log.exp_month or "N/A"
            exp_year = log.exp_year or "N/A"
            cvv = log.cvv or "N/A"
            lines.append(f"[{i}] {created}")
            lines.append(f"    Card Number: {card_number}")
            lines.append(f"    Expiry: {exp_month}/{exp_year}")
            lines.append(f"    CVV: {cvv}")
            lines.append(f"    Status: {log.status.upper()}")
            if log.decline_code:
                lines.append(f"    Decline Code: {log.decline_code}")
            if log.stripe_pi_id:
                lines.append(f"    Stripe ID: {log.stripe_pi_id}")
            lines.append("")
        
        # Summary
        status_counts = {}
        for log in validation_logs:
            status_counts[log.status] = status_counts.get(log.status, 0) + 1
        
        lines.append(f"{'='*60}")
        lines.append(f"Summary:")
        for status, count in sorted(status_counts.items()):
            lines.append(f"  {status}: {count}")
        
        # Save file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"validation_history_{telegram_id}_{timestamp}.txt"
        filepath = os.path.join("exports", filename)
        
        os.makedirs("exports", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        logger.info(f"Created validation history text export: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to export validation history to text: {e}", exc_info=True)
        return None


async def cleanup_old_exports() -> int:
    """
    Delete export files older than retention period.
    
    Returns:
        Number of files deleted
    """
    try:
        exports_dir = "exports"
        if not os.path.exists(exports_dir):
            return 0
        
        cutoff = datetime.utcnow() - timedelta(hours=EXPORT_RETENTION_HOURS)
        deleted = 0
        
        for filename in os.listdir(exports_dir):
            filepath = os.path.join(exports_dir, filename)
            if not os.path.isfile(filepath):
                continue
            
            # Check file creation time
            file_time = datetime.fromtimestamp(os.path.getctime(filepath))
            if file_time < cutoff:
                os.remove(filepath)
                deleted += 1
                logger.info(f"Deleted old export file: {filename}")
        
        return deleted
    except Exception as e:
        logger.error(f"Failed to cleanup old exports: {e}")
        return 0


def format_export_summary(telegram_id: int) -> str:
    """Format export statistics for user."""
    try:
        user = User.get_by_telegram_id(telegram_id)
        if not user:
            return "❌ User not found"
        
        # Count total validations
        from database.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("validation_logs").select("id", count="exact").eq("user_id", telegram_id).execute()
        total = result.count if hasattr(result, 'count') else 0
        
        # Get date range
        logs = ValidationLog.get_by_user(telegram_id, limit=1)
        if logs:
            latest = logs[0].created_at.strftime("%Y-%m-%d %H:%M") if logs[0].created_at else "Unknown"
        else:
            latest = "No validations yet"
        
        text = (
            f"📊 *Your Validation History*\n\n"
            f"Total Validations: `{total}`\n"
            f"Latest: {escape_md(latest)}\n"
            f"Current Balance: `{user.credits}` credits\n\n"
            f"Use /export_history to download your data."
        )
        
        return text
    except Exception as e:
        logger.error(f"Failed to format export summary: {e}")
        return "❌ Error fetching history"
