"use client"

import * as React from "react"
import { 
  Download, 
  FileText, 
  Zap, 
  CheckCircle, 
  AlertCircle, 
  Loader2,
  Play,
  Settings
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface ProgressDisplayProps {
  stage: string
  progress: number
  message: string
  isVisible: boolean
}

interface StageConfig {
  icon: React.ComponentType<{ className?: string }>
  color: string
  bgColor: string
  label: string
}

const stageConfigs: Record<string, StageConfig> = {
  download: {
    icon: Download,
    color: "text-blue-400",
    bgColor: "bg-blue-500/10 border-blue-500/20",
    label: "Downloading"
  },
  transcribe: {
    icon: FileText,
    color: "text-purple-400",
    bgColor: "bg-purple-500/10 border-purple-500/20",
    label: "Transcribing"
  },
  process: {
    icon: Zap,
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/10 border-yellow-500/20",
    label: "Processing"
  },
  analyze: {
    icon: Settings,
    color: "text-cyan-400",
    bgColor: "bg-cyan-500/10 border-cyan-500/20",
    label: "Analyzing"
  },
  complete: {
    icon: CheckCircle,
    color: "text-green-400",
    bgColor: "bg-green-500/10 border-green-500/20",
    label: "Complete"
  },
  error: {
    icon: AlertCircle,
    color: "text-red-400",
    bgColor: "bg-red-500/10 border-red-500/20",
    label: "Error"
  },
  idle: {
    icon: Play,
    color: "text-muted-foreground",
    bgColor: "bg-muted/10 border-muted/20",
    label: "Ready"
  }
}

export function ProgressDisplay({ stage, progress, message, isVisible }: ProgressDisplayProps) {
  const [displayProgress, setDisplayProgress] = React.useState(0)
  const [isAnimating, setIsAnimating] = React.useState(false)
  
  // Smooth progress animation
  React.useEffect(() => {
    if (progress !== displayProgress) {
      setIsAnimating(true)
      const difference = Math.abs(progress - displayProgress)
      const duration = Math.min(difference * 10, 1000) // Max 1 second animation
      
      const timer = setTimeout(() => {
        setDisplayProgress(progress)
        setIsAnimating(false)
      }, 50)
      
      return () => clearTimeout(timer)
    }
  }, [progress, displayProgress])

  // Get stage configuration with fallback
  const stageConfig = stageConfigs[stage] || stageConfigs.idle
  const IconComponent = stageConfig.icon

  // Visibility animation
  if (!isVisible) {
    return (
      <div className="opacity-0 translate-y-4 transition-all duration-500 ease-out pointer-events-none">
        <Card className="w-full max-w-2xl mx-auto">
          <CardContent className="p-6">
            <div className="space-y-4">
              {/* Skeleton placeholder */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-muted animate-pulse" />
                  <div className="w-20 h-4 bg-muted rounded animate-pulse" />
                </div>
                <div className="w-12 h-4 bg-muted rounded animate-pulse" />
              </div>
              <div className="w-full h-2 bg-muted rounded-full animate-pulse" />
              <div className="w-3/4 h-4 bg-muted rounded animate-pulse" />
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="opacity-100 translate-y-0 transition-all duration-500 ease-out">
      <Card className="w-full max-w-2xl mx-auto overflow-hidden">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-3 text-lg">
              <div className={cn(
                "relative flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-300",
                stageConfig.bgColor
              )}>
                {stage === "processing" || isAnimating ? (
                  <Loader2 className={cn("w-4 h-4 animate-spin", stageConfig.color)} />
                ) : (
                  <IconComponent className={cn("w-4 h-4", stageConfig.color)} />
                )}
              </div>
              <span className="font-semibold text-foreground">{stageConfig.label}</span>
            </CardTitle>
            
            <Badge 
              variant="secondary" 
              className={cn(
                "px-3 py-1 text-sm font-medium transition-all duration-300",
                stageConfig.bgColor,
                stageConfig.color
              )}
            >
              {Math.round(displayProgress)}%
            </Badge>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-4">
          {/* Progress Bar */}
          <div className="space-y-2">
            <Progress 
              value={displayProgress} 
              className={cn(
                "h-3 transition-all duration-300 ease-out",
                "bg-muted/20",
                "[&>div]:bg-primary" // Override to ensure orange color
              )}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{stageConfig.label}...</span>
              <span>{Math.round(displayProgress)}/100</span>
            </div>
          </div>
          
          {/* Status Message */}
          <div className="min-h-[1.5rem] flex items-center">
            <p className={cn(
              "text-sm transition-all duration-300",
              message ? "text-foreground" : "text-muted-foreground"
            )}>
              {message || "Waiting for updates..."}
            </p>
          </div>
        </CardContent>
        
        {/* Animated progress indicator */}
        {displayProgress > 0 && displayProgress < 100 && (
          <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-primary to-transparent opacity-50">
            <div className="h-full w-full bg-gradient-to-r from-primary to-primary/50 animate-pulse" />
          </div>
        )}
      </Card>
    </div>
  )
}

// Export the stage configs for external use if needed
export { stageConfigs }
export type { ProgressDisplayProps, StageConfig }