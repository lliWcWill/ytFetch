# Progress Callbacks in YouTubeService

## Overview

The YouTubeService now supports optional progress callbacks that provide real-time updates during long-running operations like video information fetching, transcript retrieval, and audio downloading. This feature enables better user experience through progress tracking, status updates, and integration with web interfaces.

## Feature Highlights

✅ **Backward Compatible**: All progress callbacks are optional - existing code continues to work unchanged  
✅ **Real-time Progress**: Detailed progress updates with percentages, speeds, and ETAs  
✅ **Stage-based Tracking**: Different stages for different operation phases  
✅ **yt-dlp Integration**: Native integration with yt-dlp's progress hooks for accurate download progress  
✅ **Strategy-specific**: Progress reporting for all 6 download strategies  
✅ **Web-ready**: Perfect for WebSocket, SSE, or API integration  

## Progress Callback Signature

```python
def progress_callback(stage: str, progress: float, message: str) -> None:
    """
    Args:
        stage: Current operation stage ("video_info", "transcript", "setup", "download", "downloading")
        progress: Completion percentage from 0.0 to 1.0
        message: Human-readable status description
    """
    pass
```

## Operation Stages

| Stage | Description | Progress Range | Example Messages |
|-------|-------------|----------------|------------------|
| `video_info` | Fetching video metadata | 0.0 - 1.0 | "Extracting metadata from YouTube..." |
| `transcript` | Fetching transcript | 0.0 - 1.0 | "Fetching transcript via proxy..." |
| `setup` | Preparing download | 0.0 - 0.2 | "Getting video information...", "Found cookie file" |
| `download` | Strategy selection | 0.2 - 0.9 | "Strategy 1: yt-dlp with cookie authentication..." |
| `downloading` | Active download | 0.0 - 1.0 | "iOS Client: 15.2/45.8 MB at 2.3 MB/s (ETA: 0:13)" |

## Method Support

### get_video_info()
```python
video_info = await youtube_service.get_video_info(
    video_id, 
    progress_callback=my_callback  # Optional
)
```

**Progress Updates:**
- Metadata extraction from YouTube
- Video information processing
- Success/failure status

### fetch_transcript_segments()
```python
segments, language, error = await youtube_service.fetch_transcript_segments(
    video_id,
    progress_callback=my_callback  # Optional
)
```

**Progress Updates:**
- API configuration loading
- Proxy setup (if using Webshare)
- Transcript fetching
- Data validation and conversion

### download_audio_as_mp3_enhanced()
```python
audio_path = await youtube_service.download_audio_as_mp3_enhanced(
    video_id,
    output_dir="/tmp",
    video_title="My Video",
    progress_callback=my_callback  # Optional
)
```

**Progress Updates:**
- Setup phase (cookie detection, video info)
- Strategy attempts (6 different strategies)
- Real-time download progress with yt-dlp integration
- Download speed, ETA, and file sizes

## Example Implementations

### 1. Simple Console Progress Bar

```python
def console_progress(stage: str, progress: float, message: str):
    """Simple console progress bar."""
    percentage = int(progress * 100)
    bar_length = 30
    filled_length = int(bar_length * progress)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    print(f"[{stage.upper():>11}] [{bar}] {percentage:3d}% - {message}")

# Usage
audio_path = await youtube_service.download_audio_as_mp3_enhanced(
    video_id, progress_callback=console_progress
)
```

### 2. WebSocket Real-time Updates

```python
class WebSocketProgressHandler:
    def __init__(self, websocket):
        self.websocket = websocket
    
    async def progress_callback(self, stage: str, progress: float, message: str):
        """Send progress via WebSocket."""
        await self.websocket.send_json({
            "stage": stage,
            "progress": progress,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })

# Usage in FastAPI
@app.websocket("/download/{video_id}")
async def download_with_progress(websocket: WebSocket, video_id: str):
    await websocket.accept()
    handler = WebSocketProgressHandler(websocket)
    
    audio_path = await youtube_service.download_audio_as_mp3_enhanced(
        video_id, progress_callback=handler.progress_callback
    )
```

### 3. Database Progress Tracking

```python
async def database_progress(job_id: str):
    """Create a progress callback that updates database."""
    async def callback(stage: str, progress: float, message: str):
        await db.execute(
            "UPDATE jobs SET stage=?, progress=?, message=?, updated_at=? WHERE id=?",
            (stage, progress, message, datetime.utcnow(), job_id)
        )
    return callback

# Usage
progress_cb = await database_progress("job_123")
audio_path = await youtube_service.download_audio_as_mp3_enhanced(
    video_id, progress_callback=progress_cb
)
```

### 4. Logging Integration

