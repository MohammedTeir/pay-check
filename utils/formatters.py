"""
Message formatting helpers — MarkdownV2-safe Telegram message builders.
"""

from datetime import datetime
from typing import Optional


def escape_md(text: str) -> str:
    """
    Escape special MarkdownV2 characters in user-generated content.
    Prevents parse errors from usernames, error messages, etc.
    """
    if not text:
        return ""
    special = r"\_`*[]()~`>#+-=|{}.!"
    result = []
    for ch in text:
        if ch in special:
            result.append(f"\\{ch}")
        else:
            result.append(ch)
    return "".join(result)


def safe_user(username: Optional[str], telegram_id: int) -> str:
    """Safely format a username for MarkdownV2."""
    if username:
        return escape_md(username)
    return f"ID\\:`{telegram_id}`"


def format_welcome(username: str) -> str:
    """Welcome message for /start."""
    return (
        f"👋 Welcome, {username}!\n\n"
        "I'm your **Card Validator Bot** 🔐\n\n"
        "I help you validate credit/debit cards using secure authorization checks.\n\n"
        "📋 **Commands:**\n"
        "/register — Create a new account\n"
        "/login — Log in to your account\n"
        "/validate — Validate a card\n"
        "/balance — Check your credits\n"
        "/plans — View subscription plans\n"
        "/buy — Purchase a plan\n"
        "/history — Recent validation results\n"
        "/help — Get help"
    )


def format_registered(credits: int) -> str:
    """Message after registration."""
    return (
        "✅ **Account created!**\n\n"
        f"Your Telegram ID is linked to your account.\n"
        f"💳 Credits: `{credits}`\n\n"
        "Contact an admin to add credits or purchase a plan.\n"
        "Use /validate to start validating cards."
    )


def format_logged_in(user) -> str:
    """Message after login."""
    return (
        "✅ **Logged in!**\n\n"
        f"Welcome back, {user.username or 'User'}!\n"
        f"💳 Credits: `{user.credits}`\n"
        f"📦 Plan: {user.plan_id or 'None'}\n"
        f"📅 Joined: {user.created_at.strftime('%Y-%m-%d') if user.created_at else 'Unknown'}"
    )


def format_validating(last4: str) -> str:
    """Message while validation is in progress."""
    return f"🔍 Validating card ending `{last4}`...\n⏳ Please wait..."


def format_valid(
    brand: str,
    bank: str,
    card_type: str,
    country: str,
    credits_remaining: int,
    duration_ms: float,
) -> str:
    """Message for a successful validation."""
    bank_line = f"🏦 Bank: {bank}" if bank and bank != "Unknown Bank" else ""
    type_line = f"💎 Type: {card_type}" if card_type and card_type != "Unknown" else ""
    country_line = f"🌍 Country: {country}" if country and country != "Unknown" else ""

    lines = [
        "✅ **Card is VALID**",
        "(authorization held and released)",
        "",
        f"💳 Brand: {brand}",
    ]
    if bank_line:
        lines.append(bank_line)
    if type_line:
        lines.append(type_line)
    if country_line:
        lines.append(country_line)
    lines.extend([
        "",
        f"⏱️ Time: {duration_ms:.1f} sec",
        f"💰 Credits remaining: `{credits_remaining}`",
    ])
    return "\n".join(lines)


def format_declined(decline_code: str, credits_remaining: int) -> str:
    """Message for a declined card."""
    code_msg = decline_code or "unknown"
    return (
        "❌ **Card DECLINED**\n\n"
        f"Decline code: `{code_msg}`\n"
        f"💰 Credits remaining: `{credits_remaining}`"
    )


def format_error(error_message: str, credits_remaining: int) -> str:
    """Message for a validation error."""
    return (
        "⚠️ **Validation Error**\n\n"
        f"Details: {error_message}\n"
        f"💰 Credits remaining: `{credits_remaining}`\n\n"
        "Please try again later or contact an admin."
    )


