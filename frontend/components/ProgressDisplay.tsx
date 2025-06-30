"use client"

import * as React from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Download, 
  FileText, 
  Zap, 
  CheckCircle, 
  AlertCircle, 
  Loader2,
  Play,
  Settings,
  Coffee,
  Sparkles,
  Cpu,
  Headphones,
  Music,
  Wand2,
  Brain,
  Rocket
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface ProgressDisplayProps {
  currentStage: string
  progress: number
  message: string
  jobId?: string | null
  showDetails?: boolean
}

interface StageConfig {
  icon: React.ComponentType<{ className?: string }>
  color: string
  bgColor: string
  label: string
  animation?: string
}

// Fun preprocessing messages that rotate
const preprocessingMessages = [
  { text: "Optimizing audio quality...", icon: Headphones },
  { text: "Preparing for lightning-fast transcription...", icon: Zap },
  { text: "Almost there, grab a coffee ☕", icon: Coffee },
  { text: "Enhancing audio clarity...", icon: Sparkles },
  { text: "Running AI magic...", icon: Cpu },
  { text: "Fine-tuning for best results...", icon: Settings },
  { text: "Applying sonic enhancement...", icon: Music },
  { text: "Warming up the AI engines...", icon: Rocket },
  { text: "Making it sound crystal clear...", icon: Wand2 },
  { text: "Processing with Groq power...", icon: Brain }
]

const largeVideoMessages = [
  { text: "Large video detected, this might take a moment...", icon: AlertCircle },
  { text: "Processing extra content, worth the wait!", icon: Sparkles },
  { text: "Big video = Big transcript coming up!", icon: FileText },
  { text: "Quality takes time, excellence incoming...", icon: Wand2 },
  { text: "Handling large file like a boss...", icon: Rocket }
]

const downloadMessages = [
  "Fetching audio from YouTube...",
  "Downloading at maximum speed...",
  "Grabbing that sweet audio...",
  "YouTube servers are cooperating nicely...",
  "Download in progress, looking good..."
]

const stageConfigs: Record<string, StageConfig> = {
  downloading: {
    icon: Download,
    color: "text-blue-500",
    bgColor: "bg-blue-500/10 border-blue-500/20",
    label: "Downloading Audio",
    animation: "animate-pulse"
  },
  preprocessing: {
    icon: Cpu,
    color: "text-amber-500",
    bgColor: "bg-amber-500/10 border-amber-500/20",
    label: "Preprocessing Audio",
    animation: "animate-spin"
  },
  processing: {
    icon: Settings,
    color: "text-purple-500",
    bgColor: "bg-purple-500/10 border-purple-500/20",
    label: "Processing",
    animation: "animate-spin"
  },
  transcribing: {
    icon: FileText,
    color: "text-orange-500",
    bgColor: "bg-orange-500/10 border-orange-500/20",
    label: "Transcribing with AI",
    animation: "animate-pulse"
  },
  initializing: {
    icon: Play,
    color: "text-green-500",
    bgColor: "bg-green-500/10 border-green-500/20",
    label: "Initializing",
    animation: "animate-pulse"
  },
  connecting: {
    icon: Zap,
    color: "text-yellow-500",
    bgColor: "bg-yellow-500/10 border-yellow-500/20",
    label: "Connecting",
    animation: "animate-pulse"
  },
  complete: {
    icon: CheckCircle,
    color: "text-green-500",
    bgColor: "bg-green-500/10 border-green-500/20",
    label: "Complete",
    animation: ""
  },
  error: {
    icon: AlertCircle,
    color: "text-red-500",
    bgColor: "bg-red-500/10 border-red-500/20",
    label: "Error",
    animation: ""
  },
  waiting: {
    icon: Play,
    color: "text-muted-foreground",
    bgColor: "bg-muted/10 border-muted/20",
    label: "Ready",
    animation: ""
  }
}

