'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Loader2, Search, Play, Users, AlertCircle, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import { 
  analyzeBulkSource, 
  isValidBulkUrl, 
  getBulkSourceType,
  type BulkAnalyzeResponse,
  type TranscriptMethod,
  type OutputFormat 
} from '@/services/bulkApi'
import { ApiValidationError, ApiHttpError, ApiNetworkError } from '@/services/api'

// Client-only wrapper to prevent hydration mismatch
function ClientOnlySelect({ value, onValueChange, disabled, children }: {
  value: string
  onValueChange: (value: string) => void
  disabled?: boolean
  children: React.ReactNode
}) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    // Return a simple div that matches the Select's appearance during SSR
    return (
      <div className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground">
        <span>Unofficial Transcripts</span>
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 opacity-50">
          <path d="m4.93179 5.43179 2.86768 2.86768a.5.5 0 0 0 .70711 0l2.86767-2.86768a.5.5 0 1 1 .70711.70711L7.85355 9.85355a.5.5 0 0 1-.70711 0L3.43168 6.13889a.5.5 0 0 1 .70711-.70711Z" fill="currentColor" fillRule="evenodd" clipRule="evenodd"></path>
        </svg>
      </div>
    )
  }

  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger disabled={disabled}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {children}
      </SelectContent>
    </Select>
  )
}

interface BulkDownloadFormProps {
  onAnalyze: (analysis: BulkAnalyzeResponse, params?: {
    url: string
    transcriptMethod: TranscriptMethod
    outputFormat: OutputFormat
    maxVideos?: number
  }) => void
  onCreateJob: (params: {
    url: string
    transcriptMethod: TranscriptMethod
    outputFormat: OutputFormat
    maxVideos?: number
  }) => void
  disabled?: boolean
  showAnalysis?: boolean
}

