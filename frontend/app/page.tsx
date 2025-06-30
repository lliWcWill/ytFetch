'use client'

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
// import { v4 as uuidv4 } from 'uuid' // Will be used in Phase 4
import { URLInputForm } from '@/components/URLInputForm'
import { ProgressDisplay } from '@/components/ProgressDisplay' 
import { TranscriptViewer } from '@/components/TranscriptViewer'
import { useWebSocket, WebSocketMessage } from '@/hooks/useWebSocket'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
  Zap, 
  Coins, 
  ArrowRight, 
  Play, 
  FileText, 
  Download,
  CheckCircle,
  Users,
  Sparkles
} from 'lucide-react'
import { useAuth } from '@/providers/AuthProvider'
import { useRouter } from 'next/navigation'
import { 
  startTranscriptionJob, 
  generateClientId,
  ApiValidationError,
  ApiNetworkError,
  ApiHttpError
} from '@/services/api'
import { GuestUsageDisplay } from '@/components/GuestUsageDisplay'
import { getUsage, type GuestUsageResponse } from '@/services/guestService'
import { FAQ } from '@/components/FAQ'
import { TokenPromoBanner } from '@/components/TokenPromoBanner'
import { tokenService } from '@/services/tokenService'
import { UserTokenBalance } from '@/types/tokens'
import { cn } from '@/lib/utils'

