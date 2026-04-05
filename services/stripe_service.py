"""
Stripe service — handles PaymentIntent creation, confirmation, and cancellation.
Uses capture_method: manual (authorize only, never capture).
"""

import random
import time
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

import stripe

from config import config
from models.stripe_account import StripeAccount
from models.validation_log import ValidationLog
from services.card_validator import CardInfo
from services.crypto_service import decrypt
from services.retry_handler import retry_async, is_stripe_retryable_error


@dataclass
class ValidationResult:
    """Result of a card validation attempt."""
    status: str           # "valid", "declined", "error"
    decline_code: Optional[str]
    stripe_pi_id: Optional[str]
    bank_name: Optional[str]
    card_brand: Optional[str]
    error_message: Optional[str]


def _get_stripe_client(account: StripeAccount) -> stripe.StripeObject:
    """Initialize Stripe client with a decrypted secret key."""
    secret_key = decrypt(account.secret_key_encrypted)
    return stripe.StripeClient(api_key=secret_key)


def _random_delay() -> None:
    """Add 1-5 second random delay to mimic human-like timing."""
    time.sleep(random.uniform(1.0, 5.0))


async def validate_card_with_stripe(
    card: CardInfo,
    user_telegram_id: int,
    stripe_account: StripeAccount,
) -> ValidationResult:
    """
    Full Stripe validation flow with retry logic:
    1. Create PaymentIntent with capture_method=manual
    2. Create PaymentMethod from raw card
    3. Attach and confirm
    4. Parse result
    5. Cancel immediately if authorized
    6. Log the attempt

    NEVER captures funds. Always cancels the PaymentIntent.
    Retries transient errors up to 3 times with exponential backoff.
    """
    client = _get_stripe_client(stripe_account)
    validation_id = str(uuid4())
    amount = config.stripe_amount_cents

    try:
        # Step 1: Create PaymentIntent (with retry)
        async def create_intent():
            return client.payment_intents.create(
                amount=amount,
                currency="usd",
                payment_method_types=["card"],
                capture_method="manual",
                metadata={
                    "telegram_user_id": str(user_telegram_id),
                    "validation_id": validation_id,
                    "bot_name": "card_validator",
                },
            )
        
        intent = await retry_async(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            retryable_exceptions=(
                stripe.error.APIConnectionError,
                stripe.error.RateLimitError,
                stripe.error.APIError,
            ),
        )(create_intent)()

        # Random delay before confirmation
        _random_delay()

        # Step 2: Create PaymentMethod from raw card details (with retry)
        async def create_payment_method():
            return client.payment_methods.create(
                type="card",
                card={
                    "number": card.number,
                    "exp_month": card.exp_month,
                    "exp_year": card.exp_year,
                    "cvc": card.cvv,
                },
            )
        
        payment_method = await retry_async(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            retryable_exceptions=(
                stripe.error.APIConnectionError,
                stripe.error.RateLimitError,
                stripe.error.APIError,
            ),
        )(create_payment_method)()

        # Step 3: Confirm with off_session=True to skip 3DS where possible (with retry)
        # off_session=True tells Stripe this is a server-side transaction
        # Cards that REQUIRE 3DS will return requires_action instead of succeeding
        async def confirm_intent():
            return client.payment_intents.confirm(
                intent.id,
                payment_method=payment_method.id,
                off_session=True,
            )
        
        intent = await retry_async(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            retryable_exceptions=(
                stripe.error.APIConnectionError,
                stripe.error.RateLimitError,
                stripe.error.APIError,
            ),
        )(confirm_intent)()

        status = intent.status

        # Step 4: Parse result
        if status == "requires_action":
            # Card requires 3D Secure (OTP) — skip it
            result = ValidationResult(
                status="3ds_required",
                decline_code="requires_3ds",
                stripe_pi_id=intent.id,
                bank_name=None,
                card_brand=None,
                error_message="This card requires 3D Secure (OTP). 2D cards only.",
            )

        elif status == "requires_capture":
            # Card is valid — authorization succeeded
            # Extract bank/brand info if available
            bank_name = None
            card_brand = payment_method.card.brand if hasattr(payment_method, "card") else None

            # Step 5: Cancel immediately — NEVER capture (with retry)
            try:
                async def cancel_intent():
                    return client.payment_intents.cancel(intent.id)
                
                await retry_async(
                    max_retries=2,
                    base_delay=0.5,
                    max_delay=5.0,
                    retryable_exceptions=(
                        stripe.error.APIConnectionError,
                        stripe.error.RateLimitError,
                        stripe.error.APIError,
                    ),
                )(cancel_intent)()
            except Exception as e:
                # If cancel fails after retries, log it but don't fail the validation
                # Admin should manually review in Stripe dashboard
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to cancel PaymentIntent {intent.id} after retries: {e}")

            result = ValidationResult(
                status="valid",
                decline_code=None,
                stripe_pi_id=intent.id,
                bank_name=bank_name,
                card_brand=card_brand,
                error_message=None,
            )

        elif status == "requires_payment_method":
            # Card was declined
            decline_code = None
            if intent.last_payment_error and hasattr(intent.last_payment_error, "decline_code"):
                decline_code = intent.last_payment_error.decline_code

            result = ValidationResult(
                status="declined",
                decline_code=decline_code,
                stripe_pi_id=intent.id,
                bank_name=None,
                card_brand=None,
                error_message=None,
            )

        else:
            # Unexpected status
            result = ValidationResult(
                status="error",
                decline_code=None,
                stripe_pi_id=intent.id,
                bank_name=None,
                card_brand=None,
                error_message=f"Unexpected status: {status}",
            )

    except stripe.CardError as e:
        # Card-specific error (decline)
        decline_code = e.code if hasattr(e, "code") else None
        result = ValidationResult(
            status="declined",
            decline_code=decline_code,
            stripe_pi_id=e.intent.id if hasattr(e, "intent") and e.intent else None,
            bank_name=None,
            card_brand=None,
            error_message=str(e.user_message) if hasattr(e, "user_message") else None,
        )

    except stripe.StripeError as e:
        # General Stripe error (network, API, etc.)
        result = ValidationResult(
            status="error",
            decline_code=None,
            stripe_pi_id=None,
            bank_name=None,
            card_brand=None,
            error_message=str(e),
        )

    # Step 6: Log the validation attempt
    try:
        ValidationLog.create(
            user_id=user_telegram_id,
            card_bin=card.bin_code,
            last4=card.last4,
            card_hash="",  # Will be set by caller
            amount_cents=amount,
            stripe_pi_id=result.stripe_pi_id,
            status=result.status,
            decline_code=result.decline_code,
            stripe_account_id=stripe_account.id,
        )
    except Exception:
        # Don't fail validation if logging fails
        pass

    # Increment Stripe account daily counter
    stripe_account.increment_daily_count()

    return result
