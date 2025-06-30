/**
 * Stripe Service Layer
 * Handles all Stripe-related operations including checkout sessions and customer portal
 */

import { loadStripe, Stripe } from '@stripe/stripe-js';
import { apiRequest, ApiValidationError, TierLimitError } from './api';

// Initialize Stripe instance (singleton pattern)
let stripePromise: Promise<Stripe | null> | null = null;

/**
 * Gets or creates the Stripe instance
 */
export function getStripe(): Promise<Stripe | null> {
  if (!stripePromise) {
    const publishableKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
    
    if (!publishableKey) {
      console.error('Missing NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY');
      return Promise.resolve(null);
    }
    
    stripePromise = loadStripe(publishableKey);
  }
  
  return stripePromise;
}

// Types
export interface PriceTier {
  id: string;
  name: string;
  displayName: string;
  price: number;
  priceDisplay: string;
  stripePriceId: string;
  features: string[];
  limits: {
    videosPerJob: number;
    jobsPerMonth: number;
    concurrentJobs: number;
    maxVideoDuration: number; // in minutes
  };
}

export interface CheckoutSessionResponse {
  sessionId: string;
  url: string;
}

export interface PortalSessionResponse {
  url: string;
}

export interface CustomerInfo {
  hasSubscription: boolean;
  currentTier?: string;
  subscriptionStatus?: string;
  subscriptionEndDate?: string;
  cancelAtPeriodEnd?: boolean;
}

/**
 * Creates a Stripe checkout session for upgrading to a new tier
 * @param tier - The tier to upgrade to ('pro' or 'enterprise')
 * @param successUrl - URL to redirect to after successful payment
 * @param cancelUrl - URL to redirect to if user cancels
 * @returns Promise<CheckoutSessionResponse>
 */
export async function createCheckoutSession(
  tier: 'pro' | 'enterprise',
  successUrl?: string,
  cancelUrl?: string
): Promise<CheckoutSessionResponse> {
  if (!tier || (tier !== 'pro' && tier !== 'enterprise')) {
    throw new ApiValidationError('Invalid tier. Must be "pro" or "enterprise"');
  }

  const baseUrl = window.location.origin;
  const defaultSuccessUrl = `${baseUrl}/billing/success?session_id={CHECKOUT_SESSION_ID}`;
  const defaultCancelUrl = `${baseUrl}/billing?canceled=true`;

  try {
    const response = await apiRequest<CheckoutSessionResponse>('/api/v1/stripe/create-checkout-session', {
      method: 'POST',
      body: JSON.stringify({
        tier,
        success_url: successUrl || defaultSuccessUrl,
        cancel_url: cancelUrl || defaultCancelUrl,
      }),
    });

    return response;
  } catch (error) {
    if (error instanceof TierLimitError) {
      // User is already on this tier or higher
      throw new ApiValidationError('You are already on this tier or a higher tier');
    }
    throw error;
  }
}

/**
 * Redirects the user to Stripe Checkout
 * @param sessionId - The checkout session ID from createCheckoutSession
 * @returns Promise<void>
 */
export async function redirectToCheckout(sessionId: string): Promise<void> {
  if (!sessionId) {
    throw new ApiValidationError('Session ID is required');
  }

  const stripe = await getStripe();
  
  if (!stripe) {
    throw new ApiValidationError('Stripe is not properly configured');
  }

  const { error } = await stripe.redirectToCheckout({
    sessionId,
  });

  if (error) {
    throw new ApiValidationError(error.message || 'Failed to redirect to checkout');
  }
}

/**
 * Creates a customer portal session for managing subscriptions
 * @param returnUrl - URL to return to after portal session
 * @returns Promise<PortalSessionResponse>
 */
export async function createPortalSession(
  returnUrl?: string
): Promise<PortalSessionResponse> {
  const baseUrl = window.location.origin;
  const defaultReturnUrl = `${baseUrl}/billing`;

  try {
    const response = await apiRequest<PortalSessionResponse>('/api/v1/stripe/create-portal-session', {
      method: 'POST',
      body: JSON.stringify({
        return_url: returnUrl || defaultReturnUrl,
      }),
    });

    return response;
  } catch (error) {
    if (error instanceof ApiValidationError && error.message.includes('no customer')) {
      throw new ApiValidationError('You need to have an active or past subscription to access the customer portal');
    }
    throw error;
  }
}

/**
 * Fetches available pricing tiers from the backend
 * @returns Promise<PriceTier[]>
 */
export async function getPrices(): Promise<PriceTier[]> {
  try {
    const response = await apiRequest<{ prices: PriceTier[] }>('/api/v1/stripe/prices');
    return response.prices || [];
  } catch (error) {
    console.error('Failed to fetch prices:', error);
    // Return default prices as fallback
    return getDefaultPrices();
  }
}

/**
 * Gets customer subscription information
 * @returns Promise<CustomerInfo>
 */
export async function getCustomerInfo(): Promise<CustomerInfo> {
  try {
    const response = await apiRequest<CustomerInfo>('/api/v1/stripe/customer-info');
    return response;
  } catch (error) {
    // If not authenticated or no customer record, return default
    return {
      hasSubscription: false,
    };
  }
}

/**
 * Helper function to create a checkout session and immediately redirect
 * @param tier - The tier to upgrade to
 * @returns Promise<void>
 */
export async function upgradeToTier(tier: 'pro' | 'enterprise'): Promise<void> {
  try {
    const session = await createCheckoutSession(tier);
    await redirectToCheckout(session.sessionId);
  } catch (error) {
    throw error;
  }
}

/**
 * Helper function to open the customer portal
 * @returns Promise<void>
 */
export async function openCustomerPortal(): Promise<void> {
  try {
    const session = await createPortalSession();
    window.location.href = session.url;
  } catch (error) {
    throw error;
  }
}

/**
 * Returns default pricing information for offline/fallback scenarios
 */
function getDefaultPrices(): PriceTier[] {
  return [
    {
      id: 'pro',
      name: 'pro',
      displayName: 'Professional',
      price: 29.99,
      priceDisplay: '$29.99',
      stripePriceId: '',
      features: [
        '100 videos per job',
        '200 jobs per month',
        '5 concurrent jobs',
        '2 hour max video duration',
        'Priority processing',
        'Webhook support',
        'API access'
      ],
      limits: {
        videosPerJob: 100,
        jobsPerMonth: 200,
        concurrentJobs: 5,
        maxVideoDuration: 120
      }
    },
    {
      id: 'enterprise',
      name: 'enterprise',
      displayName: 'Enterprise',
      price: 99.99,
      priceDisplay: '$99.99',
      stripePriceId: '',
      features: [
        '1000 videos per job',
        '10,000 jobs per month',
        '20 concurrent jobs',
        '6 hour max video duration',
        'Priority processing',
        'Webhook support',
        'Full API access',
        'Dedicated support'
      ],
      limits: {
        videosPerJob: 1000,
        jobsPerMonth: 10000,
        concurrentJobs: 20,
        maxVideoDuration: 360
      }
    }
  ];
}

// Export utilities
export const StripeService = {
  getStripe,
  createCheckoutSession,
  redirectToCheckout,
  createPortalSession,
  getPrices,
  getCustomerInfo,
  upgradeToTier,
  openCustomerPortal,
};

export default StripeService;