"""
Stripe configuration and initialization.

This module handles Stripe SDK setup and configuration,
including webhook secrets and price/product mappings.
"""

import os
import logging
from typing import Dict, Optional
import stripe
from ..core.config import get_settings

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Initialize Stripe with secret key from settings
stripe.api_key = settings.stripe_secret_key or ""
logger.info(f"Stripe API key loaded: {bool(stripe.api_key)}, key starts with: {stripe.api_key[:7] if stripe.api_key else 'None'}")

# Stripe configuration
STRIPE_CONFIG = {
    "publishable_key": settings.stripe_publishable_key or "",
    "secret_key": settings.stripe_secret_key or "",
    "webhook_secret": settings.stripe_webhook_secret or "",
    "success_url": os.getenv("STRIPE_SUCCESS_URL", "http://localhost:3000/billing?success=true&session_id={CHECKOUT_SESSION_ID}"),
    "cancel_url": os.getenv("STRIPE_CANCEL_URL", "http://localhost:3000/billing?canceled=true"),
    "return_url": os.getenv("STRIPE_RETURN_URL", "http://localhost:3000/billing"),
}

# Token package price IDs (from environment)
STRIPE_TOKEN_PRICES = {
    "starter": {
        "price_id": settings.stripe_price_starter,
        "display_name": "Starter Pack",
        "tokens": 50,
        "price": 2.99,
    },
    "popular": {
        "price_id": settings.stripe_price_popular,
        "display_name": "Popular Pack",
        "tokens": 150,
        "price": 6.99,
    },
    "volume": {
        "price_id": settings.stripe_price_volume,
        "display_name": "High Volume",
        "tokens": 500,
        "price": 17.99,
    }
}

# Webhook event types we handle (one-time payments only)
HANDLED_WEBHOOK_EVENTS = [
    "checkout.session.completed",
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
]


def is_stripe_configured() -> bool:
    """Check if Stripe is properly configured."""
    return bool(STRIPE_CONFIG["secret_key"] and STRIPE_CONFIG["publishable_key"])


def get_token_package_info(package_id: str) -> Optional[Dict[str, any]]:
    """Get Stripe price information for a given token package."""
    return STRIPE_TOKEN_PRICES.get(package_id)


def get_package_from_price_id(price_id: str) -> Optional[str]:
    """Get package name from a Stripe price ID."""
    for package_id, package_info in STRIPE_TOKEN_PRICES.items():
        if package_info["price_id"] == price_id:
            return package_id
    return None