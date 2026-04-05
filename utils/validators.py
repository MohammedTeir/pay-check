"""
Input validation utilities — sanitize and validate all user/admin inputs.
"""

import re
from typing import Optional


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_positive_integer(value: str) -> int:
    """Validate that input is a positive integer."""
    value = value.strip()
    if not value.isdigit():
        raise ValidationError(f"Invalid input: `{value}` — must be a positive number")
    result = int(value)
    if result <= 0:
        raise ValidationError(f"Invalid input: must be greater than 0")
    return result


def validate_non_negative_integer(value: str) -> int:
    """Validate that input is a non-negative integer."""
    value = value.strip()
    if not value.isdigit():
        raise ValidationError(f"Invalid input: `{value}` — must be a number")
    return int(value)


def validate_positive_float(value: str) -> float:
    """Validate that input is a positive float/integer."""
    value = value.strip()
    try:
        result = float(value)
    except ValueError:
        raise ValidationError(f"Invalid input: `{value}` — must be a number")
    if result <= 0:
        raise ValidationError(f"Invalid input: must be greater than 0")
    return result


def validate_crypto_address(address: str, currency: str = "USDT_TRC20") -> str:
    """Validate cryptocurrency wallet address format."""
    address = address.strip()
    
    patterns = {
        'BTC': r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}$',
        'USDT_TRC20': r'^T[a-zA-HJ-NP-Z0-9]{33}$',
        'USDT_ERC20': r'^0x[a-fA-F0-9]{40}$',
        'ETH': r'^0x[a-fA-F0-9]{40}$',
    }
    
    if currency not in patterns:
        raise ValidationError(f"Unsupported currency: {currency}")
    
    if not re.match(patterns[currency], address):
        raise ValidationError(f"Invalid {currency} address format")
    
    return address


def validate_telegram_username(username: str) -> str:
    """Validate Telegram username format."""
    username = username.strip().lstrip('@')
    
    if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
        raise ValidationError(
            f"Invalid username: `{username}`\n"
            f"Must be 5-32 characters (A-Z, 0-9, underscore)"
        )
    
    return f"@{username}"


def validate_stripe_secret_key(key: str) -> str:
    """Validate Stripe secret key format."""
    key = key.strip()
    
    if not key.startswith(('sk_live_', 'sk_test_')):
        raise ValidationError(
            f"Invalid Stripe key format — must start with `sk_live_` or `sk_test_`"
        )
    
    return key


def validate_amount_cents(value: str) -> int:
    """Validate amount for Stripe (in cents, minimum 50 = $0.50)."""
    amount = validate_positive_integer(value)
    if amount < 50:
        raise ValidationError(f"Amount must be at least 50 cents ($0.50)")
    if amount > 999999:
        raise ValidationError(f"Amount too large (max: 999999 cents = $9,999.99)")
    return amount


def validate_plan_name(name: str) -> str:
    """Validate plan name."""
    name = name.strip()
    
    if len(name) < 2:
        raise ValidationError(f"Plan name too short (minimum 2 characters)")
    if len(name) > 50:
        raise ValidationError(f"Plan name too long (maximum 50 characters)")
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name):
        raise ValidationError(f"Plan name contains invalid characters")
    
    return name


def validate_telegram_id(user_id: str) -> int:
    """Validate Telegram user ID."""
    user_id = user_id.strip()
    
    if not user_id.isdigit():
        raise ValidationError(f"Invalid user ID: must be a number")
    
    tid = int(user_id)
    if tid < 1:
        raise ValidationError(f"Invalid user ID: must be positive")
    
    return tid


def sanitize_text(text: str, max_length: int = 500) -> str:
    """Sanitize text input (remove dangerous characters, limit length)."""
    text = text.strip()
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length]
    
    return text


def validate_email(email: str) -> str:
    """Validate email format."""
    email = email.strip().lower()
    
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValidationError(f"Invalid email format")
    
    return email


def validate_url(url: str) -> str:
    """Validate URL format."""
    url = url.strip()
    
    if not re.match(r'^https?://[^\s]+$', url):
        raise ValidationError(f"Invalid URL format — must start with http:// or https://")
    
    return url