export function BulkDownloadForm({ 
  onAnalyze, 
  onCreateJob, 
  disabled = false,
  showAnalysis = false 
}: BulkDownloadFormProps) {
  const [url, setUrl] = useState('')
  const [transcriptMethod, setTranscriptMethod] = useState<TranscriptMethod>('unofficial')
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('txt')
  const [maxVideos, setMaxVideos] = useState<number | ''>('')
  const [isValid, setIsValid] = useState<boolean | null>(null)
  const [touched, setTouched] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sourceType, setSourceType] = useState<'playlist' | 'channel' | 'unknown'>('unknown')

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (touched && url) {
      const valid = isValidBulkUrl(url)
      setIsValid(valid)
      if (valid) {
        setSourceType(getBulkSourceType(url))
      } else {
        setSourceType('unknown')
      }
    } else if (touched && !url) {
      setIsValid(false)
      setSourceType('unknown')
    }
  }, [url, touched])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value)
    setError(null)
    if (!touched) {
      setTouched(true)
    }
  }

  const handleMaxVideosChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    if (value === '') {
      setMaxVideos('')
    } else {
      const num = parseInt(value, 10)
      if (!isNaN(num) && num > 0) {
        setMaxVideos(Math.min(num, 1000)) // Cap at 1000
      }
    }
  }

  const handleAnalyze = async () => {
    if (!isValid || !url.trim()) return

    setIsAnalyzing(true)
    setError(null)

    try {
      console.log('Starting bulk source analysis for URL:', url.trim())
      const analysis = await analyzeBulkSource(
        url.trim(),
        maxVideos && maxVideos > 0 ? maxVideos : undefined
      )
      console.log('Analysis successful:', analysis)
      // Pass form parameters along with the analysis
      onAnalyze(analysis, {
        url: url.trim(),
        transcriptMethod,
        outputFormat,
        maxVideos: maxVideos && maxVideos > 0 ? maxVideos : undefined
      })
    } catch (err) {
      console.error('Analysis failed:', err)
      if (err instanceof ApiValidationError) {
        setError(`Validation Error: ${err.message}`)
      } else if (err instanceof ApiNetworkError) {
        setError(`Network Error: ${err.message}. Please check your connection and try again.`)
      } else if (err instanceof ApiHttpError) {
        setError(`Server Error: ${err.message} (Status: ${err.status})`)
      } else {
        setError(`Unexpected Error: ${err instanceof Error ? err.message : 'Something went wrong'}`)
      }
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleCreateJob = () => {
    if (!isValid || !url.trim()) return

    console.log('Create job button clicked with params:', {
      url: url.trim(),
      transcriptMethod,
      outputFormat,
      maxVideos: maxVideos && maxVideos > 0 ? maxVideos : undefined,
      showAnalysis
    })

    onCreateJob({
      url: url.trim(),
      transcriptMethod,
      outputFormat,
      maxVideos: maxVideos && maxVideos > 0 ? maxVideos : undefined
    })
  }

  const getInputClassName = () => {
    const baseClasses = "w-full bg-background/50 border-border/50 text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all duration-200"
    
    if (touched && isValid === false) {
      return `${baseClasses} border-destructive focus:border-destructive focus:ring-destructive/20`
    }
    if (touched && isValid === true) {
      return `${baseClasses} border-green-500/50 focus:border-green-500 focus:ring-green-500/20`
    }
    return baseClasses
  }

  const getSourceIcon = () => {
    switch (sourceType) {
      case 'playlist':
        return <Play className="h-4 w-4" />
      case 'channel':
        return <Users className="h-4 w-4" />
      default:
        return null
    }
  }

  const getSourceLabel = () => {
    switch (sourceType) {
      case 'playlist':
        return 'Playlist'
      case 'channel':
        return 'Channel'
      default:
        return ''
    }
  }

  return (
    <Card className={cn(
      "w-full max-w-4xl mx-auto transition-all duration-300",
      "bg-gradient-to-b from-card to-card/95",
      "border-border/50",
      "shadow-[0_8px_30px_rgb(0,0,0,0.12)]",
      "hover:shadow-[0_8px_40px_rgb(0,0,0,0.15)]",
      mounted && !disabled && "hover:-translate-y-1"
    )}>
      <div className="p-8 space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold text-foreground">Bulk Transcription</h2>
          <p className="text-muted-foreground">
            Transcribe entire YouTube playlists or channels with ease
          </p>
        </div>

        {/* URL Input */}
        <div className="space-y-2">
          <label htmlFor="bulk-url" className="text-sm font-medium text-foreground flex items-center gap-2">
            YouTube Playlist or Channel URL
            {sourceType !== 'unknown' && (
              <Badge variant="secondary" className="text-xs">
                {getSourceIcon()}
                <span className="ml-1">{getSourceLabel()}</span>
              </Badge>
            )}
          </label>
          <Input
            id="bulk-url"
            type="url"
            placeholder="https://www.youtube.com/playlist?list=... or https://www.youtube.com/@channel"
            value={url}
            onChange={handleInputChange}
            disabled={disabled}
            className={getInputClassName()}
            aria-invalid={touched && isValid === false}
            aria-describedby={touched && isValid === false ? "url-error" : undefined}
            suppressHydrationWarning
          />
          {touched && isValid === false && (
            <p id="url-error" className="text-sm text-destructive mt-1 flex items-center gap-1">
              <AlertCircle className="h-3 w-3" />
              Please enter a valid YouTube playlist or channel URL
            </p>
          )}
          {touched && isValid === true && (
            <p className="text-sm text-green-500 mt-1 flex items-center gap-1">
              <Info className="h-3 w-3" />
              Valid {sourceType} URL detected
            </p>
          )}
        </div>

        {/* Settings Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Transcript Method */}
          <div className="space-y-2">
            <label htmlFor="transcript-method" className="text-sm font-medium text-foreground">
              Transcript Method
            </label>
            <ClientOnlySelect 
              value={transcriptMethod} 
              onValueChange={(value: string) => setTranscriptMethod(value as TranscriptMethod)}
              disabled={disabled}
            >
              <SelectItem value="unofficial">Unofficial Transcripts</SelectItem>
              <SelectItem value="groq">Groq AI Transcription</SelectItem>
              <SelectItem value="openai">OpenAI Transcription</SelectItem>
            </ClientOnlySelect>
          </div>

          {/* Output Format */}
          <div className="space-y-2">
            <label htmlFor="output-format" className="text-sm font-medium text-foreground">
              Output Format
            </label>
            <ClientOnlySelect 
              value={outputFormat} 
              onValueChange={(value: string) => setOutputFormat(value as OutputFormat)}
              disabled={disabled}
            >
              <SelectItem value="txt">Plain Text (.txt)</SelectItem>
              <SelectItem value="srt">SubRip (.srt)</SelectItem>
              <SelectItem value="vtt">WebVTT (.vtt)</SelectItem>
              <SelectItem value="json">JSON (.json)</SelectItem>
            </ClientOnlySelect>
          </div>

          {/* Max Videos */}
          <div className="space-y-2">
            <label htmlFor="max-videos" className="text-sm font-medium text-foreground">
              Max Videos (Optional)
            </label>
            <Input
              id="max-videos"
              type="number"
              placeholder="All videos"
              value={maxVideos}
              onChange={handleMaxVideosChange}
              disabled={disabled}
              min="1"
              max="1000"
              className="bg-background/50 border-border/50"
            />
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-b from-destructive/10 to-destructive/5 border border-destructive/20 rounded-xl p-4 shadow-lg"
          >
            <div className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-destructive flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-destructive-foreground text-xs font-bold">!</span>
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-destructive mb-1">Analysis Failed</h3>
                <p className="text-sm text-destructive/90 whitespace-pre-line">{error}</p>
              </div>
            </div>
          </motion.div>
        )}

        {/* Action Buttons */}
        <div className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Button
              type="button"
              disabled={!isValid || isAnalyzing || disabled}
              onClick={handleAnalyze}
              className={cn(
                "h-12 text-sm font-medium transition-all duration-300 transform relative overflow-hidden group",
                (!mounted || !isValid || isAnalyzing) ? 
                  "bg-gradient-to-r from-gray-800 to-gray-900 text-gray-400 border border-gray-700 hover:from-gray-700 hover:to-gray-800 shadow-inner" : 
                  "bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:from-blue-600 hover:to-blue-700 shadow-[0_4px_14px_0_rgb(59,130,246,0.39)] hover:shadow-[0_6px_20px_rgba(59,130,246,0.5)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-[0_3px_10px_rgba(59,130,246,0.3)] border border-blue-400/20"
              )}
            >
              {/* Shine effect overlay */}
              {mounted && isValid && !isAnalyzing && (
                <div className="absolute inset-0 -top-1/2 h-[200%] w-full rotate-12 bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
              )}
              {isAnalyzing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Search className={cn("mr-2 h-4 w-4 transition-all duration-300", isValid ? "opacity-100" : "opacity-50")} />
                  Analyze Source
                </>
              )}
            </Button>

            <Button
              type="button"
              disabled={!isValid || isAnalyzing || disabled}
              onClick={handleCreateJob}
              className={cn(
                "h-12 font-medium transition-all duration-300 transform relative overflow-hidden group",
                (!mounted || !isValid || isAnalyzing) ? 
                  "bg-gradient-to-r from-gray-800 to-gray-900 text-gray-400 border border-gray-700 hover:from-gray-700 hover:to-gray-800 shadow-inner cursor-not-allowed" : 
                  !showAnalysis ?
                  "bg-gradient-to-r from-amber-500 to-amber-600 text-white hover:from-amber-600 hover:to-amber-700 shadow-[0_4px_14px_0_rgb(245,158,11,0.39)] hover:shadow-[0_6px_20px_rgba(245,158,11,0.5)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-[0_3px_10px_rgba(245,158,11,0.3)] border border-amber-400/20" :
                  "bg-gradient-to-r from-green-500 to-green-600 text-white hover:from-green-600 hover:to-green-700 shadow-[0_4px_14px_0_rgb(34,197,94,0.39)] hover:shadow-[0_6px_20px_rgba(34,197,94,0.5)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-[0_3px_10px_rgba(34,197,94,0.3)] border border-green-400/20"
              )}
            >
              {/* Shine effect overlay */}
              {mounted && isValid && !isAnalyzing && (
                <div className="absolute inset-0 -top-1/2 h-[200%] w-full rotate-12 bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
              )}
              {!showAnalysis ? (
                <>
                  <Info className={cn("mr-2 h-4 w-4 transition-all duration-300", isValid ? "opacity-100" : "opacity-50")} />
                  Analyze First, Then Create Job
                </>
              ) : (
                <>
                  <span className={cn("mr-2 transition-all duration-300", isValid ? "opacity-100" : "opacity-50")}>🚀</span>
                  Create Bulk Job
                </>
              )}
            </Button>
          </div>
          
          {/* Step indicator for clarity */}
          {!showAnalysis && mounted && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center text-xs text-muted-foreground flex items-center justify-center gap-2"
            >
              <AlertCircle className="h-3 w-3" />
              <span>Start with "Analyze Source" to scan the playlist/channel</span>
            </motion.div>
          )}
        </div>

        {/* Help Text */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-border/30" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card px-4 text-muted-foreground">Supported Sources</span>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs text-muted-foreground">
          <div className="text-center space-y-1">
            <div className="font-medium text-foreground flex items-center justify-center gap-1">
              <Play className="h-3 w-3" />
              YouTube Playlists
            </div>
            <div>Process all videos in a playlist automatically</div>
          </div>
          <div className="text-center space-y-1">
            <div className="font-medium text-foreground flex items-center justify-center gap-1">
              <Users className="h-3 w-3" />
              YouTube Channels
            </div>
            <div>Transcribe recent videos from any channel</div>
          </div>
        </div>
      </div>
    </Card>
  )
}

export type { BulkDownloadFormProps }