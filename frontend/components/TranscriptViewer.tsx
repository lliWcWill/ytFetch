"use client"

import * as React from "react"
import { 
  FileText, 
  FileVideo, 
  Download, 
  Copy, 
  Check, 
  Hash,
  Eye,
  EyeOff 
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"
import { Button } from "./ui/button"
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "./ui/select"
import { Textarea } from "./ui/textarea"
import { cn } from "@/lib/utils"

// Props interface
interface TranscriptViewerProps {
  transcript: string
  format: 'txt' | 'srt' | 'vtt' | 'json'
  isVisible: boolean
  onFormatChange: (format: 'txt' | 'srt' | 'vtt' | 'json') => void
}

// Format configuration
const formatConfig = {
  txt: {
    label: 'Plain Text',
    icon: FileText,
    extension: 'txt',
    mimeType: 'text/plain',
    syntax: false
  },
  srt: {
    label: 'SubRip (SRT)',
    icon: FileVideo,
    extension: 'srt',
    mimeType: 'application/x-subrip',
    syntax: true
  },
  vtt: {
    label: 'WebVTT',
    icon: FileVideo,
    extension: 'vtt',
    mimeType: 'text/vtt',
    syntax: true
  },
  json: {
    label: 'JSON',
    icon: Hash,
    extension: 'json',
    mimeType: 'application/json',
    syntax: true
  }
} as const

export function TranscriptViewer({ 
  transcript, 
  format, 
  isVisible, 
  onFormatChange 
}: TranscriptViewerProps) {
  const [isCopied, setIsCopied] = React.useState(false)
  const [wordCount, setWordCount] = React.useState(0)
  const [isDownloading, setIsDownloading] = React.useState(false)

  // Calculate word count whenever transcript changes
  React.useEffect(() => {
    if (transcript) {
      // Remove JSON formatting, timestamps, and subtitle numbers for accurate word count
      let textOnly = transcript
      
      try {
        // If it's JSON, extract just the text content
        if (format === 'json') {
          const parsed = JSON.parse(transcript)
          if (Array.isArray(parsed)) {
            textOnly = parsed.map(item => item.text || item.content || '').join(' ')
          } else if (parsed.text) {
            textOnly = parsed.text
          }
        } else if (format === 'srt' || format === 'vtt') {
          // Remove subtitle numbers, timestamps, and formatting
          textOnly = transcript
            .replace(/^\d+$/gm, '') // Remove subtitle numbers
            .replace(/\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3}/g, '') // Remove timestamps
            .replace(/^WEBVTT\s*$/m, '') // Remove WebVTT header
            .replace(/^NOTE.*$/gm, '') // Remove WebVTT notes
            .replace(/^\s*$/gm, '') // Remove empty lines
        }
        
        // Count words
        const words = textOnly
          .trim()
          .split(/\s+/)
          .filter(word => word.length > 0)
        
        setWordCount(words.length)
      } catch {
        // Fallback word count for malformed content
        const words = transcript
          .trim()
          .split(/\s+/)
          .filter(word => word.length > 0)
        setWordCount(words.length)
      }
    } else {
      setWordCount(0)
    }
  }, [transcript, format])

  // Copy to clipboard functionality
  const handleCopy = async () => {
    if (!transcript) return
    
    try {
      await navigator.clipboard.writeText(transcript)
      setIsCopied(true)
      setTimeout(() => setIsCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy to clipboard:', error)
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = transcript
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      setIsCopied(true)
      setTimeout(() => setIsCopied(false), 2000)
    }
  }

  // Download functionality
  const handleDownload = async () => {
    if (!transcript) return
    
    setIsDownloading(true)
    
    try {
      const config = formatConfig[format]
      const blob = new Blob([transcript], { type: config.mimeType })
      const url = URL.createObjectURL(blob)
      
      const link = document.createElement('a')
      link.href = url
      link.download = `transcript.${config.extension}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to download transcript:', error)
    } finally {
      setIsDownloading(false)
    }
  }

  // Format the transcript content for display
  const formatTranscriptForDisplay = (content: string, currentFormat: string): string => {
    if (!content) return ''
    
    try {
      if (currentFormat === 'json') {
        // Pretty print JSON
        const parsed = JSON.parse(content)
        return JSON.stringify(parsed, null, 2)
      }
    } catch {
      // If JSON parsing fails, return as-is
    }
    
    return content
  }

  // Don't render if not visible
  if (!isVisible) {
    return null
  }

  const currentConfig = formatConfig[format]
  const IconComponent = currentConfig.icon
  const displayContent = formatTranscriptForDisplay(transcript, format)

  return (
    <div className={cn(
      "w-full transition-all duration-300 ease-in-out",
      isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
    )}>
      <Card className="bg-card border-border">
        <CardHeader className="border-b border-border">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-lg font-semibold">
              <IconComponent className="h-5 w-5 text-primary" />
              Transcript Viewer
            </CardTitle>
            <div className="flex items-center gap-2">
              {isVisible ? (
                <Eye className="h-4 w-4 text-muted-foreground" />
              ) : (
                <EyeOff className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
          </div>
          
          <div className="flex items-center justify-between gap-4 pt-2">
            {/* Format Selector */}
            <div className="flex items-center gap-2">
              <label htmlFor="format-select" className="text-sm font-medium text-muted-foreground">
                Format:
              </label>
              <Select
                value={format}
                onValueChange={(value) => onFormatChange(value as 'txt' | 'srt' | 'vtt' | 'json')}
              >
                <SelectTrigger id="format-select" className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(formatConfig).map(([key, config]) => {
                    const Icon = config.icon
                    return (
                      <SelectItem key={key} value={key}>
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4" />
                          <span>{config.label}</span>
                        </div>
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
            </div>

            {/* Word Count */}
            <div className="flex items-center gap-1 text-sm text-muted-foreground">
              <span>{wordCount.toLocaleString()} words</span>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {/* Transcript Display */}
          <div className="relative">
            <Textarea
              value={displayContent}
              readOnly
              className={cn(
                "min-h-[400px] max-h-[600px] resize-none border-0 rounded-none bg-muted/30 font-mono text-sm leading-relaxed",
                "focus-visible:ring-0 focus-visible:ring-offset-0",
                currentConfig.syntax && "whitespace-pre-wrap"
              )}
              placeholder={
                !transcript 
                  ? "No transcript available. Generate a transcript to view it here."
                  : "Loading transcript..."
              }
            />
            
            {/* Action Buttons */}
            <div className="absolute top-2 right-2 flex gap-2">
              {/* Copy Button */}
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopy}
                disabled={!transcript}
                className="h-8 w-8 p-0 bg-background/80 backdrop-blur-sm border-border/50 hover:bg-accent/50"
                title="Copy to clipboard"
              >
                {isCopied ? (
                  <Check className="h-3.5 w-3.5 text-green-500" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
              </Button>

              {/* Download Button */}
              <Button
                variant="default"
                size="sm"
                onClick={handleDownload}
                disabled={!transcript || isDownloading}
                className={cn(
                  "h-8 px-3 bg-primary text-primary-foreground hover:bg-primary/90",
                  "shadow-sm transition-all duration-200",
                  isDownloading && "opacity-75 cursor-not-allowed"
                )}
                title={`Download as ${currentConfig.extension.toUpperCase()}`}
              >
                <Download className={cn(
                  "h-3.5 w-3.5 mr-1.5",
                  isDownloading && "animate-pulse"
                )} />
                <span className="text-xs font-medium">
                  {isDownloading ? 'Downloading...' : currentConfig.extension.toUpperCase()}
                </span>
              </Button>
            </div>
          </div>

          {/* Status Bar */}
          <div className="flex items-center justify-between px-4 py-2 bg-muted/20 border-t border-border text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              <span>
                Format: <span className="font-medium text-foreground">{currentConfig.label}</span>
              </span>
              <span>
                Size: <span className="font-medium text-foreground">
                  {transcript ? `${(transcript.length / 1024).toFixed(1)}KB` : '0KB'}
                </span>
              </span>
            </div>
            
            {isCopied && (
              <div className="flex items-center gap-1 text-green-500 animate-in fade-in duration-200">
                <Check className="h-3 w-3" />
                <span>Copied to clipboard</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default TranscriptViewer