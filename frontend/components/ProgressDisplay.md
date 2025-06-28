# ProgressDisplay Component

A polished, animated progress display component for the ytFetch frontend application. This component provides real-time visual feedback during YouTube transcript processing operations.

## Features

### Visual Design
- **Dark Theme**: Gunmetal color scheme using CSS variables
- **Orange Progress Bar**: Uses primary color (Groq orange) for progress indication
- **Stage-Specific Icons**: Lucide React icons for each processing stage
- **Color-Coded Stages**: Different colors for each operation type
- **Responsive Design**: Works on all screen sizes
- **Smooth Animations**: Transition effects for all state changes

### Functional Features
- **Dynamic Visibility**: Show/hide based on `isVisible` prop
- **Smooth Progress**: Animated progress bar updates
- **Stage Management**: Configurable stage properties and icons
- **Skeleton Placeholder**: Professional loading state when not active
- **TypeScript Support**: Full type safety with interfaces
- **WebSocket Ready**: Designed for real-time data integration

## Props Interface

```typescript
interface ProgressDisplayProps {
  stage: string        // Current processing stage
  progress: number     // Progress percentage (0-100)
  message: string      // Status message to display
  isVisible: boolean   // Whether component is visible
}
```

## Available Stages

| Stage | Icon | Color | Description |
|-------|------|-------|-------------|
| `idle` | Play | Muted | Ready state |
| `download` | Download | Blue | Downloading video |
| `transcribe` | FileText | Purple | Converting speech to text |
| `process` | Zap | Yellow | Processing transcript |
| `analyze` | Settings | Cyan | Analyzing content |
| `complete` | CheckCircle | Green | Operation complete |
| `error` | AlertCircle | Red | Error occurred |

## Usage

### Basic Usage
```tsx
import { ProgressDisplay } from "@/components/ProgressDisplay"

<ProgressDisplay
  stage="transcribe"
  progress={65}
  message="Converting speech to text using Groq Whisper..."
  isVisible={true}
/>
```

### With State Management
```tsx
const [progressState, setProgressState] = useState({
  stage: "idle",
  progress: 0,
  message: "Ready to start",
  isVisible: false
})

<ProgressDisplay {...progressState} />
```

### Stage Configuration
```tsx
import { stageConfigs } from "@/components/ProgressDisplay"

// Access stage configuration
const downloadConfig = stageConfigs.download
// { icon: Download, color: "text-blue-400", bgColor: "bg-blue-500/10", label: "Downloading" }
```

## Animation Features

### Progress Animation
- Smooth transitions between progress values
- Configurable animation duration based on progress change
- Visual feedback during updates

### Visibility Animation
- Fade in/out with translate effects
- Skeleton placeholder when hidden
- Smooth transition timing

### Stage Transitions
- Icon changes with smooth transitions
- Color-coded visual feedback
- Loading spinner for active processing

## Styling

### CSS Variables Used
- `--background`: Deep black background
- `--foreground`: Light text color
- `--card`: Gunmetal card background
- `--primary`: Groq orange color
- `--muted-foreground`: Subtle text
- `--border`: Subtle borders

### Responsive Breakpoints
- Mobile: Full width with adjusted padding
- Tablet: Constrained max width
- Desktop: Optimal spacing and sizing

## Integration Notes

### WebSocket Integration (Phase 4)
The component is designed for easy integration with WebSocket updates:

```tsx
// Example WebSocket integration
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8000/progress')
  
  ws.onmessage = (event) => {
    const { stage, progress, message } = JSON.parse(event.data)
    setProgressState({ stage, progress, message, isVisible: true })
  }
  
  return () => ws.close()
}, [])
```

### Error Handling
```tsx
const handleError = (error: string) => {
  setProgressState({
    stage: "error",
    progress: 0,
    message: error,
    isVisible: true
  })
}
```

## Demo

A live demo is available at `/progress-demo` which showcases:
- All available stages
- Auto-play functionality
- Interactive controls
- Real-time progress updates

## Dependencies

- `@radix-ui/react-progress`: Progress bar primitive
- `lucide-react`: Icon components
- `class-variance-authority`: Variant management
- `tailwind-merge`: Class merging utility

## File Structure

```
components/
├── ProgressDisplay.tsx     # Main component
├── ProgressDisplay.md      # This documentation
└── ui/
    ├── card.tsx           # Card components
    ├── progress.tsx       # Progress primitive
    └── badge.tsx          # Badge component
```

## Future Enhancements

- Custom stage configurations
- Progress animation easing options
- Sound notifications for stage changes
- Estimated time remaining display
- Progress history tracking