```python
import logging

def logging_progress(stage: str, progress: float, message: str):
    """Log progress updates."""
    logging.info(
        f"Progress[{stage}]: {progress:.1%} - {message}",
        extra={
            'stage': stage,
            'progress': progress,
            'message': message
        }
    )

# Usage
audio_path = await youtube_service.download_audio_as_mp3_enhanced(
    video_id, progress_callback=logging_progress
)
```

## yt-dlp Integration Details

The progress callbacks integrate directly with yt-dlp's native progress hooks to provide accurate, real-time download information:

```python
# yt-dlp progress hook data includes:
{
    'status': 'downloading',           # downloading, finished, error
    'downloaded_bytes': 15728640,      # Bytes downloaded so far
    'total_bytes': 45865984,          # Total file size (if known)
    'total_bytes_estimate': 45865984,  # Estimated total (if exact unknown)
    'speed': 2431344.5,               # Download speed in bytes/sec
    'eta': 13,                        # Estimated time remaining in seconds
    'filename': '/tmp/video.mp3'       # Output filename
}
```

**Progress Calculation:**
- Progress percentage: `downloaded_bytes / total_bytes`
- Speed formatting: Automatic conversion to KB/s, MB/s
- ETA formatting: MM:SS format
- Strategy identification: Each strategy has a unique name

## Strategy-Specific Progress

Each download strategy provides distinct progress information:

| Strategy | Name | Progress Details |
|----------|------|------------------|
| 1 | "Cookie Auth" | yt-dlp with cookie file authentication |
| 2 | "iOS Client" | yt-dlp with iOS client simulation |
| 3 | "TV Client" | yt-dlp with TV embedded client |
| 4 | "PyTube" | Manual progress checkpoints (no native hooks) |
| 5 | "Embedded Client" | yt-dlp with web embedded client |
| 6 | "MoviePy Download" | Video download + audio extraction phases |

## Error Handling

Progress callbacks handle errors gracefully:

```python
def robust_progress(stage: str, progress: float, message: str):
    """Error-resistant progress callback."""
    try:
        # Your progress handling code
        update_ui(stage, progress, message)
    except Exception as e:
        logging.error(f"Progress callback error: {e}")
        # Don't let callback errors break the main operation

# The service catches callback exceptions to prevent breaking downloads
```

## Performance Considerations

- **Lightweight**: Progress callbacks add minimal overhead
- **Non-blocking**: Callbacks shouldn't perform heavy operations
- **Async-safe**: Use async callbacks for database/network operations
- **Frequency**: yt-dlp updates progress frequently (multiple times per second during downloads)

## Integration Patterns

### CLI Tools
```python
def cli_progress(stage: str, progress: float, message: str):
    """CLI-friendly progress display."""
    if stage == "downloading":
        # Show live progress for downloads only
        print(f"\r{message}", end="", flush=True)
    elif progress == 1.0:
        # Show completion messages
        print(f"\n✅ {stage.replace('_', ' ').title()}: Complete")
```

### Web APIs (FastAPI)
```python
from fastapi import BackgroundTasks

async def process_video_background(video_id: str, user_id: str):
    """Background task with progress tracking."""
    async def progress_cb(stage: str, progress: float, message: str):
        await notify_user(user_id, {
            "stage": stage, 
            "progress": progress, 
            "message": message
        })
    
    result = await youtube_service.download_audio_as_mp3_enhanced(
        video_id, progress_callback=progress_cb
    )
    await notify_user(user_id, {"completed": True, "result": result})
```

### React/Frontend Integration
```javascript
// WebSocket client for progress updates
const ws = new WebSocket(`ws://localhost/download-progress/${videoId}`);

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateProgressBar(data.progress);
    updateStatusMessage(data.message);
    
    if (data.stage === "completed") {
        showDownloadComplete(data.audio_path);
    } else if (data.stage === "error") {
        showError(data.message);
    }
};
```

## Backward Compatibility

All existing code continues to work without changes:

```python
# This still works exactly as before
video_info = await youtube_service.get_video_info(video_id)
segments, lang, error = await youtube_service.fetch_transcript_segments(video_id)
audio_path = await youtube_service.download_audio_as_mp3_enhanced(video_id)
```

## Testing Progress Callbacks

```python
import pytest

@pytest.mark.asyncio
async def test_progress_callback():
    """Test progress callback functionality."""
    progress_calls = []
    
    def test_callback(stage: str, progress: float, message: str):
        progress_calls.append((stage, progress, message))
    
    service = YouTubeService()
    await service.get_video_info("dQw4w9WgXcQ", test_callback)
    
    # Verify progress calls were made
    assert len(progress_calls) > 0
    assert any(call[0] == "video_info" for call in progress_calls)
    assert any(call[1] == 1.0 for call in progress_calls)  # Completion
```

This comprehensive progress callback system makes the YouTubeService much more suitable for production applications where user feedback and monitoring are essential.