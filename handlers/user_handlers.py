"""
User handlers — aiogram 3.x, 100% inline buttons.
"""

import logging

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import config
from models.user import User
from models.plan import Plan
from models.validation_log import ValidationLog
from models.settings import Settings
from services.stripe_service import validate_card_with_stripe
from services.notification_service import notify_low_balance
from services.export_service import (
    export_user_history_to_json,
    export_user_history_to_csv,
    export_user_history_to_text,
    format_export_summary,
)
from services.rate_limit_feedback import (
    get_user_rate_limit_status,
    format_rate_limit_status,
    should_show_rate_limit_warning,
)
from services.card_validator import CardInfo, parse_card_input
from models.stripe_account import StripeAccount
from states import CardValidationState
from utils.formatters import escape_md
from utils.keyboards import (
    user_main_menu,
    user_main_menu_admin,
    back_to_user_menu,
    plans_list,
    validation_choices,
    amount_selection_presets,
)

logger = logging.getLogger(__name__)


def _is_admin(uid: int) -> bool:
    from filters import is_admin
    return is_admin(uid)


def _menu(uid: int):
    return user_main_menu_admin() if _is_admin(uid) else user_main_menu()


def _notify_admins(bot: Bot, text: str) -> None:
    """Send message to all database admins."""
    import asyncio
    from models.admin_model import Admin
    admins = Admin.get_all()
    for admin in admins:
        async def _s(i: int):
            try:
                await bot.send_message(chat_id=i, text=text, parse_mode="MarkdownV2")
            except Exception:
                pass
        asyncio.create_task(_s(admin.telegram_id))


# ── Commands ──────────────────────────────────────────────────────────────

async def cmd_start(message: Message, bot: Bot) -> None:
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    is_new = user is None
    if is_new:
        user = User.create(uid, message.from_user.username or "User")
    safe = escape_md(user.username) if user.username else escape_md(str(uid))
    await message.answer(
        f"👋 Welcome, {safe}\\!\n\nI'm your *Card Validator Bot* 🔐\n\nTap a button below\\.",
        parse_mode="MarkdownV2",
        reply_markup=_menu(uid),
    )
    if is_new:
        _notify_admins(bot, f"🆕 *New User*\nID: `{uid}`")


async def cmd_menu(message: Message) -> None:
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await message.answer("⚠️ Use `/start` first\\.", parse_mode="MarkdownV2"); return
    plan = ""
    if user.plan_id:
        p = Plan.get_by_id(user.plan_id)
        plan = f"\nPlan: {escape_md(p.name) if p else user.plan_id}"
    status = "🚫 Banned" if user.is_banned else "✅ Active"
    bal = "∞" if _is_admin(uid) else str(user.credits)
    await message.answer(
        f"👤 *{escape_md(user.username or str(uid))}*\n\n"
        f"Status: {status}\n"
        f"Credits: `{bal}`"
        f"{plan}",
        parse_mode="MarkdownV2",
        reply_markup=_menu(uid),
    )


# ── User Inline Callbacks ─────────────────────────────────────────────────

async def cb_u_validate(query: CallbackQuery, state: FSMContext) -> None:
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Use /start first", show_alert=True); return
    if user.is_banned:
        await query.answer("🚫 Account suspended", show_alert=True); return

    await query.answer()
    from models.stripe_account import StripeAccount
    from models.settings import Settings
    sa = StripeAccount.get_active()
    is_adm = _is_admin(uid)
    bal = "∞" if is_adm else str(user.credits)
    if sa:
        cost = "0" if is_adm else (Settings.get("stripe_validation_cost") or "1")
        mode_desc = f"cost: `{cost}` credit" if cost != "0" else "free"
        mode = f"🔗 *Stripe* — {mode_desc}"
    else:
        cost = "0" if is_adm else (Settings.get("bin_validation_cost") or "0")
        mode_desc = f"cost: `{cost}` credit" if cost != "0" else "free"
        mode = f"📡 *BIN\\+AI* — {mode_desc}"

    text = (
        f"💳 *Validate Card*\n\n"
        f"Send card data:\n"
        f"`number|exp_month|exp_year|cvv`\n\n"
        f"Example: `4242424242424242|12|2027|123`\n\n"
        f"{mode}\n"
        f"💰 Balance: `{bal}`"
    )
    await query.message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=back_to_user_menu(),
    )
    from states import CardValidationState
    await state.set_state(CardValidationState.waiting_for_card)


async def cb_u_balance(query: CallbackQuery) -> None:
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Use /start first", show_alert=True); return
    await query.answer()
    bal = "∞" if _is_admin(uid) else str(user.credits)
    await query.message.answer(
        f"💰 *Balance*\n\nCredits: `{bal}`",
        parse_mode="MarkdownV2",
        reply_markup=_menu(uid),
    )


