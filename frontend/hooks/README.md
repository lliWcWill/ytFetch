# Real-time Progress Tracking Hooks

This directory contains React hooks for real-time progress tracking using Supabase subscriptions with polling fallback.

## Overview

The real-time system provides:
- Real-time subscriptions to `bulk_jobs` and `video_tasks` tables
- Automatic fallback to polling when real-time fails
- Connection status monitoring and error handling
- Automatic reconnection with exponential backoff
- Type-safe event handling
- Performance optimizations to prevent excessive re-renders

## Core Hooks

### `useSupabaseRealtime`

Low-level hook for managing Supabase real-time subscriptions.

```typescript
import { useSupabaseRealtime } from '@/hooks/useSupabaseRealtime'

const { status, isConnected, error, subscribe, unsubscribe } = useSupabaseRealtime({
  table: 'bulk_jobs',
  filter: 'id=eq.job-123',
  onUpdate: (payload) => {
    console.log('Job updated:', payload.new)
  },
  autoReconnect: true,
  maxReconnectAttempts: 5
})
```

**Options:**
- `table`: Database table to subscribe to
- `filter`: PostgreSQL filter expression (optional)
- `onInsert`, `onUpdate`, `onDelete`: Event handlers
- `autoReconnect`: Enable automatic reconnection (default: true)
- `maxReconnectAttempts`: Max reconnection attempts (default: 5)
- `reconnectDelay`: Base delay between reconnections in ms (default: 2000)

**Returns:**
- `status`: Connection status ('CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'ERROR')
- `isConnected`: Boolean connection state
- `error`: Last error (if any)
- `reconnectAttempts`: Current reconnection attempt count
- `subscribe`, `unsubscribe`: Manual control functions

### `useBulkJobProgress`

High-level hook for tracking bulk job progress with real-time updates and polling fallback.

```typescript
import { useBulkJobProgress } from '@/hooks/useBulkJobProgress'

const { state, stats, refreshAll, cancelJob } = useBulkJobProgress({
  jobId: 'job-123',
  enableRealtime: true,
  enablePolling: true,
  pollingInterval: 5000,
  onJobComplete: (job) => console.log('Job completed!'),
  onProgressUpdate: (stats) => console.log('Progress:', stats)
})
```

**Options:**
- `jobId`: Bulk job ID to track
- `enableRealtime`: Enable real-time subscriptions (default: true)
- `enablePolling`: Enable polling fallback (default: true)
- `pollingInterval`: Polling interval in ms (default: 5000)
- `onJobComplete`, `onJobError`, `onProgressUpdate`: Event callbacks

**Returns:**
- `state`: Current state including job, video tasks, loading status
- `stats`: Computed progress statistics
- `refreshJob`, `refreshTasks`, `refreshAll`: Manual refresh functions
- `cancelJob`: Function to cancel the job

## Convenience Hooks

### `useBulkJobsRealtime`

Specialized hook for bulk jobs table subscriptions.

```typescript
import { useBulkJobsRealtime } from '@/hooks/useSupabaseRealtime'

const { isConnected } = useBulkJobsRealtime(
  (job, eventType) => {
    console.log(`Job ${eventType}:`, job)
  },
  'id=eq.job-123' // Optional filter
)
```

### `useVideoTasksRealtime`

Specialized hook for video tasks table subscriptions.

```typescript
import { useVideoTasksRealtime } from '@/hooks/useSupabaseRealtime'

const { isConnected } = useVideoTasksRealtime(
  (task, eventType) => {
    console.log(`Task ${eventType}:`, task)
  },
  'bulk_job_id=eq.job-123' // Optional filter
)
```

## Usage Patterns

### Basic Progress Tracking

```typescript
import { useBulkJobProgress } from '@/hooks'

function ProgressTracker({ jobId }: { jobId: string }) {
  const { state, stats } = useBulkJobProgress({ jobId })
  
  return (
    <div>
      <h3>Progress: {stats.overallProgress.toFixed(1)}%</h3>
      <p>Completed: {stats.completedTasks}/{stats.totalTasks}</p>
      <p>Status: {state.job?.status}</p>
      <p>Real-time: {state.isRealTimeConnected ? 'Connected' : 'Polling'}</p>
    </div>
  )
}
```

### Advanced Progress Tracking with Callbacks

```typescript
import { useBulkJobProgress } from '@/hooks'
import { toast } from 'react-hot-toast'

function AdvancedProgressTracker({ jobId }: { jobId: string }) {
  const { state, stats, cancelJob } = useBulkJobProgress({
    jobId,
    onJobComplete: (job) => {
      toast.success('Download completed!')
    },
    onJobError: (job, error) => {
      toast.error(`Job failed: ${error}`)
    },
    onProgressUpdate: (stats) => {
      // Update browser title with progress
      document.title = `${stats.overallProgress.toFixed(0)}% - YT Fetch`
    }
  })

  return (
    <div>
      {/* Progress UI */}
      <button onClick={cancelJob}>
        Cancel Job
      </button>
    </div>
  )
}
```

### Real-time Event Monitoring

```typescript
import { useSupabaseRealtime } from '@/hooks'

function RealtimeMonitor() {
  const { status, error, reconnectAttempts } = useSupabaseRealtime({
    table: 'bulk_jobs',
    onUpdate: (payload) => {
      console.log('Real-time update:', payload)
    },
    onInsert: (payload) => {
      console.log('New job created:', payload.new)
    }
  })

  return (
    <div>
      <div>Status: {status}</div>
      {error && <div>Error: {error.message}</div>}
      {reconnectAttempts > 0 && (
        <div>Reconnect attempts: {reconnectAttempts}</div>
      )}
    </div>
  )
}
```

## Error Handling

The hooks provide comprehensive error handling:

1. **Connection Errors**: Automatic reconnection with exponential backoff
2. **Subscription Errors**: Graceful fallback to polling mode
3. **Network Errors**: Retry logic with configurable limits
4. **Data Errors**: Error state exposure for UI handling

## Performance Considerations

1. **Throttling**: Progress updates are throttled to once per second
2. **Cleanup**: Subscriptions are automatically cleaned up on unmount
3. **Memory**: State updates are optimized to prevent unnecessary re-renders
4. **Reconnection**: Exponential backoff prevents connection spam

## Best Practices

1. **Use High-level Hooks**: Prefer `useBulkJobProgress` over low-level hooks
2. **Handle Loading States**: Always handle loading and error states in UI
3. **Cleanup**: Hooks handle cleanup automatically, but avoid creating multiple subscriptions to the same data
4. **Error Handling**: Implement proper error boundaries and user feedback
5. **Performance**: Use React.memo() for components that render frequently

## Troubleshooting

### Real-time Not Working
- Check Supabase RLS policies
- Verify environment variables
- Check network connectivity
- Monitor browser console for errors

### Excessive Re-renders
- Use React.memo() for child components
- Avoid creating new objects in dependency arrays
- Use callback refs instead of inline functions

### Memory Leaks
- Ensure hooks are used in components that unmount properly
- Avoid creating subscriptions in useEffect without cleanup
- Monitor browser memory usage during development

## Environment Setup

1. Copy `.env.local.example` to `.env.local`
2. Add your Supabase project URL and anon key
3. Ensure RLS policies allow read access to `bulk_jobs` and `video_tasks`
4. Test connection with the included example component