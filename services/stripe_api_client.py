"""
Stripe API client using direct HTTP calls to avoid SDK lazy loading bugs.
"""

import httpx
from typing import Optional


class StripeAPIClient:
    """Direct HTTP client for Stripe API, avoiding SDK issues."""
    
    API_BASE = "https://api.stripe.com/v1"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Stripe-Version": "2024-10-28.acacia",  # Use a recent stable version
        }
    
    def create_payment_intent(self, amount: int, currency: str, metadata: dict) -> dict:
        """Create a PaymentIntent."""
        data = {
            "amount": amount,
            "currency": currency,
            "payment_method_types[]": "card",
            "capture_method": "manual",
        }
        for key, value in metadata.items():
            data[f"metadata[{key}]"] = value
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.API_BASE}/payment_intents",
                headers=self.headers,
                data=data,
            )
            # Manually raise HTTPStatusError to preserve response body
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"Stripe API error: {response.status_code}",
                    request=response.request,
                    response=response,
                )
            return response.json()
    
    def create_payment_method(self, card_number: str, exp_month: int, exp_year: int, cvc: str) -> dict:
        """Create a PaymentMethod from card details."""
        data = {
            "type": "card",
            "card[number]": card_number,
            "card[exp_month]": exp_month,
            "card[exp_year]": exp_year,
            "card[cvc]": cvc,
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.API_BASE}/payment_methods",
                headers=self.headers,
                data=data,
            )
            # Manually raise HTTPStatusError to preserve response body
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"Stripe API error: {response.status_code}",
                    request=response.request,
                    response=response,
                )
            return response.json()

    def confirm_payment_intent(self, intent_id: str, payment_method_id: str, off_session: bool = True) -> dict:
        """Confirm a PaymentIntent."""
        data = {
            "payment_method": payment_method_id,
            "off_session": off_session,
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.API_BASE}/payment_intents/{intent_id}/confirm",
                headers=self.headers,
                data=data,
            )
            # Manually raise HTTPStatusError to preserve response body
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"Stripe API error: {response.status_code}",
                    request=response.request,
                    response=response,
                )
            return response.json()

    def cancel_payment_intent(self, intent_id: str) -> dict:
        """Cancel a PaymentIntent."""
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.API_BASE}/payment_intents/{intent_id}/cancel",
                headers=self.headers,
            )
            # Manually raise HTTPStatusError to preserve response body
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"Stripe API error: {response.status_code}",
                    request=response.request,
                    response=response,
                )
            return response.json()
