"""
Rate limit feedback service — shows users their remaining quota.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from models.user import User
from models.validation_log import ValidationLog
from config import config
from utils.formatters import escape_md

logger = logging.getLogger(__name__)


def get_user_rate_limit_status(telegram_id: int) -> dict:
    """
    Get user's current rate limit status.
    
    Returns:
        Dict with hourly and daily usage stats
    """
    try:
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        # Count validations in last hour
        hourly_logs = ValidationLog.get_by_user(telegram_id, limit=1000)
        hourly_count = sum(
            1 for log in hourly_logs
            if log.created_at and log.created_at > hour_ago
        )
        
        # Count validations in last day
        daily_logs = ValidationLog.get_by_user(telegram_id, limit=1000)
        daily_count = sum(
            1 for log in daily_logs
            if log.created_at and log.created_at > day_ago
        )
        
        hourly_limit = config.rate_limit_per_hour
        daily_limit = config.rate_limit_per_day
        
        hourly_remaining = max(0, hourly_limit - hourly_count)
        daily_remaining = max(0, daily_limit - daily_count)
        
        hourly_percentage = (hourly_count / hourly_limit * 100) if hourly_limit > 0 else 0
        daily_percentage = (daily_count / daily_limit * 100) if daily_limit > 0 else 0
        
        return {
            "hourly": {
                "used": hourly_count,
                "limit": hourly_limit,
                "remaining": hourly_remaining,
                "percentage": min(100, hourly_percentage),
                "resets_in": 3600,  # seconds (simplified)
            },
            "daily": {
                "used": daily_count,
                "limit": daily_limit,
                "remaining": daily_remaining,
                "percentage": min(100, daily_percentage),
                "resets_in": 86400,  # seconds (simplified)
            },
            "is_admin": _is_admin_db(telegram_id),
        }
    except Exception as e:
        logger.error(f"Failed to get rate limit status for user {telegram_id}: {e}")
        return {
            "hourly": {"used": 0, "limit": 0, "remaining": 0, "percentage": 0, "resets_in": 0},
            "daily": {"used": 0, "limit": 0, "remaining": 0, "percentage": 0, "resets_in": 0},
            "is_admin": False,
        }


def _is_admin_db(telegram_id: int) -> bool:
    """Check if user is admin from database."""
    try:
        from models.admin_model import Admin
        return Admin.is_admin(telegram_id)
    except Exception:
        return False


def format_rate_limit_status(status: dict) -> str:
    """
    Format rate limit status for Telegram message.
    
    Returns:
        Formatted MarkdownV2 string
    """
    if status.get("is_admin"):
        return "👑 *Admin* — No rate limits applied"
    
    hourly = status["hourly"]
    daily = status["daily"]
    
    # Create progress bars
    hourly_bar = create_progress_bar(hourly["percentage"], length=10)
    daily_bar = create_progress_bar(daily["percentage"], length=10)
    
    # Format reset times
    hourly_reset = format_seconds(hourly["resets_in"])
    daily_reset = format_seconds(daily["resets_in"])
    
    # Color indicators
    hourly_icon = get_status_icon(hourly["percentage"])
    daily_icon = get_status_icon(daily["percentage"])
    
    text = (
        f"⏱️ *Rate Limit Status*\n\n"
        f"*Hourly Limit:* {hourly_icon}\n"
        f"`{hourly['used']}/{hourly['limit']}` used \\({hourly['percentage']:.0f}%\\)\n"
        f"{hourly_bar}\n"
        f"Remaining: `{hourly['remaining']}` validations\n"
        f"Resets in: {escape_md(hourly_reset)}\n\n"
        f"*Daily Limit:* {daily_icon}\n"
        f"`{daily['used']}/{daily['limit']}` used \\({daily['percentage']:.0f}%\\)\n"
        f"{daily_bar}\n"
        f"Remaining: `{daily['remaining']}` validations\n"
        f"Resets in: {escape_md(daily_reset)}\n\n"
        f"💡 _Tip: Limits reset automatically after the time period_"
    )
    
    return text


def create_progress_bar(percentage: float, length: int = 10) -> str:
    """
    Create a text-based progress bar.
    
    Args:
        percentage: Progress percentage (0-100)
        length: Bar length in characters
    
    Returns:
        Progress bar string
    """
    filled = int(length * percentage / 100)
    empty = length - filled
    
    bar = "█" * filled + "░" * empty
    return f"`[{bar}]`"


def get_status_icon(percentage: float) -> str:
    """
    Get status icon based on usage percentage.
    
    Returns:
        Emoji icon
    """
    if percentage < 50:
        return "🟢"
    elif percentage < 80:
        return "🟡"
    elif percentage < 100:
        return "🟠"
    else:
        return "🔴"


def format_seconds(seconds: int) -> str:
    """
    Format seconds into human-readable time.
    
    Returns:
        Formatted time string
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def should_show_rate_limit_warning(telegram_id: int) -> tuple[bool, str]:
    """
    Check if user should receive a rate limit warning.
    
    Returns:
        (should_warn, warning_message)
    """
    status = get_user_rate_limit_status(telegram_id)
    
    if status.get("is_admin"):
        return False, ""
    
    hourly = status["hourly"]
    daily = status["daily"]
    
    # Check if approaching hourly limit (80%+)
    if hourly["percentage"] >= 80:
        remaining = hourly["remaining"]
        message = (
            f"⚠️ *Hourly Limit Warning*\n\n"
            f"You have used `{hourly['used']}/{hourly['limit']}` validations this hour\n"
            f"Remaining: `{remaining}`\n\n"
            f"Please wait for the limit to reset before making more requests."
        )
        return True, message
    
    # Check if approaching daily limit (80%+)
    if daily["percentage"] >= 80:
        remaining = daily["remaining"]
        message = (
            f"⚠️ *Daily Limit Warning*\n\n"
            f"You have used `{daily['used']}/{daily['limit']}` validations today\n"
            f"Remaining: `{remaining}`\n\n"
            f"Please wait for the limit to reset before making more requests."
        )
        return True, message
    
    return False, ""


def get_rate_limit_footer(status: Optional[dict] = None) -> str:
    """
    Get a short rate limit status footer for validation results.
    
    Returns:
        Short status string
    """
    if not status:
        return ""
    
    if status.get("is_admin"):
        return "💰 Credits: `∞` \\(admin\\)"
    
    hourly = status["hourly"]
    daily = status["daily"]
    
    # Only show warning if approaching limits
    if hourly["percentage"] >= 80 or daily["percentage"] >= 80:
        return (
            f"⏱️ Limits: `{hourly['remaining']}`/hr, `{daily['remaining']}`/day remaining"
        )
    
    return ""
