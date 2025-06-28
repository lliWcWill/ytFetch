/**
 * Example usage of TranscriptViewer component
 * 
 * This file demonstrates how to integrate the TranscriptViewer component
 * into your application with proper state management and event handling.
 */

"use client"

import * as React from "react"
import { TranscriptViewer } from "./TranscriptViewer"

// Example transcript data for different formats
const exampleTranscripts = {
  txt: `Welcome to this video tutorial. Today we'll be learning about React components and how to build reusable UI elements. 

Let's start with the basics of component architecture and then move on to more advanced patterns like composition and state management.

Throughout this tutorial, we'll cover best practices for writing clean, maintainable React code that scales well in larger applications.`,

  srt: `1
00:00:00,000 --> 00:00:03,500
Welcome to this video tutorial.

2
00:00:03,500 --> 00:00:07,200
Today we'll be learning about React components
and how to build reusable UI elements.

3
00:00:07,200 --> 00:00:11,800
Let's start with the basics of component architecture
and then move on to more advanced patterns.

4
00:00:11,800 --> 00:00:16,300
Throughout this tutorial, we'll cover best practices
for writing clean, maintainable React code.`,

  vtt: `WEBVTT

NOTE
This is an example WebVTT file

00:00:00.000 --> 00:00:03.500
Welcome to this video tutorial.

00:00:03.500 --> 00:00:07.200
Today we'll be learning about React components
and how to build reusable UI elements.

00:00:07.200 --> 00:00:11.800
Let's start with the basics of component architecture
and then move on to more advanced patterns.

00:00:11.800 --> 00:00:16.300
Throughout this tutorial, we'll cover best practices
for writing clean, maintainable React code.`,

  json: `[
  {
    "start": 0.0,
    "end": 3.5,
    "text": "Welcome to this video tutorial."
  },
  {
    "start": 3.5,
    "end": 7.2,
    "text": "Today we'll be learning about React components and how to build reusable UI elements."
  },
  {
    "start": 7.2,
    "end": 11.8,
    "text": "Let's start with the basics of component architecture and then move on to more advanced patterns."
  },
  {
    "start": 11.8,
    "end": 16.3,
    "text": "Throughout this tutorial, we'll cover best practices for writing clean, maintainable React code."
  }
]`
}

export function TranscriptViewerExample() {
  const [format, setFormat] = React.useState<'txt' | 'srt' | 'vtt' | 'json'>('txt')
  const [isVisible, setIsVisible] = React.useState(true)
  const [currentTranscript, setCurrentTranscript] = React.useState(exampleTranscripts.txt)

  // Update transcript when format changes
  React.useEffect(() => {
    setCurrentTranscript(exampleTranscripts[format])
  }, [format])

  const handleFormatChange = (newFormat: 'txt' | 'srt' | 'vtt' | 'json') => {
    setFormat(newFormat)
  }

  return (
    <div className="w-full max-w-4xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">TranscriptViewer Example</h2>
        <button
          onClick={() => setIsVisible(!isVisible)}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
        >
          {isVisible ? 'Hide' : 'Show'} Transcript
        </button>
      </div>

      <TranscriptViewer
        transcript={currentTranscript}
        format={format}
        isVisible={isVisible}
        onFormatChange={handleFormatChange}
      />

      <div className="text-sm text-muted-foreground space-y-2">
        <p><strong>Features demonstrated:</strong></p>
        <ul className="list-disc list-inside space-y-1 ml-4">
          <li>Format switching between TXT, SRT, VTT, and JSON</li>
          <li>Word count calculation for different formats</li>
          <li>Copy to clipboard functionality with visual feedback</li>
          <li>Download as file with proper MIME types</li>
          <li>Show/hide animation transitions</li>
          <li>Syntax highlighting for structured formats</li>
          <li>Responsive design with dark theme styling</li>
        </ul>
      </div>
    </div>
  )
}

export default TranscriptViewerExample