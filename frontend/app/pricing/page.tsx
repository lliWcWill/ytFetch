'use client'

import { useState, useEffect, Suspense } from 'react'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Check, 
  Zap, 
  TrendingUp, 
  Rocket, 
  ArrowRight,
  Coins,
  Sparkles,
  Gift
} from 'lucide-react'
import { useAuth } from '@/providers/AuthProvider'
import { useRouter, useSearchParams } from 'next/navigation'
import { cn } from '@/lib/utils'
import { FAQ } from '@/components/FAQ'
import { TOKEN_PACKAGES } from '@/types/tokens'
import { tokenService } from '@/services/tokenService'

interface PricingTier {
  id: string
  name: string
  displayName: string
  tokens: number
  price: number
  priceDisplay: string
  description: string
  features: string[]
  popular?: boolean
  savings?: string
  icon: React.ReactNode
  buttonText: string
  buttonVariant: 'default' | 'outline'
  perTokenPrice: number
}

// Transform token packages into pricing tiers
const tiers: PricingTier[] = TOKEN_PACKAGES.map(pkg => ({
  ...pkg,
  icon: pkg.id === 'starter' ? <Zap className="w-6 h-6" /> :
        pkg.id === 'popular' ? <TrendingUp className="w-6 h-6" /> :
        <Rocket className="w-6 h-6" />,
  buttonText: 'Buy Tokens',
  buttonVariant: pkg.popular ? 'default' : 'outline' as 'default' | 'outline',
  features: [
    `${tokenService.formatTokens(pkg.tokens)} tokens`,
    `${pkg.priceDisplay} one-time payment`,
    'All output formats (TXT, SRT, VTT, JSON)',
    'Never expires',
    pkg.id === 'starter' ? 'Perfect for trying out' :
    pkg.id === 'popular' ? 'Most popular choice' :
    'Best value per token',
    pkg.savings ? pkg.savings : 'No commitment required'
  ]
}))

const billingFaqItems = [
  {
    question: "How do tokens work?",
    answer: "Tokens are credits you purchase to transcribe videos. Each video transcription costs 1 token, regardless of video length. Buy tokens once and use them whenever you need - they never expire!"
  },
  {
    question: "What's included with tokens?",
    answer: "All token packages include access to all features: multiple output formats (TXT, SRT, VTT, JSON), bulk processing, and priority transcription. The only difference is the number of tokens you get."
  },
  {
    question: "Do tokens expire?",
    answer: "No! Tokens never expire. Buy them once and use them at your own pace. Your token balance is saved to your account permanently."
  },
  {
    question: "Can I buy more tokens anytime?",
    answer: "Yes! You can purchase additional token packages whenever you need them. New tokens are automatically added to your existing balance."
  },
  {
    question: "Is there a free option?",
    answer: "Yes! You can transcribe up to 5 videos per day without signing in. Sign up for a free account to track your token balance and purchase tokens when you need more."
  },
  {
    question: "Do you offer refunds?",
    answer: "We offer a 30-day money-back guarantee on token purchases. If you're not satisfied, contact support for a full refund on unused tokens."
  }
]

