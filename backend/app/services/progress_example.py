#!/usr/bin/env python3
"""
Example usage of YouTubeService with progress callbacks

This demonstrates how to use the progress callback functionality
added to the YouTubeService for real-time progress reporting.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from youtube_service import YouTubeService


def progress_callback(stage: str, progress: float, message: str):
    """
    Example progress callback function.
    
    Args:
        stage: Current operation phase ("video_info", "transcript", "setup", "download", "downloading")
        progress: Completion percentage (0.0 to 1.0)
        message: Human-readable status description
    """
    # Convert progress to percentage
    percentage = int(progress * 100)
    
    # Create a simple progress bar
    bar_length = 30
    filled_length = int(bar_length * progress)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    # Print progress with stage indicator
    stage_colors = {
        'video_info': '\033[94m',    # Blue
        'transcript': '\033[92m',    # Green
        'setup': '\033[93m',         # Yellow
        'download': '\033[95m',      # Magenta
        'downloading': '\033[96m',   # Cyan
    }
    
    color = stage_colors.get(stage, '\033[0m')
    reset = '\033[0m'
    
    print(f"{color}[{stage.upper():>11}]{reset} [{bar}] {percentage:3d}% - {message}")


async def demo_youtube_service_with_progress():
    """Demonstrate YouTubeService with progress callbacks."""
    
    # Initialize the service
    service = YouTubeService()
    
    # Example YouTube video ID (replace with any valid video ID)
    video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    print("🎥 YouTubeService Progress Callback Demo")
    print("=" * 50)
    print(f"Video ID: {video_id}")
    print()
    
    try:
        # 1. Get video information with progress
        print("📋 Getting video information...")
        video_info = await service.get_video_info(video_id, progress_callback)
        print(f"✅ Video: {video_info['title']}")
        print()
        
        # 2. Fetch transcript with progress
        print("📝 Fetching transcript...")
        segments, language, error = await service.fetch_transcript_segments(video_id, progress_callback)
        
        if segments:
            print(f"✅ Transcript found in {language}: {len(segments)} segments")
        else:
            print(f"❌ Transcript error: {error}")
        print()
        
        # 3. Download audio with progress
        print("🎵 Downloading audio...")
        output_path = await service.download_audio_as_mp3_enhanced(
            video_id, 
            progress_callback=progress_callback,
            video_title=video_info['title']
        )
        
        if output_path:
            print(f"✅ Audio downloaded: {output_path}")
        else:
            print("❌ Download failed")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("🎉 Demo completed!")


async def demo_without_progress():
    """Demonstrate YouTubeService without progress callbacks (backward compatibility)."""
    
    print("\n" + "=" * 50)
    print("🔄 Testing backward compatibility (no progress callbacks)")
    print("=" * 50)
    
    service = YouTubeService()
    video_id = "dQw4w9WgXcQ"
    
    try:
        # All methods work without progress callbacks
        video_info = await service.get_video_info(video_id)
        print(f"✅ Video info (no progress): {video_info['title']}")
        
        segments, language, error = await service.fetch_transcript_segments(video_id)
        if segments:
            print(f"✅ Transcript (no progress): {len(segments)} segments in {language}")
        
        print("✅ Backward compatibility confirmed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def simple_progress_callback(stage: str, progress: float, message: str):
    """A simpler progress callback for minimal output."""
    if stage == "downloading" and progress > 0:
        # Only show downloading progress with file size info
        print(f"Downloading: {int(progress * 100):3d}% - {message}")
    elif progress == 1.0:
        # Show completion messages
        print(f"✅ {stage.replace('_', ' ').title()}: {message}")


async def demo_simple_progress():
    """Demonstrate with a simpler progress callback."""
    
    print("\n" + "=" * 50)
    print("🔧 Simple Progress Callback Demo")
    print("=" * 50)
    
    service = YouTubeService()
    video_id = "dQw4w9WgXcQ"
    
    try:
        print("Getting video info...")
        video_info = await service.get_video_info(video_id, simple_progress_callback)
        
        print("Downloading audio...")
        output_path = await service.download_audio_as_mp3_enhanced(
            video_id, 
            progress_callback=simple_progress_callback,
            video_title=video_info['title']
        )
        
        if output_path:
            print(f"✅ Complete: {output_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    # Run the demos
    asyncio.run(demo_youtube_service_with_progress())
    asyncio.run(demo_without_progress())
    asyncio.run(demo_simple_progress())