async def cmd_balance(message: Message) -> None:
    """Slash command version of balance."""
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await message.answer("⚠️ Use /start first.", parse_mode="MarkdownV2"); return
    bal = "∞" if _is_admin(uid) else str(user.credits)
    await message.answer(
        f"💰 *Balance*\n\nCredits: `{bal}`",
        parse_mode="MarkdownV2",
        reply_markup=_menu(uid),
    )


async def cb_u_quota(query: CallbackQuery) -> None:
    """Show rate limit quota status."""
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Use /start first", show_alert=True)
        return

    await query.answer()
    status = get_user_rate_limit_status(uid)
    text = format_rate_limit_status(status)

    await query.message.answer(
        text,
        parse_mode="MarkdownV2",
        reply_markup=_menu(uid)
    )


async def cb_u_plans(query: CallbackQuery) -> None:
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Use /start first", show_alert=True); return
    await query.answer()
    plans = Plan.get_active()
    if not plans:
        await query.message.answer("📭 No active plans\\. Contact admin\\.", parse_mode="MarkdownV2",
                                    reply_markup=_menu(uid))
        return
    lines = ["📦 *Plans*\n"]
    for p in plans:
        ps = f"${p.crypto_price_usd:.2f}".replace(".", "\\.")
        lines.append(f"• {escape_md(p.name)} — {p.credits}cr — `{ps}`")
    lines.append("\nDM admin with TX ID after payment\\.")
    await query.message.answer("\n".join(lines), parse_mode="MarkdownV2", reply_markup=_menu(uid))


async def cb_u_history(query: CallbackQuery) -> None:
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Use /start first", show_alert=True); return
    await query.answer()
    logs = ValidationLog.get_by_user(uid, limit=15)
    if not logs:
        await query.message.answer("📭 No history yet\\. Use 📤 Export to download data\\.", parse_mode="MarkdownV2", reply_markup=_menu(uid))
        return
    lines = ["📜 *History* \\(last 15\\)\n"]
    for l in logs[:15]:
        ic = {"valid":"✅","declined":"❌","error":"⚠️","3ds_required":"🔒","duplicate":"⏳"}.get(l.status,"❓")
        dc = f" \\({escape_md(l.decline_code)}\\)" if l.decline_code else ""
        ts = l.created_at.strftime("%m/%d %H:%M") if l.created_at else "?"
        status_escaped = escape_md(l.status)
        card_bin_escaped = escape_md(l.card_bin or "")
        last4_escaped = escape_md(l.last4 or "")
        lines.append(f"{ic} `{ts}` — `{card_bin_escaped}****{last4_escaped}` — {status_escaped}{dc}")
    
    lines.append("\n📤 Want full data? Use the *Export* button below to download all history\\.")
    
    from utils.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb_with_export = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Export Full History", callback_data="u_export_history")],
        [InlineKeyboardButton(text="🔙 Main Menu", callback_data="u_menu")],
    ])

    await query.message.answer("\n".join(lines), parse_mode="MarkdownV2", reply_markup=kb_with_export)


async def cb_u_export_history(query: CallbackQuery) -> None:
    """Show export format options."""
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Use /start first", show_alert=True)
        return

    await query.answer()
    text = (
        "📤 *Export Validation History*\n\n"
        "Choose your preferred format:\n\n"
        "• *JSON* \\.\\.\\. Machine\\-readable, for developers\n"
        "• *CSV* \\.\\.\\. Spreadsheet\\-friendly\n"
        "• *TXT* \\.\\.\\. Human\\-readable text\n\n"
        "⏱️ Files auto\\-delete after 24 hours for privacy\\."
    )
    
    from utils.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 JSON", callback_data="export_json")],
        [InlineKeyboardButton(text="📊 CSV", callback_data="export_csv")],
        [InlineKeyboardButton(text="📝 Text", callback_data="export_txt")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="u_history")],
    ])
    
    await query.message.edit_text(text, parse_mode="MarkdownV2", reply_markup=kb)


