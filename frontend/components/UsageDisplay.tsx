'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertCircle, TrendingUp, Calendar, Zap } from 'lucide-react'
import { useAuth } from '@/providers/AuthProvider'
import { cn } from '@/lib/utils'

export interface UsageDisplayProps {
  className?: string
  showUpgradeButton?: boolean
  onUpgradeClick?: () => void
}

export function UsageDisplay({ 
  className, 
  showUpgradeButton = true,
  onUpgradeClick 
}: UsageDisplayProps) {
  const { profile, refreshProfile } = useAuth()
  const [daysUntilReset, setDaysUntilReset] = useState(0)

  // Calculate days until monthly reset
  useEffect(() => {
    const now = new Date()
    const currentDay = now.getDate()
    const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
    const daysLeft = currentDay === 1 ? daysInMonth : daysInMonth - currentDay + 1
    setDaysUntilReset(daysLeft)
  }, [])

  // Refresh profile on mount
  useEffect(() => {
    refreshProfile()
  }, [refreshProfile])

  if (!profile || !profile.tier) {
    return null
  }

  const { tier } = profile
  const videosUsagePercent = (profile.videos_processed_this_month / tier.max_videos_per_job) * 100
  const jobsUsagePercent = (profile.jobs_created_this_month / tier.max_jobs_per_month) * 100

  // Determine if usage warnings should be shown
  const showVideosWarning = videosUsagePercent >= 80
  const showJobsWarning = jobsUsagePercent >= 80
  const isAtLimit = videosUsagePercent >= 100 || jobsUsagePercent >= 100

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg font-semibold">Usage Overview</CardTitle>
            <CardDescription>
              Your {tier.display_name} tier usage this month
            </CardDescription>
          </div>
          <Badge 
            variant={tier.name === 'free' ? 'secondary' : 'default'}
            className={cn(
              tier.name === 'pro' && 'bg-blue-500 hover:bg-blue-600',
              tier.name === 'enterprise' && 'bg-purple-500 hover:bg-purple-600'
            )}
          >
            {tier.display_name}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Videos Usage */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Videos Processed</span>
            <span className={cn(
              "text-muted-foreground",
              showVideosWarning && "text-orange-600 font-semibold"
            )}>
              {profile.videos_processed_this_month} / {tier.max_videos_per_job}
            </span>
          </div>
          <Progress 
            value={Math.min(videosUsagePercent, 100)} 
            className={cn(
              "h-2",
              showVideosWarning && "[&>div]:bg-orange-500",
              videosUsagePercent >= 100 && "[&>div]:bg-red-500"
            )}
          />
          {showVideosWarning && (
            <div className="flex items-center gap-2 text-sm text-orange-600">
              <AlertCircle className="h-3 w-3" />
              <span>
                {videosUsagePercent >= 100 
                  ? "Video limit reached for this month" 
                  : `${Math.round(100 - videosUsagePercent)}% remaining`
                }
              </span>
            </div>
          )}
        </div>

        {/* Jobs Usage */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Jobs Created</span>
            <span className={cn(
              "text-muted-foreground",
              showJobsWarning && "text-orange-600 font-semibold"
            )}>
              {profile.jobs_created_this_month} / {tier.max_jobs_per_month}
            </span>
          </div>
          <Progress 
            value={Math.min(jobsUsagePercent, 100)} 
            className={cn(
              "h-2",
              showJobsWarning && "[&>div]:bg-orange-500",
              jobsUsagePercent >= 100 && "[&>div]:bg-red-500"
            )}
          />
          {showJobsWarning && (
            <div className="flex items-center gap-2 text-sm text-orange-600">
              <AlertCircle className="h-3 w-3" />
              <span>
                {jobsUsagePercent >= 100 
                  ? "Job limit reached for this month" 
                  : `${Math.round(100 - jobsUsagePercent)}% remaining`
                }
              </span>
            </div>
          )}
        </div>

        {/* Tier Features */}
        <div className="space-y-2 pt-2 border-t">
          <div className="text-sm font-medium">Tier Benefits</div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center gap-2">
              <Zap className="h-3 w-3 text-muted-foreground" />
              <span className="text-muted-foreground">
                {tier.max_concurrent_jobs} concurrent {tier.max_concurrent_jobs === 1 ? 'job' : 'jobs'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="h-3 w-3 text-muted-foreground" />
              <span className="text-muted-foreground">
                Resets in {daysUntilReset} {daysUntilReset === 1 ? 'day' : 'days'}
              </span>
            </div>
          </div>
        </div>

        {/* Upgrade Button */}
        {showUpgradeButton && isAtLimit && tier.name !== 'enterprise' && (
          <div className="pt-2">
            <Button 
              onClick={onUpgradeClick}
              className="w-full bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600"
            >
              <TrendingUp className="mr-2 h-4 w-4" />
              Upgrade to {tier.name === 'free' ? 'Pro' : 'Enterprise'}
            </Button>
          </div>
        )}

        {/* Lifetime Stats */}
        <div className="text-xs text-muted-foreground pt-2 border-t">
          <div className="flex items-center justify-between">
            <span>Lifetime videos: {profile.total_videos_processed}</span>
            <span>Lifetime jobs: {profile.total_jobs_created}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}