'use client'

import React from 'react'
import { useBulkJobProgress } from '@/hooks/useBulkJobProgress'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertCircle, CheckCircle, Clock, Play, Pause, RefreshCw } from 'lucide-react'

interface RealtimeProgressExampleProps {
  jobId: string
  onJobComplete?: () => void
}

export function RealtimeProgressExample({ jobId, onJobComplete }: RealtimeProgressExampleProps) {
  const {
    state,
    stats,
    refreshAll,
    cancelJob
  } = useBulkJobProgress({
    jobId,
    enableRealtime: true,
    enablePolling: true,
    pollingInterval: 5000,
    onJobComplete: (job) => {
      console.log('Job completed:', job)
      onJobComplete?.()
    },
    onJobError: (job, error) => {
      console.error('Job error:', error)
    },
    onProgressUpdate: (progressStats) => {
      console.log('Progress update:', progressStats)
    }
  })

  const { job, videoTasks, loading, error, isRealTimeConnected } = state
  const {
    totalTasks,
    completedTasks,
    failedTasks,
    pendingTasks,
    processingTasks,
    overallProgress,
    estimatedTimeRemaining,
    tasksPerMinute
  } = stats

  const formatTime = (minutes: number | undefined) => {
    if (!minutes || !isFinite(minutes)) return 'Unknown'
    const hours = Math.floor(minutes / 60)
    const mins = Math.floor(minutes % 60)
    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'processing':
        return <Play className="h-4 w-4 text-blue-500" />
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />
      case 'cancelled':
        return <Pause className="h-4 w-4 text-gray-500" />
      default:
        return <Clock className="h-4 w-4 text-gray-500" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200'
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'processing':
        return 'bg-blue-100 text-blue-800 border-blue-200'
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'cancelled':
        return 'bg-gray-100 text-gray-800 border-gray-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  if (loading && !job) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-center">
            <RefreshCw className="h-6 w-6 animate-spin mr-2" />
            Loading job details...
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-red-600 flex items-center">
            <AlertCircle className="h-5 w-5 mr-2" />
            Error: {error.message}
          </div>
          <Button 
            variant="outline" 
            onClick={refreshAll} 
            className="mt-4"
          >
            Retry
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (!job) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-gray-600">Job not found</div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Job Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                {getStatusIcon(job.status)}
                Bulk Download Job
              </CardTitle>
              <CardDescription>Job ID: {job.id}</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className={getStatusColor(job.status)}>
                {job.status.toUpperCase()}
              </Badge>
              {isRealTimeConnected ? (
                <Badge variant="outline" className="bg-green-100 text-green-800 border-green-200">
                  Real-time Connected
                </Badge>
              ) : (
                <Badge variant="outline" className="bg-yellow-100 text-yellow-800 border-yellow-200">
                  Polling Mode
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Progress Bar */}
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span>Overall Progress</span>
                <span>{Math.round(overallProgress)}%</span>
              </div>
              <Progress value={overallProgress} className="h-2" />
            </div>

            {/* Statistics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-2xl font-bold">{totalTasks}</div>
                <div className="text-sm text-gray-600">Total</div>
              </div>
              <div className="text-center p-3 bg-green-50 rounded-lg">
                <div className="text-2xl font-bold text-green-600">{completedTasks}</div>
                <div className="text-sm text-gray-600">Completed</div>
              </div>
              <div className="text-center p-3 bg-red-50 rounded-lg">
                <div className="text-2xl font-bold text-red-600">{failedTasks}</div>
                <div className="text-sm text-gray-600">Failed</div>
              </div>
              <div className="text-center p-3 bg-blue-50 rounded-lg">
                <div className="text-2xl font-bold text-blue-600">{processingTasks}</div>
                <div className="text-sm text-gray-600">Processing</div>
              </div>
            </div>
            
            {pendingTasks > 0 && (
              <div className="text-center p-3 bg-yellow-50 rounded-lg">
                <div className="text-2xl font-bold text-yellow-600">{pendingTasks}</div>
                <div className="text-sm text-gray-600">Pending</div>
              </div>
            )}

            {/* Performance Metrics */}
            {job.status === 'processing' && (
              <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                <div>
                  <div className="text-sm text-gray-600">Processing Rate</div>
                  <div className="font-semibold">
                    {tasksPerMinute ? `${tasksPerMinute.toFixed(1)} tasks/min` : 'Calculating...'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Time Remaining</div>
                  <div className="font-semibold">
                    {formatTime(estimatedTimeRemaining)}
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 pt-4 border-t">
              <Button 
                variant="outline" 
                onClick={refreshAll}
                disabled={loading}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              {job.status === 'processing' && (
                <Button 
                  variant="destructive" 
                  onClick={cancelJob}
                >
                  Cancel Job
                </Button>
              )}
            </div>

            {/* Error Message */}
            {job.error_message && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <div className="text-sm text-red-800">
                  <strong>Error:</strong> {job.error_message}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Video Tasks List */}
      {videoTasks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Video Tasks ({videoTasks.length})</CardTitle>
            <CardDescription>Individual video processing status</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {videoTasks.map((task) => (
                <div 
                  key={task.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">
                      {task.title || task.url}
                    </div>
                    {task.title && (
                      <div className="text-xs text-gray-500 truncate">
                        {task.url}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    {task.progress_percentage > 0 && task.status === 'processing' && (
                      <div className="text-xs text-gray-600">
                        {task.progress_percentage}%
                      </div>
                    )}
                    <Badge 
                      variant="outline" 
                      className={getStatusColor(task.status)}
                    >
                      {task.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}