function PricingContent() {
  const { user } = useAuth()
  const router = useRouter()
  const [isLoading, setIsLoading] = useState<string | null>(null)
  const searchParams = useSearchParams()

  const handleSelectPlan = async (tier: PricingTier) => {
    setIsLoading(tier.id)
    
    if (!user) {
      sessionStorage.setItem('auth-redirect-to', `/pricing?package=${tier.id}`)
      router.push('/login')
    } else {
      try {
        await tokenService.purchaseTokens(tier.id)
      } catch (error) {
        console.error('Failed to start checkout:', error)
        // Error handling is done in the service
      }
    }
    
    setIsLoading(null)
  }

  // Check if we should auto-trigger checkout after auth
  useEffect(() => {
    const packageId = searchParams.get('package')
    const authSuccess = searchParams.get('auth_success')
    
    if (user && packageId && authSuccess === '1') {
      // User just authenticated and has a package to purchase
      const tier = tiers.find(t => t.id === packageId)
      if (tier) {
        // Clear the auth_success param to prevent re-triggering
        const url = new URL(window.location.href)
        url.searchParams.delete('auth_success')
        url.searchParams.delete('package')
        window.history.replaceState(null, '', url.toString())
        
        // Auto-trigger the checkout
        handleSelectPlan(tier)
      }
    }
  }, [user, searchParams])

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Hero Section */}
      <div className="container mx-auto px-4 pt-12 pb-8">
        <div className="text-center max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <Badge className="mb-4 bg-gradient-to-r from-orange-500 to-orange-600 text-white border-0 shadow-lg shadow-orange-500/20">
              <Sparkles className="w-3 h-3 mr-1" />
              Pay Once, Use Forever
            </Badge>
            <h1 className="text-5xl font-bold tracking-tight">
              <span className="text-zinc-100">Simple </span>
              <span className="bg-gradient-to-r from-orange-500 to-orange-600 bg-clip-text text-transparent">
                Token-Based Pricing
              </span>
            </h1>
            <p className="text-xl text-zinc-400 leading-relaxed max-w-2xl mx-auto">
              Buy tokens once and use them whenever you need. No subscriptions, no recurring fees - just pay for what you use.
            </p>
            <div className="flex items-center justify-center gap-6 text-sm text-zinc-500 pt-4">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span>Never expires</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                <span>1 token = 1 video</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                <span>All features included</span>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Pricing Cards */}
      <div className="container mx-auto px-4 pb-16">
        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {tiers.map((tier, index) => (
            <motion.div
              key={tier.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="relative"
            >
              {tier.popular && (
                <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 z-10">
                  <Badge className="bg-gradient-to-r from-orange-500 to-orange-600 text-white border-0 shadow-lg shadow-orange-500/20">
                    <Sparkles className="w-3 h-3 mr-1" />
                    Most Popular
                  </Badge>
                </div>
              )}
              
              <Card className={cn(
                "h-full relative bg-zinc-900 border-zinc-800",
                tier.popular && "ring-2 ring-orange-500 shadow-xl shadow-orange-500/20 scale-105"
              )}>
                <CardHeader className="text-center pb-4">
                  <div className="flex items-center justify-center w-12 h-12 mx-auto mb-4 rounded-full bg-gradient-to-br from-orange-500/20 to-red-500/20">
                    {tier.icon}
                  </div>
                  <CardTitle className="text-2xl text-zinc-100">{tier.displayName}</CardTitle>
                  <div className="space-y-2">
                    <div className="flex items-baseline justify-center gap-1">
                      <span className="text-4xl font-bold">{tier.priceDisplay}</span>
                    </div>
                    <div className="flex flex-col items-center gap-1">
                      <p className="text-lg font-semibold text-zinc-100">
                        {tokenService.formatTokens(tier.tokens)} tokens
                      </p>
                      <p className="text-sm text-zinc-500">
                        ${(tier.perTokenPrice).toFixed(3)} per token
                      </p>
                    </div>
                    {tier.savings && (
                      <Badge variant="secondary" className="bg-green-500/10 text-green-700">
                        {tier.savings}
                      </Badge>
                    )}
                  </div>
                </CardHeader>

                <CardContent className="space-y-6">
                  <ul className="space-y-3">
                    {tier.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start gap-3">
                        <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                        <span className="text-sm text-zinc-400">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    onClick={() => handleSelectPlan(tier)}
                    className={cn(
                      "w-full",
                      tier.popular && "bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-lg shadow-orange-500/20"
                    )}
                    variant={tier.buttonVariant}
                    disabled={isLoading === tier.id}
                  >
                    {isLoading === tier.id ? (
                      <span className="flex items-center gap-2">
                        <div className="w-4 h-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        Loading...
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        <Coins className="w-4 h-4" />
                        {tier.buttonText}
                      </span>
                    )}
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Token Benefits */}
      <div className="bg-gradient-to-b from-zinc-900/30 to-zinc-950 py-16">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">Why Token-Based Pricing?</h2>
            <p className="text-zinc-400 max-w-2xl mx-auto">
              Fair, transparent pricing that puts you in control
            </p>
          </div>

          <div className="grid md:grid-cols-4 gap-8 max-w-5xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="text-center space-y-4"
            >
              <div className="w-12 h-12 mx-auto rounded-full bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center">
                <Gift className="w-6 h-6 text-green-600" />
              </div>
              <h3 className="text-xl font-semibold text-zinc-100">Never Expires</h3>
              <p className="text-zinc-400">
                Buy tokens once and use them forever. No time pressure.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="text-center space-y-4"
            >
              <div className="w-12 h-12 mx-auto rounded-full bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center">
                <Zap className="w-6 h-6 text-blue-600" />
              </div>
              <h3 className="text-xl font-semibold text-zinc-100">Pay Once</h3>
              <p className="text-zinc-400">
                No subscriptions or recurring fees. Just simple one-time payments.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="text-center space-y-4"
            >
              <div className="w-12 h-12 mx-auto rounded-full bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-purple-600" />
              </div>
              <h3 className="text-xl font-semibold text-zinc-100">Volume Savings</h3>
              <p className="text-zinc-400">
                Save up to 40% with larger token packages.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="text-center space-y-4"
            >
              <div className="w-12 h-12 mx-auto rounded-full bg-gradient-to-br from-orange-500/20 to-red-500/20 flex items-center justify-center">
                <Rocket className="w-6 h-6 text-orange-600" />
              </div>
              <h3 className="text-xl font-semibold text-zinc-100">All Features</h3>
              <p className="text-zinc-400">
                Every token includes access to all premium features.
              </p>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Billing FAQ */}
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold mb-4">Billing & Plans FAQ</h2>
            <p className="text-zinc-400">Common questions about pricing and billing</p>
          </div>

          <div className="space-y-4">
            {billingFaqItems.map((item, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="bg-zinc-900 border border-zinc-800 rounded-lg p-6"
              >
                <h3 className="font-medium text-zinc-100 mb-2">{item.question}</h3>
                <p className="text-zinc-400">{item.answer}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="bg-gradient-to-b from-zinc-950 to-zinc-900/30 py-16">
        <div className="container mx-auto px-4 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="max-w-2xl mx-auto"
          >
            <h2 className="text-3xl font-bold mb-4">Ready to start transcribing?</h2>
            <p className="text-zinc-400 mb-8">
              Choose your token package and start transcribing videos instantly. Your tokens never expire!
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button
                onClick={() => router.push('/')}
                variant="outline"
                size="lg"
              >
                Try Free (5 videos/day)
              </Button>
              <Button
                onClick={() => handleSelectPlan(tiers.find(t => t.popular) || tiers[1])}
                size="lg"
                className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-lg shadow-orange-500/20"
              >
                <Coins className="w-4 h-4 mr-2" />
                Get Started with Tokens
              </Button>
            </div>
            {user && (
              <p className="text-sm text-zinc-500 mt-4">
                Already have tokens? {' '}
                <button 
                  onClick={() => router.push('/dashboard')}
                  className="text-orange-500 hover:text-orange-400 hover:underline transition-colors"
                >
                  View your balance
                </button>
              </p>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  )
}

export default function PricingPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-zinc-950">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
          <p className="text-sm text-zinc-400">Loading pricing...</p>
        </div>
      </div>
    }>
      <PricingContent />
    </Suspense>
  )
}