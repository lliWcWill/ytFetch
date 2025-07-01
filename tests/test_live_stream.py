#!/usr/bin/env python3
"""
Test script for YouTube live stream download functionality
"""

import os
import sys
import logging
from misc.appStreamlit import get_video_id_from_url, get_video_info, download_audio_as_mp3

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_live_stream_url(url):
    """Test live stream URL parsing and download"""
    print(f"\n🔍 Testing URL: {url}")
    print("=" * 60)
    
    # Step 1: Extract video ID
    video_id = get_video_id_from_url(url)
    print(f"1. Video ID: {video_id}")
    
    if not video_id:
        print("❌ Failed to extract video ID")
        return False
    
    # Step 2: Get video info
    try:
        video_info = get_video_info(video_id)
        print(f"2. Video Info:")
        print(f"   Title: {video_info.get('title', 'Unknown')}")
        print(f"   Duration: {video_info.get('duration', 0)} seconds")
        print(f"   Is Live: {video_info.get('is_live', False)}")
        print(f"   Live Status: {video_info.get('live_status', 'none')}")
        print(f"   Was Live: {video_info.get('was_live', False)}")
        print(f"   Uploader: {video_info.get('uploader', 'Unknown')}")
    except Exception as e:
        print(f"❌ Failed to get video info: {e}")
        return False
    
    # Step 3: Test download (optional - comment out if you don't want to actually download)
    print(f"\n3. Testing download...")
    try:
        # Create test output directory
        test_dir = "test_downloads"
        os.makedirs(test_dir, exist_ok=True)
        
        # Attempt download
        result = download_audio_as_mp3(
            video_id=video_id,
            output_dir=test_dir,
            video_title=video_info.get('title', f'video_{video_id}')
        )
        
        if result:
            print(f"✅ Download successful: {result}")
            # Get file size
            if os.path.exists(result):
                size_mb = os.path.getsize(result) / (1024 * 1024)
                print(f"   File size: {size_mb:.2f} MB")
        else:
            print("❌ Download failed")
            
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False
    
    return True

def main():
    """Main test function"""
    print("🎬 YouTube Live Stream Test Script")
    print("=" * 60)
    
    # Test URLs
    test_urls = [
        "https://www.youtube.com/live/BBhZ9Ltpmdw?si=00AxZvig1fM-cUwz",
        "https://www.youtube.com/watch?v=BBhZ9Ltpmdw",  # Same video, different URL format
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n🧪 Test {i}/{len(test_urls)}")
        success = test_live_stream_url(url)
        print(f"Result: {'✅ PASSED' if success else '❌ FAILED'}")
    
    print(f"\n🏁 Testing complete!")

if __name__ == "__main__":
    main()