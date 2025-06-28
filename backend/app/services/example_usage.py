"""
Example usage of the YouTubeService class.

This file demonstrates how to use the migrated YouTube functionality
in the new backend service architecture.
"""

import asyncio
import logging
import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.append(project_root)

from backend.app.services.youtube_service import YouTubeService


async def main():
    """Example usage of YouTubeService."""
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize the service
    youtube_service = YouTubeService()
    print("✅ YouTubeService initialized")
    
    # Example YouTube URL
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    # 1. Extract video ID
    video_id = youtube_service.get_video_id_from_url(youtube_url)
    if not video_id:
        print("❌ Failed to extract video ID")
        return
    
    print(f"📹 Video ID: {video_id}")
    
    # 2. Get video information
    print("🔍 Fetching video information...")
    video_info = await youtube_service.get_video_info(video_id)
    print(f"📺 Title: {video_info['title']}")
    print(f"⏱️  Duration: {video_info['duration']} seconds")
    print(f"👤 Uploader: {video_info['uploader']}")
    print(f"🔴 Is Live: {video_info['is_live']}")
    
    # 3. Try to fetch transcript segments
    print("📝 Attempting to fetch transcript segments...")
    try:
        segments, language, error = await youtube_service.fetch_transcript_segments(video_id)
        
        if segments:
            print(f"✅ Transcript found! Language: {language}")
            print(f"📊 Number of segments: {len(segments)}")
            
            # Show first few segments
            print("🔤 First 3 segments:")
            for i, segment in enumerate(segments[:3]):
                print(f"  {i+1}. [{segment['start']:.1f}s] {segment['text'][:50]}...")
            
            # 4. Format transcript in different formats
            print("\n📄 Formatting transcript...")
            
            # Text format
            txt_transcript = youtube_service.format_segments(segments, "txt")
            print(f"📝 Text format: {len(txt_transcript)} characters")
            
            # SRT format
            srt_transcript = youtube_service.format_segments(segments, "srt")
            print(f"🎬 SRT format: {len(srt_transcript)} characters")
            
            # JSON format
            json_transcript = youtube_service.format_segments(segments, "json")
            print(f"🔗 JSON format: {len(json_transcript)} characters")
            
            # Save to file (example)
            safe_title = youtube_service.sanitize_filename(video_info['title'])
            output_file = f"/tmp/{safe_title}_transcript.txt"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Video Title: {video_info['title']}\n")
                f.write(f"YouTube URL: {youtube_url}\n")
                f.write(f"Video ID: {video_id}\n")
                f.write("-" * 80 + "\n\n")
                f.write(txt_transcript)
            
            print(f"💾 Transcript saved to: {output_file}")
            
        else:
            print(f"❌ Failed to fetch transcript: {error}")
            
    except Exception as e:
        print(f"❌ Error fetching transcript: {e}")
    
    # 5. Demo progress callbacks (NEW FEATURE!)
    print("\n📈 Progress Callback Demo:")
    
    def demo_progress_callback(stage: str, progress: float, message: str):
        """Example progress callback that shows real-time progress."""
        percentage = int(progress * 100)
        bar_length = 20
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        print(f"[{stage.upper():>11}] [{bar}] {percentage:3d}% - {message}")
    
    print("Fetching video info with progress tracking:")
    video_info_with_progress = await youtube_service.get_video_info(video_id, demo_progress_callback)
    
    print("\nFetching transcript with progress tracking:")
    try:
        segments_with_progress, lang, err = await youtube_service.fetch_transcript_segments(video_id, demo_progress_callback)
        if segments_with_progress:
            print(f"✅ Transcript fetched successfully with progress tracking!")
    except Exception as e:
        print(f"Transcript fetch with progress failed: {e}")
    
    # 6. Demo audio download (commented out to avoid actual download)
    print("\n🎵 Audio download example (demo only):")
    print("To download audio with progress tracking, uncomment the following lines:")
    print("# def progress_callback(stage, progress, message):")
    print("#     print(f'[{stage}] {progress:.1f}% - {message}')")
    print("# ")
    print("# audio_path = await youtube_service.download_audio_as_mp3_enhanced(")
    print("#     video_id, ")
    print("#     output_dir='/tmp',")
    print("#     video_title=video_info['title'],")
    print("#     progress_callback=progress_callback")
    print("# )")
    print("# if audio_path:")
    print("#     print(f'🎵 Audio downloaded: {audio_path}')")
    
    # 7. Demo SRT parsing
    print("\n🎬 SRT parsing example:")
    srt_sample = '''1
00:00:00,000 --> 00:00:05,000
Hello world, this is a test

2
00:00:05,000 --> 00:00:10,000
Second subtitle segment'''
    
    parsed_segments = youtube_service.parse_srt_to_segments(srt_sample)
    print(f"📝 Parsed {len(parsed_segments)} segments from SRT")
    for segment in parsed_segments:
        print(f"  - [{segment['start']:.1f}s] {segment['text']}")
    
    # 8. Cleanup example
    print("\n🧹 Cleanup:")
    await youtube_service.cleanup_temp_files(["*.mp3", "*.tmp"])
    print("✅ Temporary files cleaned up")
    
    print("\n🎉 YouTubeService demonstration complete!")


