/**
 * Basic component test to verify TranscriptViewer functionality
 * This is a simple functional test to ensure the component renders correctly
 */

import React from 'react'
import { TranscriptViewer } from './TranscriptViewer'

// Mock component for testing basic rendering
export function TestTranscriptViewer() {
  const [format, setFormat] = React.useState<'txt' | 'srt' | 'vtt' | 'json'>('txt')
  
  const sampleTranscript = `This is a sample transcript for testing.
It contains multiple lines of text.
Word count and other features should work correctly.`

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">TranscriptViewer Test</h2>
      
      <TranscriptViewer
        transcript={sampleTranscript}
        format={format}
        isVisible={true}
        onFormatChange={(newFormat) => setFormat(newFormat)}
      />
      
      <div className="mt-4 text-sm text-muted-foreground">
        <p>Current format: <strong>{format}</strong></p>
        <p>Component should display correctly with all features functional.</p>
      </div>
    </div>
  )
}

export default TestTranscriptViewer