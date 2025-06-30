'use client'

import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Check, X, Zap, Users, Rocket } from 'lucide-react'
import { useAuth } from '@/providers/AuthProvider'
import { cn } from '@/lib/utils'
import { StripeService } from '@/services/stripeService'
import { ApiValidationError } from '@/services/api'

export interface UpgradePromptProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  reason?: 'videos' | 'jobs' | 'concurrent' | 'duration'
  recommendedTier?: 'pro' | 'enterprise'
}

interface TierComparison {
  feature: string
  free: string | boolean
  pro: string | boolean
  enterprise: string | boolean
}

const tierComparisons: TierComparison[] = [
  {
    feature: 'Videos per job',
    free: '5',
    pro: '100',
    enterprise: '1000'
  },
  {
    feature: 'Jobs per month',
    free: '10',
    pro: '200',
    enterprise: '10,000'
  },
  {
    feature: 'Concurrent jobs',
    free: '1',
    pro: '5',
    enterprise: '20'
  },
  {
    feature: 'Max video duration',
    free: '15 min',
    pro: '2 hours',
    enterprise: '6 hours'
  },
  {
    feature: 'Priority processing',
    free: false,
    pro: true,
    enterprise: true
  },
  {
    feature: 'Webhook support',
    free: false,
    pro: true,
    enterprise: true
  },
  {
    feature: 'API access',
    free: false,
    pro: true,
    enterprise: true
  }
]

const reasonMessages = {
  videos: 'You\'ve reached the maximum number of videos per job for your current tier.',
  jobs: 'You\'ve reached the maximum number of jobs per month for your current tier.',
  concurrent: 'You\'ve reached the maximum number of concurrent jobs for your current tier.',
  duration: 'This video exceeds the maximum duration for your current tier.'
}

export function UpgradePrompt({ 
  open, 
  onOpenChange, 
  reason = 'videos',
  recommendedTier = 'pro' 
}: UpgradePromptProps) {
  const { profile } = useAuth()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const currentTier = profile?.tier?.name || 'free'
  const isCurrentPro = currentTier === 'pro'

  const handleUpgrade = async () => {
    setIsLoading(true)
    setError(null)
    
    try {
      // Determine which tier to upgrade to
      const tier = isCurrentPro ? 'enterprise' : recommendedTier
      
      // Create checkout session and redirect
      await StripeService.upgradeToTier(tier as 'pro' | 'enterprise')
      // Redirect happens automatically via Stripe
    } catch (err) {
      if (err instanceof ApiValidationError) {
        setError(err.message)
      } else {
        setError('Failed to start checkout. Please try again.')
      }
      console.error('Failed to initiate upgrade:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const getTierIcon = (tier: string) => {
    switch (tier) {
      case 'free':
        return <Zap className="h-5 w-5" />
      case 'pro':
        return <Rocket className="h-5 w-5" />
      case 'enterprise':
        return <Users className="h-5 w-5" />
      default:
        return null
    }
  }

  const renderFeatureValue = (value: string | boolean) => {
    if (typeof value === 'boolean') {
      return value ? (
        <Check className="h-4 w-4 text-green-500" />
      ) : (
        <X className="h-4 w-4 text-muted-foreground" />
      )
    }
    return <span className="font-medium">{value}</span>
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold">
            Upgrade Your Plan
          </DialogTitle>
          <DialogDescription className="text-base">
            {reasonMessages[reason]}
          </DialogDescription>
          {error && (
            <div className="mt-3 p-3 bg-destructive/10 text-destructive rounded-md text-sm">
              {error}
            </div>
          )}
        </DialogHeader>

        <div className="py-6">
          {/* Tier Comparison Table */}
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left p-4 font-medium">Features</th>
                  <th className="text-center p-4">
                    <div className="flex flex-col items-center gap-2">
                      <div className="flex items-center gap-2">
                        {getTierIcon('free')}
                        <span className="font-semibold">Free</span>
                      </div>
                      {currentTier === 'free' && (
                        <Badge variant="outline" className="text-xs">Current</Badge>
                      )}
                    </div>
                  </th>
                  <th className="text-center p-4">
                    <div className="flex flex-col items-center gap-2">
                      <div className="flex items-center gap-2">
                        {getTierIcon('pro')}
                        <span className="font-semibold">Pro</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">$29.99/mo</span>
                        {currentTier === 'pro' && (
                          <Badge variant="outline" className="text-xs">Current</Badge>
                        )}
                      </div>
                      {!isCurrentPro && recommendedTier === 'pro' && (
                        <Badge className="text-xs bg-blue-500">Recommended</Badge>
                      )}
                    </div>
                  </th>
                  <th className="text-center p-4">
                    <div className="flex flex-col items-center gap-2">
                      <div className="flex items-center gap-2">
                        {getTierIcon('enterprise')}
                        <span className="font-semibold">Enterprise</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">$99.99/mo</span>
                      </div>
                      {(isCurrentPro || recommendedTier === 'enterprise') && (
                        <Badge className="text-xs bg-purple-500">Recommended</Badge>
                      )}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tierComparisons.map((comparison, index) => (
                  <tr 
                    key={comparison.feature} 
                    className={cn(
                      "border-b",
                      index % 2 === 0 && "bg-muted/20"
                    )}
                  >
                    <td className="p-4 font-medium">{comparison.feature}</td>
                    <td className="text-center p-4">
                      {renderFeatureValue(comparison.free)}
                    </td>
                    <td className="text-center p-4">
                      {renderFeatureValue(comparison.pro)}
                    </td>
                    <td className="text-center p-4">
                      {renderFeatureValue(comparison.enterprise)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Additional Benefits */}
          <div className="mt-6 p-4 bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-lg border border-primary/20">
            <h4 className="font-semibold mb-2">
              🚀 Upgrade Benefits
            </h4>
            <ul className="space-y-1 text-sm text-muted-foreground">
              <li>• Process entire playlists and channels without limits</li>
              <li>• Get priority processing for faster results</li>
              <li>• Access webhook notifications for automation</li>
              <li>• Unlock API access for custom integrations</li>
            </ul>
          </div>
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-3">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
            className="w-full sm:w-auto"
          >
            Maybe Later
          </Button>
          <Button
            onClick={handleUpgrade}
            disabled={isLoading}
            className="w-full sm:w-auto bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600"
          >
            {isLoading ? 'Loading Checkout...' : `Upgrade to ${isCurrentPro ? 'Enterprise' : recommendedTier === 'pro' ? 'Pro' : 'Enterprise'}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}