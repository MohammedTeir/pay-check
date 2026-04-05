"""
ALL inline keyboards — no ReplyKeyboard.
Every button is a CallbackQuery inside the message.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.formatters import escape_md

# ── User Menus ─────────────────────────────────────────────────────────────

def user_main_menu() -> InlineKeyboardMarkup:
    """Main user menu — shown at /start and /menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Validate Card", callback_data="u_validate"),
            InlineKeyboardButton(text="💰 My Balance", callback_data="u_balance"),
        ],
        [
            InlineKeyboardButton(text="⏱️ Quota", callback_data="u_quota"),
            InlineKeyboardButton(text="📦 Plans", callback_data="u_plans"),
        ],
        [
            InlineKeyboardButton(text="📜 History", callback_data="u_history"),
            InlineKeyboardButton(text="❓ Help", callback_data="u_help"),
        ],
    ])


def user_main_menu_admin() -> InlineKeyboardMarkup:
    """Main user menu for admins — adds Admin button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Validate Card", callback_data="u_validate"),
            InlineKeyboardButton(text="💰 My Balance", callback_data="u_balance"),
        ],
        [
            InlineKeyboardButton(text="⏱️ Quota", callback_data="u_quota"),
            InlineKeyboardButton(text="📦 Plans", callback_data="u_plans"),
        ],
        [
            InlineKeyboardButton(text="📜 History", callback_data="u_history"),
            InlineKeyboardButton(text="❓ Help", callback_data="u_help"),
        ],
        [
            InlineKeyboardButton(text="🔧 Admin Panel", callback_data="a_main"),
        ],
    ])


def back_to_user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Main Menu", callback_data="u_menu")],
    ])


def back_to_admin_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="a_main")],
    ])


# ── Admin: Main Panel ─────────────────────────────────────────────────────

def admin_panel(is_super_admin: bool = True) -> InlineKeyboardMarkup:
    """Admin panel keyboard. Shows Manage Admins only for super admins."""
    rows = [
        [
            InlineKeyboardButton(text="👥 Users", callback_data="a_users:1"),
            InlineKeyboardButton(text="📦 Plans", callback_data="a_plans"),
        ],
        [
            InlineKeyboardButton(text="🔑 Stripe", callback_data="a_stripe"),
            InlineKeyboardButton(text="📊 Stats", callback_data="a_stats"),
        ],
        [
            InlineKeyboardButton(text="📋 Audit Log", callback_data="a_audit"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="a_broadcast"),
        ],
        [
            InlineKeyboardButton(text="💾 Backups", callback_data="a_backups"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="a_settings"),
        ],
    ]
    if is_super_admin:
        rows.append([
            InlineKeyboardButton(text="👑 Manage Admins", callback_data="a_manage_admins"),
            InlineKeyboardButton(text="🔙 User Menu", callback_data="u_menu"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text="🔙 User Menu", callback_data="u_menu"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Admin: Users ──────────────────────────────────────────────────────────

def users_list(page: int = 1, total_pages: int = 1, total_users: int = 0,
               users: list = None) -> InlineKeyboardMarkup:
    keyboard = []
    users = users or []
    for u in users:
        safe = escape_md(u.username) if u.username else f"ID:{u.telegram_id}"
        keyboard.append([
            InlineKeyboardButton(
                text=f"👤 {safe} ({u.credits}cr)",
                callback_data=f"udet:{u.telegram_id}"
            )
        ])

    # Pagination row
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"a_users:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages} ({total_users})", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"a_users:{page + 1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton(text="🔍 Search", callback_data="a_user_search"),
    ])
    keyboard.append([InlineKeyboardButton(text="🔙 Admin Panel", callback_data="a_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def user_detail(telegram_id: int, is_banned: bool, is_admin_target: bool = False) -> InlineKeyboardMarkup:
    """User detail keyboard. Hides ban/delete for admin targets."""
    btns = [
        [InlineKeyboardButton(text="💰 Add Credits", callback_data=f"uaddcr:{telegram_id}")],
        [InlineKeyboardButton(text="🔄 Reset Credits", callback_data=f"urescr:{telegram_id}")],
        [InlineKeyboardButton(text="📜 Validation History", callback_data=f"uhist:{telegram_id}")],
        [InlineKeyboardButton(text="💳 Credit History", callback_data=f"ucred:{telegram_id}")],
        [InlineKeyboardButton(text="↩️ Reverse Credits", callback_data=f"urev:{telegram_id}")],
    ]
    if not is_admin_target:
        if is_banned:
            btns.append([InlineKeyboardButton(text="✅ Unban", callback_data=f"uunban:{telegram_id}")])
        else:
            btns.append([InlineKeyboardButton(text="🚫 Ban", callback_data=f"uban:{telegram_id}")])
        btns.append([InlineKeyboardButton(text="🗑️ Delete", callback_data=f"udel:{telegram_id}")])
    btns.append([InlineKeyboardButton(text="🔙 Users", callback_data="a_users:1")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


# ── Admin: Stripe ─────────────────────────────────────────────────────────

def stripe_list(accounts: list = None) -> InlineKeyboardMarkup:
    from config import config
    keyboard = []
    for acc in (accounts or []):
        tag = "✅" if acc.is_active else "❌"
        kb = InlineKeyboardButton(
            text=f"{tag} {escape_md(acc.label)} ({acc.daily_count}/{config.stripe_account_daily_limit})",
            callback_data=f"sdet:{acc.id}"
        )
        keyboard.append([kb])
    keyboard.append([InlineKeyboardButton(text="➕ Add Account", callback_data="sadd")])
    keyboard.append([InlineKeyboardButton(text="🔙 Admin Panel", callback_data="a_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def stripe_detail(account_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Activate", callback_data=f"sact:{account_id}")],
        [InlineKeyboardButton(text="📝 Rename", callback_data=f"sren:{account_id}")],
        [InlineKeyboardButton(text="🗑️ Delete", callback_data=f"sdel:{account_id}")],
        [InlineKeyboardButton(text="🔙 Stripe List", callback_data="a_stripe")],
    ])


# ── Admin: Plans ──────────────────────────────────────────────────────────

def plans_list(plans: list = None) -> InlineKeyboardMarkup:
    keyboard = []
    for p in (plans or []):
        tag = "✅" if p.is_active else "❌"
        name = escape_md(p.name)
        keyboard.append([
            InlineKeyboardButton(
                text=f"{tag} {name} — {p.credits}cr — ${p.crypto_price_usd:.2f}",
                callback_data=f"pedt:{p.id}"
            )
        ])
    keyboard.append([InlineKeyboardButton(text="➕ Create Plan", callback_data="padd")])
    keyboard.append([InlineKeyboardButton(text="🔙 Admin Panel", callback_data="a_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def plan_detail(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Edit Name", callback_data=f"pedt_name:{plan_id}")],
        [InlineKeyboardButton(text="💲 Edit Price", callback_data=f"pedt_price:{plan_id}")],
        [InlineKeyboardButton(text="💳 Edit Credits", callback_data=f"pedt_credits:{plan_id}")],
        [InlineKeyboardButton(text="🔄 Toggle Active", callback_data=f"ptog:{plan_id}")],
        [InlineKeyboardButton(text="🗑️ Delete", callback_data=f"pdel:{plan_id}")],
        [InlineKeyboardButton(text="🔙 Plans", callback_data="a_plans")],
    ])


# ── Admin: Settings ───────────────────────────────────────────────────────

def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 USDT", callback_data="sett_usdt")],
        [InlineKeyboardButton(text="📝 BTC", callback_data="sett_btc")],
        [InlineKeyboardButton(text="📝 Contact", callback_data="sett_contact")],
        [InlineKeyboardButton(text="💳 Stripe Cost", callback_data="sett_stripe_cost")],
        [InlineKeyboardButton(text="🔍 BIN Cost", callback_data="sett_bin_cost")],
        [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="a_main")],
    ])


# ── Confirm ────────────────────────────────────────────────────────────────

def confirm(yes_cb: str, no_cb: str,
            yes_text: str = "✅ Yes", no_text: str = "❌ No") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=yes_text, callback_data=yes_cb),
            InlineKeyboardButton(text=no_text, callback_data=no_cb),
        ]
    ])


def validation_choices(stripe_available: bool = False,
                       bin_cost: int = 0,
                       stripe_cost: int = 1) -> InlineKeyboardMarkup:
    """Inline buttons for choosing validation mode after card input."""
    kb = []
    bin_label = f"🔍 BIN+AI ({bin_cost} credit)" if bin_cost else "🔍 BIN+AI (Free)"
    kb.append([InlineKeyboardButton(text=bin_label, callback_data=f"val_mode:bin")])
    if stripe_available:
        stripe_label = f"🔗 Stripe ({stripe_cost} credit)"
        kb.append([InlineKeyboardButton(text=stripe_label, callback_data=f"val_mode:stripe")])
        both_cost = bin_cost + stripe_cost
        kb.append([InlineKeyboardButton(text=f"🔄 Both ({both_cost} credit)", callback_data=f"val_mode:both")])
    kb.append([InlineKeyboardButton(text="🔙 Cancel", callback_data="val_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