export default function HomePage() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [tokenBalance, setTokenBalance] = useState<UserTokenBalance | null>(null)
  const [activeSection, setActiveSection] = useState<string>('')
  const [guestUsage, setGuestUsage] = useState<GuestUsageResponse | null>(null)
  const [guestUsageLoading, setGuestUsageLoading] = useState(true)
  
  // Handle redirect after auth and load token balance / guest usage
  useEffect(() => {
    if (user && typeof window !== 'undefined') {
      const redirectTo = sessionStorage.getItem('auth-redirect-to')
      if (redirectTo) {
        sessionStorage.removeItem('auth-redirect-to')
        router.push(redirectTo)
      }
      
      // Load token balance
      tokenService.getTokenBalance()
        .then(setTokenBalance)
        .catch(err => {
          // Don't log error for unauthenticated users
          if (err.message !== 'Authentication required') {
            console.error('Failed to load token balance:', err)
          }
        })
    }
    
    // Load usage (guest or authenticated)
    setGuestUsageLoading(true)
    getUsage()
      .then(usage => {
        setGuestUsage(usage)
        setGuestUsageLoading(false)
      })
      .catch(err => {
        console.error('Failed to load usage:', err)
        setGuestUsageLoading(false)
      })
  }, [user, router])
  
  // Track active section for navigation highlighting
  useEffect(() => {
    const handleScroll = () => {
      const sections = ['how-it-works', 'features', 'pricing-section', 'faq-section']
      const scrollPosition = window.scrollY + 100
      
      for (const section of sections) {
        const element = document.getElementById(section)
        if (element) {
          const { offsetTop, offsetHeight } = element
          if (scrollPosition >= offsetTop && scrollPosition < offsetTop + offsetHeight) {
            setActiveSection(section)
            break
          }
        }
      }
    }
    
    window.addEventListener('scroll', handleScroll)
    handleScroll()
    
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])
  
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
  const [audioGatheringMessageIndex, setAudioGatheringMessageIndex] = useState<number>(0)

  // Audio gathering messages for rotation
  const audioGatheringMessages = useMemo(() => [
    "Gathering audio...",
    "Extracting sound waves...",
    "Playing with audio frequencies...",
    "Taking the sound waves apart...",
    "Reconfiguring audio for transcription...",
    "Preparing audio data..."
  ], [])

  // Rotate audio gathering messages
  useEffect(() => {
    if (progress.stage === 'downloading' && processingMethod === 'groq') {
      const interval = setInterval(() => {
        setAudioGatheringMessageIndex((prev) => (prev + 1) % audioGatheringMessages.length)
      }, 2000) // Rotate every 2 seconds
      
      return () => clearInterval(interval)
    }
  }, [progress.stage, processingMethod, audioGatheringMessages.length])

  // Handle WebSocket message
  const handleSocketMessage = useCallback((message: any) => {
    console.log('WebSocket message received:', message)
    
    // Determine the appropriate message based on stage and method
    let displayMessage = message.message || ''
    
    // For Groq method during downloading stage, use rotating audio gathering messages
    if (processingMethod === 'groq' && message.stage === 'downloading' && !message.message?.includes('Audio downloaded')) {
      displayMessage = audioGatheringMessages[audioGatheringMessageIndex]
    }
    // For processing stage with Groq, show "Processing audio" message
    else if (processingMethod === 'groq' && message.stage === 'processing') {
      displayMessage = "Processing audio"
    }
    // For transcribing stage with Groq, show "Groq transcription commenced"
    else if (processingMethod === 'groq' && message.stage === 'transcribing') {
      displayMessage = "Groq transcription commenced"
    }
    
    // Update progress state
    setProgress({
      stage: message.status || message.stage || 'processing',
      progress: message.progress || 0,
      message: displayMessage
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
        
        // Refresh usage display
        getUsage()
          .then(usage => {
            setGuestUsage(usage)
          })
          .catch(err => console.error('Failed to refresh usage:', err))
        
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
      
      // Handle guest limit exceeded
      if (message.error_code === 'guest_limit_exceeded') {
        setError(`You've reached your free limit for ${processingMethod === 'unofficial' ? 'YouTube subtitle' : 'AI'} transcriptions. Sign in to continue!`)
        // Refresh usage display
        getUsage()
          .then(usage => {
            setGuestUsage(usage)
          })
          .catch(e => console.error('Failed to refresh usage:', e))
        // Redirect after a delay
        setTimeout(() => {
          sessionStorage.setItem('auth-redirect-to', '/')
          router.push('/login')
        }, 3000)
      }
      // If unofficial transcript failed, suggest Groq
      else if (processingMethod === 'unofficial' && 
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
  }, [processingMethod, router, audioGatheringMessages, audioGatheringMessageIndex])

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
  const handleSubmit = async (submittedUrl: string, selectedFormat: 'txt' | 'srt' | 'vtt' | 'json', method: 'unofficial' | 'groq', groqModel?: string) => {
    try {
      // Only prevent submission if guest usage is still loading
      if (!user && guestUsageLoading) {
        setError('Loading usage information...')
        return
      }
      
      setError(null)
      setTranscriptFormat(selectedFormat)
      setIsProcessing(true)
      setProcessingMethod(method)
      setLastUrl(submittedUrl)
      const methodName = method === 'unofficial' ? 'Unofficial Transcript' : 'Groq AI Transcription'
      
      // Set initial progress message based on method
      if (method === 'groq') {
        setProgress({
          stage: 'starting',
          progress: 10,
          message: 'Initializing audio gathering...'
        })
      } else {
        setProgress({
          stage: 'starting',
          progress: 10,
          message: `Initializing ${methodName} job...`
        })
      }

      // Generate client ID and start transcription job
      const newClientId = generateClientId()
      setClientId(newClientId)
      
      // Set connecting message based on method
      if (method === 'groq') {
        setProgress({
          stage: 'connecting',
          progress: 25,
          message: 'Preparing to gather audio...'
        })
      } else {
        setProgress({
          stage: 'connecting',
          progress: 25,
          message: `Connecting to ${methodName} service...`
        })
      }

      const response = await startTranscriptionJob(submittedUrl, newClientId, {
        output_format: selectedFormat,
        method: method,
        ...(method === 'groq' && groqModel ? { model: groqModel } : {})
      })

      setJobId(response.job_id)
      
      // Initial progress - WebSocket will take over from here
      if (method === 'groq') {
        setProgress({
          stage: 'connecting',
          progress: 25,
          message: 'Preparing to gather audio...'
        })
      } else {
        setProgress({
          stage: 'connecting',
          progress: 25,
          message: `Connecting to ${methodName} service...`
        })
      }

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
        // Check if it's a guest limit error
        if (err.status === 401 && err.response?.error_code === 'guest_limit_exceeded') {
          setError(`You've reached your free limit for ${processingMethod === 'unofficial' ? 'YouTube subtitle' : 'AI'} transcriptions. Sign in to continue!`)
          // Refresh usage display
          getUsage()
            .then(usage => {
              setGuestUsage(usage)
            })
            .catch(e => console.error('Failed to refresh usage:', e))
          // Optionally redirect after a delay
          setTimeout(() => {
            sessionStorage.setItem('auth-redirect-to', '/')
            router.push('/login')
          }, 3000)
        } else {
          setError(`Server Error: ${err.message} (Status: ${err.status})`)
        }
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

  // Smooth scroll to section
  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' })
    }
  }

  // App is now open access - no auth blocking

  return (
    <div className="min-h-screen bg-zinc-950 relative overflow-hidden">
      {/* Enhanced animated background gradient */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-0 -left-4 w-96 h-96 bg-orange-500 rounded-full mix-blend-multiply filter blur-3xl opacity-5 animate-blob"></div>
        <div className="absolute top-0 -right-4 w-96 h-96 bg-orange-400 rounded-full mix-blend-multiply filter blur-3xl opacity-5 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-20 w-96 h-96 bg-red-500 rounded-full mix-blend-multiply filter blur-3xl opacity-5 animate-blob animation-delay-4000"></div>
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-zinc-900 via-zinc-950 to-zinc-950"></div>
      </div>
      
      {/* Quick Navigation Pills - Only show after scrolling */}
      <AnimatePresence>
        {activeSection && (
          <motion.div 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed top-20 left-1/2 transform -translate-x-1/2 z-40"
          >
            <div className="bg-zinc-900/90 backdrop-blur-xl border border-zinc-800/50 rounded-full shadow-2xl px-2 py-1">
              <nav className="flex items-center space-x-1">
                {[
                  { id: 'how-it-works', label: 'How it Works', icon: Play },
                  { id: 'features', label: 'Features', icon: Sparkles },
                  { id: 'pricing-section', label: 'Pricing', icon: Coins },
                  { id: 'faq-section', label: 'FAQ', icon: CheckCircle }
                ].map((item) => (
                  <Button
                    key={item.id}
                    variant="ghost"
                    size="sm"
                    onClick={() => scrollToSection(item.id)}
                    className={cn(
                      "relative px-3 py-1.5 text-xs font-medium transition-all duration-200 rounded-full",
                      activeSection === item.id 
                        ? "text-orange-500 bg-orange-500/10" 
                        : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
                    )}
                  >
                    <item.icon className="w-3.5 h-3.5 mr-1.5" />
                    {item.label}
                  </Button>
                ))}
              </nav>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Hero Section */}
      <div className="container mx-auto px-4 pt-12 pb-8">
        <div className="text-center max-w-4xl mx-auto">
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-6xl md:text-7xl font-bold tracking-tight mb-6"
          >
            <span className="text-zinc-100">yt</span>
            <span className="bg-gradient-to-r from-orange-500 to-orange-400 bg-clip-text text-transparent">Fetch</span>
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-xl text-zinc-400 mb-8 leading-relaxed"
          >
            Lightning-fast YouTube video transcription powered by{' '}
            <span className="text-orange-500 font-semibold">Groq&apos;s AI models</span>.
            Convert any YouTube video to text, SRT, VTT, or JSON format in seconds.
          </motion.p>
          
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex items-center justify-center gap-6 text-sm text-zinc-500 mb-8"
          >
            <div className="flex items-center gap-2">
              <motion.div 
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="w-2 h-2 bg-orange-500 rounded-full"
              />
              <span>Powered by Groq</span>
            </div>
            <div className="flex items-center gap-2">
              <motion.div 
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity, delay: 0.7 }}
                className="w-2 h-2 bg-green-500 rounded-full"
              />
              <span>Token-Based</span>
            </div>
            <div className="flex items-center gap-2">
              <motion.div 
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity, delay: 1.4 }}
                className="w-2 h-2 bg-blue-500 rounded-full"
              />
              <span>Real-time Progress</span>
            </div>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex justify-center gap-4"
          >
            <Button
              onClick={() => scrollToSection('transcribe-section')}
              size="lg"
              className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-lg shadow-orange-500/20"
            >
              Start Transcribing
              <ArrowRight className="w-5 h-5 ml-2" />
            </Button>
            <Button
              onClick={() => scrollToSection('how-it-works')}
              size="lg"
              variant="outline"
              className="border-zinc-800 hover:bg-zinc-900/50 text-zinc-300 hover:text-zinc-100"
            >
              Learn More
            </Button>
          </motion.div>
        </div>
      </div>

      {/* Main Content */}
      <div id="transcribe-section" className="container mx-auto px-4 pb-12">
        <div className="max-w-4xl mx-auto space-y-8">
          
          {/* Usage Display */}
          <GuestUsageDisplay 
            className="mb-4"
            onSignUpClick={() => router.push('/login')}
          />

          {/* URL Input Form */}
          <URLInputForm 
            onSubmit={handleSubmit}
            disabled={isProcessing || guestUsageLoading}
            processingMethod={processingMethod}
            onReset={handleReset}
            showReset={jobId !== null || finalTranscript !== ''}
          />

          {/* Bulk Process Button - Centered below main form */}
          {!isProcessing && !finalTranscript && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="flex justify-center"
            >
              <Button
                onClick={() => {
                  // Always allow access to bulk - let the bulk page handle limits
                  router.push('/bulk')
                }}
                size="lg"
                className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-medium px-8 py-6 text-lg shadow-lg shadow-blue-600/20 hover:shadow-xl hover:shadow-blue-600/30 transition-all duration-200 transform hover:scale-105"
              >
                <svg className="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                Bulk Process Playlists & Channels
              </Button>
            </motion.div>
          )}

          {/* Error Display */}
          {error && (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="bg-gradient-to-b from-red-500/10 to-red-500/5 border border-red-500/20 rounded-xl p-6 shadow-lg"
            >
              <div className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-white text-xs font-bold">!</span>
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-red-500 mb-1">Transcription Failed</h3>
                  <p className="text-sm text-red-400 whitespace-pre-line">{error}</p>
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
                className="bg-gradient-to-b from-zinc-900/50 to-zinc-900/20 rounded-2xl p-10 text-center backdrop-blur-sm border border-zinc-800"
              >
                <div className="max-w-md mx-auto">
                  <motion.h3 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="text-xl font-semibold mb-4 text-zinc-100"
                  >
                    Ready to transcribe?
                  </motion.h3>
                  <motion.p 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    className="text-zinc-400 mb-8 leading-relaxed"
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
                    <div className="bg-gradient-to-b from-zinc-800/40 to-zinc-800/20 rounded-xl p-4 backdrop-blur-sm border border-zinc-800">
                      <div className="font-medium text-zinc-100 mb-1">Supported Formats</div>
                      <div className="text-zinc-500">TXT • SRT • VTT • JSON</div>
                    </div>
                    <div className="bg-gradient-to-b from-zinc-800/40 to-zinc-800/20 rounded-xl p-4 backdrop-blur-sm border border-zinc-800">
                      <div className="font-medium text-zinc-100 mb-1">Speed</div>
                      <div className="text-zinc-500">Transcribes in seconds</div>
                    </div>
                  </motion.div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Token Promo Banner */}
      {!user && !isProcessing && !finalTranscript && (
        <div className="container mx-auto px-4 py-8">
          <TokenPromoBanner />
        </div>
      )}

      {/* How it Works Section */}
      <div id="how-it-works" className="relative py-24 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-950 via-zinc-900/30 to-zinc-950" />
        
        <div className="container mx-auto px-4 relative z-10">
          <div className="max-w-6xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-center mb-16"
            >
              <Badge className="mb-4 bg-orange-500/10 text-orange-500 border-orange-500/20">
                Simple Process
              </Badge>
              <h2 className="text-4xl md:text-5xl font-bold mb-4">How it Works</h2>
              <p className="text-xl text-zinc-400 max-w-2xl mx-auto">
                Get your YouTube video transcribed in three simple steps with our AI-powered tool
              </p>
            </motion.div>

            <div className="grid md:grid-cols-3 gap-8 md:gap-12">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
                className="relative group"
              >
                <div className="text-center space-y-6">
                  <motion.div 
                    whileHover={{ scale: 1.1, rotate: 5 }}
                    transition={{ type: "spring", stiffness: 300 }}
                    className="relative mx-auto"
                  >
                    <div className="w-24 h-24 mx-auto rounded-2xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center group-hover:shadow-xl transition-shadow">
                      <Play className="w-12 h-12 text-blue-600" />
                    </div>
                    <div className="absolute -top-2 -right-2 w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
                      1
                    </div>
                  </motion.div>
                  <div>
                    <h3 className="text-2xl font-semibold mb-2">Paste Video URL</h3>
                    <p className="text-zinc-400 leading-relaxed">
                      Simply copy any YouTube video URL and paste it into our transcription tool
                    </p>
                  </div>
                </div>
                <div className="hidden md:block absolute top-12 -right-8 w-16">
                  <motion.div
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.3 }}
                  >
                    <ArrowRight className="w-8 h-8 text-zinc-600" />
                  </motion.div>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                className="relative group"
              >
                <div className="text-center space-y-6">
                  <motion.div 
                    whileHover={{ scale: 1.1, rotate: -5 }}
                    transition={{ type: "spring", stiffness: 300 }}
                    className="relative mx-auto"
                  >
                    <div className="w-24 h-24 mx-auto rounded-2xl bg-gradient-to-br from-orange-500/20 to-red-500/20 flex items-center justify-center group-hover:shadow-xl transition-shadow">
                      <Zap className="w-12 h-12 text-orange-600" />
                    </div>
                    <div className="absolute -top-2 -right-2 w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
                      2
                    </div>
                  </motion.div>
                  <div>
                    <h3 className="text-2xl font-semibold mb-2">AI Transcribes</h3>
                    <p className="text-zinc-400 leading-relaxed">
                      Groq's lightning-fast AI models process your video and generate accurate transcripts
                    </p>
                  </div>
                </div>
                <div className="hidden md:block absolute top-12 -right-8 w-16">
                  <motion.div
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.4 }}
                  >
                    <ArrowRight className="w-8 h-8 text-zinc-600" />
                  </motion.div>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.3 }}
                className="relative group"
              >
                <div className="text-center space-y-6">
                  <motion.div 
                    whileHover={{ scale: 1.1, rotate: 5 }}
                    transition={{ type: "spring", stiffness: 300 }}
                    className="relative mx-auto"
                  >
                    <div className="w-24 h-24 mx-auto rounded-2xl bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center group-hover:shadow-xl transition-shadow">
                      <Download className="w-12 h-12 text-green-600" />
                    </div>
                    <div className="absolute -top-2 -right-2 w-8 h-8 bg-green-500 rounded-full flex items-center justify-center text-white font-bold text-sm">
                      3
                    </div>
                  </motion.div>
                  <div>
                    <h3 className="text-2xl font-semibold mb-2">Download Results</h3>
                    <p className="text-zinc-400 leading-relaxed">
                      Get your transcript in multiple formats: TXT, SRT, VTT, or JSON
                    </p>
                  </div>
                </div>
              </motion.div>
            </div>

            {/* Call to action */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.5 }}
              className="text-center mt-16"
            >
              <Button
                onClick={() => scrollToSection('transcribe-section')}
                size="lg"
                className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-lg shadow-orange-500/20"
              >
                Start Transcribing Now
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div id="features" className="relative py-24 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-900/20 via-zinc-950 to-zinc-900/20" />
        
        <div className="container mx-auto px-4 relative z-10">
          <div className="max-w-6xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-center mb-16"
            >
              <Badge className="mb-4 bg-orange-500/10 text-orange-500 border-orange-500/20">
                Powerful Tools
              </Badge>
              <h2 className="text-4xl md:text-5xl font-bold mb-4">Everything You Need</h2>
              <p className="text-xl text-zinc-400 max-w-2xl mx-auto">
                Professional-grade features for content creators, researchers, and developers
              </p>
            </motion.div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
                whileHover={{ y: -5 }}
                className="group relative bg-zinc-900 rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border border-zinc-800 hover:border-orange-500/20 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-red-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="relative z-10">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-orange-500/20 to-red-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Zap className="w-7 h-7 text-orange-600" />
                  </div>
                  <h3 className="text-2xl font-semibold mb-3 text-zinc-100">Lightning Fast</h3>
                  <p className="text-zinc-400 leading-relaxed">
                    Powered by Groq's world-class AI infrastructure for instant results. Process hours of video in seconds.
                  </p>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                whileHover={{ y: -5 }}
                className="group relative bg-zinc-900 rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border border-zinc-800 hover:border-orange-500/20 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-cyan-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="relative z-10">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <FileText className="w-7 h-7 text-blue-600" />
                  </div>
                  <h3 className="text-2xl font-semibold mb-3 text-zinc-100">Multiple Formats</h3>
                  <p className="text-zinc-400 leading-relaxed">
                    Export to TXT, SRT, VTT, or JSON. Perfect for subtitles, captions, or data analysis.
                  </p>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.3 }}
                whileHover={{ y: -5 }}
                className="group relative bg-zinc-900 rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border border-zinc-800 hover:border-orange-500/20 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-emerald-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="relative z-10">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <CheckCircle className="w-7 h-7 text-green-600" />
                  </div>
                  <h3 className="text-2xl font-semibold mb-3 text-zinc-100">99%+ Accuracy</h3>
                  <p className="text-zinc-400 leading-relaxed">
                    Industry-leading transcription accuracy with advanced AI models trained on millions of hours.
                  </p>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.4 }}
                whileHover={{ y: -5 }}
                className="group relative bg-zinc-900 rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border border-zinc-800 hover:border-orange-500/20 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-pink-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="relative z-10">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Users className="w-7 h-7 text-purple-600" />
                  </div>
                  <h3 className="text-2xl font-semibold mb-3 text-zinc-100">Bulk Processing</h3>
                  <p className="text-zinc-400 leading-relaxed">
                    Transcribe entire playlists and channels with one click. Perfect for content archives.
                  </p>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.5 }}
                whileHover={{ y: -5 }}
                className="group relative bg-zinc-900 rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border border-zinc-800 hover:border-orange-500/20 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-yellow-500/5 to-orange-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="relative z-10">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-yellow-500/20 to-orange-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Coins className="w-7 h-7 text-yellow-600" />
                  </div>
                  <h3 className="text-2xl font-semibold mb-3 text-zinc-100">Fair Pricing</h3>
                  <p className="text-zinc-400 leading-relaxed">
                    Pay once, use forever. No subscriptions, no expiry dates. Your tokens never expire.
                  </p>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.6 }}
                whileHover={{ y: -5 }}
                className="group relative bg-zinc-900 rounded-2xl p-8 shadow-lg hover:shadow-2xl transition-all duration-300 border border-zinc-800 hover:border-orange-500/20 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="relative z-10">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-indigo-500/20 to-blue-500/20 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Sparkles className="w-7 h-7 text-indigo-600" />
                  </div>
                  <h3 className="text-2xl font-semibold mb-3 text-zinc-100">Real-time Progress</h3>
                  <p className="text-zinc-400 leading-relaxed">
                    Track transcription progress with live updates. Know exactly when your transcript is ready.
                  </p>
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </div>

      {/* Pricing Preview Section */}
      <div id="pricing-section" className="relative py-24 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-950 via-zinc-900/20 to-zinc-950" />
        
        <div className="container mx-auto px-4 relative z-10">
          <div className="max-w-5xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-center mb-16"
            >
              <Badge className="mb-4 bg-orange-500/10 text-orange-500 border-orange-500/20">
                Token-Based Pricing
              </Badge>
              <h2 className="text-4xl md:text-5xl font-bold mb-4">Pay Once, Use Forever</h2>
              <p className="text-xl text-zinc-400 max-w-2xl mx-auto">
                No subscriptions, no hidden fees. Your tokens never expire.
              </p>
            </motion.div>

            <div className="grid md:grid-cols-3 gap-8 mb-12">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.1 }}
                whileHover={{ y: -5 }}
                className="relative bg-zinc-900 rounded-2xl p-8 text-center shadow-lg hover:shadow-2xl transition-all duration-300 border border-zinc-800 hover:border-orange-500/20 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-zinc-800/20 to-zinc-900/50" />
                <div className="relative z-10">
                  <h3 className="text-xl font-semibold mb-2 text-zinc-100">Starter Pack</h3>
                  <div className="mb-6">
                    <div className="text-5xl font-bold mb-2 text-zinc-100">$2.99</div>
                    <p className="text-zinc-400">50 tokens</p>
                  </div>
                  <div className="space-y-3 mb-6">
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>50 video transcriptions</span>
                    </div>
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>All export formats</span>
                    </div>
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>Never expires</span>
                    </div>
                  </div>
                  <p className="text-sm text-zinc-500">Perfect for trying out</p>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                whileHover={{ y: -5, scale: 1.02 }}
                className="relative bg-zinc-900 rounded-2xl p-8 text-center shadow-xl hover:shadow-2xl transition-all duration-300 border-2 border-orange-500 overflow-hidden"
              >
                <div className="absolute -top-10 -right-10 w-32 h-32 bg-orange-500/20 rounded-full blur-3xl" />
                <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-orange-500/20 rounded-full blur-3xl" />
                <div className="relative z-10">
                  <Badge className="mb-4 bg-gradient-to-r from-orange-500 to-orange-600 text-white border-0">
                    MOST POPULAR
                  </Badge>
                  <h3 className="text-xl font-semibold mb-2 text-zinc-100">Popular Pack</h3>
                  <div className="mb-6">
                    <div className="text-5xl font-bold mb-2 text-zinc-100">$6.99</div>
                    <p className="text-zinc-400">150 tokens</p>
                  </div>
                  <div className="space-y-3 mb-6">
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>150 video transcriptions</span>
                    </div>
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>Bulk processing</span>
                    </div>
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>Priority support</span>
                    </div>
                  </div>
                  <Badge className="bg-green-500/20 text-green-600 border-green-500/30">
                    Save 22%
                  </Badge>
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.3 }}
                whileHover={{ y: -5 }}
                className="relative bg-zinc-900 rounded-2xl p-8 text-center shadow-lg hover:shadow-2xl transition-all duration-300 border border-zinc-800 hover:border-orange-500/20 overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-zinc-800/20 to-zinc-900/50" />
                <div className="relative z-10">
                  <h3 className="text-xl font-semibold mb-2 text-zinc-100">High Volume</h3>
                  <div className="mb-6">
                    <div className="text-5xl font-bold mb-2 text-zinc-100">$17.99</div>
                    <p className="text-zinc-400">500 tokens</p>
                  </div>
                  <div className="space-y-3 mb-6">
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>500 video transcriptions</span>
                    </div>
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>API access</span>
                    </div>
                    <div className="flex items-center justify-center gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>Premium support</span>
                    </div>
                  </div>
                  <Badge className="bg-green-500/20 text-green-600 border-green-500/30">
                    Save 40%
                  </Badge>
                </div>
              </motion.div>
            </div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-center space-y-6"
            >
              <Button
                onClick={() => router.push('/pricing')}
                size="lg"
                className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 shadow-lg shadow-orange-500/20 text-lg px-8 py-6"
              >
                <Coins className="w-6 h-6 mr-2" />
                View All Pricing Options
              </Button>
              
              <div className="flex items-center justify-center gap-8 text-sm text-zinc-500">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span>30-day money back guarantee</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-500" />
                  <span>Secure payment via Stripe</span>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </div>

      {/* FAQ Section */}
      <div id="faq-section" className="relative py-24 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-900/30 via-zinc-950 to-zinc-900/20" />
        
        <div className="container mx-auto px-4 relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <FAQ />
          </motion.div>
        </div>
      </div>

      {/* Footer */}
      <footer className="relative border-t border-zinc-800 bg-gradient-to-b from-zinc-950 to-zinc-900/50">
        <div className="container mx-auto px-4 py-12">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-gradient-to-r from-orange-500 to-orange-600 rounded-lg flex items-center justify-center shadow-lg shadow-orange-500/20">
                  <span className="text-sm font-bold text-white">yt</span>
                </div>
                <span className="font-bold text-xl text-zinc-100">ytFetch</span>
              </div>
              <p className="text-sm text-zinc-500">
                Lightning-fast YouTube transcription powered by Groq AI
              </p>
            </div>
            
            <div className="space-y-4">
              <h3 className="font-semibold text-zinc-200">Product</h3>
              <ul className="space-y-2 text-sm text-zinc-500">
                <li><a href="#features" className="hover:text-orange-500 transition-colors">Features</a></li>
                <li><a href="#pricing-section" className="hover:text-orange-500 transition-colors">Pricing</a></li>
                <li><a href="/bulk" className="hover:text-orange-500 transition-colors">Bulk Processing</a></li>
                <li><a href="/dashboard" className="hover:text-orange-500 transition-colors">Dashboard</a></li>
              </ul>
            </div>
            
            <div className="space-y-4">
              <h3 className="font-semibold text-zinc-200">Resources</h3>
              <ul className="space-y-2 text-sm text-zinc-500">
                <li><a href="#how-it-works" className="hover:text-orange-500 transition-colors">How it Works</a></li>
                <li><a href="#faq-section" className="hover:text-orange-500 transition-colors">FAQ</a></li>
                <li><a href="/api-docs" className="hover:text-orange-500 transition-colors">API Documentation</a></li>
                <li><a href="/support" className="hover:text-orange-500 transition-colors">Support</a></li>
              </ul>
            </div>
            
            <div className="space-y-4">
              <h3 className="font-semibold text-zinc-200">Company</h3>
              <ul className="space-y-2 text-sm text-zinc-500">
                <li><a href="/about" className="hover:text-orange-500 transition-colors">About</a></li>
                <li><a href="/privacy" className="hover:text-orange-500 transition-colors">Privacy Policy</a></li>
                <li><a href="/terms" className="hover:text-orange-500 transition-colors">Terms of Service</a></li>
                <li><a href="mailto:support@ytfetch.com" className="hover:text-orange-500 transition-colors">Contact</a></li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-zinc-800 pt-8">
            <div className="flex flex-col md:flex-row justify-between items-center gap-4">
              <p className="text-sm text-zinc-500">
                © 2024 ytFetch. All rights reserved.
              </p>
              <div className="flex items-center gap-6 text-sm text-zinc-500">
                <span>Powered by</span>
                <a href="https://groq.com" target="_blank" rel="noopener noreferrer" className="text-orange-500 font-semibold hover:text-orange-400 transition-colors">
                  Groq AI
                </a>
                <span>•</span>
                <span>Built with ❤️ for content creators</span>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}