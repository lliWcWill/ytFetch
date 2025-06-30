"""
Stripe service for handling payments and subscriptions.

This module provides core Stripe functionality including:
- Checkout session creation
- Customer portal management
- Webhook processing
- Customer synchronization
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime
import stripe
from stripe.error import StripeError

from ..core.stripe_config import (
    STRIPE_CONFIG, 
    STRIPE_PRICES,
    get_tier_from_price_id,
    is_stripe_configured
)
from ..core.supabase import SupabaseClient
from ..core.auth import AuthenticatedUser

logger = logging.getLogger(__name__)


class StripeService:
    """Service for managing Stripe operations."""
    
    @staticmethod
    async def create_or_get_stripe_customer(user: AuthenticatedUser) -> str:
        """
        Create or retrieve a Stripe customer for the authenticated user.
        
        Args:
            user: Authenticated user object
            
        Returns:
            Stripe customer ID
            
        Raises:
            StripeError: If Stripe API call fails
        """
        try:
            # Get user profile to check for existing customer ID
            supabase = SupabaseClient.get_service_client()
            profile_response = supabase.table('user_profiles').select("stripe_customer_id").eq('id', user.id).single().execute()
            
            if profile_response.data and profile_response.data.get('stripe_customer_id'):
                # Customer already exists
                return profile_response.data['stripe_customer_id']
            
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=user.email,
                metadata={
                    'user_id': user.id,
                    'created_via': 'ytfetch_backend'
                }
            )
            
            # Update user profile with Stripe customer ID
            supabase.table('user_profiles').update({
                'stripe_customer_id': customer.id,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', user.id).execute()
            
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            return customer.id
            
        except Exception as e:
            logger.error(f"Failed to create/get Stripe customer for user {user.id}: {e}")
            raise
    
    @staticmethod
    async def create_checkout_session(
        user: AuthenticatedUser,
        price_lookup_key: str,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe checkout session for subscription.
        
        Args:
            user: Authenticated user
            price_lookup_key: Stripe price lookup key
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            
        Returns:
            Checkout session data including URL
            
        Raises:
            ValueError: If price lookup key is invalid
            StripeError: If Stripe API call fails
        """
        if not is_stripe_configured():
            raise ValueError("Stripe is not properly configured")
        
        try:
            # Get or create Stripe customer
            customer_id = await StripeService.create_or_get_stripe_customer(user)
            
            # Get prices by lookup key
            prices = stripe.Price.list(
                lookup_keys=[price_lookup_key],
                expand=['data.product']
            )
            
            if not prices.data:
                raise ValueError(f"No price found for lookup key: {price_lookup_key}")
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                line_items=[{
                    'price': prices.data[0].id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url or STRIPE_CONFIG['success_url'],
                cancel_url=cancel_url or STRIPE_CONFIG['cancel_url'],
                metadata={
                    'user_id': user.id,
                    'user_email': user.email
                },
                subscription_data={
                    'metadata': {
                        'user_id': user.id,
                        'user_email': user.email
                    }
                },
                # Allow promotion codes
                allow_promotion_codes=True,
                # Customer can manage subscription in portal
                customer_update={
                    'address': 'auto'
                }
            )
            
            logger.info(f"Created checkout session {session.id} for user {user.id}")
            
            return {
                'checkout_url': session.url,
                'session_id': session.id,
                'customer_id': customer_id,
                'price_id': prices.data[0].id,
                'product_name': prices.data[0].product.name if hasattr(prices.data[0].product, 'name') else 'Subscription'
            }
            
        except StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            raise
    
    @staticmethod
    async def create_customer_portal_session(
        user: AuthenticatedUser,
        return_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe customer portal session for subscription management.
        
        Args:
            user: Authenticated user
            return_url: URL to return to after portal session
            
        Returns:
            Portal session data including URL
            
        Raises:
            ValueError: If user has no Stripe customer
            StripeError: If Stripe API call fails
        """
        if not is_stripe_configured():
            raise ValueError("Stripe is not properly configured")
        
        try:
            # Get user's Stripe customer ID
            supabase = SupabaseClient.get_service_client()
            profile_response = supabase.table('user_profiles').select("stripe_customer_id").eq('id', user.id).single().execute()
            
            if not profile_response.data or not profile_response.data.get('stripe_customer_id'):
                # Try to create customer first
                customer_id = await StripeService.create_or_get_stripe_customer(user)
            else:
                customer_id = profile_response.data['stripe_customer_id']
            
            # Create portal session
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url or STRIPE_CONFIG['return_url']
            )
            
            logger.info(f"Created portal session for user {user.id}")
            
            return {
                'portal_url': session.url,
                'session_id': session.id,
                'customer_id': customer_id
            }
            
        except StripeError as e:
            logger.error(f"Stripe error creating portal session: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating portal session: {e}")
            raise
    
    @staticmethod
    async def handle_webhook_event(
        payload: bytes,
        sig_header: str
    ) -> Dict[str, Any]:
        """
        Handle incoming Stripe webhook events.
        
        Args:
            payload: Raw request body
            sig_header: Stripe signature header
            
        Returns:
            Processing result
            
        Raises:
            ValueError: If signature verification fails
        """
        if not STRIPE_CONFIG['webhook_secret']:
            raise ValueError("Webhook secret not configured")
        
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_CONFIG['webhook_secret']
            )
            
            logger.info(f"Received webhook event: {event['type']}")
            
            # Import handler here to avoid circular import
            from .stripe_webhook_handlers import StripeWebhookHandler
            
            # Process the event
            handler = StripeWebhookHandler()
            result = await handler.handle_event(event)
            
            return result
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise ValueError("Invalid webhook signature")
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            raise
    
    @staticmethod
    async def sync_user_with_stripe(user_id: str) -> Dict[str, Any]:
        """
        Sync user's subscription status with Stripe.
        
        Args:
            user_id: User ID to sync
            
        Returns:
            Updated user profile data
        """
        try:
            supabase = SupabaseClient.get_service_client()
            
            # Get user profile
            profile_response = supabase.table('user_profiles').select("*").eq('id', user_id).single().execute()
            if not profile_response.data:
                raise ValueError(f"User profile not found for {user_id}")
            
            profile = profile_response.data
            customer_id = profile.get('stripe_customer_id')
            
            if not customer_id:
                # No Stripe customer, ensure user is on free tier
                if profile.get('tier') != 'free':
                    supabase.table('user_profiles').update({
                        'tier': 'free',
                        'tier_updated_at': datetime.utcnow().isoformat(),
                        'stripe_subscription_id': None,
                        'stripe_subscription_status': None,
                        'subscription_ends_at': None,
                        'updated_at': datetime.utcnow().isoformat()
                    }).eq('id', user_id).execute()
                return {'tier': 'free', 'status': 'no_stripe_customer'}
            
            # Get active subscriptions from Stripe
            subscriptions = stripe.Subscription.list(
                customer=customer_id,
                status='active',
                limit=1
            )
            
            if not subscriptions.data:
                # No active subscription, check for canceled/past_due
                all_subs = stripe.Subscription.list(
                    customer=customer_id,
                    limit=1
                )
                
                if all_subs.data:
                    sub = all_subs.data[0]
                    # Update with latest status
                    updates = {
                        'stripe_subscription_id': sub.id,
                        'stripe_subscription_status': sub.status,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                    
                    if sub.status in ['canceled', 'incomplete_expired']:
                        updates['tier'] = 'free'
                        updates['tier_updated_at'] = datetime.utcnow().isoformat()
                        updates['subscription_ends_at'] = datetime.fromtimestamp(sub.current_period_end).isoformat() if sub.current_period_end else None
                    
                    supabase.table('user_profiles').update(updates).eq('id', user_id).execute()
                    return {'tier': updates.get('tier', profile.get('tier')), 'status': sub.status}
                else:
                    # No subscription at all
                    if profile.get('tier') != 'free':
                        supabase.table('user_profiles').update({
                            'tier': 'free',
                            'tier_updated_at': datetime.utcnow().isoformat(),
                            'stripe_subscription_id': None,
                            'stripe_subscription_status': None,
                            'subscription_ends_at': None,
                            'updated_at': datetime.utcnow().isoformat()
                        }).eq('id', user_id).execute()
                    return {'tier': 'free', 'status': 'no_subscription'}
            
            # Active subscription found
            subscription = subscriptions.data[0]
            
            # Get tier from price ID
            price_id = subscription['items']['data'][0]['price']['id']
            tier = get_tier_from_price_id(price_id) or 'free'
            
            # Update user profile
            updates = {
                'tier': tier,
                'tier_updated_at': datetime.utcnow().isoformat(),
                'stripe_subscription_id': subscription.id,
                'stripe_subscription_status': subscription.status,
                'subscription_ends_at': datetime.fromtimestamp(subscription.current_period_end).isoformat() if subscription.current_period_end else None,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            supabase.table('user_profiles').update(updates).eq('id', user_id).execute()
            
            logger.info(f"Synced user {user_id} with Stripe: tier={tier}, status={subscription.status}")
            return {'tier': tier, 'status': subscription.status}
            
        except Exception as e:
            logger.error(f"Error syncing user {user_id} with Stripe: {e}")
            raise
    
    @staticmethod
    async def get_subscription_info(user: AuthenticatedUser) -> Dict[str, Any]:
        """
        Get detailed subscription information for a user.
        
        Args:
            user: Authenticated user
            
        Returns:
            Subscription details
        """
        try:
            supabase = SupabaseClient.get_service_client()
            
            # Get user profile
            profile_response = supabase.table('user_profiles').select("*").eq('id', user.id).single().execute()
            if not profile_response.data:
                return {
                    'tier': 'free',
                    'status': 'no_profile',
                    'has_subscription': False
                }
            
            profile = profile_response.data
            
            result = {
                'tier': profile.get('tier', 'free'),
                'tier_display_name': STRIPE_PRICES.get(profile.get('tier', 'free'), {}).get('display_name', 'Free'),
                'stripe_customer_id': profile.get('stripe_customer_id'),
                'stripe_subscription_id': profile.get('stripe_subscription_id'),
                'subscription_status': profile.get('stripe_subscription_status'),
                'subscription_ends_at': profile.get('subscription_ends_at'),
                'has_subscription': bool(profile.get('stripe_subscription_id')),
                'tier_limits': {
                    'videos_per_job': 5 if profile.get('tier') == 'free' else (100 if profile.get('tier') == 'pro' else 999999),
                    'jobs_per_month': 10 if profile.get('tier') == 'free' else (1000 if profile.get('tier') == 'pro' else 999999),
                    'concurrent_jobs': 1 if profile.get('tier') == 'free' else (5 if profile.get('tier') == 'pro' else 20),
                }
            }
            
            # If user has active subscription, get more details from Stripe
            if (profile.get('stripe_subscription_id') and 
                profile.get('stripe_subscription_status') in ['active', 'trialing']):
                try:
                    subscription = stripe.Subscription.retrieve(profile['stripe_subscription_id'])
                    result['subscription_details'] = {
                        'current_period_start': datetime.fromtimestamp(subscription.current_period_start).isoformat(),
                        'current_period_end': datetime.fromtimestamp(subscription.current_period_end).isoformat(),
                        'cancel_at_period_end': subscription.cancel_at_period_end,
                        'canceled_at': datetime.fromtimestamp(subscription.canceled_at).isoformat() if subscription.canceled_at else None,
                        'trial_end': datetime.fromtimestamp(subscription.trial_end).isoformat() if subscription.trial_end else None,
                    }
                except Exception as e:
                    logger.warning(f"Could not fetch subscription details from Stripe: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting subscription info for user {user.id}: {e}")
            return {
                'tier': 'free',
                'status': 'error',
                'has_subscription': False,
                'error': str(e)
            }