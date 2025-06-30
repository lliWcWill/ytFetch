'use client'

import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/providers/AuthProvider'
import { supabase } from '@/providers/AuthProvider'

interface UsageData {
  videosProcessed: number
  jobsCreated: number
  videosLimit: number
  jobsLimit: number
  videosPercentage: number
  jobsPercentage: number
  isAtVideoLimit: boolean
  isAtJobLimit: boolean
  isAtAnyLimit: boolean
  canCreateJob: boolean
  canProcessVideos: (count: number) => boolean
}

interface UsageTracking {
  usage: UsageData | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function useUsageTracking(): UsageTracking {
  const { profile, refreshProfile } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Calculate usage data from profile
  const usage: UsageData | null = profile?.tier ? {
    videosProcessed: profile.videos_processed_this_month,
    jobsCreated: profile.jobs_created_this_month,
    videosLimit: profile.tier.max_videos_per_job,
    jobsLimit: profile.tier.max_jobs_per_month,
    videosPercentage: (profile.videos_processed_this_month / profile.tier.max_videos_per_job) * 100,
    jobsPercentage: (profile.jobs_created_this_month / profile.tier.max_jobs_per_month) * 100,
    isAtVideoLimit: profile.videos_processed_this_month >= profile.tier.max_videos_per_job,
    isAtJobLimit: profile.jobs_created_this_month >= profile.tier.max_jobs_per_month,
    isAtAnyLimit: 
      profile.videos_processed_this_month >= profile.tier.max_videos_per_job ||
      profile.jobs_created_this_month >= profile.tier.max_jobs_per_month,
    canCreateJob: profile.jobs_created_this_month < profile.tier.max_jobs_per_month,
    canProcessVideos: (count: number) => 
      profile.videos_processed_this_month + count <= profile.tier.max_videos_per_job
  } : null

  // Refresh usage data
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await refreshProfile()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh usage data')
    } finally {
      setLoading(false)
    }
  }, [refreshProfile])

  // Set up real-time subscription for usage updates
  useEffect(() => {
    if (!profile?.id) return

    // Subscribe to changes to the user's profile
    const channel = supabase
      .channel(`usage-${profile.id}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'user_profiles',
          filter: `id=eq.${profile.id}`
        },
        async (payload) => {
          console.log('Usage update received:', payload)
          // Refresh profile to get updated usage data
          await refresh()
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [profile?.id, refresh])

  // Also subscribe to bulk job creation to update job count
  useEffect(() => {
    if (!profile?.id) return

    const channel = supabase
      .channel(`jobs-${profile.id}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'bulk_jobs',
          filter: `user_id=eq.${profile.id}`
        },
        async (payload) => {
          console.log('New job created:', payload)
          // Refresh profile to get updated job count
          await refresh()
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [profile?.id, refresh])

  return {
    usage,
    loading,
    error,
    refresh
  }
}