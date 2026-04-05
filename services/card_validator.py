"""
Card validator — pre-validation checks before calling Stripe.
Luhn algorithm, expiry validation, BIN extraction, and input parsing.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CardInfo:
    """Parsed card information."""
    number: str           # Full card number (in memory only, never logged)
    exp_month: int        # Expiry month (1-12)
    exp_year: int         # Expiry year (2-digit or 4-digit)
    cvv: str              # Card verification value
    bin_code: str         # First 6 digits
    last4: str            # Last 4 digits


def parse_card_input(raw: str) -> Optional[CardInfo]:
    """
    Parse card input in format: number|exp_month|exp_year|cvv
    Supports separators: | / - space
    Example: 4242424242424242|12|28|123
    """
    # Try pipe separator first
    parts = raw.strip().split("|")

    if len(parts) != 4:
        # Try other separators
        for sep in ["/", "-", " "]:
            parts = raw.strip().split(sep)
            if len(parts) == 4:
                break

    if len(parts) != 4:
        return None

    number, exp_month, exp_year, cvv = [p.strip() for p in parts]

    # Remove any non-digit characters from number
    number = re.sub(r"\D", "", number)

    try:
        exp_month_int = int(exp_month)
        exp_year_int = int(exp_year)
    except ValueError:
        return None

    if not number or not cvv:
        return None

    return CardInfo(
        number=number,
        exp_month=exp_month_int,
        exp_year=exp_year_int,
        cvv=cvv,
        bin_code=number[:6],
        last4=number[-4:],
    )


def luhn_check(card_number: str) -> bool:
    """
    Luhn algorithm (mod-10) validation.
    Returns True if the card number passes the check.
    """
    digits = [int(d) for d in card_number]
    digits.reverse()

    total = 0
    for i, digit in enumerate(digits):
        if i % 2 == 1:
            doubled = digit * 2
            if doubled > 9:
                doubled -= 9
            total += doubled
        else:
            total += digit

    return total % 10 == 0


def is_expired(exp_month: int, exp_year: int) -> bool:
    """
    Check if a card's expiry date is in the past.
    Supports both 2-digit and 4-digit years.
    """
    now = datetime.utcnow()
    current_year = now.year
    current_month = now.month

    # Normalize 2-digit year
    if exp_year < 100:
        exp_year = 2000 + exp_year

    # Expired if year is past, or same year and month has passed
    if exp_year < current_year:
        return True
    if exp_year == current_year and exp_month < current_month:
        return True

    return False


def extract_bin(card_number: str) -> str:
    """Extract the first 6 digits (BIN/IIN) from a card number."""
    return card_number[:6]


def get_card_brand(card_number: str) -> Optional[str]:
    """
    Detect card brand from the card number using regex patterns.
    Returns brand name or None if unrecognized.
    """
    patterns = {
        "Visa": r"^4",
        "Mastercard": r"^(5[1-5]|2[2-7])",
        "Amex": r"^3[47]",
        "Discover": r"^(6011|65|64[4-9])",
        "JCB": r"^(3528|3589)",
        "Diners Club": r"^3(0[0-5]|6)",
        "UnionPay": r"^(62|81)",
        "Mir": r"^220[0-4]",
    }

    for brand, pattern in patterns.items():
        if re.match(pattern, card_number):
            return brand

    return None


def validate_card(card: CardInfo) -> tuple[bool, str]:
    """
    Run all pre-validation checks on a card.
    Returns (is_valid, error_message).
    """
    # Check card number length (most cards: 13-19 digits)
    if not (13 <= len(card.number) <= 19):
        return False, "Invalid card number length"

    # Luhn check
    if not luhn_check(card.number):
        return False, "Card number failed Luhn check"

    # Expiry check
    if is_expired(card.exp_month, card.exp_year):
        return False, "Card has expired"

    # Month range
    if not (1 <= card.exp_month <= 12):
        return False, "Invalid expiry month"

    # CVV length (3-4 digits)
    if not (3 <= len(card.cvv) <= 4) or not card.cvv.isdigit():
        return False, "Invalid CVV length"

    return True, ""
