'use client'

import { useState, useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { 
  Play, 
  Square, 
  Download, 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertCircle,
  RefreshCw,
  Loader2,
  Video,
  Eye
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { 
  type BulkJobResponse, 
  type JobStatus,
  cancelBulkJob,
  startBulkJob,
  getBulkJobStatus
} from '@/services/bulkApi'
import { downloadJobResults } from '@/services/api'
import { ApiHttpError, ApiNetworkError, ApiValidationError } from '@/services/api'

interface BulkProgressDisplayProps {
  job: BulkJobResponse
  onJobUpdate?: (job: BulkJobResponse) => void
  onCancel?: () => void
  autoRefresh?: boolean
  refreshInterval?: number
}

type TaskStatusInfo = {
  icon: React.ReactNode
  color: string
  bgColor: string
  label: string
}

export function BulkProgressDisplay({ 
  job, 
  onJobUpdate,
  onCancel,
  autoRefresh = true,
  refreshInterval = 3000
}: BulkProgressDisplayProps) {
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  // Auto-refresh job status (only when processing)
  useEffect(() => {
    if (!autoRefresh || job.status !== 'processing') {
      return
    }

    const interval = setInterval(async () => {
      try {
        setIsRefreshing(true)
        const updatedJob = await getBulkJobStatus(job.job_id)
        onJobUpdate?.(updatedJob)
      } catch (err) {
        console.error('Failed to refresh job status:', err)
      } finally {
        setIsRefreshing(false)
      }
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [job.job_id, job.status, autoRefresh, refreshInterval, onJobUpdate])

  // Calculate progress statistics
  const progressStats = useMemo(() => {
    const total = job.total_videos
    const completed = job.completed_videos
    const failed = job.failed_videos
    const pending = job.pending_videos || 0
    const processing = job.processing_videos || 0
    const retrying = job.retry_videos || 0
    
    const progressPercent = total > 0 ? Math.round((completed / total) * 100) : 0
    const successRate = total > 0 ? Math.round((completed / (completed + failed)) * 100) : 0
    
    return {
      total,
      completed,
      failed,
      pending,
      processing,
      retrying,
      progressPercent,
      successRate: isNaN(successRate) ? 0 : successRate,
      isCompleted: completed + failed >= total,
      hasFailures: failed > 0
    }
  }, [job])

  const getStatusInfo = (status: JobStatus): TaskStatusInfo => {
    switch (status) {
      case 'pending':
        return {
          icon: <Clock className="h-4 w-4" />,
          color: 'text-yellow-600',
          bgColor: 'bg-yellow-100 border-yellow-200',
          label: 'Pending'
        }
      case 'processing':
        return {
          icon: <Loader2 className="h-4 w-4 animate-spin" />,
          color: 'text-blue-600',
          bgColor: 'bg-blue-100 border-blue-200',
          label: 'Processing'
        }
      case 'completed':
        return {
          icon: <CheckCircle className="h-4 w-4" />,
          color: 'text-green-600',
          bgColor: 'bg-green-100 border-green-200',
          label: 'Completed'
        }
      case 'failed':
        return {
          icon: <XCircle className="h-4 w-4" />,
          color: 'text-red-600',
          bgColor: 'bg-red-100 border-red-200',
          label: 'Failed'
        }
      case 'cancelled':
        return {
          icon: <Square className="h-4 w-4" />,
          color: 'text-gray-600',
          bgColor: 'bg-gray-100 border-gray-200',
          label: 'Cancelled'
        }
      default:
        return {
          icon: <AlertCircle className="h-4 w-4" />,
          color: 'text-gray-600',
          bgColor: 'bg-gray-100 border-gray-200',
          label: 'Unknown'
        }
    }
  }

  const statusInfo = getStatusInfo(job.status)

  const handleStartJob = async () => {
    if (job.status !== 'pending') return
    
    setIsStarting(true)
    setError(null)
    
    try {
      await startBulkJob(job.job_id)
      // Refresh job status after starting
      const updatedJob = await getBulkJobStatus(job.job_id)
      onJobUpdate?.(updatedJob)
    } catch (err) {
      if (err instanceof ApiValidationError) {
        setError(`Start Error: ${err.message}`)
      } else if (err instanceof ApiNetworkError) {
        setError(`Network Error: ${err.message}`)
      } else if (err instanceof ApiHttpError) {
        setError(`Server Error: ${err.message}`)
      } else {
        setError(`Unexpected Error: ${err instanceof Error ? err.message : 'Failed to start job'}`)
      }
    } finally {
      setIsStarting(false)
    }
  }

  const handleCancelJob = async () => {
    if (!['pending', 'processing'].includes(job.status)) return
    
    setIsCancelling(true)
    setError(null)
    
    try {
      await cancelBulkJob(job.job_id)
      // Refresh job status after cancelling
      const updatedJob = await getBulkJobStatus(job.job_id)
      onJobUpdate?.(updatedJob)
      onCancel?.()
    } catch (err) {
      if (err instanceof ApiValidationError) {
        setError(`Cancel Error: ${err.message}`)
      } else if (err instanceof ApiNetworkError) {
        setError(`Network Error: ${err.message}`)
      } else if (err instanceof ApiHttpError) {
        setError(`Server Error: ${err.message}`)
      } else {
        setError(`Unexpected Error: ${err instanceof Error ? err.message : 'Failed to cancel job'}`)
      }
    } finally {
      setIsCancelling(false)
    }
  }

  const handleDownload = async () => {
    setIsDownloading(true)
    setDownloadError(null)
    
    try {
      await downloadJobResults(job.job_id)
    } catch (err) {
      if (err instanceof ApiValidationError) {
        setDownloadError(`Download Error: ${err.message}`)
      } else if (err instanceof ApiNetworkError) {
        setDownloadError(`Network Error: ${err.message}`)
      } else if (err instanceof ApiHttpError) {
        setDownloadError(`Server Error: ${err.message}`)
      } else {
        setDownloadError(`Unexpected Error: ${err instanceof Error ? err.message : 'Failed to download results'}`)
      }
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <Card className="w-full max-w-4xl mx-auto bg-gradient-to-b from-card to-card/95 border-border/50 shadow-lg">
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h3 className="text-xl font-semibold text-foreground flex items-center gap-2">
                <Video className="h-5 w-5 text-primary" />
                Bulk Transcription Job
              </h3>
              <Badge 
                className={cn(
                  "text-xs",
                  statusInfo.bgColor,
                  statusInfo.color
                )}
              >
                {statusInfo.icon}
                <span className="ml-1">{statusInfo.label}</span>
              </Badge>
              {isRefreshing && (
                <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              Job ID: {job.job_id} • Created: {new Date(job.created_at).toLocaleString()}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {job.status === 'pending' && (
              <Button
                onClick={handleStartJob}
                disabled={isStarting}
                className="bg-green-500 hover:bg-green-600 text-white"
              >
                {isStarting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    Start Job
                  </>
                )}
              </Button>
            )}
            
            {['pending', 'processing'].includes(job.status) && (
              <Button
                variant="outline"
                onClick={handleCancelJob}
                disabled={isCancelling}
                className="border-destructive text-destructive hover:bg-destructive hover:text-destructive-foreground"
              >
                {isCancelling ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Cancelling...
                  </>
                ) : (
                  <>
                    <Square className="mr-2 h-4 w-4" />
                    Cancel
                  </>
                )}
              </Button>
            )}
            
            {progressStats.completed > 0 && (
              <Button
                onClick={handleDownload}
                disabled={isDownloading}
                className="bg-blue-500 hover:bg-blue-600 text-white"
              >
                {isDownloading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Downloading...
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    Download Completed
                  </>
                )}
              </Button>
            )}
          </div>
        </div>

        {/* Error Display */}
        {(error || downloadError) && (
          <motion.div 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-b from-destructive/10 to-destructive/5 border border-destructive/20 rounded-xl p-4"
          >
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <h4 className="font-medium text-destructive">
                  {error ? 'Job Error' : 'Download Error'}
                </h4>
                <p className="text-sm text-destructive/90 mt-1">
                  {error || downloadError}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setError(null)
                  setDownloadError(null)
                }}
              >
                ×
              </Button>
            </div>
          </motion.div>
        )}

        {/* Progress Overview */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              Overall Progress
            </span>
            <span className="text-sm text-muted-foreground">
              {progressStats.completed} of {progressStats.total} completed ({progressStats.progressPercent}%)
            </span>
          </div>
          
          <Progress 
            value={progressStats.progressPercent} 
            className="h-3"
          />
          
          {progressStats.hasFailures && (
            <div className="text-sm text-destructive">
              Success rate: {progressStats.successRate}% ({progressStats.failed} failed)
            </div>
          )}
        </div>

        {/* Status Breakdown */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center p-3 rounded-lg bg-green-50 border border-green-200">
            <div className="text-2xl font-bold text-green-600">{progressStats.completed}</div>
            <div className="text-xs text-green-600 font-medium">Completed</div>
          </div>
          
          {progressStats.processing > 0 && (
            <div className="text-center p-3 rounded-lg bg-blue-50 border border-blue-200">
              <div className="text-2xl font-bold text-blue-600">{progressStats.processing}</div>
              <div className="text-xs text-blue-600 font-medium">Processing</div>
            </div>
          )}
          
          {progressStats.pending > 0 && (
            <div className="text-center p-3 rounded-lg bg-yellow-50 border border-yellow-200">
              <div className="text-2xl font-bold text-yellow-600">{progressStats.pending}</div>
              <div className="text-xs text-yellow-600 font-medium">Pending</div>
            </div>
          )}
          
          {progressStats.retrying > 0 && (
            <div className="text-center p-3 rounded-lg bg-orange-50 border border-orange-200">
              <div className="text-2xl font-bold text-orange-600">{progressStats.retrying}</div>
              <div className="text-xs text-orange-600 font-medium">Retrying</div>
            </div>
          )}
          
          {progressStats.failed > 0 && (
            <div className="text-center p-3 rounded-lg bg-red-50 border border-red-200">
              <div className="text-2xl font-bold text-red-600">{progressStats.failed}</div>
              <div className="text-xs text-red-600 font-medium">Failed</div>
            </div>
          )}
        </div>

        {/* Job Details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-foreground">Job Configuration</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Source:</span>
                <span className="text-foreground font-medium">
                  <Button
                    variant="ghost"
                    size="sm"
                    asChild
                    className="h-auto p-0 text-sm font-medium text-primary hover:text-primary/80"
                  >
                    <a
                      href={job.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1"
                    >
                      <Eye className="h-3 w-3" />
                      View Source
                    </a>
                  </Button>
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Method:</span>
                <Badge variant="outline" className="text-xs">
                  {job.transcript_method}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Format:</span>
                <Badge variant="outline" className="text-xs">
                  {job.output_format.toUpperCase()}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">User Tier:</span>
                <Badge variant="secondary" className="text-xs">
                  {job.user_tier}
                </Badge>
              </div>
            </div>
          </div>
          
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-foreground">Timestamps</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created:</span>
                <span className="text-foreground">{new Date(job.created_at).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Last Updated:</span>
                <span className="text-foreground">{new Date(job.updated_at).toLocaleString()}</span>
              </div>
              {job.completed_at && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Completed:</span>
                  <span className="text-foreground">{new Date(job.completed_at).toLocaleString()}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Download Section */}
        {job.status === 'completed' && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-r from-green-500/10 to-green-600/10 border border-green-500/20 rounded-xl p-6"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h4 className="font-semibold text-foreground flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  Job Completed Successfully!
                </h4>
                <p className="text-sm text-muted-foreground mt-1">
                  {progressStats.completed} videos transcribed successfully
                  {progressStats.failed > 0 && ` (${progressStats.failed} failed)`}
                </p>
              </div>
              
              <Button
                onClick={handleDownload}
                disabled={isDownloading}
                className="bg-green-500 hover:bg-green-600 text-white shadow-lg"
              >
                {isDownloading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Downloading...
                  </>
                ) : (
                  <>
                    <Download className="mr-2 h-4 w-4" />
                    Download All Transcripts
                  </>
                )}
              </Button>
            </div>
          </motion.div>
        )}
      </div>
    </Card>
  )
}

export type { BulkProgressDisplayProps }