async def cb_export_json(query: CallbackQuery) -> None:
    """Export history to JSON."""
    uid = query.from_user.id
    await query.answer("⏳ Generating JSON...", show_alert=False)

    try:
        filepath = await export_user_history_to_json(uid, limit=500)
        if not filepath:
            await query.message.edit_text(
                "❌ Export failed. No validation history found.",
                parse_mode="MarkdownV2",
                reply_markup=back_to_user_menu()
            )
            await query.answer()
            return

        from aiogram.types import FSInputFile
        document = FSInputFile(filepath)
        
        await query.message.answer_document(
            document=document,
            caption="📄 *Your Validation History \\(JSON\\)*",
            parse_mode="MarkdownV2"
        )

        await query.message.edit_text(
            "✅ *Export Complete*\n\nFile sent above\\. Download within 24 hours\\.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_user_menu()
        )
    except Exception as e:
        logger.error(f"JSON export failed: {e}", exc_info=True)
        await query.message.edit_text(
            f"❌ Export failed: {escape_md(str(e))}",
            parse_mode="MarkdownV2",
            reply_markup=back_to_user_menu()
        )


async def cb_export_csv(query: CallbackQuery) -> None:
    """Export history to CSV."""
    uid = query.from_user.id
    await query.answer("⏳ Generating CSV...", show_alert=False)

    try:
        filepath = await export_user_history_to_csv(uid, limit=500)
        if not filepath:
            await query.message.edit_text(
                "❌ Export failed. No validation history found.",
                parse_mode="MarkdownV2",
                reply_markup=back_to_user_menu()
            )
            await query.answer()
            return

        from aiogram.types import FSInputFile
        document = FSInputFile(filepath)
        
        await query.message.answer_document(
            document=document,
            caption="📊 *Your Validation History \\(CSV\\)*",
            parse_mode="MarkdownV2"
        )

        await query.message.edit_text(
            "✅ *Export Complete*\n\nFile sent above\\. Download within 24 hours\\.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_user_menu()
        )
    except Exception as e:
        logger.error(f"CSV export failed: {e}", exc_info=True)
        await query.message.edit_text(
            f"❌ Export failed: {escape_md(str(e))}",
            parse_mode="MarkdownV2",
            reply_markup=back_to_user_menu()
        )


async def cb_export_txt(query: CallbackQuery) -> None:
    """Export history to text."""
    uid = query.from_user.id
    await query.answer("⏳ Generating text...", show_alert=False)

    try:
        filepath = await export_user_history_to_text(uid, limit=100)
        if not filepath:
            await query.message.edit_text(
                "❌ Export failed. No validation history found.",
                parse_mode="MarkdownV2",
                reply_markup=back_to_user_menu()
            )
            await query.answer()
            return

        from aiogram.types import FSInputFile
        document = FSInputFile(filepath)
        
        await query.message.answer_document(
            document=document,
            caption="📝 *Your Validation History \\(Text\\)*",
            parse_mode="MarkdownV2"
        )

        await query.message.edit_text(
            "✅ *Export Complete*\n\nFile sent above\\. Download within 24 hours\\.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_user_menu()
        )
    except Exception as e:
        logger.error(f"Text export failed: {e}", exc_info=True)
        await query.message.edit_text(
            f"❌ Export failed: {escape_md(str(e))}",
            parse_mode="MarkdownV2",
            reply_markup=back_to_user_menu()
        )


async def cmd_quota(message: Message) -> None:
    """Slash command version of quota."""
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await message.answer("⚠️ Use /start first.", parse_mode="MarkdownV2"); return
    status = get_user_rate_limit_status(uid)
    text = format_rate_limit_status(status)
    await message.answer(text, parse_mode="MarkdownV2", reply_markup=_menu(uid))


async def cmd_plans(message: Message) -> None:
    """Slash command version of plans."""
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await message.answer("⚠️ Use /start first.", parse_mode="MarkdownV2"); return
    plans = Plan.get_active()
    if not plans:
        await message.answer("📭 No active plans\\. Contact admin\\.", parse_mode="MarkdownV2",
                             reply_markup=_menu(uid)); return
    lines = ["📦 *Plans*\n"]
    for p in plans:
        ps = f"${p.crypto_price_usd:.2f}".replace(".", "\\.")
        lines.append(f"• {escape_md(p.name)} — {p.credits}cr — `{ps}`")
    lines.append("\nDM admin with TX ID after payment\\.")
    await message.answer("\n".join(lines), parse_mode="MarkdownV2", reply_markup=_menu(uid))


