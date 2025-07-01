'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Loader2, RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'

// Client-only wrapper to prevent hydration mismatch
function ClientOnlySelect({ value, onValueChange, disabled }: {
  value: string
  onValueChange: (value: string) => void
  disabled?: boolean
}) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    // Return a simple div that matches the Select's appearance during SSR
    return (
      <div className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground">
        <span>Plain Text (.txt)</span>
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 opacity-50">
          <path d="m4.93179 5.43179 2.86768 2.86768a.5.5 0 0 0 .70711 0l2.86767-2.86768a.5.5 0 1 1 .70711.70711L7.85355 9.85355a.5.5 0 0 1-.70711 0L3.43168 6.13889a.5.5 0 0 1 .70711-.70711Z" fill="currentColor" fillRule="evenodd" clipRule="evenodd"></path>
        </svg>
      </div>
    )
  }

  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger disabled={disabled}>
        <SelectValue placeholder="Select output format" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="txt">Plain Text (.txt)</SelectItem>
        <SelectItem value="srt">SubRip (.srt)</SelectItem>
        <SelectItem value="vtt">WebVTT (.vtt)</SelectItem>
        <SelectItem value="json">JSON (.json)</SelectItem>
      </SelectContent>
    </Select>
  )
}

// Client-only wrapper for Groq model select
function ClientOnlyGroqSelect({ value, onValueChange, disabled }: {
  value: string
  onValueChange: (value: string) => void
  disabled?: boolean
}) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    // Return a simple div that matches the Select's appearance during SSR
    return (
      <div className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground">
        <span>Whisper Large v3 Turbo (Fastest)</span>
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 opacity-50">
          <path d="m4.93179 5.43179 2.86768 2.86768a.5.5 0 0 0 .70711 0l2.86767-2.86768a.5.5 0 1 1 .70711.70711L7.85355 9.85355a.5.5 0 0 1-.70711 0L3.43168 6.13889a.5.5 0 0 1 .70711-.70711Z" fill="currentColor" fillRule="evenodd" clipRule="evenodd"></path>
        </svg>
      </div>
    )
  }

  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger disabled={disabled}>
        <SelectValue placeholder="Select Groq model" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="whisper-large-v3-turbo">Whisper Large v3 Turbo (Fastest)</SelectItem>
        <SelectItem value="whisper-large-v3">Whisper Large v3 (Standard)</SelectItem>
        <SelectItem value="distil-whisper-large-v3-en">Distil Whisper v3 (English Only)</SelectItem>
      </SelectContent>
    </Select>
  )
}

interface URLInputFormProps {
  onSubmit: (url: string, format: 'txt' | 'srt' | 'vtt' | 'json', method: 'unofficial' | 'groq', groqModel?: string) => void
  disabled?: boolean
  processingMethod?: 'unofficial' | 'groq' | null
  onReset?: () => void
  showReset?: boolean
}

