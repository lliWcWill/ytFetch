"use client"

import * as React from "react"
import { ProgressDisplay } from "@/components/ProgressDisplay"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

const demoStages = [
  { stage: "idle", message: "Ready to start processing", progress: 0 },
  { stage: "download", message: "Downloading video content...", progress: 25 },
  { stage: "transcribe", message: "Converting speech to text using Groq Whisper...", progress: 60 },
  { stage: "process", message: "Processing and formatting transcript...", progress: 85 },
  { stage: "complete", message: "Transcript ready for download!", progress: 100 },
  { stage: "error", message: "Failed to process video. Please try again.", progress: 45 },
]

export default function ProgressDemo() {
  const [currentStageIndex, setCurrentStageIndex] = React.useState(0)
  const [isVisible, setIsVisible] = React.useState(true)
  const [isAutoPlaying, setIsAutoPlaying] = React.useState(false)

  const currentStage = demoStages[currentStageIndex]

  // Auto-play demo
  React.useEffect(() => {
    if (isAutoPlaying) {
      const timer = setInterval(() => {
        setCurrentStageIndex((prev) => {
          const next = (prev + 1) % (demoStages.length - 1) // Skip error stage in auto-play
          return next
        })
      }, 2000)
      
      return () => clearInterval(timer)
    }
  }, [isAutoPlaying])

  const nextStage = () => {
    setCurrentStageIndex((prev) => (prev + 1) % demoStages.length)
  }

  const toggleAutoPlay = () => {
    setIsAutoPlaying(!isAutoPlaying)
  }

  const toggleVisibility = () => {
    setIsVisible(!isVisible)
  }

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold text-foreground">
            ProgressDisplay Component Demo
          </h1>
          <p className="text-muted-foreground text-lg">
            Interactive demonstration of the YouTube transcript progress display
          </p>
        </div>

        {/* Controls */}
        <Card>
          <CardHeader>
            <CardTitle>Demo Controls</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-4">
            <Button onClick={nextStage} variant="default">
              Next Stage
            </Button>
            <Button 
              onClick={toggleAutoPlay} 
              variant={isAutoPlaying ? "destructive" : "secondary"}
            >
              {isAutoPlaying ? "Stop Auto-Play" : "Start Auto-Play"}
            </Button>
            <Button onClick={toggleVisibility} variant="outline">
              {isVisible ? "Hide Progress" : "Show Progress"}
            </Button>
          </CardContent>
        </Card>

        {/* Progress Display Component */}
        <div className="space-y-4">
          <h2 className="text-2xl font-semibold text-center">Live Demo</h2>
          <ProgressDisplay
            stage={currentStage.stage}
            progress={currentStage.progress}
            message={currentStage.message}
            isVisible={isVisible}
          />
        </div>

        {/* Stage Information */}
        <Card>
          <CardHeader>
            <CardTitle>Current Stage Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="font-semibold text-muted-foreground">Stage:</span>
                <p className="text-foreground">{currentStage.stage}</p>
              </div>
              <div>
                <span className="font-semibold text-muted-foreground">Progress:</span>
                <p className="text-foreground">{currentStage.progress}%</p>
              </div>
              <div>
                <span className="font-semibold text-muted-foreground">Visible:</span>
                <p className="text-foreground">{isVisible ? "Yes" : "No"}</p>
              </div>
            </div>
            <div>
              <span className="font-semibold text-muted-foreground">Message:</span>
              <p className="text-foreground">{currentStage.message}</p>
            </div>
          </CardContent>
        </Card>

        {/* Features Overview */}
        <Card>
          <CardHeader>
            <CardTitle>Component Features</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <h3 className="font-semibold text-lg">Visual Features</h3>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li>• Dark theme with gunmetal colors</li>
                  <li>• Orange progress bar using CSS variables</li>
                  <li>• Stage-specific icons from Lucide React</li>
                  <li>• Color-coded stages (download=blue, transcribe=purple, etc.)</li>
                  <li>• Smooth animations and transitions</li>
                  <li>• Responsive design</li>
                </ul>
              </div>
              <div className="space-y-3">
                <h3 className="font-semibold text-lg">Functional Features</h3>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li>• Show/hide based on isVisible prop</li>
                  <li>• Smooth progress animations</li>
                  <li>• Skeleton placeholder when not active</li>
                  <li>• TypeScript interfaces for type safety</li>
                  <li>• Configurable stage properties</li>
                  <li>• Ready for WebSocket integration</li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Code Example */}
        <Card>
          <CardHeader>
            <CardTitle>Usage Example</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="bg-muted p-4 rounded-lg text-sm overflow-x-auto">
              <code>{`import { ProgressDisplay } from "@/components/ProgressDisplay"

<ProgressDisplay
  stage="transcribe"
  progress={65}
  message="Converting speech to text using Groq Whisper..."
  isVisible={true}
/>`}</code>
            </pre>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}