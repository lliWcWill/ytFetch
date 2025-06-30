/**
 * Example component showing how to use Stripe Checkout integration
 * This demonstrates the key functions from stripeService.ts
 */

'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { CreditCard, Loader2, Settings } from 'lucide-react'
import { StripeService } from '@/services/stripeService'
import { ApiValidationError } from '@/services/api'

export function StripeCheckoutExample() {
  const [isLoading, setIsLoading] = useState(false)
  const [isPortalLoading, setIsPortalLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Example: Create checkout session and redirect
  const handleUpgrade = async (tier: 'pro' | 'enterprise') => {
    setIsLoading(true)
    setError(null)
    
    try {
      // This creates a checkout session and immediately redirects to Stripe
      await StripeService.upgradeToTier(tier)
      // User will be redirected to Stripe Checkout page
    } catch (err) {
      if (err instanceof ApiValidationError) {
        setError(err.message)
      } else {
        setError('Failed to start checkout. Please try again.')
      }
      console.error('Checkout error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  // Example: Open customer portal
  const handleOpenPortal = async () => {
    setIsPortalLoading(true)
    setError(null)
    
    try {
      // This opens the Stripe customer portal where users can manage their subscription
      await StripeService.openCustomerPortal()
      // User will be redirected to Stripe Customer Portal
    } catch (err) {
      if (err instanceof ApiValidationError) {
        setError(err.message)
      } else {
        setError('Failed to open portal. Please try again.')
      }
      console.error('Portal error:', err)
    } finally {
      setIsPortalLoading(false)
    }
  }

  return (
    <Card className="max-w-md mx-auto">
      <CardHeader>
        <CardTitle>Stripe Checkout Example</CardTitle>
        <CardDescription>
          Example implementation of Stripe integration
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="p-3 bg-destructive/10 text-destructive rounded-md text-sm">
            {error}
          </div>
        )}
        
        <div className="space-y-2">
          <Button
            onClick={() => handleUpgrade('pro')}
            disabled={isLoading}
            className="w-full bg-blue-500 hover:bg-blue-600"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading Checkout...
              </>
            ) : (
              <>
                <CreditCard className="mr-2 h-4 w-4" />
                Upgrade to Pro ($29.99/mo)
              </>
            )}
          </Button>
          
          <Button
            onClick={() => handleUpgrade('enterprise')}
            disabled={isLoading}
            className="w-full bg-purple-500 hover:bg-purple-600"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading Checkout...
              </>
            ) : (
              <>
                <CreditCard className="mr-2 h-4 w-4" />
                Upgrade to Enterprise ($99.99/mo)
              </>
            )}
          </Button>
          
          <Button
            onClick={handleOpenPortal}
            disabled={isPortalLoading}
            variant="outline"
            className="w-full"
          >
            {isPortalLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading...
              </>
            ) : (
              <>
                <Settings className="mr-2 h-4 w-4" />
                Manage Subscription
              </>
            )}
          </Button>
        </div>
        
        <div className="text-xs text-muted-foreground space-y-1">
          <p>• Clicking upgrade creates a Stripe checkout session</p>
          <p>• Users are redirected to Stripe's hosted checkout page</p>
          <p>• After payment, they return to /billing/success</p>
          <p>• Manage subscription opens the Stripe customer portal</p>
        </div>
      </CardContent>
    </Card>
  )
}