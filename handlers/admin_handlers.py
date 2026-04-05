"""
Admin handlers — aiogram 3.x, 100% inline buttons, full back navigation.
"""

import logging

from aiogram import Bot, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from config import config
from models.user import User
from models.plan import Plan
from models.stripe_account import StripeAccount
from models.validation_log import ValidationLog
from models.admin_log import AdminLog
from models.credit_transaction import CreditTransaction
from models.settings import Settings
from services.crypto_service import encrypt
from utils.formatters import escape_md
from utils.validators import (
    validate_positive_integer,
    validate_non_negative_integer,
    validate_positive_float,
    validate_crypto_address,
    validate_telegram_username,
    validate_stripe_secret_key,
    validate_amount_cents,
    validate_plan_name,
    validate_telegram_id,
    sanitize_text,
    ValidationError,
)
from utils.keyboards import (
    admin_panel,
    users_list,
    user_detail,
    stripe_list,
    stripe_detail,
    plans_list,
    plan_detail,
    settings_keyboard,
    confirm,
    back_to_admin_panel,
)

logger = logging.getLogger(__name__)


def _is_admin(uid: int) -> bool:
    from filters import is_admin
    return is_admin(uid)


def _require_super_admin(query: CallbackQuery) -> bool:
    """Check if user is super admin. Sends alert and returns False if not."""
    from models.admin_model import Admin
    if not Admin.is_super_admin(query.from_user.id):
        query.answer("🚫 Super admin only!", show_alert=True)
        return False
    return True


def _is_target_admin(query: CallbackQuery, target_id: int) -> bool:
    """Check if target is an admin. Sends alert and returns True if protected."""
    from models.admin_model import Admin
    if Admin.is_admin(target_id):
        query.answer("🛡️ Cannot modify another admin!", show_alert=True)
        return True
    return False


def _is_self(query: CallbackQuery, target_id: int) -> bool:
    """Check if user targeting themselves. Sends alert and returns True if so."""
    if query.from_user.id == target_id:
        query.answer("🚫 Cannot modify your own account!", show_alert=True)
        return True
    return False


def _log(uid: int, uname: str, action: str, details: dict = None):
    AdminLog.log(admin_id=uid, admin_username=uname, action=action, details=details)


async def _deny(m: Message):
    await m.answer("🚫 Admin only\\.", parse_mode="MarkdownV2")


# ── Admin FSM ──────────────────────────────────────────────────────────────

class AdminFSM(StatesGroup):
    search = State()
    add_stripe = State()
    rename_stripe = State()
    create_plan = State()
    edit_plan_name = State()
    edit_plan_price = State()
    edit_plan_credits = State()
    broadcast = State()
    set_usdt = State()
    set_btc = State()
    set_contact = State()
    add_credits = State()
    set_stripe_cost = State()
    set_bin_cost = State()
    add_admin = State()
    reverse_credits = State()
    reversal_reason = State()


# ── Commands ──────────────────────────────────────────────────────────────

async def cmd_admin(message: Message) -> None:
    uid = message.from_user.id
    uname = message.from_user.username or ""
    from models.admin_model import Admin
    # Check if already an admin
    if Admin.is_admin(uid):
        is_sa = Admin.is_super_admin(uid)
        await message.answer("🔧 *Admin Panel*", parse_mode="MarkdownV2", reply_markup=admin_panel(is_super_admin=is_sa))
        return
    # Bootstrap: first user ever becomes super admin ONLY if no admins exist
    if not Admin.get_all():
        Admin.add(uid, username=uname, role="super_admin")
        _log(uid, uname, "bootstrap_admin", {"role": "super_admin"})
        await message.answer("🔧 *Admin Panel*\n\nYou are the first admin\\! You are now *super admin*\\.", parse_mode="MarkdownV2", reply_markup=admin_panel(is_super_admin=True))
    else:
        await _deny(message)


# ── Admin: Main ────────────────────────────────────────────────────────────

async def cb_a_main(query: CallbackQuery) -> None:
    uid = query.from_user.id
    from models.admin_model import Admin
    if not Admin.is_admin(uid):
        await query.answer("🚫 Admin only", show_alert=True); return
    is_sa = Admin.is_super_admin(uid)
    await query.message.edit_text("🔧 *Admin Panel*", parse_mode="MarkdownV2", reply_markup=admin_panel(is_super_admin=is_sa))
    await query.answer()


# ── Admin: Users ───────────────────────────────────────────────────────────

async def cb_a_users(query: CallbackQuery) -> None:
    page = int(query.data.split(":")[1])
    pp = 8
    total = User.count()
    if total == 0:
        txt = "📭 No registered users\\."
        kb = back_to_admin_panel()
        await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=kb)
        await query.answer(); return
    tp = max(1, (total + pp - 1) // pp)
    off = (page - 1) * pp
    users = User.get_all(limit=pp, offset=off)
    txt = f"👥 *Users* \\({total}\\) — Page {page}/{tp}\n\n_Tap a user below to manage\\._"
    kb = users_list(page, tp, total, users)
    await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=kb)
    await query.answer()


async def cb_user_detail(query: CallbackQuery) -> None:
    tid = int(query.data.split(":")[1])
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    pn = "None"
    if u.plan_id:
        p = Plan.get_by_id(u.plan_id)
        pn = escape_md(p.name) if p else str(u.plan_id)
    safe = escape_md(u.username) if u.username else str(tid)
    cr = escape_md(u.created_at.strftime("%Y-%m-%d")) if u.created_at else "?"
    ban = "🚫 Banned" if u.is_banned else "✅ Active"
    is_adm = _is_admin(tid)
    txt = f"👤 *{safe}*"
    if is_adm:
        txt += " 🛡️"
    txt += f"\n\nID: `{tid}`\nStatus: {ban}\nCredits: `{u.credits}`\nPlan: {pn}\nJoined: {cr}"
    await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=user_detail(tid, u.is_banned, is_admin_target=is_adm))
    await query.answer()