export function URLInputForm({ onSubmit, disabled, processingMethod, onReset, showReset }: URLInputFormProps) {
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<'txt' | 'srt' | 'vtt' | 'json'>('txt')
  const [groqModel, setGroqModel] = useState<string>('whisper-large-v3-turbo')
  const [isValid, setIsValid] = useState<boolean | null>(null)
  const [touched, setTouched] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  // YouTube URL validation regex - more permissive
  const validateYouTubeUrl = (url: string): boolean => {
    if (!url) return false
    // More flexible regex that accepts various YouTube URL formats
    const youtubeRegex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/
    return youtubeRegex.test(url) || 
           url.includes('youtube.com/watch') || 
           url.includes('youtu.be/') ||
           url.includes('youtube.com/embed/') ||
           url.includes('m.youtube.com/watch')
  }

  useEffect(() => {
    if (touched && url) {
      setIsValid(validateYouTubeUrl(url))
    } else if (touched && !url) {
      setIsValid(false)
    }
  }, [url, touched])

  const handleSubmit = (method: 'unofficial' | 'groq') => {
    if (isValid && !disabled && url.trim()) {
      onSubmit(url.trim(), format, method, method === 'groq' ? groqModel : undefined)
    }
  }

  const handleReset = () => {
    setUrl('')
    setFormat('txt')
    setGroqModel('whisper-large-v3-turbo')
    setIsValid(null)
    setTouched(false)
    if (onReset) {
      onReset()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value)
    if (!touched) {
      setTouched(true)
    }
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

  return (
    <Card className={cn(
      "w-full max-w-2xl mx-auto transition-all duration-300",
      "bg-gradient-to-b from-card to-card/95",
      "border-border/50",
      "shadow-[0_8px_30px_rgb(0,0,0,0.12)]",
      "hover:shadow-[0_8px_40px_rgb(0,0,0,0.15)]",
      mounted && "hover:-translate-y-1"
    )}>
      <div className="p-8 space-y-6">
        <div className="space-y-2">
          <label htmlFor="youtube-url" className="text-sm font-medium text-foreground">
            YouTube URL
          </label>
          <Input
            id="youtube-url"
            type="url"
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={handleInputChange}
            disabled={disabled}
            className={getInputClassName()}
            aria-invalid={touched && isValid === false}
            aria-describedby={touched && isValid === false ? "url-error" : undefined}
            suppressHydrationWarning
          />
          {touched && isValid === false && (
            <p id="url-error" className="text-sm text-destructive mt-1">
              Please enter a valid YouTube URL
            </p>
          )}
          {touched && isValid === true && (
            <p className="text-sm text-green-500 mt-1">
              Valid YouTube URL
            </p>
          )}
        </div>

        {/* Output Format and Groq Model Selectors */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="output-format" className="text-sm font-medium text-foreground">
              Output Format
            </label>
            <ClientOnlySelect 
              value={format} 
              onValueChange={(value: string) => setFormat(value as 'txt' | 'srt' | 'vtt' | 'json')}
              disabled={disabled}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="groq-model" className="text-sm font-medium text-foreground">
              Groq Model
            </label>
            <ClientOnlyGroqSelect 
              value={groqModel} 
              onValueChange={setGroqModel}
              disabled={disabled}
            />
          </div>
        </div>

        {/* Two Transcription Method Buttons */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Button
            type="button"
            disabled={!isValid || (disabled && processingMethod === 'unofficial')}
            onClick={() => handleSubmit('unofficial')}
            className={cn(
              "h-12 text-sm font-medium transition-all duration-300 transform relative overflow-hidden group",
              (!mounted || !isValid) ? 
                "bg-gradient-to-r from-gray-800 to-gray-900 text-gray-400 border border-gray-700 hover:from-gray-700 hover:to-gray-800 shadow-inner" : 
                "bg-gradient-to-r from-green-500 to-green-600 text-white hover:from-green-600 hover:to-green-700 shadow-[0_4px_14px_0_rgb(34,197,94,0.39)] hover:shadow-[0_6px_20px_rgba(34,197,94,0.5)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-[0_3px_10px_rgba(34,197,94,0.3)] border border-green-400/20"
            )}
          >
            {/* Shine effect overlay */}
            {mounted && isValid && (
              <div className="absolute inset-0 -top-1/2 h-[200%] w-full rotate-12 bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            )}
            {disabled && processingMethod === 'unofficial' ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <span className={cn("mr-2 transition-all duration-300", isValid ? "opacity-100" : "opacity-50")}>📝</span>
                Unofficial Transcripts
              </>
            )}
          </Button>

          <Button
            type="button"
            disabled={!isValid || (disabled && processingMethod === 'groq')}
            onClick={() => handleSubmit('groq')}
            className={cn(
              "h-12 font-medium transition-all duration-300 transform relative overflow-hidden group",
              (!mounted || !isValid) ? 
                "bg-gradient-to-r from-gray-800 to-gray-900 text-gray-400 border border-gray-700 hover:from-gray-700 hover:to-gray-800 shadow-inner" : 
                "bg-gradient-to-r from-orange-500 to-orange-600 text-white hover:from-orange-600 hover:to-orange-700 shadow-[0_4px_14px_0_rgb(251,146,60,0.39)] hover:shadow-[0_6px_20px_rgba(251,146,60,0.5)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-[0_3px_10px_rgba(251,146,60,0.3)] border border-orange-400/20"
            )}
          >
            {/* Shine effect overlay */}
            {mounted && isValid && (
              <div className="absolute inset-0 -top-1/2 h-[200%] w-full rotate-12 bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
            )}
            {disabled && processingMethod === 'groq' ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <span className={cn("mr-2 transition-all duration-300", isValid ? "opacity-100" : "opacity-50")}>⚡</span>
                Groq AI Transcription
              </>
            )}
          </Button>
        </div>

        {/* Elegant Help Text */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-border/30" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card px-4 text-muted-foreground">How it works</span>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs text-muted-foreground">
          <div className="text-center space-y-1">
            <div className="font-medium text-foreground">Unofficial Transcripts</div>
            <div>Instantly fetch existing YouTube captions</div>
          </div>
          <div className="text-center space-y-1">
            <div className="font-medium text-foreground">Groq AI Transcription</div>
            <div>Download & transcribe with lightning-fast AI</div>
          </div>
        </div>

        {/* Reset Button */}
        {showReset && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-center pt-2"
          >
            <Button
              type="button"
              variant="ghost"
              onClick={handleReset}
              className="text-muted-foreground hover:text-foreground transition-all duration-200"
              size="sm"
            >
              <RotateCcw className="mr-2 h-3 w-3" />
              Start over
            </Button>
          </motion.div>
        )}
      </div>
    </Card>
  )
}

export type { URLInputFormProps }