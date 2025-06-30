'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import { useBulkJobsRealtime, useVideoTasksRealtime } from './useSupabaseRealtime'
import type { BulkJob, VideoTask } from '@/types/supabase'

export interface BulkJobProgressState {
  job: BulkJob | null
  videoTasks: VideoTask[]
  loading: boolean
  error: Error | null
  isRealTimeConnected: boolean
}

export interface BulkJobProgressStats {
  totalTasks: number
  completedTasks: number
  failedTasks: number
  pendingTasks: number
  processingTasks: number
  overallProgress: number
  estimatedTimeRemaining?: number
  tasksPerMinute?: number
}

export interface UseBulkJobProgressOptions {
  jobId: string
  enablePolling?: boolean
  pollingInterval?: number
  enableRealtime?: boolean
  onJobComplete?: (job: BulkJob) => void
  onJobError?: (job: BulkJob, error: string) => void
  onProgressUpdate?: (stats: BulkJobProgressStats) => void
}

export interface UseBulkJobProgressReturn {
  state: BulkJobProgressState
  stats: BulkJobProgressStats
  refreshJob: () => Promise<void>
  refreshTasks: () => Promise<void>
  refreshAll: () => Promise<void>
  cancelJob: () => Promise<void>
}

/**
 * Custom hook for tracking bulk job progress with real-time updates and polling fallback
 */