async def cb_user_search(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.search)
    await query.message.answer("🔍 *Search* — send username or ID:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


# ── Admin: User Actions ───────────────────────────────────────────────────

async def cb_user_add_credits(query: CallbackQuery, state: FSMContext) -> None:
    tid = int(query.data.split(":")[1])
    await state.update_data(tid=tid)
    await state.set_state(AdminFSM.add_credits)
    await query.message.answer(f"💰 Send credit amount for user `{tid}`:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_user_reset_credits(query: CallbackQuery) -> None:
    tid = int(query.data.split(":")[1])
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    await query.message.answer(
        f"🔄 Reset credits for *{escape_md(u.username or str(tid))}* to 0?",
        parse_mode="MarkdownV2",
        reply_markup=confirm(f"urescr_ok:{tid}", f"udet:{tid}")
    )
    await query.answer()


async def cb_user_reset_ok(query: CallbackQuery, bot: Bot) -> None:
    tid = int(query.data.split(":")[1])
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    old = u.credits
    u.reset_credits()
    _log(query.from_user.id, query.from_user.username, "reset_user", {"tid": tid})
    try:
        await bot.send_message(tid, "🔄 Credits reset to `0`\\.", parse_mode="MarkdownV2")
    except Exception:
        pass
    await query.message.answer(f"✅ Reset: `{old}` → `0`", parse_mode="MarkdownV2",
                                reply_markup=user_detail(tid, u.is_banned, is_admin_target=_is_admin(tid)))
    await query.answer()


async def cb_user_ban(query: CallbackQuery, bot: Bot) -> None:
    tid = int(query.data.split(":")[1])
    if _is_self(query, tid): return
    if _is_target_admin(query, tid): return
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    if u.is_banned:
        await query.answer("Already banned", show_alert=True); return
    u.ban()
    _log(query.from_user.id, query.from_user.username, "ban_user", {"tid": tid})
    try:
        await bot.send_message(tid, "🚫 Account suspended\\.", parse_mode="MarkdownV2")
    except Exception:
        pass
    await query.answer("🚫 Banned")
    await cb_user_detail(query)


async def cb_user_unban(query: CallbackQuery, bot: Bot) -> None:
    tid = int(query.data.split(":")[1])
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    if not u.is_banned:
        await query.answer("Not banned", show_alert=True); return
    u.unban()
    _log(query.from_user.id, query.from_user.username, "unban_user", {"tid": tid})
    try:
        await bot.send_message(tid, "✅ Account restored\\.", parse_mode="MarkdownV2")
    except Exception:
        pass
    await query.answer("✅ Unbanned")
    await cb_user_detail(query)


async def cb_user_delete(query: CallbackQuery) -> None:
    tid = int(query.data.split(":")[1])
    if _is_self(query, tid): return
    if _is_target_admin(query, tid): return
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    await query.message.answer(
        f"🗑️ Delete *{escape_md(u.username or str(tid))}*?",
        parse_mode="MarkdownV2",
        reply_markup=confirm(f"udel_ok:{tid}", f"udet:{tid}")
    )
    await query.answer()


async def cb_user_delete_ok(query: CallbackQuery) -> None:
    tid = int(query.data.split(":")[1])
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    if _is_target_admin(query, tid): return
    if _is_self(query, tid): return
    nm = u.username or str(tid)
    User.delete(tid)
    _log(query.from_user.id, query.from_user.username, "delete_user", {"tid": tid})
    await query.message.edit_text(f"🗑️ `{escape_md(nm)}` deleted\\.", parse_mode="MarkdownV2",
                                   reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_user_history(query: CallbackQuery) -> None:
    tid = int(query.data.split(":")[1])
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    logs = ValidationLog.get_by_user(tid, limit=15)
    d = escape_md(u.username) if u.username else str(tid)
    if not logs:
        await query.message.answer(f"📭 No history for {d}\\.", parse_mode="MarkdownV2",
                                    reply_markup=back_to_admin_panel())
        await query.answer(); return
    lines = [f"📜 *{d}*\n"]
    for l in logs[:15]:
        ic = {"valid":"✅","declined":"❌","error":"⚠️","3ds_required":"🔒"}.get(l.status,"❓")
        dc = f" \\({escape_md(l.decline_code)}\\)" if l.decline_code else ""
        lines.append(f"{ic} `{l.card_bin}****{l.last4}` — {l.status}{dc}")
    await query.message.answer("\n".join(lines), parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_user_credits(query: CallbackQuery) -> None:
    tid = int(query.data.split(":")[1])
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    txs = CreditTransaction.get_by_user(tid, limit=20)
    d = escape_md(u.username) if u.username else str(tid)
    if not txs:
        await query.message.answer(f"📭 No txns for {d}\\.", parse_mode="MarkdownV2",
                                    reply_markup=back_to_admin_panel())
        await query.answer(); return
    icons = {"validation":"💳","admin_add":"💰","admin_reset":"🔄","plan_assign":"📦"}
    lines = [f"📜 *Credits: {d}*\\n"]
    for t in txs[:20]:
        ic = icons.get(t.reason, "📝")
        ts = escape_md(t.created_at.strftime("%m/%d %H:%M")) if t.created_at else "?"
        s = "\\+" if t.amount > 0 else ""
        amt = escape_md(str(t.amount))
        bal = escape_md(str(t.balance_after))
        reason = escape_md(str(t.reason))
        lines.append(f"{ic} `{ts}` — {s}{amt}cr \\({reason}\\) → `{bal}`cr")
    await query.message.answer("\n".join(lines), parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


# ── Admin: Credit Reversals ───────────────────────────────────────────────

async def cb_user_reverse_credits(query: CallbackQuery) -> None:
    """Show reversible transactions for a user."""
    from services.credit_reversal import get_reversible_transactions
    tid = int(query.data.split(":")[1])
    u = User.get_by_telegram_id(tid)
    if not u:
        await query.answer("❌ Not found", show_alert=True); return
    
    reversible = get_reversible_transactions(tid, limit=20)
    
    if not reversible:
        await query.answer("ℹ️ No reversible transactions", show_alert=True)
        return
    
    d = escape_md(u.username) if u.username else str(tid)
    lines = [f"🔄 *Reversible Transactions: {d}*\n"]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for tx in reversible[:10]:
        ts = tx.get("created_at", "?")[:16].replace("T", " ")
        amount = tx.get("amount", 0)
        reason = tx.get("reason", "unknown")
        tx_id = tx.get("id")
        lines.append(f"• ID `{tx_id}` — +{amount}cr ({reason}) — {ts}")
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🔄 Reverse #{tx_id}",
                callback_data=f"urev_confirm:{tx_id}"
            )
        ])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Back", callback_data=f"ucred:{tid}")
    ])
    
    await query.message.edit_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=kb)
    await query.answer()


