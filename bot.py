"""
Bot entry — aiogram 3.x.
100% inline buttons. No ReplyKeyboard.
Supports both webhook and polling modes.
"""

import asyncio
import logging
import signal
import sys
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, Update

from config import config
from states import CardValidationState
from middleware.session_timeout import SessionTimeoutMiddleware
from handlers.admin_handlers import AdminFSM
from handlers.user_handlers import (
    cmd_start, cmd_menu,
    cmd_validate, cmd_balance, cmd_quota, cmd_plans, cmd_history, cmd_help,
    cb_u_validate, cb_u_balance, cb_u_plans, cb_u_history, cb_u_help, cb_u_menu, cb_u_quota,
    cb_u_export_history, cb_export_json, cb_export_csv, cb_export_txt,
    handle_card_text, cb_validate_choice, cb_validate_cancel,
)
from utils.health import cmd_ping, cmd_health
from handlers.admin_handlers import (
    cmd_admin,
    cb_a_main,
    cb_a_users, cb_user_detail, cb_user_search,
    cb_user_add_credits, cb_user_reset_credits, cb_user_reset_ok,
    cb_user_ban, cb_user_unban, cb_user_delete, cb_user_delete_ok,
    cb_user_history, cb_user_credits,
    cb_user_reverse_credits, cb_user_reverse_confirm, cb_user_reverse_ok,
    cb_a_backups, cb_backup_create, cb_backup_list,
    cb_backup_export_users_json, cb_backup_export_users_csv,
    cb_a_stripe, cb_stripe_detail, cb_stripe_activate,
    cb_stripe_rename, cb_stripe_delete, cb_stripe_delete_ok, cb_stripe_add,
    cb_a_plans, cb_plan_detail, cb_plan_toggle,
    cb_plan_delete, cb_plan_delete_ok, cb_plan_add,
    cb_plan_edit_name, cb_plan_edit_price, cb_plan_edit_credits,
    cb_a_stats, cb_a_audit,
    cb_a_broadcast, cb_a_settings,
    cb_settings_usdt, cb_settings_btc, cb_settings_contact,
    cb_set_stripe_cost, cb_set_bin_cost,
    cb_manage_admins, cb_admin_detail, cb_add_admin_prompt,
    cb_admin_promote, cb_admin_demote,
    cb_admin_remove_confirm, cb_admin_remove_ok,
    cb_noop,
    handle_admin_text,
)
from webapp.app import app as flask_app

# ── Logging setup with rotation ────────────────────────────────────────────

def setup_logging() -> None:
    """Configure logging with rotating file handler (10MB max, keep 5 backups)."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Rotating file handler (10MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        "logs/bot.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        format=log_format,
        level=logging.INFO,
        handlers=[console_handler, file_handler]
    )


setup_logging()
logger = logging.getLogger(__name__)


# ── Periodic cleanup ──────────────────────────────────────────────────────

async def periodic_cooldown(bot: Bot) -> None:
    try:
        from database.supabase_client import get_supabase
        from datetime import datetime
        sb = get_supabase()
        now = datetime.utcnow().isoformat()
        r = sb.table("card_cooldowns").delete().lt("expires_at", now).execute()
        if r.data:
            logger.info(f"Cleaned {len(r.data)} expired cooldowns")
    except Exception as e:
        logger.error(f"Cooldown cleanup failed: {e}")


async def run_jobs(bot: Bot) -> None:
    while True:
        await asyncio.sleep(3600)
        await periodic_cooldown(bot)


# ── Graceful shutdown ──────────────────────────────────────────────────────

_shutdown_event = asyncio.Event()


async def graceful_shutdown(bot: Bot, dp: Dispatcher) -> None:
    """Safely shut down the bot and release resources."""
    if _shutdown_event.is_set():
        return
    
    logger.info("Graceful shutdown initiated...")
    _shutdown_event.set()
    
    try:
        # Stop accepting new updates
        logger.info("Stopping dispatcher...")
        await dp.storage.close()
        
        # Close bot session
        logger.info("Closing bot session...")
        await bot.session.close()
        
        logger.info("Shutdown complete.")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)
    finally:
        sys.exit(0)


def setup_signal_handlers(bot: Bot, dp: Dispatcher) -> None:
    """Register OS signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} signal")
        asyncio.create_task(graceful_shutdown(bot, dp))
    
    # Windows supports SIGBREAK and CTRL events
    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGBREAK, signal_handler)
        except (ValueError, AttributeError):
            pass  # SIGBREAK may not be available
    else:
        # Unix-like systems
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("Signal handlers registered")


