# YouTubeService Migration Documentation

## Overview

Successfully migrated all YouTube-related functions from `appStreamlit.py` into a clean, reusable `YouTubeService` class in the backend service architecture.

## Migrated Functions

### Core Functions Extracted:
1. ✅ **`get_video_id_from_url()`** - Extract video IDs from various YouTube URL formats
2. ✅ **`get_video_info()`** - Fetch video metadata using yt-dlp (now async)
3. ✅ **`download_audio_as_mp3_enhanced()`** - Download audio with 6 fallback strategies (now async)
4. ✅ **`fetch_transcript_segments()`** - Fetch transcripts with Webshare proxy support (now async)
5. ✅ **`sanitize_filename()`** - Clean filenames for safe filesystem usage

### Additional Utility Functions:
6. ✅ **`parse_srt_to_segments()`** - Parse SRT format into transcript segments
7. ✅ **`format_segments()`** - Format segments into txt/srt/vtt/json
8. ✅ **`cleanup_temp_files()`** - Clean up temporary files (new)

## Key Improvements

### ✅ Removed Streamlit Dependencies
- Eliminated all `import streamlit as st` dependencies
- Removed Streamlit progress bars and status placeholders
- Replaced with callback-based progress reporting

### ✅ Added Async Support
- All major operations are now async (`get_video_info`, `fetch_transcript_segments`, `download_audio_as_mp3_enhanced`)
- Non-blocking I/O operations using `asyncio.run_in_executor()`
- Better scalability for web services

### ✅ Enhanced Configuration Integration
- Uses `backend.app.core.config` for settings management
- Supports both environment variables and config files
- Proper dependency injection pattern

### ✅ Improved Error Handling
- Comprehensive logging throughout all operations
- Structured error responses
- Graceful fallback mechanisms maintained

### ✅ Progress Callback Support (NEW!)
- Optional progress callbacks for real-time status updates
- Integration with yt-dlp progress hooks for accurate download progress
- Stage-based progress tracking (video_info, transcript, setup, download, downloading)
- WebSocket-ready for real-time web interfaces
- Backward compatible - all callbacks are optional

### ✅ All 6 Download Strategies Preserved
1. **Strategy 1**: yt-dlp with cookie authentication
2. **Strategy 2**: yt-dlp with iOS client simulation and anti-bot headers
3. **Strategy 3**: yt-dlp with TV client
4. **Strategy 4**: pytube fallback with pydub conversion
5. **Strategy 5**: yt-dlp with embedded client
6. **Strategy 6**: moviepy + youtube-dl combination

## File Structure

```
backend/app/services/
├── __init__.py                 # Service exports
├── youtube_service.py          # Main YouTubeService class
├── example_usage.py           # Usage examples and demos
├── progress_example.py        # Progress callback examples
├── PROGRESS_CALLBACKS.md      # Detailed progress callback documentation
└── README.md                  # This documentation
```

## Usage Examples

### Basic Usage
```python
from backend.app.services import YouTubeService

# Initialize service
youtube_service = YouTubeService()

# Extract video ID
video_id = youtube_service.get_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Get video info (async)
video_info = await youtube_service.get_video_info(video_id)

# Fetch transcript (async)
segments, language, error = await youtube_service.fetch_transcript_segments(video_id)

# Format transcript
transcript = youtube_service.format_segments(segments, "txt")
```

### FastAPI Integration
```python
from fastapi import FastAPI
from backend.app.services import YouTubeService

app = FastAPI()
youtube_service = YouTubeService()

@app.post("/transcribe")
async def transcribe_video(url: str):
    video_id = youtube_service.get_video_id_from_url(url)
    video_info = await youtube_service.get_video_info(video_id)
    segments, language, error = await youtube_service.fetch_transcript_segments(video_id)
    
    if segments:
        transcript = youtube_service.format_segments(segments, "txt")
        return {"transcript": transcript, "language": language}
    else:
        return {"error": error}
```

### Progress Callback Examples (NEW!)

