'use client'

import { useState, useEffect } from 'react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Loader2, RotateCcw } from 'lucide-react'

interface URLInputFormProps {
  onSubmit: (url: string, format: 'txt' | 'srt' | 'vtt' | 'json') => void
  disabled?: boolean
  onReset?: () => void
  showReset?: boolean
}

export function URLInputForm({ onSubmit, disabled, onReset, showReset }: URLInputFormProps) {
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<'txt' | 'srt' | 'vtt' | 'json'>('txt')
  const [isValid, setIsValid] = useState<boolean | null>(null)
  const [touched, setTouched] = useState(false)

  // YouTube URL validation regex
  const validateYouTubeUrl = (url: string): boolean => {
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|embed\/|v\/)|youtu\.be\/|m\.youtube\.com\/watch\?v=)[\w-]+(&[\w=]*)?$/
    return youtubeRegex.test(url)
  }

  useEffect(() => {
    if (touched && url) {
      setIsValid(validateYouTubeUrl(url))
    } else if (touched && !url) {
      setIsValid(false)
    }
  }, [url, touched])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (isValid && !disabled) {
      onSubmit(url, format)
    }
  }

  const handleReset = () => {
    setUrl('')
    setFormat('txt')
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
    <Card className="w-full max-w-2xl mx-auto bg-card/50 backdrop-blur-sm border-border/50 shadow-xl">
      <form onSubmit={handleSubmit} className="p-6 space-y-4">
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

        <div className="space-y-2">
          <label htmlFor="output-format" className="text-sm font-medium text-foreground">
            Output Format
          </label>
          <Select value={format} onValueChange={(value: 'txt' | 'srt' | 'vtt' | 'json') => setFormat(value)}>
            <SelectTrigger id="output-format" disabled={disabled}>
              <SelectValue placeholder="Select output format" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="txt">Plain Text (.txt)</SelectItem>
              <SelectItem value="srt">SubRip (.srt)</SelectItem>
              <SelectItem value="vtt">WebVTT (.vtt)</SelectItem>
              <SelectItem value="json">JSON (.json)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex gap-3">
          <Button
            type="submit"
            disabled={!isValid || disabled}
            className="flex-1 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold py-2 px-4 rounded-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {disabled ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              'Transcribe with Groq'
            )}
          </Button>

          {showReset && (
            <Button
              type="button"
              variant="outline"
              onClick={handleReset}
              className="px-4 py-2 border-border/50 hover:bg-muted/50 transition-all duration-200"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          )}
        </div>

        <div className="text-xs text-muted-foreground text-center mt-3">
          Powered by Groq's Lightning-Fast AI
        </div>
      </form>
    </Card>
  )
}