async def cb_user_reverse_confirm(query: CallbackQuery) -> None:
    """Confirm reversal of a transaction."""
    tx_id = int(query.data.split(":")[1])
    from services.credit_reversal import can_reverse_transaction
    can_rev, reason = can_reverse_transaction(tx_id)
    
    if not can_rev:
        await query.answer(f"❌ {reason}", show_alert=True)
        return
    
    await query.message.edit_text(
        f"⚠️ *Confirm Reversal*\n\n"
        f"Transaction ID: `{tx_id}`\n"
        f"Reason: {reason}\n\n"
        f"This will deduct credits from the user's balance.\n"
        f"Are you sure?",
        parse_mode="MarkdownV2",
        reply_markup=confirm(f"urev_ok:{tx_id}")
    )
    await query.answer()


async def cb_user_reverse_ok(query: CallbackQuery) -> None:
    """Execute the reversal."""
    from services.credit_reversal import reverse_credit_transaction, ReversalError
    tx_id = int(query.data.split(":")[1])
    
    try:
        result = reverse_credit_transaction(
            tx_id=tx_id,
            reversed_by=query.from_user.id,
            reason=f"Admin reversal by {query.from_user.username or query.from_user.id}"
        )
        
        _log(query.from_user.id, query.from_user.username, "reverse_credits", {
            "tx_id": tx_id,
            "amount": result["amount_reversed"],
            "user_id": result["user_id"],
            "old_balance": result["old_balance"],
            "new_balance": result["new_balance"],
        })
        
        await query.message.edit_text(
            f"✅ *Reversal Successful*\n\n"
            f"Transaction `{tx_id}` reversed\n"
            f"Amount: `{result['amount_reversed']}` credits\n"
            f"Balance: `{result['old_balance']}` → `{result['new_balance']}`\n\n"
            f"User has been notified.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_admin_panel()
        )
        
        # Notify user
        try:
            from aiogram import Bot
            bot = Bot(token=config.telegram_bot_token)
            await bot.send_message(
                result["user_id"],
                f"⚠️ *Credit Adjustment*\n\n"
                f"A credit transaction has been reversed:\n"
                f"Amount: `-{result['amount_reversed']}` credits\n"
                f"Reason: Admin review\n"
                f"New balance: `{result['new_balance']}` credits\n\n"
                f"Contact admin if you have questions.",
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"Failed to notify user of reversal: {e}")
        
        await query.answer()
    except ReversalError as e:
        await query.answer(f"❌ {str(e)}", show_alert=True)
    except Exception as e:
        logger.error(f"Reversal error: {e}", exc_info=True)
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)


# ── Admin: Backups ────────────────────────────────────────────────────────

async def cb_a_backups(query: CallbackQuery) -> None:
    """Show backup management menu."""
    from services.backup_service import list_backups, format_backup_summary
    
    backups = await list_backups(limit=5)
    text = "💾 *Backup Management*\n\n"
    text += "Create and manage database backups.\n"
    text += "Backups are stored in the database for easy restoration.\n\n"
    
    if backups:
        latest = backups[0]
        created = latest.get("created_at", "Unknown")[:19].replace("T", " ")
        metadata = latest.get("metadata", {})
        text += f"*Latest Backup:* `{latest.get('backup_id', 'N/A')}`\n"
        text += f"📅 {escape_md(created)}\n"
        text += f"📊 {metadata.get('total_records', 0)} records\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Create Backup Now", callback_data="backup_create")],
        [InlineKeyboardButton(text="📋 List All Backups", callback_data="backup_list")],
        [InlineKeyboardButton(text="📤 Export Users (JSON)", callback_data="backup_export_users_json")],
        [InlineKeyboardButton(text="📤 Export Users (CSV)", callback_data="backup_export_users_csv")],
        [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="a_main")],
    ])
    
    await query.message.edit_text(text, parse_mode="MarkdownV2", reply_markup=kb)
    await query.answer()


