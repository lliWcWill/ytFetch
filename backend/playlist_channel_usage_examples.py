#!/usr/bin/env python3
"""
Usage Examples for YouTube Playlist and Channel Extraction

This file contains practical examples of how to use the new playlist and channel
extraction features in the YouTubeService class.
"""

import asyncio
from app.services.youtube_service import YouTubeService


async def example_url_detection():
    """Example: Detect different types of YouTube URLs."""
    service = YouTubeService()
    
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Video
        "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLMHjMZOz3xPOZ6F2w3",  # Playlist
        "https://www.youtube.com/@3Blue1Brown",  # Channel
    ]
    
    for url in urls:
        print(f"URL: {url}")
        if service.is_playlist_url(url):
            print("  Type: Playlist")
        elif service.is_channel_url(url):
            print("  Type: Channel") 
        elif service.get_video_id_from_url(url):
            print("  Type: Single Video")
        else:
            print("  Type: Unknown")


async def example_playlist_metadata():
    """Example: Get playlist metadata."""
    service = YouTubeService()
    
    def progress_callback(stage, progress, message):
        print(f"{stage}: {progress*100:.0f}% - {message}")
    
    playlist_url = "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
    info = await service.get_playlist_info(playlist_url, progress_callback)
    
    print(f"Playlist: {info['title']}")
    print(f"Videos: {info['video_count']}")
    print(f"Creator: {info['uploader']}")


async def example_extract_playlist_videos():
    """Example: Extract videos from a playlist."""
    service = YouTubeService()
    
    def progress_callback(stage, progress, message):
        print(f"\r{stage}: {progress*100:.0f}% - {message}", end='')
        if progress >= 1.0:
            print()
    
    playlist_url = "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
    
    # Extract first 10 videos
    videos = await service.extract_playlist_videos(
        playlist_url, 
        max_videos=10, 
        progress_callback=progress_callback
    )
    
    print(f"\nFound {len(videos)} videos:")
    for video in videos:
        print(f"- {video['title']} ({video['duration_string']})")


async def example_extract_channel_videos():
    """Example: Extract videos from a channel."""
    service = YouTubeService()
    
    def progress_callback(stage, progress, message):
        print(f"\r{stage}: {progress*100:.0f}% - {message}", end='')
        if progress >= 1.0:
            print()
    
    channel_url = "https://www.youtube.com/@YOUR_CHANNEL"
    
    # Extract first 20 videos
    videos = await service.extract_channel_videos(
        channel_url, 
        max_videos=20, 
        progress_callback=progress_callback
    )
    
    print(f"\nFound {len(videos)} videos:")
    for video in videos[:5]:  # Show first 5
        print(f"- {video['title']} ({video['duration_string']}) - {video['view_count']} views")


async def example_batch_processing():
    """Example: Process multiple playlists/channels in batch."""
    service = YouTubeService()
    
    sources = [
        ("playlist", "https://www.youtube.com/playlist?list=PLAYLIST_ID_1"),
        ("playlist", "https://www.youtube.com/playlist?list=PLAYLIST_ID_2"),
        ("channel", "https://www.youtube.com/@CHANNEL_1"),
        ("channel", "https://www.youtube.com/@CHANNEL_2"),
    ]
    
    all_videos = []
    
    for source_type, url in sources:
        print(f"\nProcessing {source_type}: {url}")
        
        try:
            if source_type == "playlist":
                videos = await service.extract_playlist_videos(url, max_videos=5)
            else:  # channel
                videos = await service.extract_channel_videos(url, max_videos=5)
            
            all_videos.extend(videos)
            print(f"  Found {len(videos)} videos")
            
        except Exception as e:
            print(f"  Error: {e}")
    
    print(f"\nTotal videos collected: {len(all_videos)}")


async def example_filtering_videos():
    """Example: Filter videos by criteria."""
    service = YouTubeService()
    
    playlist_url = "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
    videos = await service.extract_playlist_videos(playlist_url)
    
    # Filter videos longer than 10 minutes (600 seconds)
    long_videos = [v for v in videos if v['duration'] > 600]
    
    # Filter videos with high view counts
    popular_videos = [v for v in videos if v['view_count'] > 100000]
    
    # Filter recent videos (uploaded this year)
    import datetime
    current_year = str(datetime.datetime.now().year)
    recent_videos = [v for v in videos if v['upload_date'].startswith(current_year)]
    
    print(f"Total videos: {len(videos)}")
    print(f"Long videos (>10 min): {len(long_videos)}")
    print(f"Popular videos (>100k views): {len(popular_videos)}")
    print(f"Recent videos ({current_year}): {len(recent_videos)}")


async def example_error_handling():
    """Example: Proper error handling for playlists/channels."""
    service = YouTubeService()
    
    problematic_urls = [
        "https://www.youtube.com/playlist?list=INVALID_PLAYLIST_ID",
        "https://www.youtube.com/@NONEXISTENT_CHANNEL",
        "https://www.youtube.com/playlist?list=PRIVATE_PLAYLIST_ID",
    ]
    
    for url in problematic_urls:
        try:
            if service.is_playlist_url(url):
                info = await service.get_playlist_info(url)
                videos = await service.extract_playlist_videos(url, max_videos=1)
                print(f"✓ {url}: {info['title']} ({len(videos)} videos)")
            
            elif service.is_channel_url(url):
                info = await service.get_channel_info(url)
                videos = await service.extract_channel_videos(url, max_videos=1)
                print(f"✓ {url}: {info['title']} ({len(videos)} videos)")
                
        except Exception as e:
            print(f"✗ {url}: Error - {e}")


# Integration with existing functionality
async def example_download_from_playlist():
    """Example: Download audio from playlist videos."""
    service = YouTubeService()
    
    def progress_callback(stage, progress, message):
        print(f"\r{stage}: {progress*100:.0f}% - {message}", end='')
        if progress >= 1.0:
            print()
    
    playlist_url = "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
    
    # Get first 3 videos from playlist
    videos = await service.extract_playlist_videos(playlist_url, max_videos=3)
    
    for i, video in enumerate(videos, 1):
        print(f"\nDownloading {i}/{len(videos)}: {video['title']}")
        
        # Download audio for each video
        audio_path = await service.download_audio_as_mp3_enhanced(
            video['id'],
            video_title=video['title'],
            progress_callback=progress_callback
        )
        
        if audio_path:
            print(f"✓ Downloaded: {audio_path}")
        else:
            print(f"✗ Failed to download: {video['title']}")


if __name__ == "__main__":
    # Uncomment the example you want to run
    # asyncio.run(example_url_detection())
    # asyncio.run(example_playlist_metadata())
    # asyncio.run(example_extract_playlist_videos())
    # asyncio.run(example_extract_channel_videos())
    # asyncio.run(example_batch_processing())
    # asyncio.run(example_filtering_videos())
    # asyncio.run(example_error_handling())
    # asyncio.run(example_download_from_playlist())
    
    print("Replace placeholder URLs with real ones and uncomment the example you want to run.")