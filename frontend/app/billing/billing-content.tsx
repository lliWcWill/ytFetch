'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/providers/AuthProvider'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { TokenBalance } from '@/components/TokenBalance'
import { 
  CreditCard, 
  Coins, 
  Package,
  Clock,
  CheckCircle2
} from 'lucide-react'
import { TOKEN_PACKAGES } from '@/types/tokens'
import { tokenService } from '@/services/tokenService'

export default function BillingContent() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [isLoading, setIsLoading] = useState<string | null>(null)

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="animate-pulse">
          <div className="h-8 bg-muted rounded w-1/3 mb-8"></div>
          <div className="grid gap-4">
            <div className="h-32 bg-muted rounded"></div>
            <div className="h-48 bg-muted rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  if (!user) {
    return null
  }

  const handlePurchase = async (packageId: string) => {
    console.log('Starting purchase for package:', packageId)
    setIsLoading(packageId)
    
    try {
      const result = await tokenService.purchaseTokens(packageId)
      console.log('Purchase result:', result)
    } catch (error) {
      console.error('Failed to start checkout:', error)
      // Show error to user
      alert(`Error: ${error instanceof Error ? error.message : 'Failed to start checkout'}`)
    } finally {
      setIsLoading(null)
    }
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-zinc-100 mb-8">Billing & Tokens</h1>

        {/* Current Balance Card */}
        <Card className="p-6 mb-8 bg-zinc-900 border-zinc-800">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-zinc-100">Current Balance</h2>
            <Coins className="h-6 w-6 text-orange-500" />
          </div>
          <TokenBalance variant="detailed" showBuyButton={false} />
        </Card>

        {/* Token Packages */}
        <div className="mb-8">
          <h2 className="text-2xl font-semibold text-zinc-100 mb-6">Buy Token Packages</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {TOKEN_PACKAGES.map((pkg) => (
              <Card 
                key={pkg.id}
                className={`
                  p-6 bg-zinc-900 border-zinc-800 relative
                  ${pkg.popular ? 'ring-2 ring-orange-500' : ''}
                `}
              >
                {pkg.popular && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                    <span className="bg-orange-500 text-white text-xs px-3 py-1 rounded-full">
                      Most Popular
                    </span>
                  </div>
                )}
                <div className="text-center mb-4">
                  <h3 className="text-lg font-semibold text-zinc-100 mb-2">{pkg.displayName}</h3>
                  <div className="text-3xl font-bold text-zinc-100 mb-1">
                    {tokenService.formatTokens(pkg.tokens)}
                    <span className="text-sm font-normal text-zinc-400 ml-1">tokens</span>
                  </div>
                  <div className="text-2xl font-semibold text-orange-500">{pkg.priceDisplay}</div>
                  {pkg.savings && (
                    <div className="text-sm text-green-500 mt-1">{pkg.savings}</div>
                  )}
                </div>
                <p className="text-sm text-zinc-400 mb-4 text-center">{pkg.description}</p>
                <Button 
                  className="w-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700"
                  onClick={() => handlePurchase(pkg.id)}
                  disabled={isLoading === pkg.id}
                >
                  {isLoading === pkg.id ? (
                    <span className="flex items-center gap-2">
                      <div className="w-4 h-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      Loading...
                    </span>
                  ) : (
                    <>
                      <Package className="mr-2 h-4 w-4" />
                      Buy Now
                    </>
                  )}
                </Button>
              </Card>
            ))}
          </div>
        </div>

        {/* Usage History */}
        <Card className="p-6 bg-zinc-900 border-zinc-800">
          <h2 className="text-xl font-semibold text-zinc-100 mb-4">Recent Activity</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm font-medium text-zinc-100">Video Transcription</p>
                  <p className="text-xs text-zinc-500">2 minutes ago</p>
                </div>
              </div>
              <div className="text-sm text-zinc-400">-1 token</div>
            </div>
            <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
              <div className="flex items-center gap-3">
                <CreditCard className="h-5 w-5 text-blue-500" />
                <div>
                  <p className="text-sm font-medium text-zinc-100">Token Purchase</p>
                  <p className="text-xs text-zinc-500">1 hour ago</p>
                </div>
              </div>
              <div className="text-sm text-green-500">+500 tokens</div>
            </div>
            <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm font-medium text-zinc-100">Bulk Transcription</p>
                  <p className="text-xs text-zinc-500">3 hours ago</p>
                </div>
              </div>
              <div className="text-sm text-zinc-400">-25 tokens</div>
            </div>
          </div>
          <Button 
            variant="outline" 
            className="w-full mt-4 border-zinc-800"
            onClick={() => router.push('/dashboard')}
          >
            <Clock className="mr-2 h-4 w-4" />
            View Full History
          </Button>
        </Card>
      </div>
    </div>
  )
}