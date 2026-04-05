"""
Health check utilities — verify bot connectivity and uptime.
"""

import time
from datetime import datetime

from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message

from database.supabase_client import get_supabase
from utils.formatters import escape_md

_start_time = time.time()


async def check_database() -> tuple[bool, str]:
    """Test Supabase connectivity."""
    try:
        sb = get_supabase()
        result = sb.table("users").select("id", count="exact").limit(1).execute()
        return True, f"✅ Database connected ({result.count if hasattr(result, 'count') else 'N/A'} users)"
    except Exception as e:
        return False, f"❌ Database error: {escape_md(str(e))}"


async def check_stripe() -> tuple[bool, str]:
    """Test Stripe API connectivity."""
    try:
        from services.stripe_service import StripeService
        stripe = StripeService()
        accounts = await stripe.list_accounts()
        active = sum(1 for acc in accounts if acc.get("is_active"))
        return True, f"✅ Stripe API reachable ({active} active account(s))"
    except Exception as e:
        return False, f"❌ Stripe API error: {escape_md(str(e))}"


async def cmd_ping(message: Message, bot: Bot) -> None:
    """Simple health check command."""
    uptime = time.time() - _start_time
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    seconds = int(uptime % 60)
    
    bot_info = await bot.get_me()
    
    text = (
        f"🟢 *Bot Status: Online*\n\n"
        f"🤖 *Bot:* {escape_md(bot_info.first_name)}\n"
        f"⏱ *Uptime:* {hours}h {minutes}m {seconds}s\n"
        f"📅 *Started:* {_start_time:.0f}\n"
        f"🆔 *User ID:* `{message.from_user.id}`\n"
    )
    
    await message.answer(text, parse_mode="MarkdownV2")


async def cmd_health(message: Message, bot: Bot) -> None:
    """Detailed health check command (admin only)."""
    from filters import IsAdminFilter
    from aiogram.fsm.context import FSMContext
    
    if not await IsAdminFilter()(message.from_user.id):
        return
    
    text = "🔍 *System Health Check*\n\n"
    
    # Bot status
    bot_info = await bot.get_me()
    uptime = time.time() - _start_time
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    text += f"🤖 *Bot:* {escape_md(bot_info.first_name)}\n"
    text += f"⏱ *Uptime:* {hours}h {minutes}m\n\n"
    
    # Database check
    db_ok, db_msg = await check_database()
    text += f"{db_msg}\n"
    
    # Stripe check
    stripe_ok, stripe_msg = await check_stripe()
    text += f"{stripe_msg}\n\n"
    
    # Overall status
    if db_ok and stripe_ok:
        text += "🟢 *All systems operational*"
    else:
        text += "🔴 *Some systems experiencing issues*"
    
    await message.answer(text, parse_mode="MarkdownV2")