# ── Text router ────────────────────────────────────────────────────────────

async def handle_text(message: Message, state: FSMContext, bot: Bot) -> None:
    cur = await state.get_state()
    from states import CardValidationState
    if cur in (CardValidationState.waiting_for_card.state, CardValidationState.pending_choice.state):
        await handle_card_text(message, state)
        return
    admin_states = {s.state for s in AdminFSM.__dict__.values() if hasattr(s, 'state')}
    if cur in admin_states:
        await handle_admin_text(message, state, bot)
        return
    # Ignore random messages
    logger.debug(f"Ignoring text from {message.from_user.id}: {message.text[:50]}")


async def start_webapp(bot: Bot, dp: Dispatcher):
    """Start the Flask webapp for Stripe Elements using waitress.

    In webhook mode, also registers the /webhook route on Flask so Telegram
    can push updates to the same server.
    """
    import asyncio
    import threading
    from flask import request as flask_request
    from waitress import serve

    # Capture reference to the main event loop (we're on the main thread here)
    main_loop = asyncio.get_running_loop()

    # Register Telegram webhook route on Flask
    @flask_app.route(config.webhook_path, methods=["POST"])
    def handle_telegram_webhook():
        update_data = flask_request.get_json()
        update = Update.model_validate(update_data)
        # Fire-and-forget: schedule processing on the main loop and return
        # immediately so Telegram doesn't timeout (it only waits 60s).
        asyncio.run_coroutine_threadsafe(
            dp.feed_webhook_update(bot, update), main_loop
        )
        return "ok"

    def run_waitress():
        serve(
            flask_app,
            host='0.0.0.0',
            port=config.webapp_port,
            threads=2,
        )

    thread = threading.Thread(target=run_waitress, daemon=True)
    thread.start()
    logger.info(f"Waitress webapp started on port {config.webapp_port}")