async def cb_backup_create(query: CallbackQuery) -> None:
    """Create a new backup."""
    from services.backup_service import create_backup
    
    await query.answer("⏳ Creating backup...", show_alert=False)
    
    try:
        metadata = await create_backup()
        
        _log(query.from_user.id, query.from_user.username, "create_backup", {
            "backup_id": metadata.get("backup_id"),
            "total_records": metadata.get("total_records"),
        })
        
        text = (
            f"✅ *Backup Created Successfully*\n\n"
            f"ID: `{metadata.get('backup_id')}`\n"
            f"📅 {metadata.get('created_at', '')[:19].replace('T', ' ')}\n"
            f"📊 {metadata.get('total_records')} records\n"
            f"📁 {metadata.get('table_count')} tables\n\n"
            f"Backup stored safely in database."
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 View All Backups", callback_data="backup_list")],
            [InlineKeyboardButton(text="🔙 Backup Menu", callback_data="a_backups")],
        ])
        
        await query.message.edit_text(text, parse_mode="MarkdownV2", reply_markup=kb)
    except Exception as e:
        logger.error(f"Backup creation failed: {e}", exc_info=True)
        await query.message.edit_text(
            f"❌ *Backup Failed*\n\n{escape_md(str(e))}",
            parse_mode="MarkdownV2",
            reply_markup=back_to_admin_panel()
        )
    
    await query.answer()


async def cb_backup_list(query: CallbackQuery) -> None:
    """List all backups."""
    from services.backup_service import list_backups, format_backup_summary
    
    backups = await list_backups(limit=20)
    text = format_backup_summary(backups)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Backup Menu", callback_data="a_backups")],
    ])
    
    await query.message.edit_text(text, parse_mode="MarkdownV2", reply_markup=kb)
    await query.answer()


async def cb_backup_export_users_json(query: CallbackQuery) -> None:
    """Export users to JSON."""
    from services.backup_service import export_table_to_json
    
    await query.answer("⏳ Generating JSON...", show_alert=False)
    
    try:
        json_data = await export_table_to_json("users", limit=1000)
        
        # Save to file
        import tempfile
        import os
        from datetime import datetime
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"users_export_{timestamp}.json"
        filepath = os.path.join("exports", filename)
        
        os.makedirs("exports", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json_data)
        
        _log(query.from_user.id, query.from_user.username, "export_users_json", {
            "file": filename,
        })
        
        # Send file to admin
        await query.message.answer_document(
            document=open(filepath, "rb"),
            caption=f"📤 *Users Export (JSON)*\n\nFile: `{filename}`"
        )
        
        await query.message.edit_text(
            f"✅ *Export Complete*\n\nFile sent above.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_admin_panel()
        )
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        await query.message.edit_text(
            f"❌ *Export Failed*\n\n{escape_md(str(e))}",
            parse_mode="MarkdownV2",
            reply_markup=back_to_admin_panel()
        )
    
    await query.answer()


async def cb_backup_export_users_csv(query: CallbackQuery) -> None:
    """Export users to CSV."""
    from services.backup_service import export_table_to_csv
    
    await query.answer("⏳ Generating CSV...", show_alert=False)
    
    try:
        csv_data = await export_table_to_csv("users", limit=1000)
        
        # Save to file
        import tempfile
        import os
        from datetime import datetime
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"users_export_{timestamp}.csv"
        filepath = os.path.join("exports", filename)
        
        os.makedirs("exports", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(csv_data)
        
        _log(query.from_user.id, query.from_user.username, "export_users_csv", {
            "file": filename,
        })
        
        # Send file to admin
        await query.message.answer_document(
            document=open(filepath, "rb"),
            caption=f"📤 *Users Export (CSV)*\n\nFile: `{filename}`"
        )
        
        await query.message.edit_text(
            f"✅ *Export Complete*\n\nFile sent above.",
            parse_mode="MarkdownV2",
            reply_markup=back_to_admin_panel()
        )
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        await query.message.edit_text(
            f"❌ *Export Failed*\n\n{escape_md(str(e))}",
            parse_mode="MarkdownV2",
            reply_markup=back_to_admin_panel()
        )
    
    await query.answer()


# ── Admin: Stripe ─────────────────────────────────────────────────────────

async def cb_a_stripe(query: CallbackQuery) -> None:
    accts = StripeAccount.get_all()
    txt = "🔑 *Stripe Accounts*"
    if not accts:
        txt += "\n\n_No accounts yet\\._"
    kb = stripe_list(accts)
    await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=kb)
    await query.answer()


async def cb_stripe_detail(query: CallbackQuery) -> None:
    aid = int(query.data.split(":")[1])
    a = StripeAccount.get_by_id(aid)
    if not a:
        await query.answer("❌ Not found", show_alert=True); return
    tag = "✅ Active" if a.is_active else "❌ Inactive"
    txt = f"🔑 *{escape_md(a.label)}*\n\nID: `{a.id}`\nStatus: {tag}\nToday: {a.daily_count}/{config.stripe_account_daily_limit}"
    await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=stripe_detail(aid))
    await query.answer()


async def cb_stripe_activate(query: CallbackQuery) -> None:
    aid = int(query.data.split(":")[1])
    a = StripeAccount.get_by_id(aid)
    if not a:
        await query.answer("❌ Not found", show_alert=True); return
    a.activate()
    _log(query.from_user.id, query.from_user.username, "switch_stripe", {"label": a.label})
    await query.answer(f"✅ {a.label}")
    await cb_stripe_detail(query)


