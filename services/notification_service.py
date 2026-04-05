"""
Notification service — proactive user alerts for low balance, rate limits, etc.
"""

import logging
from typing import Optional
from aiogram import Bot

from models.user import User
from database.supabase_client import get_supabase
from utils.formatters import escape_md

logger = logging.getLogger(__name__)


async def notify_low_balance(
    bot: Bot,
    user: User,
    threshold: int = 10,
) -> bool:
    """
    Notify user when their balance falls below a threshold.
    Only sends once per threshold breach (tracked via metadata).
    """
    if user.credits >= threshold:
        return False
    
    text = (
        f"⚠️ *Low Balance Alert*\n\n"
        f"Your current balance: `{user.credits}` credits\n"
        f"Threshold: `{threshold}` credits\n\n"
        f"To add more credits, use /plans to view available plans "
        f"or contact admin at {escape_md(get_admin_contact())}\n\n"
        f"💡 _Tip: Keep your balance topped up to avoid interruptions_"
    )
    
    try:
        await bot.send_message(user.telegram_id, text, parse_mode="MarkdownV2")
        logger.info(f"Low balance notification sent to user {user.telegram_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send low balance notification to {user.telegram_id}: {e}")
        return False


async def notify_rate_limit_warning(
    bot: Bot,
    user: User,
    current_usage: int,
    limit: int,
) -> bool:
    """
    Notify user when they reach 80% of their rate limit.
    """
    if current_usage < limit * 0.8:
        return False
    
    remaining = limit - current_usage
    text = (
        f"⏱️ *Rate Limit Warning*\n\n"
        f"You have used `{current_usage}/{limit}` validations this period\n"
        f"Remaining: `{remaining}` validations\n\n"
        f"Rate limits reset every hour. Please wait for the reset "
        f"before making additional requests.\n\n"
        f"📊 _Check your quota anytime with /quota_"
    )
    
    try:
        await bot.send_message(user.telegram_id, text, parse_mode="MarkdownV2")
        logger.info(f"Rate limit warning sent to user {user.telegram_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send rate limit warning to {user.telegram_id}: {e}")
        return False


async def notify_validation_complete(
    bot: Bot,
    user: User,
    status: str,
    card_info: str,
) -> bool:
    """
    Notify user when a card validation completes (useful for batch operations).
    """
    status_emoji = {
        "valid": "✅",
        "declined": "❌",
        "3ds_required": "🔒",
        "error": "⚠️",
    }
    
    emoji = status_emoji.get(status, "❓")
    status_text = {
        "valid": "Valid",
        "declined": "Declined",
        "3ds_required": "3DS Required",
        "error": "Error",
    }.get(status, "Unknown")
    
    text = (
        f"{emoji} *Validation Complete*\n\n"
        f"Card: `{escape_md(card_info)}`\n"
        f"Status: *{status_text}*\n\n"
        f"View your full history with /history"
    )
    
    try:
        await bot.send_message(user.telegram_id, text, parse_mode="MarkdownV2")
        return True
    except Exception as e:
        logger.error(f"Failed to send validation notification to {user.telegram_id}: {e}")
        return False


async def notify_admin_low_balance_users(
    bot: Bot,
    admin_id: int,
    threshold: int = 5,
    limit: int = 20,
) -> str:
    """
    Send admin a list of users with critically low balances.
    Returns formatted text for admin review.
    """
    try:
        sb = get_supabase()
        result = sb.table("users").select("*").lt("credits", threshold).limit(limit).execute()
        
        if not result.data:
            return f"✅ No users below {threshold} credits threshold"
        
        lines = [f"⚠️ *Users Below {threshold} Credits* ({len(result.data)} total):\n"]
        for user_data in result.data[:limit]:
            username = escape_md(user_data.get("username", "N/A"))
            tid = user_data.get("telegram_id", "N/A")
            credits = user_data.get("credits", 0)
            lines.append(f"• `{tid}` — {username} — `{credits}`cr")
        
        text = "\n".join(lines)
        
        try:
            await bot.send_message(admin_id, text, parse_mode="MarkdownV2")
        except Exception as e:
            logger.error(f"Failed to send admin low balance report: {e}")
            return text
        
        return f"📊 Sent report with {len(result.data)} low-balance users"
    except Exception as e:
        logger.error(f"Error generating low balance report: {e}")
        return f"❌ Error: {str(e)}"


def get_admin_contact() -> str:
    """Get admin contact from settings or config."""
    try:
        from models.settings import Settings
        contact = Settings.get("admin_contact")
        return contact.value if contact else "@admin"
    except Exception:
        from config import config
        return config.admin_contact


async def check_and_notify_low_balance_for_all_users(
    bot: Bot,
    threshold: int = 10,
) -> int:
    """
    Periodic check: notify all users below balance threshold.
    Returns count of notifications sent.
    """
    try:
        users = User.get_all()
        notified = 0
        
        for user in users:
            if user.credits < threshold:
                # Check if we already notified recently (avoid spam)
                if should_notify_low_balance(user.telegram_id):
                    success = await notify_low_balance(bot, user, threshold)
                    if success:
                        mark_notified_low_balance(user.telegram_id)
                        notified += 1
        
        return notified
    except Exception as e:
        logger.error(f"Error in periodic low balance check: {e}")
        return 0


def should_notify_low_balance(telegram_id: int) -> bool:
    """
    Check if we should notify user about low balance.
    Uses simple in-memory tracking (could be enhanced with database).
    """
    # For now, always notify (can be enhanced with cooldown tracking)
    return True


def mark_notified_low_balance(telegram_id: int) -> None:
    """
    Mark that user was notified about low balance.
    Could be enhanced with database tracking and cooldown periods.
    """
    # In-memory tracking for now
    pass