async def main() -> None:
    config.validate()
    logger.info("Starting Card Validator Bot (aiogram 3.x, inline)...")

    bot = Bot(token=config.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers(bot, dp)

    # Start Flask webapp for Stripe Elements (also registers /webhook route in webhook mode)
    if config.stripe_publishable_key:
        await start_webapp(bot, dp)
    else:
        logger.warning("STRIPE_PUBLISHABLE_KEY not set - Stripe Elements validation disabled")

    # Setup session timeout middleware
    session_middleware = SessionTimeoutMiddleware(
        timeout_seconds=900,    # 15 minutes
        warning_seconds=600     # 10 minutes (warn at 10 min)
    )
    dp.message.middleware(session_middleware)
    dp.callback_query.middleware(session_middleware)

    # ── Commands ──────────────────────────────────────────────────────
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_menu, Command("menu"))
    dp.message.register(cmd_admin, Command("admin"))
    dp.message.register(lambda m, b: cmd_ping(m, b), Command("ping"))
    dp.message.register(lambda m, b: cmd_health(m, b), Command("health"))
    # User commands (also as slash commands)
    dp.message.register(cmd_validate, Command("validate"))
    dp.message.register(cmd_balance, Command("balance"))
    dp.message.register(cmd_quota, Command("quota"))
    dp.message.register(cmd_plans, Command("plans"))
    dp.message.register(cmd_history, Command("history"))
    dp.message.register(cmd_help, Command("help"))

    # ── Callback: User ────────────────────────────────────────────────
    dp.callback_query.register(cb_u_validate, F.data == "u_validate")
    dp.callback_query.register(cb_u_balance, F.data == "u_balance")
    dp.callback_query.register(cb_u_quota, F.data == "u_quota")
    dp.callback_query.register(cb_u_plans, F.data == "u_plans")
    dp.callback_query.register(cb_u_history, F.data == "u_history")
    dp.callback_query.register(cb_u_export_history, F.data == "u_export_history")
    dp.callback_query.register(cb_export_json, F.data == "export_json")
    dp.callback_query.register(cb_export_csv, F.data == "export_csv")
    dp.callback_query.register(cb_export_txt, F.data == "export_txt")
    dp.callback_query.register(cb_u_help, F.data == "u_help")
    dp.callback_query.register(cb_u_menu, F.data == "u_menu")
    # Validation mode choices
    async def _val_choice_handler(query: CallbackQuery, state: FSMContext):
        # Get bot instance from dispatcher data
        bot = query.bot
        await cb_validate_choice(query, state, bot)
    dp.callback_query.register(_val_choice_handler, F.data.regexp(r"^val_mode:"))
    dp.callback_query.register(cb_validate_cancel, F.data == "val_cancel")

    # ── Callback: Admin ───────────────────────────────────────────────
    dp.callback_query.register(cb_a_main, F.data == "a_main")
    dp.callback_query.register(cb_a_users, F.data.regexp(r"^a_users:\d+$"))
    dp.callback_query.register(cb_user_detail, F.data.regexp(r"^udet:\d+$"))
    dp.callback_query.register(cb_user_search, F.data == "a_user_search")
    dp.callback_query.register(cb_user_add_credits, F.data.regexp(r"^uaddcr:\d+$"))
    dp.callback_query.register(cb_user_reset_credits, F.data.regexp(r"^urescr:\d+$"))
    dp.callback_query.register(cb_user_reset_ok, F.data.regexp(r"^urescr_ok:\d+$"))
    dp.callback_query.register(cb_user_ban, F.data.regexp(r"^uban:\d+$"))
    dp.callback_query.register(cb_user_unban, F.data.regexp(r"^uunban:\d+$"))
    dp.callback_query.register(cb_user_delete, F.data.regexp(r"^udel:\d+$"))
    dp.callback_query.register(cb_user_delete_ok, F.data.regexp(r"^udel_ok:\d+$"))
    dp.callback_query.register(cb_user_history, F.data.regexp(r"^uhist:\d+$"))
    dp.callback_query.register(cb_user_credits, F.data.regexp(r"^ucred:\d+$"))
    dp.callback_query.register(cb_user_reverse_credits, F.data.regexp(r"^urev:\d+$"))
    dp.callback_query.register(cb_user_reverse_confirm, F.data.regexp(r"^urev_confirm:\d+$"))
    dp.callback_query.register(cb_user_reverse_ok, F.data.regexp(r"^urev_ok:\d+$"))

    # Backups
    dp.callback_query.register(cb_a_backups, F.data == "a_backups")
    dp.callback_query.register(cb_backup_create, F.data == "backup_create")
    dp.callback_query.register(cb_backup_list, F.data == "backup_list")
    dp.callback_query.register(cb_backup_export_users_json, F.data == "backup_export_users_json")
    dp.callback_query.register(cb_backup_export_users_csv, F.data == "backup_export_users_csv")

    dp.callback_query.register(cb_a_stripe, F.data == "a_stripe")
    dp.callback_query.register(cb_stripe_detail, F.data.regexp(r"^sdet:\d+$"))
    dp.callback_query.register(cb_stripe_activate, F.data.regexp(r"^sact:\d+$"))
    dp.callback_query.register(cb_stripe_rename, F.data.regexp(r"^sren:\d+$"))
    dp.callback_query.register(cb_stripe_delete, F.data.regexp(r"^sdel:\d+$"))
    dp.callback_query.register(cb_stripe_delete_ok, F.data.regexp(r"^sdel_ok:\d+$"))
    dp.callback_query.register(cb_stripe_add, F.data == "sadd")

    dp.callback_query.register(cb_a_plans, F.data == "a_plans")
    dp.callback_query.register(cb_plan_detail, F.data.regexp(r"^pedt:\d+$"))
    dp.callback_query.register(cb_plan_toggle, F.data.regexp(r"^ptog:\d+$"))
    dp.callback_query.register(cb_plan_delete, F.data.regexp(r"^pdel:\d+$"))
    dp.callback_query.register(cb_plan_delete_ok, F.data.regexp(r"^pdel_ok:\d+$"))
    dp.callback_query.register(cb_plan_add, F.data == "padd")
    dp.callback_query.register(cb_plan_edit_name, F.data.regexp(r"^pedt_name:\d+$"))
    dp.callback_query.register(cb_plan_edit_price, F.data.regexp(r"^pedt_price:\d+$"))
    dp.callback_query.register(cb_plan_edit_credits, F.data.regexp(r"^pedt_credits:\d+$"))

    dp.callback_query.register(cb_a_stats, F.data == "a_stats")
    dp.callback_query.register(cb_a_audit, F.data == "a_audit")
    dp.callback_query.register(cb_a_broadcast, F.data == "a_broadcast")
    dp.callback_query.register(cb_a_settings, F.data == "a_settings")
    dp.callback_query.register(cb_settings_usdt, F.data == "sett_usdt")
    dp.callback_query.register(cb_settings_btc, F.data == "sett_btc")
    dp.callback_query.register(cb_settings_contact, F.data == "sett_contact")

    # Stripe/BIN cost - register before noop
    async def _stripe_cost_handler(query: CallbackQuery, state: FSMContext):
        try:
            logger.info(f"Stripe cost handler called: {query.data}")
            from handlers.admin_handlers import cb_set_stripe_cost
            await cb_set_stripe_cost(query, state)
        except Exception as e:
            logger.error(f"Stripe cost handler error: {e}", exc_info=True)
            await query.answer(f"Error: {e}", show_alert=True)
    dp.callback_query.register(_stripe_cost_handler, F.data == "sett_stripe_cost")

    async def _bin_cost_handler(query: CallbackQuery, state: FSMContext):
        try:
            logger.info(f"BIN cost handler called: {query.data}")
            from handlers.admin_handlers import cb_set_bin_cost
            await cb_set_bin_cost(query, state)
        except Exception as e:
            logger.error(f"BIN cost handler error: {e}", exc_info=True)
            await query.answer(f"Error: {e}", show_alert=True)
    dp.callback_query.register(_bin_cost_handler, F.data == "sett_bin_cost")

    # Admin management callbacks
    dp.callback_query.register(cb_manage_admins, F.data == "a_manage_admins")
    dp.callback_query.register(cb_admin_detail, F.data.regexp(r"^udet:\d+$"))
    dp.callback_query.register(cb_add_admin_prompt, F.data == "a_add_admin")
    dp.callback_query.register(cb_admin_promote, F.data.regexp(r"^aprom:\d+$"))
    dp.callback_query.register(cb_admin_demote, F.data.regexp(r"^adem:\d+$"))
    dp.callback_query.register(cb_admin_remove_confirm, F.data.regexp(r"^adel:\d+$"))
    dp.callback_query.register(cb_admin_remove_ok, F.data.regexp(r"^adel_ok:\d+$"))

    # Catch-all for any remaining unhandled callbacks
    dp.callback_query.register(cb_noop, F.data == "noop")

    # ── Text (card input + admin FSM) ─────────────────────────────────
    dp.message.register(handle_text, F.text)

    # ── Startup: Webhook or Polling ─────────────────────────────────
    asyncio.create_task(run_jobs(bot))

    if config.use_webhook:
        # Webhook mode (typically production)
        logger.info(f"🌐 Starting in WEBHOOK mode (environment: {config.app_env})")
        logger.info(f"   Webhook URL: {config.webhook_url}")
        logger.info(f"   Webhook Port: {config.webapp_port}")
        await run_webhook(bot, dp)
    else:
        # Polling mode (typically development)
        logger.info(f"🔄 Starting in POLLING mode (environment: {config.app_env})")
        try:
            await dp.start_polling(bot, drop_pending_updates=True)
        except (KeyboardInterrupt, SystemExit) as e:
            logger.info(f"Polling interrupted: {type(e).__name__}")
        finally:
            await graceful_shutdown(bot, dp)


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    """Run bot in webhook mode.

    The webhook endpoint is handled by the Flask webapp (via start_webapp).
    This function just sets the webhook URL on Telegram and keeps running.
    """
    # Set webhook on Telegram
    await bot.set_webhook(
        url=config.webhook_url,
        secret_token=config.webhook_secret if config.webhook_secret else None,
        allowed_updates=dp.resolve_used_update_types()
    )

    logger.info(f"Webhook set to: {config.webhook_url}")
    logger.info(f"Webhook endpoint handled by Flask on port {config.webapp_port}")

    # Keep running until interrupted
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit) as e:
        logger.info(f"Webhook mode interrupted: {type(e).__name__}")
    finally:
        await bot.delete_webhook()
        await graceful_shutdown(bot, dp)


if __name__ == "__main__":
    asyncio.run(main())