export function ProgressDisplay({ currentStage, progress, message, jobId, showDetails }: ProgressDisplayProps) {
  const [displayProgress, setDisplayProgress] = React.useState(0)
  const [messageIndex, setMessageIndex] = React.useState(0)
  const [downloadMessageIndex, setDownloadMessageIndex] = React.useState(0)
  
  // Parse duration from message if available
  const duration = React.useMemo(() => {
    const durationMatch = message.match(/duration:\s*(\d+)s/);
    return durationMatch ? parseInt(durationMatch[1]) : 0;
  }, [message]);
  
  // Determine if it's a large video (> 45 minutes)
  const isLargeVideo = duration > 2700 // 45 minutes in seconds
  
  // Rotate fun messages for preprocessing stage
  React.useEffect(() => {
    if (currentStage === "preprocessing") {
      const messages = isLargeVideo ? [...preprocessingMessages, ...largeVideoMessages] : preprocessingMessages;
      
      const interval = setInterval(() => {
        setMessageIndex((prev) => (prev + 1) % messages.length);
      }, 3000);
      
      return () => clearInterval(interval);
    } else if (currentStage === "downloading") {
      const interval = setInterval(() => {
        setDownloadMessageIndex((prev) => (prev + 1) % downloadMessages.length);
      }, 2500);
      
      return () => clearInterval(interval);
    }
  }, [currentStage, isLargeVideo]);
  
  // Smooth progress animation
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDisplayProgress(progress);
    }, 100);
    
    return () => clearTimeout(timer);
  }, [progress]);

  // Get stage configuration with fallback
  const stageConfig = stageConfigs[currentStage] || stageConfigs.waiting;
  const IconComponent = stageConfig.icon;
  
  // Get appropriate message
  const displayMessage = React.useMemo(() => {
    if (currentStage === "preprocessing") {
      const messages = isLargeVideo ? [...preprocessingMessages, ...largeVideoMessages] : preprocessingMessages;
      return messages[messageIndex % messages.length].text;
    } else if (currentStage === "downloading" && !message.includes("Audio downloaded")) {
      return downloadMessages[downloadMessageIndex % downloadMessages.length];
    }
    return message;
  }, [currentStage, message, messageIndex, downloadMessageIndex, isLargeVideo]);

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={currentStage}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      >
        <Card className="w-full max-w-2xl mx-auto overflow-hidden transition-all duration-300 bg-gradient-to-b from-card to-card/95 border-border/50 shadow-[0_8px_30px_rgb(0,0,0,0.12)] hover:shadow-[0_8px_40px_rgb(0,0,0,0.15)]">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-3 text-lg">
                <motion.div 
                  className={cn(
                    "relative flex items-center justify-center w-10 h-10 rounded-lg transition-all duration-300",
                    stageConfig.bgColor
                  )}
                  animate={
                    currentStage === "preprocessing" ? {
                      rotate: [0, 360],
                      scale: [1, 1.1, 1],
                    } : currentStage === "downloading" ? {
                      y: [0, -5, 0],
                    } : currentStage === "transcribing" ? {
                      scale: [1, 1.05, 1],
                    } : {}
                  }
                  transition={
                    currentStage === "preprocessing" ? {
                      rotate: { duration: 2, repeat: Infinity, ease: "linear" },
                      scale: { duration: 1, repeat: Infinity }
                    } : currentStage === "downloading" ? {
                      y: { duration: 1, repeat: Infinity, ease: "easeInOut" }
                    } : currentStage === "transcribing" ? {
                      scale: { duration: 1.5, repeat: Infinity, ease: "easeInOut" }
                    } : {}
                  }
                >
                  <IconComponent className={cn("w-5 h-5", stageConfig.color)} />
                </motion.div>
                <span className="font-semibold text-foreground">{stageConfig.label}</span>
              </CardTitle>
              
              <motion.div
                animate={{ scale: [0.95, 1, 0.95] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
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
              </motion.div>
            </div>
          </CardHeader>
          
          <CardContent className="space-y-4">
            {/* Progress Bar with animation */}
            <div className="space-y-2">
              <div className="relative">
                <Progress 
                  value={displayProgress} 
                  className={cn(
                    "h-3 transition-all duration-500 ease-out",
                    "bg-muted/20"
                  )}
                />
                {/* Animated shimmer effect */}
                {displayProgress > 0 && displayProgress < 100 && (
                  <motion.div
                    className="absolute inset-0 h-3 overflow-hidden rounded-full"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                  >
                    <motion.div
                      className="h-full w-1/3 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                      animate={{ x: ["0%", "400%"] }}
                      transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                    />
                  </motion.div>
                )}
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{stageConfig.label}...</span>
                <span>{Math.round(displayProgress)}/100</span>
              </div>
            </div>
            
            {/* Animated Status Message */}
            <AnimatePresence mode="wait">
              <motion.div
                key={displayMessage}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.3 }}
                className="min-h-[1.5rem] flex items-center"
              >
                <p className={cn(
                  "text-sm transition-all duration-300",
                  displayMessage ? "text-foreground" : "text-muted-foreground"
                )}>
                  {displayMessage || "Waiting for updates..."}
                </p>
              </motion.div>
            </AnimatePresence>
            
            {/* Show job ID if details enabled */}
            {showDetails && jobId && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-xs text-muted-foreground"
              >
                Job ID: {jobId}
              </motion.div>
            )}
            
            {/* Fun animation for different stages */}
            {currentStage === "preprocessing" && (
              <motion.div className="flex justify-center gap-1 mt-2">
                {[...Array(3)].map((_, i) => (
                  <motion.div
                    key={i}
                    className="w-2 h-2 rounded-full bg-amber-500"
                    animate={{ y: [0, -10, 0] }}
                    transition={{
                      duration: 0.6,
                      repeat: Infinity,
                      delay: i * 0.1,
                      ease: "easeInOut"
                    }}
                  />
                ))}
              </motion.div>
            )}
            
            {currentStage === "transcribing" && (
              <motion.div className="flex justify-center gap-2 mt-2">
                <motion.span
                  className="text-2xl"
                  animate={{ rotate: [0, 360] }}
                  transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                >
                  🎙️
                </motion.span>
                <motion.span
                  className="text-2xl"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  ✨
                </motion.span>
                <motion.span
                  className="text-2xl"
                  animate={{ rotate: [0, -360] }}
                  transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                >
                  📝
                </motion.span>
              </motion.div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </AnimatePresence>
  );
}

// Export the stage configs for external use if needed
export { stageConfigs }
export type { ProgressDisplayProps, StageConfig }