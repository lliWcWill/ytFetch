'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { AlertCircle, Sparkles, Zap, Package } from 'lucide-react'
import { useAuth } from '@/providers/AuthProvider'
import { getUsage, getUsageMessage, getUsageTypeDisplayName, type GuestUsageResponse } from '@/services/guestService'
import { cn } from '@/lib/utils'

interface GuestUsageDisplayProps {
  className?: string
  onSignUpClick?: () => void
}

export function GuestUsageDisplay({ className, onSignUpClick }: GuestUsageDisplayProps) {
  const { user } = useAuth()
  const [usage, setUsage] = useState<GuestUsageResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchUsage()
  }, [user])

  const fetchUsage = async () => {
    try {
      setLoading(true)
      const data = await getUsage()
      setUsage(data)
      setError(null)
    } catch (err) {
      setError('Failed to load usage data')
      console.error('Error fetching usage:', err)
    } finally {
      setLoading(false)
    }
  }

  // Don't show for authenticated users with paid tiers
  if (!loading && usage && !usage.is_guest && usage.tier !== 'free') {
    return null
  }

  if (loading) {
    return (
      <Card className={cn("p-4 bg-muted/50", className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-muted rounded w-1/3"></div>
          <div className="h-2 bg-muted rounded"></div>
          <div className="h-2 bg-muted rounded"></div>
        </div>
      </Card>
    )
  }

  if (error || !usage) {
    return null
  }

  const isGuest = usage.is_guest
  
  // Handle different usage structures for guests vs authenticated users
  // For authenticated users, the backend might not return the expected structure
  const hasUsageData = usage.usage && 
    usage.usage.unofficial && 
    usage.usage.groq &&
    typeof usage.usage.unofficial.used === 'number' &&
    typeof usage.usage.unofficial.limit === 'number' &&
    typeof usage.usage.groq.used === 'number' &&
    typeof usage.usage.groq.limit === 'number'
  
  if (!hasUsageData) {
    // If we don't have the expected usage data structure, don't show the component
    return null
  }
  
  const unofficialPercentage = (usage.usage.unofficial.used / usage.usage.unofficial.limit) * 100
  const groqPercentage = (usage.usage.groq.used / usage.usage.groq.limit) * 100

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={className}
    >
      <Card className="p-4 bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              {isGuest ? (
                <>
                  <AlertCircle className="h-4 w-4 text-primary" />
                  Guest Usage
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 text-primary" />
                  Free Tier Usage
                </>
              )}
            </h3>
            {isGuest && (
              <Button 
                size="sm" 
                variant="ghost" 
                onClick={onSignUpClick || (() => window.location.href = '/auth/login')}
                className="text-xs"
              >
                Sign Up Free
              </Button>
            )}
          </div>

          <div className="space-y-3">
            {/* YouTube Subtitles Usage */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground flex items-center gap-1">
                  <Zap className="h-3 w-3" />
                  {getUsageTypeDisplayName('unofficial')}
                </span>
                <span className="font-medium">
                  {usage.usage.unofficial.remaining}/{usage.usage.unofficial.limit} left
                </span>
              </div>
              <Progress 
                value={unofficialPercentage} 
                className="h-1.5"
                indicatorClassName={cn(
                  unofficialPercentage > 80 ? "bg-destructive" : 
                  unofficialPercentage > 50 ? "bg-warning" : 
                  "bg-primary"
                )}
              />
            </div>

            {/* AI Transcriptions Usage */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground flex items-center gap-1">
                  <Package className="h-3 w-3" />
                  {getUsageTypeDisplayName('groq')}
                </span>
                <span className="font-medium">
                  {usage.usage.groq.remaining}/{usage.usage.groq.limit} left
                </span>
              </div>
              <Progress 
                value={groqPercentage} 
                className="h-1.5"
                indicatorClassName={cn(
                  groqPercentage > 80 ? "bg-destructive" : 
                  groqPercentage > 50 ? "bg-warning" : 
                  "bg-primary"
                )}
              />
            </div>
          </div>

          {isGuest && (
            <p className="text-xs text-muted-foreground text-center">
              {usage.message || "Sign up for a free account to get more transcriptions!"}
            </p>
          )}
        </div>
      </Card>
    </motion.div>
  )
}

interface UsageAlertProps {
  method: 'unofficial' | 'groq'
  usage: GuestUsageResponse
  className?: string
}

export function UsageAlert({ method, usage, className }: UsageAlertProps) {
  // Ensure usage data exists
  if (!usage?.usage?.[method]) {
    return null
  }
  
  const message = getUsageMessage(usage.usage, method)
  const remaining = usage.usage[method].remaining
  
  if (remaining > 3) return null

  const variant = remaining === 0 ? 'destructive' : 'warning'
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn("rounded-lg p-3 flex items-center gap-2", 
        variant === 'destructive' ? 'bg-destructive/10 text-destructive' : 'bg-warning/10 text-warning',
        className
      )}
    >
      <AlertCircle className="h-4 w-4 flex-shrink-0" />
      <p className="text-sm">{message}</p>
    </motion.div>
  )
}