export function useBulkJobProgress({
  jobId,
  enablePolling = true,
  pollingInterval = 5000,
  enableRealtime = true,
  onJobComplete,
  onJobError,
  onProgressUpdate
}: UseBulkJobProgressOptions): UseBulkJobProgressReturn {
  const [state, setState] = useState<BulkJobProgressState>({
    job: null,
    videoTasks: [],
    loading: true,
    error: null,
    isRealTimeConnected: false
  })

  const pollingTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const lastProgressUpdateRef = useRef<number>(0)
  const startTimeRef = useRef<number>(Date.now())

  // Real-time subscriptions
  const bulkJobRealtime = useBulkJobsRealtime(
    useCallback((job: BulkJob, eventType) => {
      if (job.id === jobId) {
        setState(prev => ({ ...prev, job, loading: false }))
        
        // Trigger callbacks
        if (eventType === 'UPDATE') {
          if (job.status === 'completed' && onJobComplete) {
            onJobComplete(job)
          } else if (job.status === 'failed' && onJobError && job.error_message) {
            onJobError(job, job.error_message)
          }
        }
      }
    }, [jobId, onJobComplete, onJobError]),
    enableRealtime ? `id=eq.${jobId}` : undefined
  )

  const videoTasksRealtime = useVideoTasksRealtime(
    useCallback((task: VideoTask, eventType) => {
      if (task.bulk_job_id === jobId) {
        setState(prev => {
          const existingIndex = prev.videoTasks.findIndex(t => t.id === task.id)
          let newTasks = [...prev.videoTasks]
          
          if (eventType === 'DELETE') {
            newTasks = newTasks.filter(t => t.id !== task.id)
          } else if (existingIndex >= 0) {
            newTasks[existingIndex] = task
          } else {
            newTasks.push(task)
          }
          
          return { ...prev, videoTasks: newTasks }
        })
      }
    }, [jobId]),
    enableRealtime ? `bulk_job_id=eq.${jobId}` : undefined
  )

  // Update real-time connection status
  useEffect(() => {
    setState(prev => ({
      ...prev,
      isRealTimeConnected: enableRealtime && bulkJobRealtime.isConnected && videoTasksRealtime.isConnected
    }))
  }, [enableRealtime, bulkJobRealtime.isConnected, videoTasksRealtime.isConnected])

  // Fetch bulk job data
  const refreshJob = useCallback(async () => {
    try {
      const { data: job, error } = await supabase
        .from('bulk_jobs')
        .select('*')
        .eq('id', jobId)
        .single()

      if (error) throw error

      setState(prev => ({ ...prev, job, loading: false, error: null }))
      return job
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch job')
      setState(prev => ({ ...prev, error, loading: false }))
      throw error
    }
  }, [jobId])

  // Fetch video tasks data
  const refreshTasks = useCallback(async () => {
    try {
      const { data: videoTasks, error } = await supabase
        .from('video_tasks')
        .select('*')
        .eq('bulk_job_id', jobId)
        .order('created_at', { ascending: true })

      if (error) throw error

      setState(prev => ({ ...prev, videoTasks: videoTasks || [], error: null }))
      return videoTasks || []
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch tasks')
      setState(prev => ({ ...prev, error }))
      throw error
    }
  }, [jobId])

  // Refresh all data
  const refreshAll = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true }))
    try {
      await Promise.all([refreshJob(), refreshTasks()])
    } catch (err) {
      console.error('Error refreshing bulk job data:', err)
    }
  }, [refreshJob, refreshTasks])

  // Cancel job
  const cancelJob = useCallback(async () => {
    try {
      const { error } = await supabase
        .from('bulk_jobs')
        .update({ status: 'cancelled' })
        .eq('id', jobId)

      if (error) throw error
      
      await refreshJob()
    } catch (err) {
      console.error('Error cancelling job:', err)
      throw err
    }
  }, [jobId, refreshJob])

  // Calculate progress statistics
  const stats: BulkJobProgressStats = (() => {
    const { videoTasks, job } = state
    
    const totalTasks = videoTasks.length
    const completedTasks = videoTasks.filter(t => t.status === 'completed').length
    const failedTasks = videoTasks.filter(t => t.status === 'failed').length
    const pendingTasks = videoTasks.filter(t => t.status === 'pending').length
    const processingTasks = videoTasks.filter(t => t.status === 'processing').length
    
    const overallProgress = totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0
    
    // Calculate processing rate and ETA
    const now = Date.now()
    const elapsedMinutes = (now - startTimeRef.current) / (1000 * 60)
    const tasksPerMinute = elapsedMinutes > 0 ? completedTasks / elapsedMinutes : 0
    
    let estimatedTimeRemaining: number | undefined
    if (tasksPerMinute > 0 && pendingTasks + processingTasks > 0) {
      estimatedTimeRemaining = (pendingTasks + processingTasks) / tasksPerMinute
    }

    return {
      totalTasks,
      completedTasks,
      failedTasks,
      pendingTasks,
      processingTasks,
      overallProgress,
      estimatedTimeRemaining,
      tasksPerMinute: tasksPerMinute > 0 ? tasksPerMinute : undefined
    }
  })()

  // Trigger progress update callback with throttling
  useEffect(() => {
    const now = Date.now()
    if (onProgressUpdate && now - lastProgressUpdateRef.current > 1000) { // Throttle to once per second
      onProgressUpdate(stats)
      lastProgressUpdateRef.current = now
    }
  }, [stats, onProgressUpdate])

  // Polling fallback when real-time is not connected or disabled
  useEffect(() => {
    const shouldPoll = enablePolling && 
      (!enableRealtime || !state.isRealTimeConnected) &&
      state.job?.status === 'processing'

    if (shouldPoll) {
      const poll = () => {
        refreshAll().finally(() => {
          pollingTimeoutRef.current = setTimeout(poll, pollingInterval)
        })
      }
      
      pollingTimeoutRef.current = setTimeout(poll, pollingInterval)
    }

    return () => {
      if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current)
        pollingTimeoutRef.current = null
      }
    }
  }, [enablePolling, pollingInterval, enableRealtime, state.isRealTimeConnected, state.job?.status, refreshAll])

  // Initial data fetch
  useEffect(() => {
    refreshAll()
  }, [refreshAll])

  // Update start time when job processing begins
  useEffect(() => {
    if (state.job?.status === 'processing' && state.job.updated_at) {
      startTimeRef.current = new Date(state.job.updated_at).getTime()
    }
  }, [state.job?.status, state.job?.updated_at])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current)
      }
    }
  }, [])

  return {
    state,
    stats,
    refreshJob,
    refreshTasks,
    refreshAll,
    cancelJob
  }
}