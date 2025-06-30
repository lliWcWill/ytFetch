'use client'

import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, ListVideo, Zap, Play, Users } from 'lucide-react'
import { BulkDownloadForm } from '@/components/BulkDownloadForm'
import { VideoSelector } from '@/components/VideoSelector'
import { BulkProgressDisplay } from '@/components/BulkProgressDisplay'
import { useAuth } from '@/providers/AuthProvider'
import { 
  createBulkJob,
  type BulkAnalyzeResponse,
  type BulkJobResponse,
  type TranscriptMethod,
  type OutputFormat
} from '@/services/bulkApi'
import { ApiValidationError, ApiNetworkError, ApiHttpError, TierLimitError } from '@/services/api'
import { UsageDisplay } from '@/components/UsageDisplay'
// import { UpgradePrompt } from '@/components/UpgradePrompt' // Removed - using token-based system
import { useSupabaseRealtime } from '@/hooks/useSupabaseRealtime'
import { cn } from '@/lib/utils'
import { checkGuestLimit, incrementGuestUsage, getRemainingGuestUsage, GUEST_LIMITS } from '@/utils/guestLimits'

type PageState = 'form' | 'selection' | 'job-created' | 'processing'

export default function BulkPage() {
  const { user, loading, profile } = useAuth()
  const router = useRouter()
  const [pageState, setPageState] = useState<PageState>('form')
  const [analysis, setAnalysis] = useState<BulkAnalyzeResponse | null>(null)
  const [selectedVideos, setSelectedVideos] = useState<string[]>([])
  const [currentJob, setCurrentJob] = useState<BulkJobResponse | null>(null)
  const [isCreatingJob, setIsCreatingJob] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // const [showUpgradePrompt, setShowUpgradePrompt] = useState(false) // Removed - using token-based system
  // const [upgradeReason, setUpgradeReason] = useState<'videos' | 'jobs' | 'concurrent' | 'duration'>('videos')
  const [formParams, setFormParams] = useState<{
    url: string
    transcriptMethod: TranscriptMethod
    outputFormat: OutputFormat
    maxVideos?: number
  } | null>(null)

  // Handle analysis completion
  const handleAnalyze = useCallback((analysisResult: BulkAnalyzeResponse, params?: {
    url: string
    transcriptMethod: TranscriptMethod
    outputFormat: OutputFormat
    maxVideos?: number
  }) => {
    setAnalysis(analysisResult)
    setSelectedVideos(analysisResult.videos.map(v => v.video_id)) // Select all by default
    setPageState('selection')
    setError(null)
    // Store form params if provided
    if (params) {
      setFormParams(params)
    }
  }, [])

  // Handle real-time video task updates
  const handleTaskUpdate = useCallback((updatedTask: any) => {
    if (!analysis) return

    // Update the videos array with the new task status
    setAnalysis(currentAnalysis => {
      if (!currentAnalysis) return currentAnalysis

      return {
        ...currentAnalysis,
        videos: currentAnalysis.videos.map(video => 
          video.video_id === updatedTask.video_id
            ? {
                ...video,
                status: updatedTask.status,
                progress: updatedTask.progress || 0,
                error_message: updatedTask.error_message || null
              }
            : video
        )
      }
    })
  }, [analysis])

  // Set up real-time subscription when we have a job
  useSupabaseRealtime(
    currentJob ? `video_tasks:job_id=eq.${currentJob.job_id}` : '',
    handleTaskUpdate
  )

  // Handle job creation
  const handleCreateJob = useCallback(async (params: {
    url: string
    transcriptMethod: TranscriptMethod
    outputFormat: OutputFormat
    maxVideos?: number
  }) => {
    console.log('handleCreateJob called with params:', params, 'pageState:', pageState)
    
    if (pageState === 'form') {
      // Store params and show message to analyze first
      setFormParams(params)
      setError('Please click "Analyze Source" first to scan the playlist/channel and select videos for transcription.')
      console.log('User tried to create job without analyzing first')
      return
    }

    if (!analysis || selectedVideos.length === 0) {
      setError('Please select at least one video to transcribe.')
      return
    }

    // Token-based system - no tier limits, users pay per use
    // Guest users can use up to 60 videos in bulk
    if (!user) {
      const limitCheck = checkGuestLimit('bulkJobs')
      if (!limitCheck.allowed) {
        setError(`You've reached your free daily limit (${limitCheck.limit} bulk job). Sign in to continue!`)
        return
      }
    }

    setIsCreatingJob(true)
    setError(null)

    try {
      const job = await createBulkJob({
        url: params.url,
        transcript_method: params.transcriptMethod,
        output_format: params.outputFormat,
        max_videos: selectedVideos.length
      })

      setCurrentJob(job)
      setPageState('job-created')
      
      // Increment guest usage if not authenticated
      if (!user) {
        incrementGuestUsage('bulkJobs')
      }
    } catch (err) {
      if (err instanceof TierLimitError) {
        // Token-based system - just show the error
        setError(`Limit reached: ${err.message}`)
      } else if (err instanceof ApiValidationError) {
        setError(`Validation Error: ${err.message}`)
      } else if (err instanceof ApiNetworkError) {
        setError(`Network Error: ${err.message}. Please check your connection and try again.`)
      } else if (err instanceof ApiHttpError) {
        // Check if it's a guest limit error
        if (err.status === 401 && err.response?.error_code === 'guest_limit_exceeded') {
          setError(`You've reached your free daily bulk job limit. Sign in to continue!`)
        } else {
          setError(`Server Error: ${err.message} (Status: ${err.status})`)
        }
      } else {
        setError(`Unexpected Error: ${err instanceof Error ? err.message : 'Failed to create bulk job'}`)
      }
    } finally {
      setIsCreatingJob(false)
    }
  }, [pageState, analysis, selectedVideos])

  // Handle job updates
  const handleJobUpdate = useCallback((updatedJob: BulkJobResponse) => {
    setCurrentJob(updatedJob)
    if (updatedJob.status === 'processing' && pageState !== 'processing') {
      setPageState('processing')
    }
  }, [pageState])

  // Handle job cancellation
  const handleJobCancel = useCallback(() => {
    // Could navigate back or show completion message
    setPageState('job-created')
  }, [])

  // Reset to start over
  const handleStartOver = useCallback(() => {
    setPageState('form')
    setAnalysis(null)
    setSelectedVideos([])
    setCurrentJob(null)
    setFormParams(null)
    setError(null)
  }, [])

  // Go back to form
  const handleBackToForm = useCallback(() => {
    setPageState('form')
    setAnalysis(null)
    setSelectedVideos([])
    setError(null)
  }, [])

  // App is now open access - allow everyone to try bulk processing

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Subtle animated background gradient */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-0 -left-4 w-72 h-72 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob"></div>
        <div className="absolute top-0 -right-4 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-20 w-72 h-72 bg-green-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob animation-delay-4000"></div>
      </div>

      {/* Header */}
      <div className="container mx-auto px-4 pt-8 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              asChild
              className="text-muted-foreground hover:text-foreground"
            >
              <Link href="/" className="flex items-center gap-2">
                <ArrowLeft className="h-4 w-4" />
                Back to Single Transcription
              </Link>
            </Button>
          </div>

          {pageState !== 'form' && (
            <Button
              variant="outline"
              onClick={handleStartOver}
              className="text-muted-foreground hover:text-foreground"
            >
              Start Over
            </Button>
          )}
        </div>
      </div>

      {/* Hero Section */}
      <div className="container mx-auto px-4 pb-8">
        <div className="text-center max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <div className="flex items-center justify-center gap-3 mb-4">
              <h1 className="text-5xl font-bold tracking-tight">
                <span className="text-foreground">Bulk</span>
                <span className="text-primary"> Transcription</span>
              </h1>
              {profile?.tier && (
                <Badge 
                  variant={profile.tier.name === 'free' ? 'secondary' : 'default'}
                  className={cn(
                    "text-sm",
                    profile.tier.name === 'pro' && 'bg-blue-500 hover:bg-blue-600',
                    profile.tier.name === 'enterprise' && 'bg-purple-500 hover:bg-purple-600'
                  )}
                >
                  {profile.tier.display_name}
                </Badge>
              )}
            </div>
            <p className="text-xl text-muted-foreground leading-relaxed">
              Transcribe entire YouTube playlists and channels with{' '}
              <span className="text-primary font-semibold">lightning speed</span>.
              Process dozens of videos in a single job.
            </p>
            
            {/* Quick Instructions */}
            <div className="mt-6 p-4 bg-muted/30 rounded-lg max-w-2xl mx-auto">
              <p className="text-sm text-muted-foreground">
                <strong>How it works:</strong> 
                <span className="text-primary font-medium">Step 1:</span> Enter a YouTube playlist or channel URL → 
                <span className="text-primary font-medium">Step 2:</span> Click "Analyze Source" to scan available videos → 
                <span className="text-primary font-medium">Step 3:</span> Select up to {GUEST_LIMITS.maxBulkVideos} videos (free tier) → 
                <span className="text-primary font-medium">Step 4:</span> Click "Create Bulk Job" to start transcription
              </p>
            </div>
            <div className="flex items-center justify-center gap-6 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                <span>Batch Processing</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span>ZIP Downloads</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                <span>Progress Tracking</span>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 pb-12">
        <div className="max-w-6xl mx-auto space-y-8">

          {/* Guest Usage Display */}
          {!user && pageState === 'form' && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-950/20 dark:to-purple-950/20 rounded-lg p-4 text-center"
            >
              <p className="text-sm text-muted-foreground">
                Free tier: {getRemainingGuestUsage().bulkJobs} bulk job remaining today (max {GUEST_LIMITS.maxBulkVideos} videos)
                {' • '}
                <button 
                  onClick={() => {
                    sessionStorage.setItem('auth-redirect-to', '/bulk')
                    router.push('/login')
                  }}
                  className="text-primary hover:underline font-medium"
                >
                  Sign in for unlimited access
                </button>
              </p>
            </motion.div>
          )}
          
          {/* Usage Display for authenticated users */}
          {user && profile && pageState === 'form' && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="max-w-lg mx-auto"
            >
              <UsageDisplay 
                onUpgradeClick={() => {
                  setUpgradeReason('jobs')
                  setShowUpgradePrompt(true)
                }}
              />
            </motion.div>
          )}

          {/* Progress Indicator */}
          <div className="flex items-center justify-center gap-4">
            <div className={`flex items-center gap-2 ${pageState === 'form' ? 'text-primary' : 'text-muted-foreground'}`}>
              <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm font-semibold ${
                pageState === 'form' ? 'border-primary bg-primary text-primary-foreground' : 
                ['selection', 'job-created', 'processing'].includes(pageState) ? 'border-green-500 bg-green-500 text-white' : 'border-muted'
              }`}>
                1
              </div>
              <span className="font-medium">Setup</span>
            </div>
            <div className={`w-12 h-0.5 ${['selection', 'job-created', 'processing'].includes(pageState) ? 'bg-green-500' : 'bg-border'}`} />
            <div className={`flex items-center gap-2 ${pageState === 'selection' ? 'text-primary' : 'text-muted-foreground'}`}>
              <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm font-semibold ${
                pageState === 'selection' ? 'border-primary bg-primary text-primary-foreground' : 
                ['job-created', 'processing'].includes(pageState) ? 'border-green-500 bg-green-500 text-white' : 'border-muted'
              }`}>
                2
              </div>
              <span className="font-medium">Select</span>
            </div>
            <div className={`w-12 h-0.5 ${['job-created', 'processing'].includes(pageState) ? 'bg-green-500' : 'bg-border'}`} />
            <div className={`flex items-center gap-2 ${['job-created', 'processing'].includes(pageState) ? 'text-primary' : 'text-muted-foreground'}`}>
              <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm font-semibold ${
                ['job-created', 'processing'].includes(pageState) ? 'border-primary bg-primary text-primary-foreground' : 'border-muted'
              }`}>
                3
              </div>
              <span className="font-medium">Process</span>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="bg-gradient-to-b from-destructive/10 to-destructive/5 border border-destructive/20 rounded-xl p-6 shadow-lg"
            >
              <div className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-destructive flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-destructive-foreground text-xs font-bold">!</span>
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-destructive mb-1">Error</h3>
                  <p className="text-sm text-destructive/90 whitespace-pre-line">{error}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setError(null)}
                  className="text-destructive hover:text-destructive/80"
                >
                  ×
                </Button>
              </div>
            </motion.div>
          )}

          {/* Page Content */}
          <AnimatePresence mode="wait">
            {/* Step 1: Form */}
            {pageState === 'form' && (
              <motion.div
                key="form"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
              >
                <BulkDownloadForm
                  onAnalyze={handleAnalyze}
                  onCreateJob={handleCreateJob}
                  disabled={isCreatingJob}
                  showAnalysis={false}
                />
              </motion.div>
            )}

            {/* Step 2: Video Selection */}
            {pageState === 'selection' && analysis && (
              <motion.div
                key="selection"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                {/* Analysis Summary */}
                <div className="bg-gradient-to-r from-primary/5 to-primary/10 border border-primary/20 rounded-xl p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
                        {analysis.source_type === 'playlist' ? (
                          <Play className="h-5 w-5 text-primary" />
                        ) : (
                          <Users className="h-5 w-5 text-primary" />
                        )}
                        {analysis.title}
                      </h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        {analysis.source_type === 'playlist' ? 'Playlist' : 'Channel'} • 
                        {analysis.total_videos} videos • 
                        ~{analysis.estimated_duration_hours.toFixed(1)} hours total
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">
                        {analysis.analyzed_videos} analyzed
                      </Badge>
                      {!analysis.can_process_all && (
                        <Badge variant="outline" className="border-orange-500 text-orange-600">
                          Tier Limited
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                {/* Video Selector */}
                <VideoSelector
                  analysis={analysis}
                  selectedVideos={selectedVideos}
                  onSelectionChange={setSelectedVideos}
                  disabled={isCreatingJob}
                />

                {/* Action Buttons */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                  <Button
                    variant="outline"
                    onClick={handleBackToForm}
                    disabled={isCreatingJob}
                  >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back to Setup
                  </Button>

                  <Button
                    onClick={() => formParams && handleCreateJob(formParams)}
                    disabled={isCreatingJob || selectedVideos.length === 0}
                    className="bg-gradient-to-r from-green-500 to-green-600 text-white hover:from-green-600 hover:to-green-700 shadow-lg px-8"
                  >
                    {isCreatingJob ? (
                      <>
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                          className="mr-2"
                        >
                          <Zap className="h-4 w-4" />
                        </motion.div>
                        Creating Job...
                      </>
                    ) : (
                      <>
                        <ListVideo className="mr-2 h-4 w-4" />
                        Create Bulk Job ({selectedVideos.length} videos)
                      </>
                    )}
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Step 3: Job Processing */}
            {(pageState === 'job-created' || pageState === 'processing') && currentJob && (
              <motion.div
                key="processing"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
              >
                <BulkProgressDisplay
                  job={currentJob}
                  onJobUpdate={handleJobUpdate}
                  onCancel={handleJobCancel}
                  autoRefresh={true}
                />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Feature Highlights (shown on form page) */}
          <AnimatePresence>
            {pageState === 'form' && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.5, ease: "easeOut", delay: 0.2 }}
                className="bg-gradient-to-b from-card/30 to-card/10 rounded-2xl p-10 text-center backdrop-blur-sm"
              >
                <div className="max-w-4xl mx-auto">
                  <motion.h3 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    className="text-2xl font-semibold mb-6 text-foreground"
                  >
                    Why Choose Bulk Transcription?
                  </motion.h3>
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="grid grid-cols-1 md:grid-cols-3 gap-6"
                  >
                    <div className="bg-gradient-to-b from-muted/40 to-muted/20 rounded-xl p-6 backdrop-blur-sm">
                      <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <ListVideo className="h-6 w-6 text-blue-500" />
                      </div>
                      <div className="font-medium text-foreground mb-2">Process Entire Playlists</div>
                      <div className="text-sm text-muted-foreground">Transcribe all videos in a playlist with a single click. Perfect for educational content and series.</div>
                    </div>
                    <div className="bg-gradient-to-b from-muted/40 to-muted/20 rounded-xl p-6 backdrop-blur-sm">
                      <div className="w-12 h-12 bg-green-500/10 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <Users className="h-6 w-6 text-green-500" />
                      </div>
                      <div className="font-medium text-foreground mb-2">Archive Channel Content</div>
                      <div className="text-sm text-muted-foreground">Download transcripts from your favorite creators. Great for research and content analysis.</div>
                    </div>
                    <div className="bg-gradient-to-b from-muted/40 to-muted/20 rounded-xl p-6 backdrop-blur-sm">
                      <div className="w-12 h-12 bg-purple-500/10 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <Zap className="h-6 w-6 text-purple-500" />
                      </div>
                      <div className="font-medium text-foreground mb-2">Lightning Fast Processing</div>
                      <div className="text-sm text-muted-foreground">Powered by Groq AI for ultra-fast transcription. Process hours of content in minutes.</div>
                    </div>
                  </motion.div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-border bg-card/30">
        <div className="container mx-auto px-4 py-6">
          <div className="text-center text-sm text-muted-foreground">
            <p>
              Bulk transcription powered by{' '}
              <span className="text-primary font-semibold">ytFetch</span>
              {' '}• Perfect for content creators, researchers, and educators
            </p>
          </div>
        </div>
      </div>

      {/* Token-based system - no upgrade prompts needed */}
    </div>
  )
}