def format_3ds_required(credits_remaining: int) -> str:
    """Message when card requires 3D Secure (OTP)."""
    return (
        "🔒 **3D Secure Required**\n\n"
        "This card requires OTP authentication.\n"
        "Only 2D (non-3DS) cards are supported.\n"
        f"💰 Credits remaining: `{credits_remaining}`"
    )


def format_no_credits() -> str:
    """Message when user has insufficient credits."""
    return (
        "❌ **Insufficient credits!**\n\n"
        "You need at least 1 credit to validate a card.\n"
        "Use /plans to view available plans and /buy to purchase.\n"
        "Or contact an admin to add credits."
    )


def format_duplicate_card() -> str:
    """Message when card was already validated within cooldown period."""
    return (
        "⏳ **Card recently validated**\n\n"
        "This card was already validated within the last 24 hours.\n"
        "Please wait or use a different card."
    )


def format_balance(credits: int) -> str:
    """Balance display."""
    return f"💳 **Your Balance**\n\nCredits: `{credits}`"


def format_plans(plans: list) -> str:
    """List of available plans."""
    lines = ["📦 **Available Plans**\n"]
    for plan in plans:
        active_tag = "✅" if plan.is_active else "❌"
        lines.append(
            f"{active_tag} **{plan.name}**\n"
            f"   Credits: {plan.credits}\n"
            f"   Price: ${plan.crypto_price_usd:.2f} USD\n"
        )
    lines.append("Use /buy <plan_name> to purchase.")
    return "\n".join(lines)


def format_buy_instructions(
    plan_name: str,
    credits: int,
    price_usd: float,
    crypto_address_usdt: str,
    crypto_address_btc: str,
    admin_contact: str,
) -> str:
    """Instructions for purchasing a plan with crypto."""
    return (
        f"📦 **Plan: {plan_name}**\n"
        f"Credits: {credits}\n"
        f"Price: ${price_usd:.2f} USD\n\n"
        "💰 **Payment Instructions:**\n\n"
        f"1. Send exactly **${price_usd:.2f}** in one of the following:\n"
        f"   • **USDT (TRC20):** `{crypto_address_usdt}`\n"
        f"   • **BTC:** `{crypto_address_btc}`\n\n"
        f"2. After sending, DM {admin_contact} with:\n"
        f"   • Your transaction ID (hash)\n"
        f"   • Your Telegram username\n\n"
        f"3. An admin will verify and add credits within 24 hours.\n\n"
        "⚠️ Send the **exact amount**. Do not use exchanges that deduct fees."
    )


def format_history(logs: list) -> str:
    """Display recent validation history."""
    if not logs:
        return "📭 No validation history yet."

    lines = ["📜 **Last Validation Results**\n"]
    for log in logs[:10]:
        status_icon = {
            "valid": "✅",
            "declined": "❌",
            "error": "⚠️",
            "duplicate": "⏳",
            "no_credits": "💰",
        }.get(log.status, "❓")

        created = log.created_at.strftime("%m/%d %H:%M") if log.created_at else "?"
        decline_info = f" ({log.decline_code})" if log.decline_code else ""
        lines.append(
            f"{status_icon} `{log.card_bin}****{log.last4}` — {log.status}{decline_info}\n"
            f"   📅 {created}"
        )

    return "\n".join(lines)


def format_help() -> str:
    """Help message — button-based UI."""
    return (
        "📖 **How to Use This Bot**\n\n"
        "💳 **Validate a Card:**\n"
        "   Tap 'Validate Card' then send:\n"
        "   `number|exp_month|exp_year|cvv`\n\n"
        "💰 **Check Balance:**\n"
        "   Tap 'Balance' anytime\n\n"
        "📦 **Buy Credits:**\n"
        "   Tap 'Plans' → select a plan\n"
        "   Send crypto and DM admin with TX ID\n\n"
        "📜 **History:**\n"
        "   Tap 'History' for last 10 results\n\n"
        "⚠️ **Note:** Each validation costs 1 credit.\n"
        "The same card can only be validated once per 24 hours."
    )
