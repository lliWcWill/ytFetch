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

# Price lookup keys and IDs (to be set in environment)
STRIPE_PRICES = {
    "free": {
        "lookup_key": "free_tier",
        "price_id": os.getenv("STRIPE_PRICE_FREE", ""),
        "display_name": "Free",
        "price_monthly": 0,
        "price_yearly": 0,
    },
    "pro": {
        "lookup_key": "pro_tier",
        "price_id": os.getenv("STRIPE_PRICE_PRO", ""),
        "display_name": "Pro",
        "price_monthly": 19,
        "price_yearly": 190,
    },
    "enterprise": {
        "lookup_key": "enterprise_tier", 
        "price_id": os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
        "display_name": "Enterprise",
        "price_monthly": 99,
        "price_yearly": 990,
    }
}

# Product IDs (optional, for reference)
STRIPE_PRODUCTS = {
    "free": os.getenv("STRIPE_PRODUCT_FREE", ""),
    "pro": os.getenv("STRIPE_PRODUCT_PRO", ""),
    "enterprise": os.getenv("STRIPE_PRODUCT_ENTERPRISE", ""),
}

# Webhook event types we handle
HANDLED_WEBHOOK_EVENTS = [
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated", 
    "customer.subscription.deleted",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
    "customer.subscription.trial_will_end",
]


def is_stripe_configured() -> bool:
    """Check if Stripe is properly configured."""
    return bool(STRIPE_CONFIG["secret_key"] and STRIPE_CONFIG["publishable_key"])


def get_price_for_tier(tier: str) -> Optional[Dict[str, any]]:
    """Get Stripe price information for a given tier."""
    return STRIPE_PRICES.get(tier)


def get_tier_from_price_id(price_id: str) -> Optional[str]:
    """Get tier name from a Stripe price ID."""
    for tier, price_info in STRIPE_PRICES.items():
        if price_info["price_id"] == price_id:
            return tier
    return None


def get_tier_from_lookup_key(lookup_key: str) -> Optional[str]:
    """Get tier name from a Stripe price lookup key."""
    for tier, price_info in STRIPE_PRICES.items():
        if price_info["lookup_key"] == lookup_key:
            return tier
    return None