async def cb_stripe_rename(query: CallbackQuery, state: FSMContext) -> None:
    aid = int(query.data.split(":")[1])
    await state.update_data(tid=aid)
    await state.set_state(AdminFSM.rename_stripe)
    await query.message.answer("📝 Send new name:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_stripe_delete(query: CallbackQuery) -> None:
    aid = int(query.data.split(":")[1])
    a = StripeAccount.get_by_id(aid)
    if not a:
        await query.answer("❌ Not found", show_alert=True); return
    await query.message.answer(f"🗑️ Delete *{escape_md(a.label)}*?", parse_mode="MarkdownV2",
                                reply_markup=confirm(f"sdel_ok:{aid}", "a_stripe"))
    await query.answer()


async def cb_stripe_delete_ok(query: CallbackQuery) -> None:
    aid = int(query.data.split(":")[1])
    a = StripeAccount.get_by_id(aid)
    nm = a.label if a else "?"
    StripeAccount.delete(aid)
    _log(query.from_user.id, query.from_user.username, "delete_stripe", {"label": nm})
    await query.message.edit_text(f"🗑️ *{escape_md(nm)}* deleted\\.", parse_mode="MarkdownV2",
                                   reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_stripe_add(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.add_stripe)
    await query.message.answer(
        "➕ *Add Stripe*\n\nSend: `label sk_live_key`\nEx: `Main sk_live_abc123`",
        parse_mode="MarkdownV2", reply_markup=back_to_admin_panel())
    await query.answer()


# ── Admin: Plans ──────────────────────────────────────────────────────────

async def cb_a_plans(query: CallbackQuery) -> None:
    pls = Plan.get_all()
    txt = "📦 *Plans*"
    if not pls:
        txt += "\n\n_None yet\\._"
    await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=plans_list(pls))
    await query.answer()


async def cb_plan_detail(query: CallbackQuery) -> None:
    pid = int(query.data.split(":")[1])
    p = Plan.get_by_id(pid)
    if not p:
        await query.answer("❌ Not found", show_alert=True); return
    tag = "✅" if p.is_active else "❌"
    ps = f"${p.crypto_price_usd:.2f}".replace(".", "\\.")
    txt = f"{tag} *{escape_md(p.name)}*\n\nCredits: `{p.credits}`\nPrice: `{ps}`"
    await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=plan_detail(pid))
    await query.answer()


async def cb_plan_toggle(query: CallbackQuery) -> None:
    pid = int(query.data.split(":")[1])
    p = Plan.get_by_id(pid)
    if not p:
        await query.answer("❌ Not found", show_alert=True); return
    p.toggle_active()
    _log(query.from_user.id, query.from_user.username, "toggle_plan", {"pid": pid})
    await query.answer(f"{'✅' if p.is_active else '❌'} {p.name}")
    await cb_plan_detail(query)


async def cb_plan_delete(query: CallbackQuery) -> None:
    pid = int(query.data.split(":")[1])
    p = Plan.get_by_id(pid)
    if not p:
        await query.answer("❌ Not found", show_alert=True); return
    await query.message.answer(f"🗑️ Delete *{escape_md(p.name)}*?", parse_mode="MarkdownV2",
                                reply_markup=confirm(f"pdel_ok:{pid}", f"pedt:{pid}"))
    await query.answer()


async def cb_plan_delete_ok(query: CallbackQuery) -> None:
    pid = int(query.data.split(":")[1])
    p = Plan.get_by_id(pid)
    nm = p.name if p else "?"
    Plan.delete(pid)
    _log(query.from_user.id, query.from_user.username, "delete_plan", {"pid": pid})
    await query.message.edit_text(f"🗑️ *{escape_md(nm)}* deleted\\.", parse_mode="MarkdownV2",
                                   reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_plan_add(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.create_plan)
    await query.message.answer(
        "➕ *Create Plan*\n\nSend: `name price credits`\nEx: `Premium 25.00 100`",
        parse_mode="MarkdownV2", reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_plan_edit_name(query: CallbackQuery, state: FSMContext) -> None:
    pid = int(query.data.split(":")[1])
    await state.update_data(tid=pid)
    await state.set_state(AdminFSM.edit_plan_name)
    await query.message.answer("📝 Send new name:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_plan_edit_price(query: CallbackQuery, state: FSMContext) -> None:
    pid = int(query.data.split(":")[1])
    await state.update_data(tid=pid)
    await state.set_state(AdminFSM.edit_plan_price)
    await query.message.answer("💲 Send new price:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_plan_edit_credits(query: CallbackQuery, state: FSMContext) -> None:
    pid = int(query.data.split(":")[1])
    await state.update_data(tid=pid)
    await state.set_state(AdminFSM.edit_plan_credits)
    await query.message.answer("💳 Send new credits:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


# ── Admin: Stats ──────────────────────────────────────────────────────────

async def cb_a_stats(query: CallbackQuery) -> None:
    st = ValidationLog.get_stats()
    act = StripeAccount.get_active()
    si = act.label if act else "None"
    sd = f" ({act.daily_count}/{config.stripe_account_daily_limit} today)" if act else ""
    users = User.get_all()
    with_credits = sum(1 for u in users if u.credits > 0)
    txt = (
        f"📊 Stats\n\n"
        f"Validations: {st['total_validations']}\n"
        f"Success: {st['successful']} ({st['success_rate']:.1f}%)\n"
        f"Declines (24h): {st['recent_declines']}\n\n"
        f"Stripe: {si}{sd}\n\n"
        f"Users: {len(users)} total, {with_credits} with credits"
    )
    await query.message.edit_text(txt, reply_markup=back_to_admin_panel())
    await query.answer()


# ── Admin: Audit ──────────────────────────────────────────────────────────

async def cb_a_audit(query: CallbackQuery) -> None:
    logs = AdminLog.get_recent(limit=20)
    if not logs:
        txt = "📋 *No logs*"
    else:
        icons = {"add_stripe":"🔑","switch_stripe":"🔄","delete_stripe":"🗑️","create_plan":"📦",
                 "toggle_plan":"🔄","delete_plan":"🗑️","add_credits":"💰","set_plan":"📦",
                 "reset_user":"🔄","delete_user":"🗑️","update_setting":"⚙️","broadcast":"📢",
                 "ban_user":"🚫","unban_user":"✅","clear_audit_logs":"🧹","rename_stripe":"📝",
                 "edit_plan":"✏️"}
        lines = ["📋 *Recent*\n"]
        for l in logs[:20]:
            ic = icons.get(l.action, "📝")
            ts = l.created_at.strftime("%m/%d %H:%M") if l.created_at else "?"
            safe = escape_md(l.admin_username) if l.admin_username else str(l.admin_id)
            lines.append(f"{ic} `{ts}` {safe}: {escape_md(l.action)}")
        txt = "\n".join(lines)
    await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=back_to_admin_panel())
    await query.answer()


# ── Admin: Broadcast ──────────────────────────────────────────────────────

async def cb_a_broadcast(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.broadcast)
    await query.message.answer("📢 *Type message to broadcast*", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


# ── Admin: Settings ───────────────────────────────────────────────────────

async def cb_a_settings(query: CallbackQuery) -> None:
    s = Settings.get_crypto_addresses()
    u = f"`{escape_md(s['usdt'][:8])}...{escape_md(s['usdt'][-6:])}`" if s['usdt'] else "`—`"
    b = f"`{escape_md(s['btc'][:8])}...{escape_md(s['btc'][-6:])}`" if s['btc'] else "`—`"
    c = escape_md(s['admin_contact'])
    sc = Settings.get("stripe_validation_cost") or "1"
    bc = Settings.get("bin_validation_cost") or "0"
    txt = f"⚙️ Settings\n\nUSDT: {u}\nBTC: {b}\nContact: {c}\n\nStripe cost: {sc} cr\nBIN cost: {bc} cr"
    await query.message.edit_text(txt, reply_markup=settings_keyboard())
    await query.answer()


async def cb_settings_usdt(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.set_usdt)
    await query.message.answer("📝 Send USDT address:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_settings_btc(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.set_btc)
    await query.message.answer("📝 Send BTC address:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_settings_contact(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.set_contact)
    await query.message.answer("📝 Send admin contact:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_set_stripe_cost(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.set_stripe_cost)
    await query.message.answer(
        "💳 Send Stripe validation cost in credits:",
        reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_set_bin_cost(query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFSM.set_bin_cost)
    await query.message.answer(
        "🔍 Send BIN validation cost in credits:",
        reply_markup=back_to_admin_panel())
    await query.answer()


# ── Admin: Manage Admins ─────────────────────────────────────────────────

async def cb_manage_admins(query: CallbackQuery) -> None:
    if not _require_super_admin(query): return
    from models.admin_model import Admin
    admins = Admin.get_all()
    if not admins:
        txt = "👑 *No admins configured*\\.\n\nTap ➕ Add Admin below to make admin\\."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Admin", callback_data="a_add_admin")],
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="a_main")],
        ])
        await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=kb)
        await query.answer(); return
    lines = ["👑 *Admin Management*"]
    for a in admins:
        tag = "🌟" if a.role == "super_admin" else "👤"
        nm = escape_md(a.username) if a.username else str(a.telegram_id)
        role = escape_md(a.role)
        lines.append(f"{tag} `{nm}` \\({role}\\)")
    lines.append("")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Admin", callback_data="a_add_admin")],
        [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="a_main")],
    ])
    await query.message.edit_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=kb)
    await query.answer()