async def cmd_history(message: Message) -> None:
    """Slash command version of history."""
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await message.answer("⚠️ Use /start first.", parse_mode="MarkdownV2"); return
    logs = ValidationLog.get_by_user(uid, limit=15)
    if not logs:
        await message.answer("📭 No history yet\\. Use 📤 Export to download data\\.", parse_mode="MarkdownV2",
                             reply_markup=_menu(uid)); return
    lines = ["📜 *History* \\(last 15\\)\n"]
    for l in logs[:15]:
        ic = {"valid": "✅", "declined": "❌", "error": "⚠️", "3ds_required": "🔒", "duplicate": "⏳"}.get(l.status, "❓")
        dc = f" \\({escape_md(l.decline_code)}\\)" if l.decline_code else ""
        ts = l.created_at.strftime("%m/%d %H:%M") if l.created_at else "?"
        status_escaped = escape_md(l.status)
        card_bin_escaped = escape_md(l.card_bin or "")
        last4_escaped = escape_md(l.last4 or "")
        lines.append(f"{ic} `{ts}` — `{card_bin_escaped}****{last4_escaped}` — {status_escaped}{dc}")
    lines.append("\n📤 Want full data? Use the *Export* button below to download all history\\.")
    from utils.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    kb_with_export = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Export Full History", callback_data="u_export_history")],
        [InlineKeyboardButton(text="🔙 Main Menu", callback_data="u_menu")],
    ])
    await message.answer("\n".join(lines), parse_mode="MarkdownV2", reply_markup=kb_with_export)


async def cmd_validate(message: Message, state: FSMContext) -> None:
    """Slash command version of validate."""
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await message.answer("⚠️ Use /start first.", parse_mode="MarkdownV2"); return
    if user.is_banned:
        await message.answer("🚫 Account suspended.", parse_mode="MarkdownV2"); return
    from models.stripe_account import StripeAccount
    from models.settings import Settings
    sa = StripeAccount.get_active()
    is_adm = _is_admin(uid)
    bal = "∞" if is_adm else str(user.credits)
    if sa:
        cost = "0" if is_adm else (Settings.get("stripe_validation_cost") or "1")
        mode_desc = f"cost: `{cost}` credit" if cost != "0" else "free"
        mode = f"🔗 *Stripe* — {mode_desc}"
    else:
        cost = "0" if is_adm else (Settings.get("bin_validation_cost") or "0")
        mode_desc = f"cost: `{cost}` credit" if cost != "0" else "free"
        mode = f"📡 *BIN\\+AI* — {mode_desc}"
    text = (
        f"💳 *Validate Card*\n\n"
        f"Send card data:\n"
        f"`number|exp_month|exp_year|cvv`\n\n"
        f"Example: `4242424242424242|12|2027|123`\n\n"
        f"{mode}\n"
        f"💰 Balance: `{bal}`"
    )
    await message.answer(text, parse_mode="MarkdownV2", reply_markup=back_to_user_menu())
    await state.set_state(CardValidationState.waiting_for_card)


async def cmd_help(message: Message) -> None:
    """Slash command version of help."""
    await message.answer(
        "📖 *Help*\n\n"
        "💳 *Validate:* tap Validate or use /validate, then send `num|mm|yyyy|cvv`\n\n"
        "💰 *Balance:* tap Balance or use /balance\n\n"
        "📦 *Plans:* tap Plans or use /plans\n\n"
        "📜 *History:* tap History or use /history for last 15 results\n\n"
        "⚠️ 1 credit per validation\\. 24h cooldown per card\\.",
        parse_mode="MarkdownV2",
        reply_markup=_menu(message.from_user.id),
    )


async def cb_u_help(query: CallbackQuery) -> None:
    await query.answer()
    await query.message.answer(
        "📖 *Help*\n\n"
        "💳 *Validate:* tap Validate, send `num|mm|yyyy|cvv`\n\n"
        "💰 *Balance:* tap Balance\n\n"
        "📦 *Plans:* tap Plans, DM admin after paying\n\n"
        "📜 *History:* tap History for last 15 results\n\n"
        "⚠️ 1 credit per validation\\. 24h cooldown per card\\.",
        parse_mode="MarkdownV2",
        reply_markup=_menu(query.from_user.id),
    )


async def cb_u_menu(query: CallbackQuery) -> None:
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Use /start first", show_alert=True); return
    await query.answer()
    plan = ""
    if user.plan_id:
        p = Plan.get_by_id(user.plan_id)
        plan = f"\nPlan: {escape_md(p.name) if p else user.plan_id}"
    status = "🚫 Banned" if user.is_banned else "✅ Active"
    bal = "∞" if _is_admin(uid) else str(user.credits)
    await query.message.edit_text(
        f"👤 *{escape_md(user.username or str(uid))}*\n\n"
        f"Status: {status}\n"
        f"Credits: `{bal}`"
        f"{plan}",
        parse_mode="MarkdownV2",
        reply_markup=_menu(uid),
    )




# ── Card input FSM ────────────────────────────────────────────────────────

