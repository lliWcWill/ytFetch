'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Coins, TrendingUp, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useRouter } from 'next/navigation'
import { tokenService } from '@/services/tokenService'
import { UserTokenBalance } from '@/types/tokens'
import { cn } from '@/lib/utils'
import { useAuth } from '@/providers/AuthProvider'

interface TokenBalanceProps {
  variant?: 'default' | 'compact' | 'inline' | 'detailed'
  showBuyButton?: boolean
  className?: string
  onBalanceUpdate?: (balance: UserTokenBalance) => void
}

export function TokenBalance({ 
  variant = 'default', 
  showBuyButton = true,
  className,
  onBalanceUpdate
}: TokenBalanceProps) {
  const router = useRouter()
  const { user } = useAuth()
  const [balance, setBalance] = useState<UserTokenBalance | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (user) {
      loadBalance()
    } else {
      setBalance(null)
      setLoading(false)
    }
  }, [user])

  // Listen for auth state changes to refresh balance
  useEffect(() => {
    const handleAuthStateChange = () => {
      console.log('Auth state changed, refreshing token balance')
      if (user) {
        loadBalance()
      }
    }

    window.addEventListener('auth-state-changed', handleAuthStateChange)
    return () => window.removeEventListener('auth-state-changed', handleAuthStateChange)
  }, [user])

  const loadBalance = async () => {
    try {
      const data = await tokenService.getTokenBalance()
      setBalance(data)
      onBalanceUpdate?.(data)
      setError(null)
    } catch (err: any) {
      console.error('Failed to load token balance:', err)
      // Only show error if it's not an authentication error
      if (err.message !== 'Authentication required') {
        setError('Failed to load balance')
      }
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className={cn("animate-pulse", className)}>
        <div className="h-6 bg-zinc-800 rounded w-24"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn("flex items-center gap-2 text-destructive", className)}>
        <AlertCircle className="w-4 h-4" />
        <span className="text-sm">{error}</span>
      </div>
    )
  }

  // Don't render anything if user is not authenticated
  if (!user || !balance) {
    return null
  }

  const isLowBalance = balance.balance < 10

  if (variant === 'inline') {
    return (
      <div className={cn("flex items-center gap-2", className)}>
        <Coins className="w-4 h-4 text-orange-500" />
        <span className="text-sm font-medium text-zinc-200">
          {tokenService.formatTokens(balance.balance)} tokens
        </span>
        {isLowBalance && showBuyButton && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => router.push('/pricing')}
            className="text-xs h-6 px-2 text-orange-500 hover:text-orange-400"
          >
            Buy more
          </Button>
        )}
      </div>
    )
  }

  if (variant === 'compact') {
    return (
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn("bg-zinc-900 rounded-lg p-3 border border-zinc-800", className)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-500/20 to-orange-600/20 flex items-center justify-center">
              <Coins className="w-4 h-4 text-orange-500" />
            </div>
            <div>
              <p className="text-sm text-zinc-500">Token Balance</p>
              <p className="font-semibold text-zinc-100">
                {tokenService.formatTokens(balance.balance)}
              </p>
            </div>
          </div>
          {showBuyButton && (
            <Button
              size="sm"
              variant={isLowBalance ? "default" : "outline"}
              onClick={() => router.push('/pricing')}
              className={cn(
                "text-xs",
                isLowBalance && "bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-sm shadow-orange-500/20"
              )}
            >
              {isLowBalance ? "Low balance" : "Buy tokens"}
            </Button>
          )}
        </div>
      </motion.div>
    )
  }

  if (variant === 'detailed') {
    return (
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn("space-y-4", className)}
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-4xl font-bold text-zinc-100">
              {tokenService.formatTokens(balance.balance)}
            </p>
            <p className="text-sm text-zinc-500">tokens available</p>
          </div>
          {isLowBalance && (
            <Badge variant="secondary" className="bg-orange-500/10 text-orange-500 border border-orange-500/20">
              Low balance
            </Badge>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <p className="text-xs text-zinc-500 mb-1">Lifetime Purchased</p>
            <p className="text-lg font-semibold text-zinc-100">
              {tokenService.formatTokens(balance.lifetimePurchased)}
            </p>
          </div>
          <div className="bg-zinc-800/50 rounded-lg p-3">
            <p className="text-xs text-zinc-500 mb-1">Lifetime Used</p>
            <p className="text-lg font-semibold text-zinc-100">
              {tokenService.formatTokens(balance.lifetimeUsed)}
            </p>
          </div>
        </div>

        {showBuyButton && (
          <Button
            onClick={() => router.push('/pricing')}
            className={cn(
              "w-full",
              isLowBalance 
                ? "bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-sm shadow-orange-500/20"
                : ""
            )}
            variant={isLowBalance ? "default" : "outline"}
          >
            {isLowBalance ? "Buy more tokens" : "View token packages"}
          </Button>
        )}
      </motion.div>
    )
  }

  // Default variant
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("bg-zinc-900 rounded-xl p-6 border border-zinc-800 shadow-sm", className)}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Coins className="w-5 h-5 text-orange-500" />
          Token Balance
        </h3>
        {isLowBalance && (
          <Badge variant="secondary" className="bg-orange-500/10 text-orange-500 border border-orange-500/20">
            Low balance
          </Badge>
        )}
      </div>
      
      <div className="space-y-4">
        <div>
          <p className="text-3xl font-bold text-zinc-100">
            {tokenService.formatTokens(balance.balance)}
          </p>
          <p className="text-sm text-zinc-500">tokens available</p>
        </div>

        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-1">
            <TrendingUp className="w-4 h-4 text-green-500" />
            <span className="text-zinc-500">
              {tokenService.formatTokens(balance.lifetimePurchased)} purchased
            </span>
          </div>
        </div>

        {showBuyButton && (
          <div className="pt-2">
            <Button
              onClick={() => router.push('/pricing')}
              className={cn(
                "w-full",
                isLowBalance 
                  ? "bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-sm shadow-orange-500/20"
                  : ""
              )}
              variant={isLowBalance ? "default" : "outline"}
            >
              {isLowBalance ? "Buy more tokens" : "View token packages"}
            </Button>
          </div>
        )}
      </div>
    </motion.div>
  )
}