async def cb_admin_detail(query: CallbackQuery) -> None:
    from models.admin_model import Admin
    tid = int(query.data.split(":")[1])
    a = Admin.get_by_id(tid)
    if not a:
        await query.answer("❌ Not found", show_alert=True); return
    nm = escape_md(a.username) if a.username else str(tid)
    txt = f"👑 *{nm}*\n\nID: `{tid}`\nRole: *{a.role}*"
    kb_btns = []
    if a.role == "super_admin":
        kb_btns.append([InlineKeyboardButton(text="🔻 Demote to Admin", callback_data=f"adem:{tid}")])
    else:
        kb_btns.append([InlineKeyboardButton(text="🌟 Promote to Super", callback_data=f"aprom:{tid}")])
    kb_btns.append([InlineKeyboardButton(text="🗑️ Remove", callback_data=f"adel:{tid}")])
    kb_btns.append([InlineKeyboardButton(text="🔙 Admin List", callback_data="a_manage_admins")])
    await query.message.edit_text(txt, parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_btns))
    await query.answer()


async def cb_add_admin_prompt(query: CallbackQuery, state: FSMContext) -> None:
    if not _require_super_admin(query): return
    await state.set_state(AdminFSM.add_admin)
    await query.message.answer("➕ *Add Admin*\n\nSend Telegram ID or @username:", parse_mode="MarkdownV2",
                                reply_markup=back_to_admin_panel())
    await query.answer()


async def cb_admin_promote(query: CallbackQuery) -> None:
    if not _require_super_admin(query): return
    from models.admin_model import Admin
    tid = int(query.data.split(":")[1])
    Admin.set_role(tid, "super_admin")
    _log(query.from_user.id, query.from_user.username, "promote_admin", {"telegram_id": tid})
    await query.answer("🌟 Promoted to super admin")
    await cb_admin_detail(query)


async def cb_admin_demote(query: CallbackQuery) -> None:
    if not _require_super_admin(query): return
    from models.admin_model import Admin
    tid = int(query.data.split(":")[1])
    Admin.set_role(tid, "admin")
    _log(query.from_user.id, query.from_user.username, "demote_admin", {"telegram_id": tid})
    await query.answer("🔻 Demoted to admin")
    await cb_admin_detail(query)


async def cb_admin_remove_confirm(query: CallbackQuery) -> None:
    if not _require_super_admin(query): return
    from models.admin_model import Admin
    tid = int(query.data.split(":")[1])
    a = Admin.get_by_id(tid)
    nm = a.username if a else str(tid)
    await query.message.answer(
        f"🗑️ Remove *{escape_md(nm)}* from admins?",
        parse_mode="MarkdownV2",
        reply_markup=confirm(f"adel_ok:{tid}", f"adet:{tid}")
    )
    await query.answer()


