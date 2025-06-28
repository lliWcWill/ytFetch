# TranscriptViewer Component

A comprehensive React component for displaying, formatting, and managing transcript content with multiple output formats and advanced features.

## Features

- **Multi-format Support**: TXT, SRT, VTT, and JSON formats
- **Interactive Format Switching**: Seamless switching between formats with proper syntax highlighting
- **Copy to Clipboard**: One-click copying with visual feedback
- **Download Functionality**: Download transcripts as files with proper MIME types
- **Word Count**: Real-time word count calculation for all formats
- **Dark Theme**: Gunmetal backgrounds with orange Groq-style branding
- **Responsive Design**: Works on all screen sizes
- **Accessibility**: Proper ARIA labels and keyboard navigation
- **Animations**: Smooth show/hide transitions and loading states

## Props Interface

```typescript
interface TranscriptViewerProps {
  transcript: string                           // The transcript content to display
  format: 'txt' | 'srt' | 'vtt' | 'json'     // Current format
  isVisible: boolean                           // Show/hide the component
  onFormatChange: (format: string) => void     // Format change callback
}
```

## Usage Example

```tsx
import { TranscriptViewer } from '@/components'

function MyComponent() {
  const [transcript, setTranscript] = useState('')
  const [format, setFormat] = useState<'txt' | 'srt' | 'vtt' | 'json'>('txt')
  const [isVisible, setIsVisible] = useState(true)

  const handleFormatChange = (newFormat: 'txt' | 'srt' | 'vtt' | 'json') => {
    setFormat(newFormat)
    // Optionally transform transcript data based on format
  }

  return (
    <TranscriptViewer
      transcript={transcript}
      format={format}
      isVisible={isVisible}
      onFormatChange={handleFormatChange}
    />
  )
}
```

## Format Support

### TXT (Plain Text)
- Simple text format
- Basic word counting
- No special formatting

### SRT (SubRip Subtitle)
- Numbered subtitle blocks
- Timestamp format: `HH:MM:SS,mmm --> HH:MM:SS,mmm`
- Proper subtitle parsing for word count

### VTT (WebVTT)
- Web Video Text Tracks format
- Timestamp format: `HH:MM:SS.mmm --> HH:MM:SS.mmm`
- Supports WebVTT headers and notes

### JSON
- Structured data format
- Pretty-printed display
- Extracts text content for word counting
- Expected structure:
  ```json
  [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "Transcript text here"
    }
  ]
  ```

## Styling

The component uses CSS variables for theming:

```css
/* Key CSS variables used */
--color-background: Deep black backgrounds
--color-card: Gunmetal card backgrounds
--color-primary: Orange Groq branding
--color-border: Subtle borders
--color-muted-foreground: Secondary text
```

## Component Structure

```
TranscriptViewer
├── Card Container
│   ├── CardHeader
│   │   ├── Title with format icon
│   │   ├── Format selector dropdown
│   │   └── Word count display
│   ├── CardContent
│   │   ├── Textarea (monospace, readonly)
│   │   ├── Action buttons (copy, download)
│   │   └── Status bar (format info, file size)
```

## Advanced Features

### Word Count Calculation
- Automatically strips formatting, timestamps, and metadata
- Accurate counting across all formats
- Real-time updates when content changes

### Copy to Clipboard
- Uses modern Clipboard API with fallback
- Visual feedback with check icon
- 2-second success indicator

### Download Functionality
- Generates appropriate file extensions
- Sets correct MIME types for each format
- Handles large files efficiently

### Error Handling
- Graceful degradation for malformed content
- Fallback mechanisms for older browsers
- TypeScript ensures type safety

## Dependencies

- React 18+
- lucide-react (icons)
- shadcn/ui components:
  - Card
  - Button
  - Select
  - Textarea
- Tailwind CSS
- clsx/tailwind-merge for styling

## Accessibility

- Proper ARIA labels
- Keyboard navigation support
- High contrast ratios
- Screen reader friendly
- Focus indicators

## Performance

- Efficient re-rendering with React.memo patterns
- Debounced word count calculations
- Optimized for large transcript files
- Minimal DOM updates

## Browser Support

- Modern browsers with ES2018+ support
- Clipboard API (with fallback for older browsers)
- CSS custom properties support
- CSS Grid and Flexbox

## Customization

The component can be customized by:
1. Modifying CSS variables for theming
2. Extending the format configuration object
3. Adding custom icons or styling
4. Implementing additional download formats

## File Structure

```
components/
├── TranscriptViewer.tsx        # Main component
├── TranscriptViewer.example.tsx # Usage example
├── TranscriptViewer.test.tsx   # Basic test
└── TranscriptViewer.md         # This documentation
```

## Notes

- The component is fully TypeScript typed
- Uses "use client" directive for Next.js App Router compatibility
- Follows React best practices and hooks patterns
- Designed for integration with video/audio transcription workflows