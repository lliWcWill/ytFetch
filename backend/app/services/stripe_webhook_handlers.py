"""
Stripe webhook event handlers.

This module processes Stripe webhook events and updates
user profiles accordingly.
"""

import logging
from typing import Dict, Any
from datetime import datetime
import stripe

from ..core.supabase import SupabaseClient
from ..core.stripe_config import get_package_from_price_id, HANDLED_WEBHOOK_EVENTS

logger = logging.getLogger(__name__)


class StripeWebhookHandler:
    """Handler for processing Stripe webhook events."""
    
    def __init__(self):
        self.supabase = SupabaseClient.get_service_client()
    
    async def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route webhook event to appropriate handler.
        
        Args:
            event: Stripe webhook event
            
        Returns:
            Processing result
        """
        event_type = event.get('type')
        
        if event_type not in HANDLED_WEBHOOK_EVENTS:
            logger.info(f"Unhandled webhook event type: {event_type}")
            return {'status': 'unhandled', 'event_type': event_type}
        
        # Route to specific handler
        handler_map = {
            'checkout.session.completed': self.handle_checkout_completed,
            'customer.subscription.created': self.handle_subscription_created,
            'customer.subscription.updated': self.handle_subscription_updated,
            'customer.subscription.deleted': self.handle_subscription_deleted,
            'invoice.payment_succeeded': self.handle_invoice_payment_succeeded,
            'invoice.payment_failed': self.handle_invoice_payment_failed,
            'customer.subscription.trial_will_end': self.handle_trial_will_end,
        }
        
        handler = handler_map.get(event_type)
        if handler:
            try:
                result = await handler(event)
                logger.info(f"Successfully processed {event_type}: {result}")
                return result
            except Exception as e:
                logger.error(f"Error processing {event_type}: {e}")
                raise
        
        return {'status': 'unhandled', 'event_type': event_type}
    
    async def handle_checkout_completed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle successful checkout session completion.
        
        This is triggered when a user completes the checkout process
        and their payment method is confirmed.
        """
        session = event['data']['object']
        
        # Get user ID from metadata
        user_id = session.get('metadata', {}).get('user_id')
        if not user_id:
            logger.error(f"No user_id in checkout session metadata: {session['id']}")
            return {'status': 'error', 'error': 'missing_user_id'}
        
        # Check if this is a token purchase (has tokens in metadata)
        tokens = session.get('metadata', {}).get('tokens')
        if tokens:
            return await self.handle_token_purchase(session, user_id, int(tokens))
        
        # Otherwise, handle as subscription
        subscription_id = session.get('subscription')
        customer_id = session.get('customer')
        
        if not subscription_id:
            logger.warning(f"No subscription in checkout session: {session['id']}")
            return {'status': 'error', 'error': 'missing_subscription'}
        
        try:
            # Retrieve full subscription details
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Get tier from price ID
            price_id = subscription['items']['data'][0]['price']['id']
            tier = get_tier_from_price_id(price_id) or 'pro'  # Default to pro if not found
            
            # Update user profile
            updates = {
                'stripe_customer_id': customer_id,
                'stripe_subscription_id': subscription_id,
                'stripe_subscription_status': subscription['status'],
                'tier': tier,
                'tier_updated_at': datetime.utcnow().isoformat(),
                'subscription_ends_at': datetime.fromtimestamp(subscription['current_period_end']).isoformat() if subscription.get('current_period_end') else None,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self.supabase.table('user_profiles').update(updates).eq('id', user_id).execute()
            
            logger.info(f"Updated user {user_id} to {tier} tier after checkout")
            return {
                'status': 'success',
                'user_id': user_id,
                'tier': tier,
                'subscription_id': subscription_id
            }
            
        except Exception as e:
            logger.error(f"Error handling checkout completion: {e}")
            raise
    
    async def handle_subscription_created(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle new subscription creation."""
        subscription = event['data']['object']
        return await self._update_subscription_status(subscription, 'created')
    
    async def handle_subscription_updated(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle subscription updates.
        
        This includes plan changes, status changes, and renewals.
        """
        subscription = event['data']['object']
        return await self._update_subscription_status(subscription, 'updated')
    
    async def handle_subscription_deleted(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle subscription deletion/cancellation.
        
        When a subscription is canceled or expires, downgrade user to free tier.
        """
        subscription = event['data']['object']
        
        # Get user ID from subscription metadata or customer
        user_id = subscription.get('metadata', {}).get('user_id')
        
        if not user_id:
            # Try to find user by customer ID
            customer_id = subscription.get('customer')
            if customer_id:
                profile_response = self.supabase.table('user_profiles').select("id").eq('stripe_customer_id', customer_id).single().execute()
                if profile_response.data:
                    user_id = profile_response.data['id']
        
        if not user_id:
            logger.error(f"Cannot find user for deleted subscription: {subscription['id']}")
            return {'status': 'error', 'error': 'user_not_found'}
        
        try:
            # Downgrade to free tier
            updates = {
                'tier': 'free',
                'tier_updated_at': datetime.utcnow().isoformat(),
                'stripe_subscription_status': 'canceled',
                'subscription_ends_at': datetime.fromtimestamp(subscription['canceled_at']).isoformat() if subscription.get('canceled_at') else datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self.supabase.table('user_profiles').update(updates).eq('id', user_id).execute()
            
            logger.info(f"Downgraded user {user_id} to free tier after subscription deletion")
            return {
                'status': 'success',
                'user_id': user_id,
                'action': 'downgraded_to_free'
            }
            
        except Exception as e:
            logger.error(f"Error handling subscription deletion: {e}")
            raise
    
    async def handle_invoice_payment_succeeded(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle successful invoice payment.
        
        This is triggered for subscription renewals. We can use this
        to reset monthly usage counters.
        """
        invoice = event['data']['object']
        
        # Only process for subscription invoices (not one-time charges)
        if not invoice.get('subscription'):
            return {'status': 'skipped', 'reason': 'not_subscription_invoice'}
        
        customer_id = invoice.get('customer')
        if not customer_id:
            return {'status': 'error', 'error': 'missing_customer_id'}
        
        try:
            # Find user by customer ID
            profile_response = self.supabase.table('user_profiles').select("*").eq('stripe_customer_id', customer_id).single().execute()
            if not profile_response.data:
                logger.warning(f"No user found for customer {customer_id}")
                return {'status': 'error', 'error': 'user_not_found'}
            
            user_id = profile_response.data['id']
            current_usage = profile_response.data.get('usage_data', {})
            
            # Reset monthly counters for new billing period
            current_month = datetime.utcnow().strftime("%Y-%m")
            if 'monthly' not in current_usage:
                current_usage['monthly'] = {}
            
            # Clear the current month's usage (new billing period)
            current_usage['monthly'][current_month] = {
                'videos_processed': 0,
                'jobs_created': 0,
                'transcription_minutes': 0
            }
            
            # Update user profile
            updates = {
                'usage_data': current_usage,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self.supabase.table('user_profiles').update(updates).eq('id', user_id).execute()
            
            logger.info(f"Reset monthly usage for user {user_id} after successful payment")
            return {
                'status': 'success',
                'user_id': user_id,
                'action': 'usage_reset'
            }
            
        except Exception as e:
            logger.error(f"Error handling invoice payment: {e}")
            raise
    
    async def handle_invoice_payment_failed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle failed invoice payment.
        
        We might want to notify the user or temporarily restrict access.
        """
        invoice = event['data']['object']
        customer_id = invoice.get('customer')
        
        if not customer_id:
            return {'status': 'error', 'error': 'missing_customer_id'}
        
        try:
            # Find user and update status
            profile_response = self.supabase.table('user_profiles').select("id").eq('stripe_customer_id', customer_id).single().execute()
            if not profile_response.data:
                return {'status': 'error', 'error': 'user_not_found'}
            
            user_id = profile_response.data['id']
            
            # Update subscription status to reflect payment issue
            updates = {
                'stripe_subscription_status': 'past_due',
                'updated_at': datetime.utcnow().isoformat()
            }
            
            self.supabase.table('user_profiles').update(updates).eq('id', user_id).execute()
            
            logger.warning(f"Payment failed for user {user_id}")
            return {
                'status': 'success',
                'user_id': user_id,
                'action': 'marked_past_due'
            }
            
        except Exception as e:
            logger.error(f"Error handling payment failure: {e}")
            raise
    
    async def handle_trial_will_end(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle trial ending soon notification.
        
        We can use this to send reminder emails.
        """
        subscription = event['data']['object']
        
        # Log for now, email notifications can be added later
        logger.info(f"Trial ending soon for subscription {subscription['id']}")
        
        return {
            'status': 'success',
            'action': 'trial_ending_logged'
        }
    
    async def _update_subscription_status(self, subscription: Dict[str, Any], action: str) -> Dict[str, Any]:
        """
        Common method to update subscription status in database.
        
        Args:
            subscription: Stripe subscription object
            action: Action being performed (created/updated)
            
        Returns:
            Processing result
        """
        # Get user ID from subscription metadata or customer
        user_id = subscription.get('metadata', {}).get('user_id')
        customer_id = subscription.get('customer')
        
        if not user_id and customer_id:
            # Try to find user by customer ID
            profile_response = self.supabase.table('user_profiles').select("id").eq('stripe_customer_id', customer_id).single().execute()
            if profile_response.data:
                user_id = profile_response.data['id']
        
        if not user_id:
            logger.error(f"Cannot find user for subscription: {subscription['id']}")
            return {'status': 'error', 'error': 'user_not_found'}
        
        try:
            # Get tier from price ID
            price_id = subscription['items']['data'][0]['price']['id']
            tier = get_tier_from_price_id(price_id) or 'pro'
            
            # Prepare updates based on subscription status
            updates = {
                'stripe_customer_id': customer_id,
                'stripe_subscription_id': subscription['id'],
                'stripe_subscription_status': subscription['status'],
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Update tier if subscription is active or trialing
            if subscription['status'] in ['active', 'trialing']:
                updates['tier'] = tier
                updates['tier_updated_at'] = datetime.utcnow().isoformat()
                updates['subscription_ends_at'] = datetime.fromtimestamp(subscription['current_period_end']).isoformat() if subscription.get('current_period_end') else None
            elif subscription['status'] in ['canceled', 'incomplete_expired']:
                updates['tier'] = 'free'
                updates['tier_updated_at'] = datetime.utcnow().isoformat()
            
            # Update user profile
            self.supabase.table('user_profiles').update(updates).eq('id', user_id).execute()
            
            logger.info(f"Updated user {user_id} subscription: status={subscription['status']}, tier={updates.get('tier', 'unchanged')}")
            return {
                'status': 'success',
                'user_id': user_id,
                'action': action,
                'subscription_status': subscription['status'],
                'tier': updates.get('tier')
            }
            
        except Exception as e:
            logger.error(f"Error updating subscription status: {e}")
            raise
    
    async def handle_token_purchase(self, session: Dict[str, Any], user_id: str, tokens: int) -> Dict[str, Any]:
        """
        Handle successful token purchase.
        
        Args:
            session: Stripe checkout session object
            user_id: User ID from metadata
            tokens: Number of tokens purchased
            
        Returns:
            Processing result
        """
        try:
            # Get or create token balance
            balance_result = self.supabase.table('user_token_balances') \
                .select("*") \
                .eq('user_id', user_id) \
                .single() \
                .execute()
            
            if balance_result.data:
                # Update existing balance
                current_balance = balance_result.data['balance']
                new_balance = current_balance + tokens
                lifetime_purchased = balance_result.data['lifetime_purchased'] + tokens
                
                self.supabase.table('user_token_balances') \
                    .update({
                        'balance': new_balance,
                        'lifetime_purchased': lifetime_purchased,
                        'last_purchase_at': datetime.utcnow().isoformat(),
                        'updated_at': datetime.utcnow().isoformat()
                    }) \
                    .eq('user_id', user_id) \
                    .execute()
            else:
                # Create new balance record
                self.supabase.table('user_token_balances') \
                    .insert({
                        'user_id': user_id,
                        'balance': tokens,
                        'lifetime_purchased': tokens,
                        'lifetime_spent': 0,
                        'last_purchase_at': datetime.utcnow().isoformat()
                    }) \
                    .execute()
                new_balance = tokens
            
            # Record the transaction
            package_id = session.get('metadata', {}).get('package_id', 'unknown')
            self.supabase.table('token_transactions') \
                .insert({
                    'user_id': user_id,
                    'amount': tokens,
                    'type': 'purchase',
                    'description': f'Purchased {tokens} tokens - {package_id} package',
                    'metadata': {
                        'session_id': session['id'],
                        'package_id': package_id,
                        'payment_intent': session.get('payment_intent'),
                        'amount_total': session.get('amount_total', 0) / 100  # Convert from cents
                    }
                }) \
                .execute()
            
            logger.info(f"Successfully credited {tokens} tokens to user {user_id}")
            
            return {
                'status': 'success',
                'user_id': user_id,
                'tokens_credited': tokens,
                'new_balance': new_balance,
                'package_id': package_id
            }
            
        except Exception as e:
            logger.error(f"Error handling token purchase: {e}")
            return {'status': 'error', 'error': str(e)}