#### Simple Console Progress
```python
def progress_callback(stage: str, progress: float, message: str):
    """Simple progress callback for console output."""
    percentage = int(progress * 100)
    print(f"[{stage.upper():>11}] {percentage:3d}% - {message}")

# Use with any async method
video_info = await youtube_service.get_video_info(video_id, progress_callback)
segments, lang, error = await youtube_service.fetch_transcript_segments(video_id, progress_callback)
audio_path = await youtube_service.download_audio_as_mp3_enhanced(video_id, progress_callback=progress_callback)
```

#### WebSocket Progress (Real-time Web UI)
```python
async def websocket_progress(websocket):
    """Progress callback for WebSocket updates."""
    async def callback(stage: str, progress: float, message: str):
        await websocket.send_json({
            "stage": stage,
            "progress": progress,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
    return callback

# Use in FastAPI WebSocket endpoint
progress_cb = await websocket_progress(websocket)
audio_path = await youtube_service.download_audio_as_mp3_enhanced(video_id, progress_callback=progress_cb)
```

#### Advanced Progress Bar
```python
def fancy_progress(stage: str, progress: float, message: str):
    """Fancy progress bar with colors and animations."""
    percentage = int(progress * 100)
    bar_length = 30
    filled_length = int(bar_length * progress)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    # Color coding by stage
    colors = {
        'video_info': '\033[94m',    # Blue
        'transcript': '\033[92m',    # Green  
        'downloading': '\033[96m',   # Cyan
        'download': '\033[95m'       # Magenta
    }
    color = colors.get(stage, '\033[0m')
    reset = '\033[0m'
    
    print(f"{color}[{stage.upper():>11}]{reset} [{bar}] {percentage:3d}% - {message}")
```

## Configuration Requirements

### Environment Variables
```bash
# Optional API Keys
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key
WEBSHARE_USERNAME=your_username
WEBSHARE_PASSWORD=your_password

# Service Configuration
TEMP_DIR=/tmp/ytfetch
MAX_FILE_SIZE_MB=100
```

### Dependencies
All required dependencies are specified in `backend/pyproject.toml`:
- `yt-dlp` - Video downloading
- `youtube-transcript-api` - Transcript fetching
- `pydub` - Audio processing
- `pytube` - Fallback downloader
- `moviepy` - Alternative audio extraction
- `tenacity` - Retry logic
- `isodate` - Duration parsing

## Testing

### ✅ Verified Functionality
- Video ID extraction from various URL formats
- Async video info retrieval
- Transcript fetching with Webshare proxy support
- SRT parsing and formatting
- Filename sanitization
- All output formats (txt, srt, vtt, json)

### Test Results
```
✅ YouTubeService import successful
✅ YouTubeService instantiation successful  
✅ Video ID extraction: dQw4w9WgXcQ
✅ Filename sanitization: "Test Video Special Characters devnull @"
✅ Video info retrieved: Rick Astley - Never Gonna Give You Up...
✅ Transcript found! Language: English
✅ 61 segments processed successfully
```

## Migration Benefits

1. **Modularity**: Clean separation of YouTube operations from UI
2. **Reusability**: Service can be used across different interfaces (FastAPI, CLI, etc.)
3. **Testability**: Easy to unit test without UI dependencies
4. **Scalability**: Async operations support concurrent requests
5. **Maintainability**: Clear structure and comprehensive error handling
6. **Configuration**: Centralized settings management

## Next Steps

1. **Integration**: Use YouTubeService in FastAPI endpoints
2. **Testing**: Add comprehensive unit tests
3. **Documentation**: Add API documentation with examples
4. **Monitoring**: Add metrics and performance tracking
5. **Caching**: Implement transcript caching mechanisms

## Files Created/Modified

### ✅ New Files
- `/backend/app/services/youtube_service.py` - Main service class
- `/backend/app/services/example_usage.py` - Usage examples
- `/backend/app/services/README.md` - This documentation

### ✅ Modified Files  
- `/backend/app/services/__init__.py` - Added YouTubeService exports
- `/backend/app/core/config.py` - Made API keys optional

### ✅ Dependencies
- All required packages already specified in `backend/pyproject.toml`
- `pydantic-settings` installed for configuration management

The YouTubeService migration is now complete and fully functional! 🎉