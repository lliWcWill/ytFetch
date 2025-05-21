# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ytFetch is a YouTube video processing toolkit with two main components:

1. **fetchTscript.py** - A command-line script that extracts transcripts from YouTube videos using the YouTube Transcript API, with fallback to audio download using yt-dlp when transcripts aren't available
2. **transcribeVid.py** - A Streamlit web application for multi-provider audio transcription using both Groq and OpenAI Whisper APIs

## Architecture

### Core Components

- **fetchTscript.py**: Standalone CLI tool for YouTube transcript extraction
  - Handles various YouTube URL formats (youtu.be, youtube.com/watch, /embed/, /v/, /shorts/)
  - Prioritizes manually created transcripts over auto-generated ones
  - Falls back to audio download (MP3) when no transcripts are available
  - Uses yt-dlp for YouTube audio extraction

- **transcribeVid.py**: Streamlit web app for audio transcription
  - Multi-provider support (Groq and OpenAI APIs)
  - Intelligent provider selection based on file size and rate limits
  - Audio preprocessing with ffmpeg (16kHz mono FLAC)
  - Automatic chunking for large files with overlap handling
  - Quality analysis with confidence metrics and speech detection
  - Export options (TXT, SRT formats)

### Configuration

- **config.yaml**: Contains API keys for Groq and OpenAI services
- **config.yaml.example**: Template showing required configuration structure
- Uses Python virtual environment in `venv/` directory

## Common Commands

### Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (if requirements.txt exists)
pip install -r requirements.txt
```

### Running the Applications

```bash
# YouTube transcript extraction (CLI)
python fetchTscript.py <youtube_url>

# Audio transcription web app
streamlit run transcribeVid.py
```

## Key Dependencies

- **youtube-transcript-api**: YouTube transcript extraction
- **yt-dlp**: YouTube audio downloading
- **streamlit**: Web UI framework
- **groq**: Groq API client
- **openai**: OpenAI API client
- **pydub**: Audio processing
- **ffmpeg**: Audio format conversion (system dependency)

## File Processing Logic

### Transcript Extraction (fetchTscript.py)
1. Parse YouTube URL to extract video ID
2. Attempt to fetch transcript (manual → auto-generated → any language)
3. If no transcript available, download audio as MP3
4. Save results to local files with video ID naming

### Audio Transcription (transcribeVid.py)
1. Preprocess audio to optimal format (16kHz mono FLAC)
2. Calculate appropriate chunk sizes based on API limits (25MB max)
3. Split audio with configurable overlap (5 seconds default)
4. Select provider based on file size and rate limits
5. Process chunks in parallel with progress tracking
6. Combine results and analyze quality metrics
7. Generate downloadable outputs

## Provider Selection Strategy

- Files > 5MB: Prefer OpenAI (higher rate limits)
- Files ≤ 5MB: Prefer Groq (cost-effective)
- Rate limit handling: Switch providers when limits approached
- Fallback: Use available provider if preferred is unavailable