"""
Stripe API endpoints for handling payments and subscriptions.

This module provides REST endpoints for:
- Creating checkout sessions
- Managing customer portal
- Processing webhooks
- Listing available pricing tiers
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel

from ..core.auth import AuthenticatedUser, RequireAuth
from ..core.stripe_config import STRIPE_PRICES, is_stripe_configured
from ..services.stripe_service import StripeService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/stripe", tags=["Stripe"])


class CreateCheckoutSessionRequest(BaseModel):
    """Request model for creating checkout session."""
    price_lookup_key: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CreatePortalSessionRequest(BaseModel):
    """Request model for creating customer portal session."""
    return_url: Optional[str] = None


class CheckoutSessionResponse(BaseModel):
    """Response model for checkout session creation."""
    checkout_url: str
    session_id: str
    customer_id: str
    price_id: str
    product_name: str


class PortalSessionResponse(BaseModel):
    """Response model for portal session creation."""
    portal_url: str
    session_id: str
    customer_id: str


class PricingTier(BaseModel):
    """Model for pricing tier information."""
    tier: str
    lookup_key: str
    display_name: str
    price_monthly: int
    price_yearly: int
    features: dict


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    user: AuthenticatedUser = RequireAuth
):
    """
    Create a Stripe checkout session for subscription purchase.
    
    This endpoint creates a new checkout session that redirects the user
    to Stripe's hosted checkout page where they can enter payment details
    and complete the subscription.
    
    Args:
        request: Checkout session parameters
        user: Authenticated user
        
    Returns:
        Checkout session details including URL
        
    Raises:
        HTTPException: 400 if Stripe not configured, 500 for other errors
    """
    if not is_stripe_configured():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "stripe_not_configured",
                "message": "Payment processing is not available at this time",
                "status_code": 400
            }
        )
    
    try:
        result = await StripeService.create_checkout_session(
            user=user,
            price_lookup_key=request.price_lookup_key,
            success_url=request.success_url,
            cancel_url=request.cancel_url
        )
        
        return CheckoutSessionResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "message": str(e),
                "status_code": 400
            }
        )
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "checkout_creation_failed",
                "message": "Failed to create checkout session",
                "details": str(e),
                "status_code": 500
            }
        )


@router.post("/portal-session", response_model=PortalSessionResponse)
async def create_portal_session(
    request: CreatePortalSessionRequest,
    user: AuthenticatedUser = RequireAuth
):
    """
    Create a Stripe customer portal session for subscription management.
    
    This endpoint creates a portal session that allows users to:
    - View their subscription details
    - Update payment methods
    - Cancel or change their subscription
    - Download invoices
    
    Args:
        request: Portal session parameters
        user: Authenticated user
        
    Returns:
        Portal session details including URL
        
    Raises:
        HTTPException: 400 if Stripe not configured, 500 for other errors
    """
    if not is_stripe_configured():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "stripe_not_configured",
                "message": "Payment processing is not available at this time",
                "status_code": 400
            }
        )
    
    try:
        result = await StripeService.create_customer_portal_session(
            user=user,
            return_url=request.return_url
        )
        
        return PortalSessionResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "message": str(e),
                "status_code": 400
            }
        )
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "portal_creation_failed",
                "message": "Failed to create customer portal session",
                "details": str(e),
                "status_code": 500
            }
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """
    Handle Stripe webhook events.
    
    This endpoint receives webhook events from Stripe and processes them
    to keep user subscription data in sync. Events include:
    - Checkout completion
    - Subscription updates
    - Payment successes/failures
    
    Note: This endpoint does NOT require authentication as it's called
    by Stripe directly. Security is ensured through signature verification.
    
    Args:
        request: Raw request containing webhook payload
        stripe_signature: Stripe signature header for verification
        
    Returns:
        Success response
        
    Raises:
        HTTPException: 400 for invalid signatures, 500 for processing errors
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_signature",
                "message": "No stripe-signature header",
                "status_code": 400
            }
        )
    
    try:
        # Get raw body
        payload = await request.body()
        
        # Process webhook
        result = await StripeService.handle_webhook_event(
            payload=payload,
            sig_header=stripe_signature
        )
        
        return {"status": "success", "result": result}
        
    except ValueError as e:
        # Invalid signature
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_signature",
                "message": str(e),
                "status_code": 400
            }
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Return 200 to prevent Stripe from retrying
        # Log the error for investigation
        return {"status": "error", "error": str(e)}


@router.get("/prices", response_model=list[PricingTier])
async def get_pricing_tiers():
    """
    Get available pricing tiers and their features.
    
    This endpoint returns information about all available subscription
    tiers including pricing and feature limits. No authentication required
    as this is public information.
    
    Returns:
        List of pricing tiers with features
    """
    tiers = []
    
    for tier_name, price_info in STRIPE_PRICES.items():
        # Get tier limits from auth module
        from ..core.auth import TIER_LIMITS
        tier_limits = TIER_LIMITS.get(tier_name, {})
        
        tier = PricingTier(
            tier=tier_name,
            lookup_key=price_info["lookup_key"],
            display_name=price_info["display_name"],
            price_monthly=price_info["price_monthly"],
            price_yearly=price_info["price_yearly"],
            features={
                "videos_per_job": tier_limits.get("videos_per_job", 0),
                "jobs_per_month": tier_limits.get("jobs_per_month", 0),
                "concurrent_jobs": tier_limits.get("concurrent_jobs", 0),
                "videos_per_month": tier_limits.get("videos_per_month", 0),
                "transcription_minutes_per_month": tier_limits.get("transcription_minutes_per_month", 0),
            }
        )
        tiers.append(tier)
    
    return tiers


@router.get("/subscription-info")
async def get_subscription_info(user: AuthenticatedUser = RequireAuth):
    """
    Get current user's subscription information.
    
    This endpoint returns detailed information about the user's current
    subscription including tier, status, and usage limits.
    
    Args:
        user: Authenticated user
        
    Returns:
        Subscription details and limits
    """
    try:
        info = await StripeService.get_subscription_info(user)
        return info
    except Exception as e:
        logger.error(f"Error getting subscription info: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "subscription_info_failed",
                "message": "Failed to retrieve subscription information",
                "details": str(e),
                "status_code": 500
            }
        )


@router.post("/sync-subscription")
async def sync_subscription(user: AuthenticatedUser = RequireAuth):
    """
    Manually sync user's subscription status with Stripe.
    
    This endpoint forces a synchronization between the local database
    and Stripe's current subscription data. Useful if webhook events
    were missed or for troubleshooting.
    
    Args:
        user: Authenticated user
        
    Returns:
        Updated subscription status
    """
    try:
        result = await StripeService.sync_user_with_stripe(user.id)
        return {
            "status": "success",
            "tier": result.get("tier"),
            "subscription_status": result.get("status")
        }
    except Exception as e:
        logger.error(f"Error syncing subscription: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "sync_failed", 
                "message": "Failed to sync subscription status",
                "details": str(e),
                "status_code": 500
            }
        )