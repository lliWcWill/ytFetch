'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { 
  CheckCircle, 
  Coins, 
  ArrowRight, 
  Sparkles,
  Loader2,
  AlertCircle
} from 'lucide-react'
import { useAuth } from '@/providers/AuthProvider'
import { tokenService } from '@/services/tokenService'
import { UserTokenBalance } from '@/types/tokens'
import confetti from 'canvas-confetti'

function TokenSuccessContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()
  
  const [balance, setBalance] = useState<UserTokenBalance | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Get purchase details from URL params
  const packageId = searchParams.get('package') || ''
  const tokens = parseInt(searchParams.get('tokens') || '0')
  const sessionId = searchParams.get('session_id')

  useEffect(() => {
    if (!user) {
      router.push('/login')
      return
    }

    // Load updated balance
    loadBalance()
    
    // Trigger confetti animation
    if (tokens > 0) {
      triggerConfetti()
    }
  }, [user])

  const loadBalance = async () => {
    try {
      const data = await tokenService.getTokenBalance()
      setBalance(data)
    } catch (err) {
      console.error('Failed to load balance:', err)
      setError('Failed to load your updated balance')
    } finally {
      setLoading(false)
    }
  }

  const triggerConfetti = () => {
    const duration = 3000
    const animationEnd = Date.now() + duration
    const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 0 }

    const randomInRange = (min: number, max: number) => {
      return Math.random() * (max - min) + min
    }

    const interval: any = setInterval(() => {
      const timeLeft = animationEnd - Date.now()

      if (timeLeft <= 0) {
        return clearInterval(interval)
      }

      const particleCount = 50 * (timeLeft / duration)

      // Confetti from left side
      confetti({
        ...defaults,
        particleCount,
        origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 },
        colors: ['#f97316', '#ef4444', '#f59e0b', '#eab308', '#84cc16']
      })

      // Confetti from right side
      confetti({
        ...defaults,
        particleCount,
        origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 },
        colors: ['#f97316', '#ef4444', '#f59e0b', '#eab308', '#84cc16']
      })
    }, 250)
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className="h-12 w-12 animate-spin text-orange-500" />
          <p className="text-sm text-muted-foreground">Loading your purchase...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-2xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
          >
            <Card className="relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-orange-500/10 to-red-500/10" />
              
              <CardHeader className="relative text-center pb-4">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                  className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center"
                >
                  <CheckCircle className="w-10 h-10 text-green-600" />
                </motion.div>
                
                <CardTitle className="text-3xl">Purchase Successful!</CardTitle>
                <CardDescription className="text-lg mt-2">
                  Your tokens have been added to your account
                </CardDescription>
              </CardHeader>

              <CardContent className="relative space-y-6">
                {error && (
                  <div className="p-4 bg-destructive/10 text-destructive rounded-lg flex items-center gap-2">
                    <AlertCircle className="w-5 h-5" />
                    <span>{error}</span>
                  </div>
                )}

                {tokens > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="bg-gradient-to-r from-orange-50 to-red-50 dark:from-orange-950/20 dark:to-red-950/20 rounded-lg p-6 text-center"
                  >
                    <div className="flex items-center justify-center gap-2 mb-2">
                      <Sparkles className="w-5 h-5 text-orange-500" />
                      <span className="text-sm font-medium text-muted-foreground">You purchased</span>
                      <Sparkles className="w-5 h-5 text-orange-500" />
                    </div>
                    <div className="text-4xl font-bold text-orange-600">
                      {tokenService.formatTokens(tokens)} tokens
                    </div>
                  </motion.div>
                )}

                {balance && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="bg-card rounded-lg p-6 border"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-500/20 to-red-500/20 flex items-center justify-center">
                          <Coins className="w-5 h-5 text-orange-500" />
                        </div>
                        <div>
                          <p className="text-sm text-muted-foreground">New Balance</p>
                          <p className="text-2xl font-bold">
                            {tokenService.formatTokens(balance.balance)} tokens
                          </p>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}

                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5 }}
                  className="space-y-3"
                >
                  <Button
                    onClick={() => router.push('/')}
                    className="w-full bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600"
                    size="lg"
                  >
                    Start Transcribing
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                  
                  <Button
                    onClick={() => router.push('/dashboard')}
                    variant="outline"
                    className="w-full"
                    size="lg"
                  >
                    View Dashboard
                  </Button>
                </motion.div>

                {sessionId && (
                  <p className="text-xs text-center text-muted-foreground">
                    Transaction ID: {sessionId}
                  </p>
                )}
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mt-8 text-center"
          >
            <p className="text-sm text-muted-foreground">
              Need help? {' '}
              <a href="mailto:support@ytfetch.com" className="text-primary hover:underline">
                Contact support
              </a>
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  )
}

export default function TokenSuccessPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className="h-12 w-12 animate-spin text-orange-500" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    }>
      <TokenSuccessContent />
    </Suspense>
  )
}