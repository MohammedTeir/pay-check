"""
Playwright-based Stripe Elements automation service.
Validates cards using Stripe Elements in a headless browser.
Full flow: Create PaymentMethod → Create PaymentIntent → Confirm → Cancel → Result
"""

import asyncio
import httpx
import logging
import os
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CardValidationResult:
    """Result of a card validation attempt."""
    success: bool
    payment_method_id: Optional[str] = None
    payment_intent_id: Optional[str] = None
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    card_country: Optional[str] = None
    card_funding: Optional[str] = None
    cvc_check: Optional[str] = None
    status: Optional[str] = None  # "valid", "declined", "error", "3ds_required"
    decline_code: Optional[str] = None
    error_message: Optional[str] = None


class StripeElementsValidator:
    """Validates cards using Stripe Elements in headless browser."""
    
    def __init__(self, publishable_key: str, webapp_url: str = "http://127.0.0.1:5000"):
        self.publishable_key = publishable_key
        self.webapp_url = webapp_url
        self.browser = None
        self.page = None
    
    async def initialize(self):
        """Initialize Playwright browser."""
        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            logger.info("Playwright browser launched")
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            raise
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise
    
    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
            logger.info("Browser closed")
    
    async def validate_card(
        self,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvc: str,
    ) -> CardValidationResult:
        """
        Validate a card using Stripe Elements + PaymentIntent full flow.
        1. Create PaymentMethod via Stripe Elements (browser)
        2. Create PaymentIntent via backend API
        3. PaymentIntent is auto-confirmed (off_session=True)
        4. Cancel PaymentIntent to release hold
        5. Return full validation result
        """
        if not self.browser:
            await self.initialize()

        context = None
        try:
            # Create new browser context (isolated session)
            context = await self.browser.new_context()
            page = await context.new_page()

            # Navigate to validation page (load=commit to avoid waiting for external scripts)
            await page.goto(self.webapp_url, wait_until="commit", timeout=15000)
            
            # Wait for Stripe Elements iframe to load (may take a few seconds for Stripe.js)
            # Use first() to avoid strict mode violation (multiple iframes)
            await page.wait_for_selector('#card-element iframe', timeout=12000)

            # Get the first iframe (the card input frame, not the link button frame)
            iframe_element = page.frame_locator('#card-element iframe').first

            # Fill card number in Stripe Elements
            card_input = iframe_element.locator('input[name="cardnumber"]')
            await card_input.click()
            await card_input.press_sequentially(card_number, delay=20)

            # Fill expiry - Stripe Elements expects MM/YY format
            expiry_input = iframe_element.locator('input[name="exp-date"]')
            await expiry_input.click()
            # Convert year to 2-digit format (2029 -> 29)
            yy = str(exp_year)[-2:]
            await expiry_input.press_sequentially(f"{exp_month:02d}/{yy}", delay=20)

            # Fill CVC
            cvc_input = iframe_element.locator('input[name="cvc"]')
            await cvc_input.click()
            await cvc_input.press_sequentially(cvc, delay=20)

            # Small delay for Stripe to process input
            await asyncio.sleep(0.3)

            # Click validate button to create PaymentMethod
            await page.click('#submit-btn')

            # Wait for result (up to 10 seconds)
            try:
                await page.wait_for_selector('#result', state='visible', timeout=10000)
            except Exception:
                return CardValidationResult(
                    success=False,
                    status="error",
                    error_message="Validation timeout - no response from Stripe"
                )

            # Get PaymentMethod result from JavaScript
            result = await page.evaluate("() => window.getValidationResult()")
            
            # Log browser console messages for debugging
            logger.info(f"Validation result from browser: {result}")

            if result is None:
                return CardValidationResult(
                    success=False,
                    status="error",
                    error_message="No validation result returned"
                )

            # If PaymentMethod creation failed, return result immediately
            if not result.get('success'):
                return CardValidationResult(
                    success=False,
                    status="declined",
                    payment_method_id=None,
                    error_message=result.get('error', 'Unknown error'),
                    decline_code=result.get('code'),
                )

            # PaymentMethod created successfully, now create PaymentIntent
            payment_method_id = result.get('id')
            card_info = result.get('card', {})

            # Step 2: Create and confirm PaymentIntent via backend
            async with httpx.AsyncClient(timeout=30.0) as client:
                intent_response = await client.post(
                    f"{self.webapp_url}/create_payment_intent",
                    json={"payment_method_id": payment_method_id},
                )
                intent_data = intent_response.json()
                logger.info(f"PaymentIntent API response: status={intent_response.status_code}, body={intent_data}")

            if not intent_data.get('success'):
                # PaymentIntent creation failed (card declined)
                return CardValidationResult(
                    success=False,
                    status=intent_data.get('status', 'declined'),
                    payment_method_id=payment_method_id,
                    payment_intent_id=intent_data.get('intent_id'),
                    decline_code=intent_data.get('decline_code') or intent_data.get('error_code'),
                    error_message=intent_data.get('error_message'),
                    card_brand=intent_data.get('card_brand') or card_info.get('brand'),
                    card_last4=card_info.get('last4'),
                    card_country=intent_data.get('card_country') or card_info.get('country'),
                    card_funding=intent_data.get('card_type') or card_info.get('funding'),
                    cvc_check=card_info.get('checks', {}).get('cvc_check'),
                )

            # Step 3: PaymentIntent succeeded - cancel it to release hold
            intent_id = intent_data.get('intent_id')
            intent_status = intent_data.get('status')

            if intent_status == 'requires_action':
                # Card requires 3DS
                return CardValidationResult(
                    success=False,
                    status="3ds_required",
                    payment_method_id=payment_method_id,
                    payment_intent_id=intent_id,
                    decline_code="requires_3ds",
                    error_message="This card requires 3D Secure (OTP). 2D cards only.",
                    card_brand=intent_data.get('card_brand') or card_info.get('brand'),
                    card_last4=card_info.get('last4'),
                    card_country=intent_data.get('card_country'),
                    card_funding=intent_data.get('card_type'),
                    cvc_check=card_info.get('checks', {}).get('cvc_check'),
                )

            # Cancel PaymentIntent to release authorization hold
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    cancel_response = await client.post(
                        f"{self.webapp_url}/cancel_payment_intent",
                        json={"intent_id": intent_id},
                    )
                    cancel_data = cancel_response.json()
                    logger.info(f"PaymentIntent {intent_id} canceled: {cancel_data.get('status')}")
            except Exception as e:
                logger.warning(f"Failed to cancel PaymentIntent {intent_id}: {e}")
                # Don't fail validation if cancel fails - authorization was already checked

            # Step 4: Return success
            return CardValidationResult(
                success=True,
                status="valid",
                payment_method_id=payment_method_id,
                payment_intent_id=intent_id,
                card_brand=intent_data.get('card_brand') or card_info.get('brand'),
                card_last4=card_info.get('last4'),
                card_country=intent_data.get('card_country') or card_info.get('country'),
                card_funding=intent_data.get('card_type') or card_info.get('funding'),
                cvc_check=card_info.get('checks', {}).get('cvc_check'),
            )

        except Exception as e:
            logger.error(f"Validation failed: {e}", exc_info=True)
            return CardValidationResult(
                success=False,
                status="error",
                error_message=str(e),
            )
        finally:
            if context:
                await context.close()


# Singleton instance
_validator: Optional[StripeElementsValidator] = None


async def get_validator(publishable_key: str, webapp_url: str = "http://127.0.0.1:5000") -> StripeElementsValidator:
    """Get or create the validator singleton."""
    global _validator
    if _validator is None:
        _validator = StripeElementsValidator(publishable_key=publishable_key, webapp_url=webapp_url)
        await _validator.initialize()
    return _validator


async def validate_card_with_elements(
    card_number: str,
    exp_month: int,
    exp_year: int,
    cvc: str,
    publishable_key: str,
    webapp_url: str = "http://127.0.0.1:5000",
) -> CardValidationResult:
    """
    Convenience function to validate a card using Stripe Elements + PaymentIntent.
    Full flow: PaymentMethod → PaymentIntent → Cancel → Result
    
    Args:
        card_number: Full card number
        exp_month: Expiration month
        exp_year: Expiration year
        cvc: CVC code
        publishable_key: Stripe publishable key
        webapp_url: URL of the Flask webapp
        
    Returns:
        CardValidationResult
    """
    validator = await get_validator(publishable_key=publishable_key, webapp_url=webapp_url)
    return await validator.validate_card(card_number, exp_month, exp_year, cvc)