async def cb_admin_remove_ok(query: CallbackQuery) -> None:
    if not _require_super_admin(query): return
    from models.admin_model import Admin
    tid = int(query.data.split(":")[1])
    a = Admin.get_by_id(tid)
    nm = a.username if a else str(tid)
    Admin.remove(tid)
    _log(query.from_user.id, query.from_user.username, "remove_admin", {"telegram_id": tid})
    await query.message.edit_text(f"🗑️ `{escape_md(nm)}` removed from admins\\.", parse_mode="MarkdownV2",
                                   reply_markup=back_to_admin_panel())
    await query.answer()


# ── Text Router (admin FSM) ───────────────────────────────────────────────

async def handle_admin_text(message: Message, state, bot: Bot) -> None:
    """Handle admin text input with validation."""
    cur = await state.get_state()
    d = await state.get_data()
    
    # Sanitize all text input
    try:
        t = sanitize_text(message.text.strip(), max_length=1000)
    except Exception:
        await message.answer("❌ Invalid input")
        await state.clear()
        return

    if cur == AdminFSM.add_credits.state:
        tid = d.get("tid")
        try:
            amt = validate_positive_integer(t)
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}")
            return
        u = User.get_by_telegram_id(tid)
        if not u:
            await message.answer("❌ Not found"); await state.clear(); return
        old = u.credits
        u.add_credits(amt)
        _log(message.from_user.id, message.from_user.username, "add_credits", {"tid": tid, "amt": amt})
        try:
            await bot.send_message(tid, f"💰 \\+{amt} credits\\. Balance: `{u.credits}`", parse_mode="MarkdownV2")
        except Exception:
            pass
        await message.answer(f"✅ `{old}` → `{u.credits}`", parse_mode="MarkdownV2",
                              reply_markup=user_detail(tid, u.is_banned, is_admin_target=_is_admin(tid)))
        await state.clear(); return

    if cur == AdminFSM.rename_stripe.state:
        aid = d.get("tid")
        a = StripeAccount.get_by_id(aid)
        if not a:
            await message.answer("❌ Not found"); await state.clear(); return
        label = sanitize_text(t, max_length=50)
        old = a.label
        a.update_label(label)
        _log(message.from_user.id, message.from_user.username, "rename_stripe", {"old": old, "new": label})
        await message.answer(f"✅ *{escape_md(old)}* → *{escape_md(label)}*", parse_mode="MarkdownV2",
                              reply_markup=stripe_detail(aid))
        await state.clear(); return

    if cur == AdminFSM.create_plan.state:
        parts = t.split()
        if len(parts) < 3:
            await message.answer("❌ Format: `name price_cents credits`\\nExample: `Premium 1000 500`", parse_mode="MarkdownV2"); return
        nm = parts[0]
        ps = parts[1]
        cs = parts[2]
        
        try:
            nm = validate_plan_name(nm)
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}"); return
        
        try:
            price = validate_positive_integer(ps)
        except ValidationError as e:
            await message.answer(f"❌ Price: {str(e)}"); return
        
        try:
            credits = validate_positive_integer(cs)
        except ValidationError as e:
            await message.answer(f"❌ Credits: {str(e)}"); return
        
        if Plan.get_by_name(nm):
            await message.answer(f"❌ `{escape_md(nm)}` exists"); return
        Plan.create(name=nm, crypto_price_usd=price, credits=credits)
        _log(message.from_user.id, message.from_user.username, "create_plan", {"name": nm})
        await message.answer(f"✅ *{escape_md(nm)}* created", parse_mode="MarkdownV2",
                              reply_markup=back_to_admin_panel())
        await state.clear(); return

    if cur == AdminFSM.edit_plan_name.state:
        pid = d.get("tid")
        p = Plan.get_by_id(pid)
        if not p:
            await message.answer("❌ Not found"); await state.clear(); return
        try:
            name = validate_plan_name(t)
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}"); return
        old = p.name
        p.update(name=name)
        _log(message.from_user.id, message.from_user.username, "edit_plan", {"field": "name"})
        await message.answer(f"✅ `{escape_md(old)}` → *{escape_md(name)}*", parse_mode="MarkdownV2",
                              reply_markup=plan_detail(pid))
        await state.clear(); return

    if cur == AdminFSM.edit_plan_price.state:
        pid = d.get("tid")
        p = Plan.get_by_id(pid)
        if not p:
            await message.answer("❌ Not found"); await state.clear(); return
        try:
            price = validate_positive_integer(t)
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}"); return
        old = p.crypto_price_usd
        p.update(crypto_price_usd=price)
        _log(message.from_user.id, message.from_user.username, "edit_plan", {"field": "price"})
        await message.answer(f"✅ `${old:.2f}` → `${price:.2f}`", parse_mode="MarkdownV2",
                              reply_markup=plan_detail(pid))
        await state.clear(); return

    if cur == AdminFSM.edit_plan_credits.state:
        pid = d.get("tid")
        p = Plan.get_by_id(pid)
        if not p:
            await message.answer("❌ Not found"); await state.clear(); return
        try:
            cr = validate_positive_integer(t)
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}"); return
        old = p.credits
        p.update(credits=cr)
        _log(message.from_user.id, message.from_user.username, "edit_plan", {"field": "credits"})
        await message.answer(f"✅ `{old}` → `{cr}`", parse_mode="MarkdownV2",
                              reply_markup=plan_detail(pid))
        await state.clear(); return

    if cur == AdminFSM.broadcast.state:
        msg = sanitize_text(t, max_length=4000)
        users = User.get_all()
        ok = fail = 0
        for u in users:
            try:
                await bot.send_message(u.telegram_id, text=msg, parse_mode="MarkdownV2")
                ok += 1
            except Exception:
                fail += 1
        _log(message.from_user.id, message.from_user.username, "broadcast", {"sent": ok, "failed": fail})
        await message.answer(f"📢 ✅ `{ok}`  ❌ `{fail}`", parse_mode="MarkdownV2",
                              reply_markup=back_to_admin_panel())
        await state.clear(); return

    if cur == AdminFSM.set_usdt.state:
        try:
            addr = validate_crypto_address(t, "USDT_TRC20")
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}")
            return
        Settings.set("crypto_address_usdt", addr)
        _log(message.from_user.id, message.from_user.username, "update_setting", {"key": "usdt"})
        await message.answer("✅ USDT updated", parse_mode="MarkdownV2",
                              reply_markup=back_to_admin_panel())
        await state.clear(); return

    if cur == AdminFSM.set_btc.state:
        try:
            addr = validate_crypto_address(t, "BTC")
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}")
            return
        Settings.set("crypto_address_btc", addr)
        _log(message.from_user.id, message.from_user.username, "update_setting", {"key": "btc"})
        await message.answer("✅ BTC updated", parse_mode="MarkdownV2",
                              reply_markup=back_to_admin_panel())
        await state.clear(); return

    if cur == AdminFSM.set_contact.state:
        try:
            contact = validate_telegram_username(t)
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}")
            return
        Settings.set("admin_contact", contact)
        _log(message.from_user.id, message.from_user.username, "update_setting", {"key": "contact"})
        await message.answer("✅ Contact updated", parse_mode="MarkdownV2",
                              reply_markup=back_to_admin_panel())
        await state.clear(); return

    if cur == AdminFSM.set_stripe_cost.state:
        try:
            cost = validate_non_negative_integer(t)
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}")
            return
        Settings.set("stripe_validation_cost", str(cost))
        _log(message.from_user.id, message.from_user.username, "update_setting", {"key": "stripe_cost", "value": cost})
        await message.answer(f"✅ Stripe cost set to `{cost}` credits", parse_mode="MarkdownV2",
                              reply_markup=back_to_admin_panel())
        await state.clear(); return

    if cur == AdminFSM.set_bin_cost.state:
        try:
            cost = validate_non_negative_integer(t)
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}")
            return
        Settings.set("bin_validation_cost", str(cost))
        _log(message.from_user.id, message.from_user.username, "update_setting", {"key": "bin_cost", "value": cost})
        await message.answer(f"✅ BIN cost set to `{cost}` credits", parse_mode="MarkdownV2",
                              reply_markup=back_to_admin_panel())
        await state.clear(); return

    if cur == AdminFSM.add_stripe.state:
        parts = t.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("❌ Format: `label sk_live_key`")
            return
        label, key = parts
        try:
            key = validate_stripe_secret_key(key)
        except ValidationError as e:
            await message.answer(f"❌ {str(e)}")
            return
        label = sanitize_text(label, max_length=50)
        enc = encrypt(key)
        a = StripeAccount.create(label=label, secret_key_encrypted=enc)
        _log(message.from_user.id, message.from_user.username, "add_stripe", {"label": label})
        await message.answer(f"✅ *{escape_md(label)}* \\(ID: `{a.id}`\\)", parse_mode="MarkdownV2",
                              reply_markup=stripe_detail(a.id))
        await state.clear(); return

    if cur == AdminFSM.search.state:
        query = sanitize_text(t, max_length=200)
        matches = User.search(query, limit=20)
        if not matches:
            await message.answer(f"🔍 No results for `{escape_md(query)}`", parse_mode="MarkdownV2",
                                  reply_markup=back_to_admin_panel())
            await state.clear(); return
        lines = [f"🔍 *{len(matches)}* result\\(s\\)\n"]
        for u in matches[:20]:
            s = escape_md(u.username) if u.username else str(u.telegram_id)
            lines.append(f"`{u.telegram_id}` — {s} — `{u.credits}`cr")
        await message.answer("\n".join(lines), parse_mode="MarkdownV2",
                              reply_markup=back_to_admin_panel())
        await state.clear(); return

    if cur == AdminFSM.add_admin.state:
        from models.admin_model import Admin
        tid = 0
        uname = ""
        if t.startswith("@"):
            try:
                uname = validate_telegram_username(t)
                uname = uname.lstrip('@')
            except ValidationError as e:
                await message.answer(f"❌ {str(e)}")
                await state.clear()
                return
        elif t.isdigit():
            try:
                tid = validate_telegram_id(t)
            except ValidationError as e:
                await message.answer(f"❌ {str(e)}")
                await state.clear()
                return
        else:
            try:
                uname = validate_telegram_username(t).lstrip('@')
            except ValidationError as e:
                await message.answer(f"❌ {str(e)}")
                await state.clear()
                return
        
        Admin.add(tid, username=uname, role="admin", added_by=message.from_user.id)
        _log(message.from_user.id, message.from_user.username, "add_admin", {"telegram_id": tid, "username": uname})
        await message.answer(f"✅ `{tid or uname}` added as admin", parse_mode="MarkdownV2",
                              reply_markup=back_to_admin_panel())
        await state.clear(); return


# ── Noop ──────────────────────────────────────────────────────────────────

async def cb_noop(query: CallbackQuery) -> None:
    await query.answer()


# ── Helpers ────────────────────────────────────────────────────────────────

async def _reply(src, text: str, kb):
    """Reply via Message.answer or CallbackQuery.message.edit_text."""
    if hasattr(src, 'answer'):
        await src.answer(text, parse_mode="MarkdownV2", reply_markup=kb)
    else:
        await src.message.edit_text(text, parse_mode="MarkdownV2", reply_markup=kb)
