'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { CheckCircle2, Loader2, Home, FileText } from 'lucide-react'
import Link from 'next/link'
import { useAuth } from '@/providers/AuthProvider'
import confetti from 'canvas-confetti'

export default function BillingSuccessContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, loading, refreshProfile } = useAuth()
  
  const sessionId = searchParams.get('session_id')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [countdown, setCountdown] = useState(5)
  
  // Trigger confetti on mount
  useEffect(() => {
    // Fire confetti
    confetti({
      particleCount: 100,
      spread: 70,
      origin: { y: 0.6 }
    })
    
    // Second burst
    setTimeout(() => {
      confetti({
        particleCount: 50,
        angle: 60,
        spread: 55,
        origin: { x: 0 }
      })
    }, 250)
    
    // Third burst
    setTimeout(() => {
      confetti({
        particleCount: 50,
        angle: 120,
        spread: 55,
        origin: { x: 1 }
      })
    }, 400)
  }, [])
  
  // Refresh user profile to get updated subscription status
  useEffect(() => {
    const doRefresh = async () => {
      setIsRefreshing(true)
      await refreshProfile()
      setIsRefreshing(false)
    }
    
    if (user && !loading) {
      doRefresh()
    }
  }, [user, loading])
  
  // Auto-redirect countdown
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          router.push('/bulk')
          return 0
        }
        return prev - 1
      })
    }, 1000)
    
    return () => clearInterval(timer)
  }, [router])

  if (loading || isRefreshing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="space-y-4 text-center">
          <Loader2 className="w-12 h-12 animate-spin mx-auto text-primary" />
          <p className="text-muted-foreground">
            {isRefreshing ? 'Updating your subscription...' : 'Loading...'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="max-w-md w-full space-y-6">
        <Card className="border-2 border-green-500/20">
          <CardHeader className="text-center">
            <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-10 h-10 text-green-500" />
            </div>
            <CardTitle className="text-2xl">Payment Successful!</CardTitle>
            <CardDescription>
              Your subscription has been activated
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {sessionId && (
              <div className="bg-muted rounded-lg p-3 text-sm">
                <p className="text-muted-foreground">Transaction ID:</p>
                <p className="font-mono text-xs break-all">{sessionId}</p>
              </div>
            )}
            
            <div className="space-y-4">
              <p className="text-center text-sm text-muted-foreground">
                You can now enjoy all the benefits of your upgraded plan!
              </p>
              
              <div className="flex flex-col gap-2">
                <Button asChild className="w-full">
                  <Link href="/bulk">
                    <Home className="mr-2 h-4 w-4" />
                    Go to Dashboard
                  </Link>
                </Button>
                
                <Button asChild variant="outline" className="w-full">
                  <Link href="/billing">
                    <FileText className="mr-2 h-4 w-4" />
                    View Subscription Details
                  </Link>
                </Button>
              </div>
              
              <p className="text-center text-xs text-muted-foreground">
                Redirecting to dashboard in {countdown} seconds...
              </p>
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-primary/5 border-primary/20">
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-2">What's next?</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>• Your new limits are now active</li>
              <li>• You'll receive a receipt via email</li>
              <li>• Manage your subscription anytime from settings</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}