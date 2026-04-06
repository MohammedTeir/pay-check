"""
Flask web app with Stripe Elements for card validation.
This app is used by Playwright automation to validate cards.
Includes PaymentIntent creation, confirmation, and cancellation.
Secret key is fetched from database (encrypted storage).
"""

from flask import Flask, render_template, request, jsonify
import os
import sys
import httpx
import logging

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import get_supabase
from services.crypto_service import decrypt

app = Flask(__name__, template_folder='templates')
logger = logging.getLogger(__name__)

# Configuration
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', 'pk_live_placeholder')
STRIPE_AMOUNT_CENTS = int(os.getenv('STRIPE_AMOUNT_CENTS', '50'))
STRIPE_API_BASE = 'https://api.stripe.com/v1'


def get_active_stripe_secret_key() -> str:
    """Fetch and decrypt the active Stripe account's secret key from database."""
    try:
        sb = get_supabase()
        response = sb.table("stripe_accounts").select("*").eq("is_active", True).execute()
        
        if not response.data:
            logger.error("No active Stripe account found in database")
            return None
        
        account = response.data[0]
        encrypted_key = account.get("secret_key_encrypted")
        
        if not encrypted_key:
            logger.error("Stripe account has no secret key")
            return None
        
        secret_key = decrypt(encrypted_key)
        logger.info(f"Successfully loaded Stripe key for account: {account.get('label', 'unknown')}")
        return secret_key
    except Exception as e:
        logger.error(f"Failed to fetch Stripe secret key: {e}", exc_info=True)
        return None


@app.route('/')
def index():
    """Main validation page with Stripe Elements."""
    return render_template('validate.html', stripe_key=STRIPE_PUBLISHABLE_KEY)


@app.route('/validate', methods=['POST'])
def validate_card():
    """Receive card data and return Stripe publishable key for automation."""
    return jsonify({
        'publishable_key': STRIPE_PUBLISHABLE_KEY,
        'amount': STRIPE_AMOUNT_CENTS,
        'success': True
    })


@app.route('/create_payment_intent', methods=['POST'])
def create_payment_intent():
    """Create a PaymentIntent for validation using direct HTTP calls."""
    try:
        secret_key = get_active_stripe_secret_key()
        if not secret_key:
            logger.error("No Stripe secret key found in database!")
            return jsonify({
                'success': False,
                'status': 'error',
                'error_code': 'no_stripe_account',
                'error_message': 'No active Stripe account configured',
                'intent_id': None,
            }), 500
        
        data = request.json
        payment_method_id = data.get('payment_method_id')
        
        logger.info(f"Creating PaymentIntent for: {payment_method_id}")
        
        if not payment_method_id:
            return jsonify({'success': False, 'error': 'Missing payment_method_id'}), 400
        
        # Create and confirm PaymentIntent via direct HTTP
        form_data = {
            'amount': STRIPE_AMOUNT_CENTS,
            'currency': 'usd',
            'payment_method': payment_method_id,
            'capture_method': 'manual',
            'confirm': 'true',
            'off_session': 'true',
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f'{STRIPE_API_BASE}/payment_intents',
                headers={
                    'Authorization': f'Bearer {secret_key}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Stripe-Version': '2024-10-28.acacia',
                },
                data=form_data,
            )
            response.raise_for_status()
            intent = response.json()
        
        logger.info(f"PaymentIntent created: {intent['id']} - status: {intent['status']}")
        
        # Extract card details from PaymentIntent
        pm_data = intent.get('payment_method_details', {}).get('card', {})
        
        return jsonify({
            'success': True,
            'intent_id': intent['id'],
            'status': intent['status'],
            'card_brand': pm_data.get('brand') or intent.get('payment_method_options', {}).get('card', {}).get('network', ''),
            'card_type': pm_data.get('funding', ''),
            'card_country': pm_data.get('country', ''),
            'cvc_check': pm_data.get('checks', {}).get('cvc_check', ''),
            'error': None,
        })
    except httpx.HTTPStatusError as e:
        error_data = e.response.json()
        error_obj = error_data.get('error', {})
        logger.info(f"Card declined: code={error_obj.get('code')}, decline_code={error_obj.get('decline_code')}, message={error_obj.get('message')}")
        
        intent_id = None
        if hasattr(e, 'response'):
            # Try to extract intent ID from error response
            pass
        
        return jsonify({
            'success': False,
            'status': 'declined',
            'error_code': error_obj.get('code'),
            'decline_code': error_obj.get('decline_code'),
            'error_message': error_obj.get('message'),
            'intent_id': intent_id,
        })
    except httpx.RequestError as e:
        logger.error(f"HTTP request error: {e}")
        return jsonify({
            'success': False,
            'status': 'error',
            'error_code': None,
            'error_message': str(e),
            'intent_id': None,
        }), 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'status': 'error',
            'error_code': None,
            'error_message': str(e),
            'intent_id': None,
        }), 500


@app.route('/cancel_payment_intent', methods=['POST'])
def cancel_payment_intent():
    """Cancel a PaymentIntent (release authorization hold)."""
    try:
        secret_key = get_active_stripe_secret_key()
        if not secret_key:
            return jsonify({
                'success': False,
                'error': 'No active Stripe account configured',
            }), 500
        
        data = request.json
        intent_id = data.get('intent_id')
        
        logger.info(f"Canceling PaymentIntent: {intent_id}")
        
        if not intent_id:
            return jsonify({'success': False, 'error': 'Missing intent_id'}), 400
        
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f'{STRIPE_API_BASE}/payment_intents/{intent_id}/cancel',
                headers={
                    'Authorization': f'Bearer {secret_key}',
                    'Stripe-Version': '2024-10-28.acacia',
                },
            )
            logger.info(f"Cancel response status: {response.status_code}")
            
            if response.status_code == 400:
                # Already canceled or can't cancel
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', '')
                logger.warning(f"Cancel failed (400): {error_msg}")
                # Still return success - the intent was processed
                return jsonify({
                    'success': True,
                    'status': 'already_canceled',
                    'intent_id': intent_id,
                })
            
            response.raise_for_status()
            intent = response.json()
        
        logger.info(f"PaymentIntent canceled: {intent['id']} - status: {intent['status']}")
        
        return jsonify({
            'success': True,
            'status': intent['status'],
            'intent_id': intent['id'],
        })
    except httpx.RequestError as e:
        logger.error(f"Failed to cancel PaymentIntent: {e}")
        return jsonify({
            'success': True,  # Don't fail validation if cancel fails
            'status': 'cancel_error',
            'intent_id': intent_id,
        })
    except Exception as e:
        logger.error(f"Unexpected error canceling intent: {e}", exc_info=True)
        return jsonify({
            'success': True,  # Don't fail validation if cancel fails
            'status': 'cancel_error',
            'intent_id': intent_id,
        })


if __name__ == '__main__':
    port = int(os.getenv('WEBAPP_PORT', '5000'))
    app.run(host='127.0.0.1', port=port, debug=False)