async def fastapi_integration_example():
    """Example of how to integrate YouTubeService with FastAPI."""
    
    print("\n🚀 FastAPI Integration Example:")
    print("Here's how you would use YouTubeService in a FastAPI endpoint:")
    
    example_code = '''
from fastapi import FastAPI, HTTPException, WebSocket
from backend.app.services import YouTubeService
from backend.app.api.schemas import TranscribeRequest, TranscribeResponse

app = FastAPI()
youtube_service = YouTubeService()

@app.post("/api/v1/transcribe", response_model=TranscribeResponse)
async def transcribe_video(request: TranscribeRequest):
    """Transcribe a YouTube video."""
    
    # Extract video ID
    video_id = youtube_service.get_video_id_from_url(request.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    # Get video information
    video_info = await youtube_service.get_video_info(video_id)
    
    # Try to get transcript
    segments, language, error = await youtube_service.fetch_transcript_segments(video_id)
    
    if not segments:
        # Fallback to AI transcription would go here
        raise HTTPException(status_code=404, detail="No transcript available")
    
    # Format transcript
    transcript = youtube_service.format_segments(segments, request.output_format)
    
    return TranscribeResponse(
        transcript=transcript,
        video_metadata=VideoMetadata(**video_info),
        processing_metadata=ProcessingMetadata(
            processing_time=1.5,
            source="transcript_api"
        ),
        format=request.output_format,
        language=language
    )

# NEW: WebSocket endpoint for real-time progress updates
@app.websocket("/api/v1/download-progress/{video_id}")
async def download_with_progress(websocket: WebSocket, video_id: str):
    """Download audio with real-time progress updates via WebSocket."""
    await websocket.accept()
    
    async def progress_callback(stage: str, progress: float, message: str):
        """Send progress updates via WebSocket."""
        await websocket.send_json({
            "stage": stage,
            "progress": progress,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    try:
        # Get video info with progress
        video_info = await youtube_service.get_video_info(video_id, progress_callback)
        
        # Download audio with progress
        audio_path = await youtube_service.download_audio_as_mp3_enhanced(
            video_id,
            progress_callback=progress_callback,
            video_title=video_info['title']
        )
        
        # Send completion message
        await websocket.send_json({
            "stage": "completed",
            "progress": 1.0,
            "message": f"Download completed: {audio_path}",
            "audio_path": audio_path,
            "video_info": video_info
        })
        
    except Exception as e:
        await websocket.send_json({
            "stage": "error",
            "progress": 0.0,
            "message": f"Error: {str(e)}"
        })
    finally:
        await websocket.close()
'''
    
    print(example_code)
    
    print("\n🔄 Progress Callback Patterns:")
    progress_patterns = '''
# Pattern 1: Simple logging
def log_progress(stage, progress, message):
    logger.info(f"[{stage}] {progress:.1%} - {message}")

# Pattern 2: Database updates
async def db_progress(stage, progress, message):
    await update_job_progress(job_id, stage, progress, message)

# Pattern 3: WebSocket broadcasting
async def websocket_progress(stage, progress, message):
    await websocket_manager.broadcast({
        "type": "progress",
        "stage": stage,
        "progress": progress,
        "message": message
    })

# Pattern 4: File-based progress (for CLI tools)
def file_progress(stage, progress, message):
    with open(f"/tmp/progress_{job_id}.json", "w") as f:
        json.dump({
            "stage": stage,
            "progress": progress,
            "message": message,
            "timestamp": time.time()
        }, f)
'''
    
    print(progress_patterns)


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
    asyncio.run(fastapi_integration_example())