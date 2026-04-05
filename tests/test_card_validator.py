"""
Tests for card validation service — Luhn check, expiry, parsing, brand detection.
"""

import pytest
from datetime import datetime
from services.card_validator import (
    luhn_check,
    is_expired,
    parse_card_input,
    validate_card,
    get_card_brand,
    CardInfo,
)


class TestLuhnCheck:
    """Luhn algorithm tests."""

    def test_valid_visa(self):
        assert luhn_check("4242424242424242") is True

    def test_valid_mastercard(self):
        assert luhn_check("5555555555554444") is True

    def test_valid_amex(self):
        assert luhn_check("378282246310005") is True

    def test_valid_discover(self):
        assert luhn_check("6011111111111117") is True

    def test_invalid_number(self):
        assert luhn_check("4242424242424241") is False

    def test_empty_string(self):
        assert luhn_check("") is True  # Edge case: empty sums to 0

    def test_single_digit(self):
        assert luhn_check("0") is True


class TestExpiryCheck:
    """Card expiry validation tests."""

    def test_future_date(self):
        assert is_expired(12, 2030) is False

    def test_current_month(self):
        now = datetime.utcnow()
        assert is_expired(now.month, now.year) is False

    def test_last_month(self):
        now = datetime.utcnow()
        last_month = now.month - 1 if now.month > 1 else 12
        assert is_expired(last_month, now.year) is True

    def test_past_year(self):
        assert is_expired(1, 2020) is True

    def test_two_digit_future(self):
        # 2-digit year in the future
        assert is_expired(12, 35) is False  # 2035

    def test_two_digit_past(self):
        # 2-digit year in the past
        assert is_expired(1, 20) is True  # 2020

    def test_invalid_month(self):
        assert is_expired(13, 2030) is False  # Month validation is separate


class TestCardParsing:
    """Card input parsing tests."""

    def test_pipe_separator(self):
        card = parse_card_input("4242424242424242|12|28|123")
        assert card is not None
        assert card.number == "4242424242424242"
        assert card.exp_month == 12
        assert card.exp_year == 28
        assert card.cvv == "123"
        assert card.bin_code == "424242"
        assert card.last4 == "4242"

    def test_slash_separator(self):
        card = parse_card_input("4242424242424242/12/28/123")
        assert card is not None
        assert card.number == "4242424242424242"

    def test_spaces(self):
        card = parse_card_input("4242424242424242 12 28 123")
        assert card is not None

    def test_invalid_format(self):
        card = parse_card_input("4242424242424242")
        assert card is None

    def test_missing_cvv(self):
        card = parse_card_input("4242424242424242|12|28|")
        assert card is not None  # CVV can be empty string, caught by validate_card

    def test_non_numeric_expiry(self):
        card = parse_card_input("4242424242424242|ab|cd|123")
        assert card is None


class TestValidateCard:
    """Full pre-validation tests."""

    def test_valid_card(self):
        card = CardInfo(
            number="4242424242424242",
            exp_month=12,
            exp_year=2030,
            cvv="123",
            bin_code="424242",
            last4="4242",
        )
        is_valid, error = validate_card(card)
        assert is_valid is True
        assert error == ""

    def test_invalid_luhn(self):
        card = CardInfo(
            number="4242424242424241",
            exp_month=12,
            exp_year=2030,
            cvv="123",
            bin_code="424242",
            last4="4241",
        )
        is_valid, error = validate_card(card)
        assert is_valid is False
        assert "Luhn" in error

    def test_expired_card(self):
        card = CardInfo(
            number="4242424242424242",
            exp_month=1,
            exp_year=2020,
            cvv="123",
            bin_code="424242",
            last4="4242",
        )
        is_valid, error = validate_card(card)
        assert is_valid is False
        assert "expired" in error.lower()

    def test_invalid_month(self):
        card = CardInfo(
            number="4242424242424242",
            exp_month=13,
            exp_year=2030,
            cvv="123",
            bin_code="424242",
            last4="4242",
        )
        is_valid, error = validate_card(card)
        assert is_valid is False

    def test_invalid_cvv_length(self):
        card = CardInfo(
            number="4242424242424242",
            exp_month=12,
            exp_year=2030,
            cvv="12",
            bin_code="424242",
            last4="4242",
        )
        is_valid, error = validate_card(card)
        assert is_valid is False

    def test_too_short_number(self):
        card = CardInfo(
            number="4242",
            exp_month=12,
            exp_year=2030,
            cvv="123",
            bin_code="4242",
            last4="4242",
        )
        is_valid, error = validate_card(card)
        assert is_valid is False


class TestCardBrand:
    """Card brand detection tests."""

    def test_visa(self):
        assert get_card_brand("4242424242424242") == "Visa"

    def test_mastercard(self):
        assert get_card_brand("5555555555554444") == "Mastercard"

    def test_amex(self):
        assert get_card_brand("378282246310005") == "Amex"

    def test_discover(self):
        assert get_card_brand("6011111111111117") == "Discover"

    def test_unknown(self):
        assert get_card_brand("9999999999999999") is None
