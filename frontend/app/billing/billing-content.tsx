'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, CreditCard, Check, Loader2, Settings } from 'lucide-react'
import Link from 'next/link'
import { useAuth } from '@/providers/AuthProvider'
import { StripeService, CustomerInfo } from '@/services/stripeService'
import { ApiValidationError } from '@/services/api'

export default function BillingContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, loading, profile } = useAuth()
  
  // Redirect to dashboard as we're using token-based system now
  useEffect(() => {
    router.push('/dashboard')
  }, [])
  
  const selectedTier = searchParams.get('tier') || 'pro'
  const reason = searchParams.get('reason')
  const canceled = searchParams.get('canceled') === 'true'
  
  const [isUpgrading, setIsUpgrading] = useState(false)
  const [isLoadingPortal, setIsLoadingPortal] = useState(false)
  const [customerInfo, setCustomerInfo] = useState<CustomerInfo | null>(null)
  const [customerLoading, setCustomerLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!loading && !user) {
      sessionStorage.setItem('auth-redirect-to', '/billing')
      router.push('/login')
    }
  }, [user, loading, router])
  
  // Fetch customer info when user is loaded
  useEffect(() => {
    if (user && !loading) {
      StripeService.getCustomerInfo()
        .then(setCustomerInfo)
        .catch(err => {
          console.error('Failed to load customer info:', err)
        })
        .finally(() => setCustomerLoading(false))
    }
  }, [user, loading])
  
  // Show canceled message if user canceled checkout
  useEffect(() => {
    if (canceled) {
      setError('Checkout was canceled. You can try again whenever you\'re ready.')
      // Remove canceled param from URL
      const url = new URL(window.location.href)
      url.searchParams.delete('canceled')
      window.history.replaceState({}, '', url)
    }
  }, [canceled])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return null
  }

  const handleUpgrade = async (tier: 'pro' | 'enterprise') => {
    setIsUpgrading(true)
    setError(null)
    
    try {
      await StripeService.upgradeToTier(tier)
      // Redirect happens automatically via Stripe
    } catch (err) {
      if (err instanceof ApiValidationError) {
        setError(err.message)
      } else {
        setError('Failed to start checkout. Please try again.')
      }
      console.error('Upgrade error:', err)
    } finally {
      setIsUpgrading(false)
    }
  }
  
  const handleManageSubscription = async () => {
    setIsLoadingPortal(true)
    setError(null)
    
    try {
      await StripeService.redirectToCustomerPortal()
    } catch (err) {
      setError('Failed to open billing portal. Please try again.')
      console.error('Portal error:', err)
    } finally {
      setIsLoadingPortal(false)
    }
  }
  
  const currentTier = profile?.tier || 'free'
  const isSubscribed = currentTier !== 'free'

  return (
    <div className="container mx-auto px-4 py-16 max-w-4xl">
      <div className="mb-8">
        <Link href="/settings">
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Settings
          </Button>
        </Link>
        
        <h1 className="text-4xl font-bold mb-2">Billing & Subscription</h1>
        <p className="text-lg text-muted-foreground">
          Manage your subscription and billing details
        </p>
      </div>

      {error && (
        <Card className="mb-6 border-destructive">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {reason && (
        <Card className="mb-6 bg-muted">
          <CardContent className="pt-6">
            <p className="text-sm">
              {reason === 'limit' && 'You\'ve reached your plan limits. Upgrade to continue using all features.'}
              {reason === 'feature' && 'This feature requires a paid subscription.'}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Current Plan */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Current Plan</CardTitle>
            {isSubscribed && customerInfo && (
              <Button
                onClick={handleManageSubscription}
                variant="outline"
                size="sm"
                disabled={isLoadingPortal}
              >
                {isLoadingPortal ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Settings className="w-4 h-4 mr-2" />
                    Manage Billing
                  </>
                )}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-2xl font-semibold capitalize">
                {currentTier} {currentTier !== 'free' && 'Plan'}
              </h3>
              <p className="text-muted-foreground">
                {currentTier === 'free' && 'Basic features with limited usage'}
                {currentTier === 'pro' && 'Advanced features for professionals'}
                {currentTier === 'enterprise' && 'Unlimited access for teams'}
              </p>
            </div>
            <Badge variant={currentTier === 'free' ? 'secondary' : 'default'} className="text-lg px-3 py-1">
              {currentTier === 'free' ? 'Free' : 'Active'}
            </Badge>
          </div>
          
          {customerInfo && customerInfo.subscription && (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Billing period</span>
                <span>{customerInfo.subscription.interval === 'month' ? 'Monthly' : 'Yearly'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Next billing date</span>
                <span>{new Date(customerInfo.subscription.current_period_end * 1000).toLocaleDateString()}</span>
              </div>
              {customerInfo.subscription.cancel_at_period_end && (
                <div className="flex justify-between text-destructive">
                  <span>Cancels on</span>
                  <span>{new Date(customerInfo.subscription.current_period_end * 1000).toLocaleDateString()}</span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Available Plans */}
      {currentTier !== 'enterprise' && (
        <div className="space-y-6">
          <h2 className="text-2xl font-semibold">Available Plans</h2>
          
          <div className="grid gap-6 md:grid-cols-2">
            {/* Pro Plan */}
            {currentTier !== 'pro' && (
              <Card className={selectedTier === 'pro' ? 'ring-2 ring-primary' : ''}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-xl">Pro</CardTitle>
                    <Badge>Popular</Badge>
                  </div>
                  <CardDescription>Perfect for professionals</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="mb-6">
                    <span className="text-3xl font-bold">$19</span>
                    <span className="text-muted-foreground">/month</span>
                  </div>
                  
                  <ul className="space-y-2 mb-6">
                    <li className="flex items-center">
                      <Check className="w-4 h-4 mr-2 text-green-500" />
                      <span className="text-sm">10,000 transcription minutes/month</span>
                    </li>
                    <li className="flex items-center">
                      <Check className="w-4 h-4 mr-2 text-green-500" />
                      <span className="text-sm">Advanced AI models</span>
                    </li>
                    <li className="flex items-center">
                      <Check className="w-4 h-4 mr-2 text-green-500" />
                      <span className="text-sm">Priority processing</span>
                    </li>
                    <li className="flex items-center">
                      <Check className="w-4 h-4 mr-2 text-green-500" />
                      <span className="text-sm">Export in all formats</span>
                    </li>
                  </ul>
                  
                  <Button 
                    className="w-full" 
                    onClick={() => handleUpgrade('pro')}
                    disabled={isUpgrading || currentTier === 'pro'}
                  >
                    {isUpgrading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        <CreditCard className="w-4 h-4 mr-2" />
                        {currentTier === 'pro' ? 'Current Plan' : 'Upgrade to Pro'}
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            )}
            
            {/* Enterprise Plan */}
            <Card className={selectedTier === 'enterprise' ? 'ring-2 ring-primary' : ''}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-xl">Enterprise</CardTitle>
                  <Badge variant="secondary">Best Value</Badge>
                </div>
                <CardDescription>For teams and power users</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-6">
                  <span className="text-3xl font-bold">$99</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
                
                <ul className="space-y-2 mb-6">
                  <li className="flex items-center">
                    <Check className="w-4 h-4 mr-2 text-green-500" />
                    <span className="text-sm">Unlimited transcriptions</span>
                  </li>
                  <li className="flex items-center">
                    <Check className="w-4 h-4 mr-2 text-green-500" />
                    <span className="text-sm">All AI models included</span>
                  </li>
                  <li className="flex items-center">
                    <Check className="w-4 h-4 mr-2 text-green-500" />
                    <span className="text-sm">Real-time processing</span>
                  </li>
                  <li className="flex items-center">
                    <Check className="w-4 h-4 mr-2 text-green-500" />
                    <span className="text-sm">API access & integrations</span>
                  </li>
                </ul>
                
                <Button 
                  className="w-full" 
                  onClick={() => handleUpgrade('enterprise')}
                  disabled={isUpgrading}
                >
                  {isUpgrading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <CreditCard className="w-4 h-4 mr-2" />
                      Upgrade to Enterprise
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}