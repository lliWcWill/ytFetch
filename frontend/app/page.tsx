'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
// import { v4 as uuidv4 } from 'uuid' // Will be used in Phase 4
import { URLInputForm } from '@/components/URLInputForm'
import { ProgressDisplay } from '@/components/ProgressDisplay' 
import { TranscriptViewer } from '@/components/TranscriptViewer'
import { useWebSocket, WebSocketMessage } from '@/hooks/useWebSocket'
import { Button } from '@/components/ui/button'
import { Zap } from 'lucide-react'
import { useAuth } from '@/providers/AuthProvider'
import { 
  startTranscriptionJob, 
  generateClientId,
  ApiValidationError,
  ApiNetworkError,
  ApiHttpError
} from '@/services/api'

export default function HomePage() {
  const { user, loading } = useAuth()
  
  // State management
  const [jobId, setJobId] = useState<string | null>(null)
  const [clientId, setClientId] = useState<string | null>(null)
  const [socketUrl, setSocketUrl] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState<boolean>(false)
  const [processingMethod, setProcessingMethod] = useState<'unofficial' | 'groq' | null>(null)
  const [lastUrl, setLastUrl] = useState<string>('')
  const [progress, setProgress] = useState<{
    stage: string
    progress: number
    message: string
  }>({
    stage: 'waiting',
    progress: 0,
    message: 'Ready to start transcription'
  })
  const [finalTranscript, setFinalTranscript] = useState<string>('')
  const [allFormats, setAllFormats] = useState<Record<string, string> | null>(null)
  const [transcriptFormat, setTranscriptFormat] = useState<'txt' | 'srt' | 'vtt' | 'json'>('txt')
  const [error, setError] = useState<string | null>(null)
  const [videoTitle, setVideoTitle] = useState<string>('')

  // Handle WebSocket message
  const handleSocketMessage = useCallback((message: any) => {
    console.log('WebSocket message received:', message)
    
    // Update progress state
    setProgress({
      stage: message.status || message.stage || 'processing',
      progress: message.progress || 0,
      message: message.message || ''
    })
    
    // Handle completion
    if (message.type === 'complete' || message.status === 'completed') {
      console.log('Completion message received:', message)
      console.log('Message data:', message.data)
      
      if (message.data && message.data.transcript) {
        console.log('Transcript found in message:', message.data.transcript.substring(0, 200) + '...')
        setFinalTranscript(message.data.transcript)
        
        // Store all formats if available
        if (message.data.all_formats) {
          console.log('All formats received:', Object.keys(message.data.all_formats))
          setAllFormats(message.data.all_formats)
        }
        
        // Also store the format and metadata
        if (message.data.format) {
          setTranscriptFormat(message.data.format)
        }
        
        // Store video title from metadata
        if (message.data.video_metadata && message.data.video_metadata.title) {
          setVideoTitle(message.data.video_metadata.title)
          console.log('Video title received:', message.data.video_metadata.title)
        }
        
        setIsProcessing(false)
        // Keep the connection open a bit longer before cleanup
        setTimeout(() => {
          setJobId(null)
          setClientId(null)
          setProcessingMethod(null)
        }, 1000)
      } else {
        console.error('No transcript in completion message!')
      }
    }
    
    // Handle errors
    if (message.type === 'error' || message.status === 'error') {
      const errorMessage = message.message || 'Transcription failed'
      setError(errorMessage)
      setIsProcessing(false)
      
      // If unofficial transcript failed, suggest Groq
      if (processingMethod === 'unofficial' && 
          (message.error_code === 'no_transcript_available' || 
           message.error_code === 'transcript_fetch_failed')) {
        setError(errorMessage + '\n\nWould you like to try Groq AI transcription instead? It downloads the audio and transcribes it with AI.')
      }
      
      // Clean up on error
      setTimeout(() => {
        setJobId(null)
        setClientId(null)
        setProcessingMethod(null)
      }, 1000)
      setProgress({
        stage: 'error',
        progress: 0,
        message: errorMessage
      })
    }
  }, [])

  // WebSocket connection
  useWebSocket(socketUrl, handleSocketMessage)

  // Handle format change
  const handleFormatChange = (newFormat: 'txt' | 'srt' | 'vtt' | 'json') => {
    setTranscriptFormat(newFormat)
    
    // If we have all formats stored, update the displayed transcript
    if (allFormats && allFormats[newFormat]) {
      console.log(`Switching to ${newFormat} format`)
      setFinalTranscript(allFormats[newFormat])
    }
  }

  // Generate WebSocket URL based on jobId and processing state
  useEffect(() => {
    if (!jobId || !isProcessing) {
      setSocketUrl(null)
      return
    }
    
    // Small delay to ensure backend has started processing
    const timer = setTimeout(() => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const wsProtocol = apiUrl.startsWith('https://') ? 'wss://' : 'ws://'
      const wsBase = apiUrl.replace(/^https?:\/\//, '')
      const wsUrl = `${wsProtocol}${wsBase}/ws/${jobId}`
      console.log('Setting WebSocket URL for job:', jobId)
      setSocketUrl(wsUrl)
    }, 100)
    
    return () => {
      clearTimeout(timer)
    }
  }, [jobId, isProcessing])

  // Handle form submission
  const handleSubmit = async (submittedUrl: string, selectedFormat: 'txt' | 'srt' | 'vtt' | 'json', method: 'unofficial' | 'groq') => {
    try {
      setError(null)
      setTranscriptFormat(selectedFormat)
      setIsProcessing(true)
      setProcessingMethod(method)
      setLastUrl(submittedUrl)
      const methodName = method === 'unofficial' ? 'Unofficial Transcript' : 'Groq AI Transcription'
      setProgress({
        stage: 'starting',
        progress: 10,
        message: `Initializing ${methodName} job...`
      })

      // Generate client ID and start transcription job
      const newClientId = generateClientId()
      setClientId(newClientId)
      
      setProgress({
        stage: 'connecting',
        progress: 25,
        message: `Connecting to ${methodName} service...`
      })

      const response = await startTranscriptionJob(submittedUrl, newClientId, {
        output_format: selectedFormat,
        method: method
      })

      setJobId(response.job_id)
      
      // Initial progress - WebSocket will take over from here
      setProgress({
        stage: 'connecting',
        progress: 25,
        message: `Connecting to ${methodName} service...`
      })

    } catch (err) {
      setIsProcessing(false)
      setClientId(null)
      setJobId(null)
      setSocketUrl(null)
      setProcessingMethod(null)
      
      if (err instanceof ApiValidationError) {
        setError(`Validation Error: ${err.message}`)
      } else if (err instanceof ApiNetworkError) {
        setError(`Network Error: ${err.message}. Please check your connection and try again.`)
      } else if (err instanceof ApiHttpError) {
        setError(`Server Error: ${err.message} (Status: ${err.status})`)
      } else {
        setError(`Unexpected Error: ${err instanceof Error ? err.message : 'Something went wrong'}`)
      }
      
      setProgress({
        stage: 'error',
        progress: 0,
        message: 'Transcription failed'
      })
    }
  }

  // Reset function for starting over
  const handleReset = () => {
    setJobId(null)
    setClientId(null)
    setSocketUrl(null)
    setIsProcessing(false)
    setProcessingMethod(null)
    setProgress({
      stage: 'waiting',
      progress: 0,
      message: 'Ready to start transcription'
    })
    setFinalTranscript('')
    setAllFormats(null)
    setTranscriptFormat('txt')
    setError(null)
  }

  // Show loading spinner while checking auth
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500"></div>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <div className="text-center space-y-6 max-w-md">
          <div className="mx-auto w-16 h-16 bg-gradient-to-r from-orange-500 to-red-500 rounded-xl flex items-center justify-center">
            <span className="text-2xl font-bold text-white">yt</span>
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold">Welcome to ytFetch</h1>
            <p className="text-muted-foreground">Please sign in to access YouTube transcription tools</p>
          </div>
          <Button 
            onClick={() => {
              // Store current path for redirect after login
              sessionStorage.setItem('auth-redirect-to', '/')
              window.location.href = '/login'
            }}
            size="lg" 
            className="w-full"
          >
            Sign In to Continue
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Subtle animated background gradient */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-0 -left-4 w-72 h-72 bg-orange-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob"></div>
        <div className="absolute top-0 -right-4 w-72 h-72 bg-green-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-20 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob animation-delay-4000"></div>
      </div>
      
      {/* Hero Section */}
      <div className="container mx-auto px-4 pt-12 pb-8">
        <div className="text-center max-w-4xl mx-auto">
          <h1 className="text-6xl font-bold tracking-tight mb-6">
            <span className="text-foreground">yt</span>
            <span className="text-primary">Fetch</span>
          </h1>
          <p className="text-xl text-muted-foreground mb-8 leading-relaxed">
            Lightning-fast YouTube video transcription powered by{' '}
            <span className="text-primary font-semibold">Groq&apos;s AI models</span>.
            Convert any YouTube video to text, SRT, VTT, or JSON format in seconds.
          </p>
          <div className="flex items-center justify-center gap-6 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-primary rounded-full"></div>
              <span>Powered by Groq</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span>Multiple Formats</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
              <span>Real-time Progress</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 pb-12">
        <div className="max-w-4xl mx-auto space-y-8">
          
          {/* URL Input Form */}
          <URLInputForm 
            onSubmit={handleSubmit}
            disabled={isProcessing}
            processingMethod={processingMethod}
            onReset={handleReset}
            showReset={jobId !== null || finalTranscript !== ''}
          />

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
                  <h3 className="font-semibold text-destructive mb-1">Transcription Failed</h3>
                  <p className="text-sm text-destructive/90 whitespace-pre-line">{error}</p>
                  {/* Show Try Groq button if unofficial failed */}
                  {error.includes('Would you like to try Groq AI') && (
                    <div className="mt-3">
                      <Button
                        onClick={() => {
                          setError(null)
                          if (lastUrl) {
                            handleSubmit(lastUrl, transcriptFormat, 'groq')
                          }
                        }}
                        className="bg-orange-500 hover:bg-orange-600 text-white"
                        size="sm"
                      >
                        <Zap className="mr-2 h-4 w-4" />
                        Try Groq AI Transcription
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {/* Progress Display */}
          <AnimatePresence mode="wait">
            {isProcessing && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              >
                <ProgressDisplay
                  currentStage={progress.stage}
                  progress={progress.progress}
                  message={progress.message}
                  jobId={jobId}
                  showDetails={true}
                />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Transcript Viewer */}
          <AnimatePresence mode="wait">
            {finalTranscript && !isProcessing && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              >
                <TranscriptViewer
                  transcript={finalTranscript}
                  format={transcriptFormat}
                  onFormatChange={handleFormatChange}
                  isVisible={true}
                  videoTitle={videoTitle}
                />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Getting Started Section (shown when no activity) */}
          <AnimatePresence>
            {!isProcessing && !finalTranscript && !error && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                className="bg-gradient-to-b from-card/30 to-card/10 rounded-2xl p-10 text-center backdrop-blur-sm"
              >
                <div className="max-w-md mx-auto">
                  <motion.h3 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="text-xl font-semibold mb-4 text-foreground"
                  >
                    Ready to transcribe?
                  </motion.h3>
                  <motion.p 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    className="text-muted-foreground mb-8 leading-relaxed"
                  >
                    Paste any YouTube URL above and watch the magic happen. 
                    Lightning-fast transcription powered by Groq AI.
                  </motion.p>
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="grid grid-cols-2 gap-4 text-sm"
                  >
                    <div className="bg-gradient-to-b from-muted/40 to-muted/20 rounded-xl p-4 backdrop-blur-sm">
                      <div className="font-medium text-foreground mb-1">Supported Formats</div>
                      <div className="text-muted-foreground">TXT • SRT • VTT • JSON</div>
                    </div>
                    <div className="bg-gradient-to-b from-muted/40 to-muted/20 rounded-xl p-4 backdrop-blur-sm">
                      <div className="font-medium text-foreground mb-1">Speed</div>
                      <div className="text-muted-foreground">Transcribes in seconds</div>
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
              Powered by{' '}
              <span className="text-primary font-semibold">Groq&apos;s lightning-fast AI models</span>
              {' '}• Built for developers and content creators
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}