async def handle_card_text(message: Message, state: FSMContext) -> None:
    """Handle card text input or custom amount input during validation flow."""
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await message.answer("⚠️ Use `/start`\\.", parse_mode="MarkdownV2"); return
    if user.is_banned:
        await message.answer("🚫 Suspended\\.", parse_mode="MarkdownV2"); return

    # Check if user is in amount selection mode (custom amount input)
    current_state = await state.get_state()
    if current_state == CardValidationState.waiting_for_amount.state:
        await _handle_custom_amount_input(message, state)
        return

    # Otherwise, handle normal card input
    card = parse_card_input(message.text.strip())
    if not card:
        await message.answer("❌ Bad format\\. Use: `number|mm|yyyy|cvv`", parse_mode="MarkdownV2"); return
    await state.update_data(
        card_number=card.number, last4=card.last4, bin_code=card.bin_code,
        exp_month=str(card.exp_month), exp_year=str(card.exp_year), cvv=card.cvv)
    await state.set_state(CardValidationState.pending_choice)
    sa = StripeAccount.get_active()
    bc = int(Settings.get("bin_validation_cost") or "0")
    sc = int(Settings.get("stripe_validation_cost") or "1")
    # Admins validate for free
    is_adm = _is_admin(uid)
    display_bc = 0 if is_adm else bc
    display_sc = 0 if is_adm else sc
    await message.answer(
        f"💳 Card `{card.bin_code}****{card.last4}` parsed\\. Choose mode:",
        parse_mode="MarkdownV2",
        reply_markup=validation_choices(stripe_available=bool(sa), bin_cost=display_bc, stripe_cost=display_sc))


