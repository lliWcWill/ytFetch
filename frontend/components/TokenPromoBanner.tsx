'use client'

import { motion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Coins, Sparkles, Gift, ArrowRight } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'

interface TokenPromoBannerProps {
  className?: string
  variant?: 'default' | 'compact'
}

export function TokenPromoBanner({ className, variant = 'default' }: TokenPromoBannerProps) {
  const router = useRouter()

  if (variant === 'compact') {
    return (
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn(
          "bg-gradient-to-r from-orange-500/10 to-orange-600/10 rounded-lg p-4 border border-orange-500/20 backdrop-blur-sm",
          className
        )}
      >
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-500/20 to-orange-600/20 flex items-center justify-center">
              <Coins className="w-4 h-4 text-orange-500" />
            </div>
            <div>
              <p className="font-medium text-sm text-zinc-100">New Token-Based Pricing!</p>
              <p className="text-xs text-zinc-400">Pay once, use forever</p>
            </div>
          </div>
          <Button
            size="sm"
            onClick={() => router.push('/pricing')}
            className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-sm shadow-orange-500/20"
          >
            View Pricing
          </Button>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      className={cn(
        "relative overflow-hidden bg-gradient-to-r from-orange-500 to-orange-600 rounded-2xl p-8 shadow-2xl shadow-orange-500/20",
        className
      )}
    >
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-10 -right-10 w-40 h-40 bg-white/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-10 -left-10 w-40 h-40 bg-white/10 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10">
        <div className="flex flex-col lg:flex-row items-center justify-between gap-6">
          <div className="flex-1 text-center lg:text-left">
            <div className="flex items-center gap-3 justify-center lg:justify-start mb-4">
              <Badge className="bg-white/20 text-white border-white/30 backdrop-blur-sm">
                <Sparkles className="w-3 h-3 mr-1" />
                New Pricing Model
              </Badge>
              <Badge className="bg-green-500/20 text-green-100 border-green-400/30 backdrop-blur-sm">
                <Gift className="w-3 h-3 mr-1" />
                Never Expires
              </Badge>
            </div>
            
            <h3 className="text-3xl font-bold text-white mb-2">
              Token-Based Pricing is Here!
            </h3>
            <p className="text-white/90 text-lg mb-6 max-w-2xl">
              Buy tokens once and use them whenever you need. No subscriptions, no expiry dates - just simple, fair pricing.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
              <div className="bg-white/10 backdrop-blur-sm rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-white">$2.99</p>
                <p className="text-sm text-white/80">50 tokens</p>
              </div>
              <div className="bg-white/20 backdrop-blur-sm rounded-lg p-3 text-center ring-2 ring-white/30">
                <p className="text-2xl font-bold text-white">$6.99</p>
                <p className="text-sm text-white/80">150 tokens</p>
                <Badge className="mt-1 bg-green-500 text-white text-xs">Save 22%</Badge>
              </div>
              <div className="bg-white/10 backdrop-blur-sm rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-white">$17.99</p>
                <p className="text-sm text-white/80">500 tokens</p>
                <Badge className="mt-1 bg-green-500 text-white text-xs">Save 40%</Badge>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 justify-center lg:justify-start">
              <Button
                size="lg"
                onClick={() => router.push('/pricing')}
                className="bg-white text-orange-600 hover:bg-white/90 font-semibold"
              >
                <Coins className="w-5 h-5 mr-2" />
                View Token Packages
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
              <Button
                size="lg"
                variant="outline"
                onClick={() => router.push('/')}
                className="border-white/30 text-white hover:bg-white/10 backdrop-blur-sm"
              >
                Try Free First
              </Button>
            </div>
          </div>

          <div className="hidden lg:flex items-center justify-center">
            <motion.div
              animate={{ 
                y: [0, -10, 0],
                rotate: [0, 5, -5, 0]
              }}
              transition={{ 
                duration: 4,
                repeat: Infinity,
                ease: "easeInOut"
              }}
              className="w-32 h-32 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center"
            >
              <Coins className="w-16 h-16 text-white" />
            </motion.div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}