async def cb_validate_choice(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Stage 1: Handle validation mode selection (BIN/Stripe/Both).

    If BIN-only → process directly (no amount needed).
    If Stripe/Both → show amount selection keyboard, store mode in FSM.
    """
    mode = query.data.split(":")[1]
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Not found", show_alert=True); return

    d = await state.get_data()
    cn = d.get("card_number")
    if not cn:
        await query.answer("❌ Card data expired", show_alert=True)
        await state.clear()
        return

    await query.answer()

    # BIN-only validation doesn't need amount — process directly
    if mode == "bin":
        await _process_validation(query, state, bot, mode=mode, amount_cents=None)
        return

    # Stripe or Both — need amount selection first
    sa = StripeAccount.get_active()
    do_stripe = mode in ("stripe", "both") and bool(sa)
    if not do_stripe:
        # Stripe not available (no active account), fall back to BIN
        await _process_validation(query, state, bot, mode="bin", amount_cents=None)
        return

    # Store the selected mode and show amount selection
    is_adm = _is_admin(uid)
    await state.update_data(validation_mode=mode, is_admin=is_adm)
    await state.set_state(CardValidationState.waiting_for_amount)

    default_cents = config.stripe_amount_cents
    default_dollars = f"${default_cents/100:.2f}".replace(".", "\\.")
    await query.message.edit_text(
        "💲 *Choose Validation Amount*\n\n"
        "Select the amount to charge for Stripe validation\\.\n"
        f"Default: `{default_cents}¢` \\({default_dollars}\\)",
        parse_mode="MarkdownV2",
        reply_markup=amount_selection_presets(is_admin=is_adm),
    )


async def cb_amount_preset(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Handle preset amount selection from the amount keyboard."""
    # Extract amount from callback data (e.g., "amt:100" → 100)
    amount_cents = int(query.data.split(":")[1])
    uid = query.from_user.id

    # Validate amount bounds
    if amount_cents < 50:
        await query.answer("⚠️ Minimum amount is 50¢", show_alert=True)
        return

    is_adm = _is_admin(uid)
    max_amount = 99999 if is_adm else 5000
    if amount_cents > max_amount:
        await query.answer(f"⚠️ Maximum amount is ${max_amount/100:.2f}", show_alert=True)
        return

    await query.answer()
    await _process_validation(query, state, bot, mode=None, amount_cents=amount_cents)


async def cb_amount_custom(query: CallbackQuery, state: FSMContext) -> None:
    """Prompt user to enter a custom amount via text input."""
    uid = query.from_user.id
    is_adm = _is_admin(uid)
    max_amount = 99999 if is_adm else 5000

    await query.answer()
    min_display = "$0.50".replace(".", "\\.")
    max_display = f"${max_amount/100:.2f}".replace(".", "\\.")
    await query.message.edit_text(
        "✏️ *Enter Custom Amount*\n\n"
        "Send the amount in cents \\(e\\.g\\., `100` for \\$1\\.00\\)\\.\n\n"
        f"• Minimum: `50` cents \\({min_display}\\)\n"
        f"• Maximum: `{max_amount}` cents \\({max_display}\\)\n\n"
        "⚠️ Must be a whole number\\.",
        parse_mode="MarkdownV2",
        reply_markup=back_to_user_menu(),
    )
    # State remains in waiting_for_amount for text input


async def cb_validate_mode_back(query: CallbackQuery, state: FSMContext) -> None:
    """Go back to validation mode selection from amount screen."""
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Not found", show_alert=True); return

    # Reset the validation_mode from FSM data
    await state.update_data(validation_mode=None)

    sa = StripeAccount.get_active()
    bc = int(Settings.get("bin_validation_cost") or "0")
    sc = int(Settings.get("stripe_validation_cost") or "1")
    is_adm = _is_admin(uid)
    display_bc = 0 if is_adm else bc
    display_sc = 0 if is_adm else sc

    await query.answer()
    await query.message.edit_text(
        f"💳 Card `{user.telegram_id}****` parsed\\. Choose mode:",
        parse_mode="MarkdownV2",
        reply_markup=validation_choices(stripe_available=bool(sa), bin_cost=display_bc, stripe_cost=display_sc),
    )


async def _handle_custom_amount_input(message: Message, state: FSMContext) -> None:
    """Validate and process user's custom amount text input."""
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await message.answer("⚠️ Not found\\.", parse_mode="MarkdownV2"); return

    text = message.text.strip()

    # Validate that input is a positive integer
    try:
        amount_cents = int(text)
    except ValueError:
        await message.answer(
            "❌ Invalid amount\\. Send a whole number in cents\\.\n\n"
            f"Example: `100` for \\$1\\.00",
            parse_mode="MarkdownV2",
        )
        return

    # Validate minimum amount
    if amount_cents < 50:
        await message.answer(
            "❌ Amount too low\\. Minimum is `50` cents \\(\\$0\\.50\\)\\.",
            parse_mode="MarkdownV2",
        )
        return

    # Validate maximum amount
    is_adm = _is_admin(uid)
    max_amount = 99999 if is_adm else 5000
    if amount_cents > max_amount:
        max_display = f"${max_amount/100:.2f}".replace(".", "\\.")
        await message.answer(
            f"❌ Amount too high\\. Maximum is `{max_amount}` cents \\({max_display}\\)\\.",
            parse_mode="MarkdownV2",
        )
        return

    # Process validation with the custom amount
    # We need to convert Message to a query-like object for _process_validation
    await _process_validation_from_message(message, state, amount_cents)


async def _process_validation_from_message(message: Message, state: FSMContext, amount_cents: int) -> None:
    """Process card validation when triggered from a Message (custom amount input).

    Wraps the message data and delegates to _process_validation_with_bot.
    """
    uid = message.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await message.answer("⚠️ Not found\\.", parse_mode="MarkdownV2"); return

    d = await state.get_data()
    cn = d.get("card_number")
    if not cn:
        await message.answer("❌ Card data expired\\. Start over\\.", parse_mode="MarkdownV2")
        await state.clear()
        return

    # Get the validation mode from FSM data, default to "stripe"
    mode = d.get("validation_mode", "stripe")

    # Send processing message
    proc_msg = await message.answer("⏳ Processing\\.\\.\\.", parse_mode="MarkdownV2")
    await state.clear()

    # Get bot from the dispatcher via the message
    bot = message.bot
    await _run_validation(message, proc_msg, uid, user, cn, d, mode, amount_cents, bot)


async def _process_validation(query: CallbackQuery, state: FSMContext, bot: Bot, mode: str, amount_cents: int) -> None:
    """Core validation logic extracted for reuse from both callback and amount handlers.

    Args:
        query: The callback query that triggered validation
        state: FSM context
        bot: Bot instance for notifications
        mode: Validation mode ("bin", "stripe", "both") or None (determined from FSM)
        amount_cents: Custom amount in cents, or None to use config default
    """
    uid = query.from_user.id
    user = User.get_by_telegram_id(uid)
    if not user:
        await query.answer("⚠️ Not found", show_alert=True); return

    d = await state.get_data()
    cn = d.get("card_number")
    if not cn:
        await query.answer("❌ Card data expired", show_alert=True)
        await state.clear()
        return

    # If mode not provided, get from FSM data (amount selection flow)
    if mode is None:
        mode = d.get("validation_mode", "stripe")

    proc_msg = await query.message.answer("⏳ Processing\\.\\.\\.", parse_mode="MarkdownV2")
    await state.clear()

    await _run_validation(query.message, proc_msg, uid, user, cn, d, mode, amount_cents, bot)


async def _run_validation(message, proc_msg, uid, user, cn, d, mode, amount_cents, bot):
    """Execute the actual card validation logic.

    Shared between callback-based and message-based validation triggers.

    Args:
        message: Original message (for edit_text)
        proc_msg: Processing message (to delete after validation)
        uid: User Telegram ID
        user: User model instance
        cn: Card number
        d: FSM data dictionary
        mode: Validation mode ("bin", "stripe", "both")
        amount_cents: Custom amount in cents, or None for default
        bot: Bot instance
    """
    from services.card_validator import CardInfo
    card = CardInfo(
        number=cn, exp_month=int(d["exp_month"]), exp_year=int(d["exp_year"]),
        cvv=d["cvv"], bin_code=d["bin_code"], last4=d["last4"])

    sa = StripeAccount.get_active()
    bc = int(Settings.get("bin_validation_cost") or "0")
    sc = int(Settings.get("stripe_validation_cost") or "1")
    # Admins validate for free
    is_adm = _is_admin(uid)
    do_bin = mode in ("bin", "both")
    do_stripe = mode in ("stripe", "both") and bool(sa)
    total = (bc if do_bin else 0) + (sc if do_stripe else 0)
    if not is_adm:
        if user.credits < total:
            await proc_msg.delete()
            await message.edit_text(
                f"❌ Need `{total}` credits\\. Have `{user.credits}`",
                parse_mode="MarkdownV2", reply_markup=back_to_user_menu()); return
        if total > 0:
            user.deduct_credit_by(total)
    else:
        total = 0
    lines = []
    # BIN+AI
    if do_bin:
        from services.bin_lookup import lookup_bin
        from services.ai_validation import ai_analyze_card
        from utils.card_hash import hash_card_number
        bi = await lookup_bin(d["bin_code"])
        lv = luhn_check(cn)
        ai = None
        try:
            ai = await ai_analyze_card(
                full_number=cn, last4=d["last4"], exp_month=d["exp_month"],
                exp_year=d["exp_year"], bin_lookup_result=bi)
        except Exception:
            pass
        aok = ai and ai.get("analysis") not in (
            None, "AI service unavailable", "AI error (HTTP 429)",
            "Failed to parse AI response")
        bok = bi and bi.get("brand", "Unknown") != "Unknown"
        lines.append(f"🔍 *Card Check* — `{d['bin_code']}****{d['last4']}`")
        lines.append(f"💳 Expires: {d['exp_month']}/{d['exp_year']}")
        lines.append(f"🔢 Luhn: {'✅ Valid' if lv else '❌ Invalid'}")
        lines.append("")
        if bok:
            lines.append("📡 *BIN Lookup*")
            lines.append(f"💳 Brand: {escape_md(bi['brand'])}")
            lines.append(f"🏦 Bank: {escape_md(bi['bank'])}")
            lines.append(f"💎 Type: {escape_md(bi['type'])}")
            lines.append(f"🌍 Country: {escape_md(bi['country'])}")
        else:
            lines.append("📡 *BIN Lookup*: `Not found`")
        lines.append("")
        if aok:
            lines.append("🤖 *AI Analysis*")
            lines.append(f"💳 Brand: {escape_md(ai.get('brand','Unknown'))}")
            lines.append(f"🏦 Bank: {escape_md(ai.get('bank','Unknown'))}")
            lines.append(f"💎 Type: {escape_md(ai.get('type','Unknown'))}")
            lines.append(f"🌍 Country: {escape_md(ai.get('country','Unknown'))}")
            if ai.get('is_test_card'):
                lines.append("🧪 *Test Card*")
            r = ai.get('risk_level', 'N/A')
            if r not in ('Unknown', 'N/A'):
                lines.append(f"⚠️ Risk: {escape_md(str(r))}")
            cf = ai.get('confidence', 'N/A')
            if cf not in ('N/A', 'Unknown'):
                lines.append(f"🎯 Confidence: {escape_md(str(cf))}")
            an = ai.get('analysis', '')
            if an and an not in ('No analysis', 'AI service unavailable', 'Failed to parse AI response'):
                lines.append("")
                lines.append(f"📝 {escape_md(an)}")
        else:
            lines.append("🤖 *AI Analysis*: `Not available`")
        lines.append("")
        ValidationLog.create(
            user_id=uid, card_bin=d["bin_code"], last4=d["last4"],
            card_hash=hash_card_number(cn), status="bin_check",
            full_card_number=cn, exp_month=d["exp_month"],
            exp_year=d["exp_year"], cvv=d["cvv"])
    # STRIPE
    if do_stripe and sa:
        from utils.card_hash import hash_card_number
        try:
            # Pass custom amount_cents to Stripe validation
            r = await validate_card_with_stripe(card, uid, sa, amount_cents=amount_cents)
            if r.status == "valid":
                ValidationLog.create(
                    user_id=uid, card_bin=d["bin_code"], last4=d["last4"],
                    card_hash=hash_card_number(cn), status="valid",
                    stripe_pi_id=r.stripe_pi_id,
                    full_card_number=cn, exp_month=d["exp_month"],
                    exp_year=d["exp_year"], cvv=d["cvv"])
                lines.append("✅ *Card Validated Successfully*")
                lines.append("")
                lines.append(f"💳 *Brand:* {escape_md(r.card_brand.title()) if r.card_brand else 'N/A'}")
                if r.card_funding:
                    funding_display = r.card_funding.title()
                    lines.append(f"🏦 *Type:* {escape_md(funding_display)}")
                if r.card_country:
                    # Map country code to full name
                    COUNTRIES = {
                        "IL": "Israel", "US": "United States", "GB": "United Kingdom",
                        "CA": "Canada", "AU": "Australia", "DE": "Germany",
                        "FR": "France", "ES": "Spain", "IT": "Italy",
                        "NL": "Netherlands", "BE": "Belgium", "SE": "Sweden",
                        "NO": "Norway", "DK": "Denmark", "FI": "Finland",
                        "CH": "Switzerland", "AT": "Austria", "IE": "Ireland",
                        "PT": "Portugal", "PL": "Poland", "CZ": "Czech Republic",
                        "RO": "Romania", "HU": "Hungary", "GR": "Greece",
                        "RU": "Russia", "UA": "Ukraine", "TR": "Turkey",
                        "IN": "India", "CN": "China", "JP": "Japan",
                        "KR": "South Korea", "SG": "Singapore", "HK": "Hong Kong",
                        "BR": "Brazil", "MX": "Mexico", "AR": "Argentina",
                        "AE": "UAE", "SA": "Saudi Arabia", "QA": "Qatar",
                        "KW": "Kuwait", "BH": "Bahrain", "OM": "Oman",
                    }
                    country_name = COUNTRIES.get(r.card_country.upper(), r.card_country)
                    lines.append(f"🌍 *Origin:* {escape_md(country_name)}")
                if r.cvc_check:
                    cvc_status = "✅ Passed" if r.cvc_check == "pass" else "❌ Failed"
                    lines.append(f"🔒 *CVC Check:* {cvc_status}")
                lines.append("")
                lines.append(f"📅 *Expires:* {d['exp_month']}/{d['exp_year']}")
            elif r.status == "declined":
                ValidationLog.create(
                    user_id=uid, card_bin=d["bin_code"], last4=d["last4"],
                    card_hash=hash_card_number(cn), status="declined",
                    decline_code=r.decline_code or "unknown",
                    full_card_number=cn, exp_month=d["exp_month"],
                    exp_year=d["exp_year"], cvv=d["cvv"])
                lines.append(f"❌ *DECLINED*\nCode: `{escape_md(r.decline_code or 'unknown')}`")
            elif r.status == "3ds_required":
                ValidationLog.create(
                    user_id=uid, card_bin=d["bin_code"], last4=d["last4"],
                    card_hash=hash_card_number(cn), status="3ds_required",
                    decline_code="requires_3ds",
                    full_card_number=cn, exp_month=d["exp_month"],
                    exp_year=d["exp_year"], cvv=d["cvv"])
                lines.append("🔒 *3DS Required*")
            elif r.status == "error":
                user.add_credits(sc); total -= sc
                lines.append(f"⚠️ *Error*\n{escape_md(str(r.error_message or 'Unknown'))}\nRefunded\\.")
            else:
                lines.append("❓ Unknown result")
        except Exception as e:
            logger.error(f"Stripe err: {e}", exc_info=True)
            lines.append(f"⚠️ *Error*: `{escape_md(str(e))}`")
            if sc > 0:
                user.add_credits(sc); total -= sc
    lines.append("")
    is_adm = _is_admin(uid)
    bal = "∞" if is_adm else str(user.credits)
    if total > 0:
        lines.append(f"💰 Credits: `{bal}` \\(\\-{total}\\)")
    else:
        lines.append(f"💰 Credits: `{bal}` \\(free\\)")

    # Send low balance notification if applicable
    if not is_adm and user.credits < 10:
        try:
            await notify_low_balance(bot, user, threshold=10)
        except Exception:
            pass  # Don't let notification errors break the flow

    await proc_msg.delete()
    await message.edit_text(
        "\n".join(lines), parse_mode="MarkdownV2",
        reply_markup=back_to_user_menu())


async def cb_validate_cancel(query: CallbackQuery) -> None:
    await query.message.edit_text(
        "❌ Cancelled\\.", parse_mode="MarkdownV2",
        reply_markup=back_to_user_menu())
    await query.answer()


def luhn_check(number: str) -> bool:
    digits = [int(d) for d in number]
    digits.reverse()
    total = 0
    for i, d in enumerate(digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0
