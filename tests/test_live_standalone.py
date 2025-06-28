#!/usr/bin/env python3
"""
Standalone test script for the specific live stream that's failing
No Streamlit dependencies - pure yt-dlp testing
"""

import os
import sys
import logging
import yt_dlp
from urllib.parse import urlparse, parse_qs

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_video_id_from_url(youtube_url):
    """Extract video ID from YouTube URL - standalone version"""
    if not youtube_url:
        return None
    
    youtube_url = youtube_url.strip()
    parsed_url = urlparse(youtube_url)
    
    # Handle youtu.be short URLs
    if parsed_url.hostname == 'youtu.be':
        video_id = parsed_url.path[1:].split('?')[0].split('&')[0]
        return video_id if video_id else None
    
    # Handle youtube.com URLs
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
        if parsed_url.path == '/watch':
            p = parse_qs(parsed_url.query)
            video_id_list = p.get('v', [])
            if video_id_list:
                return video_id_list[0].split('&')[0]
        if parsed_url.path.startswith('/embed/'):
            return parsed_url.path.split('/')[2].split('?')[0]
        if parsed_url.path.startswith('/v/'):
            return parsed_url.path.split('/')[2].split('?')[0]
        if parsed_url.path.startswith('/shorts/'):
            return parsed_url.path.split('/')[2].split('?')[0]
        if parsed_url.path.startswith('/live/'):
            return parsed_url.path.split('/')[2].split('?')[0]
    
    return None

def get_video_info_standalone(video_id):
    """Get basic video info using yt-dlp - standalone version"""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            return {
                'title': info.get('title', f'video_{video_id}'),
                'id': video_id,
                'url': video_url,
                'duration': info.get('duration', 0),
                'is_live': info.get('is_live', False),
                'live_status': info.get('live_status', 'none'),
                'was_live': info.get('live_status') == 'was_live',
                'uploader': info.get('uploader', ''),
            }
    except Exception as e:
        print(f"❌ Could not get video info: {e}")
        return None

def test_live_strategy_1_standard(video_url, output_dir):
    """Strategy 1: Standard yt-dlp for live streams"""
    print("🧪 Live Strategy 1: Standard yt-dlp")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s_standard.%(ext)s'),
        'quiet': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

def test_live_strategy_2_android_client(video_url, output_dir):
    """Strategy 2: Android client for live streams"""
    print("🧪 Live Strategy 2: Android client")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s_android.%(ext)s'),
        'quiet': False,
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],
            }
        },
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

def test_live_strategy_3_live_options(video_url, output_dir):
    """Strategy 3: Live stream specific options"""
    print("🧪 Live Strategy 3: Live stream options")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s_live_opts.%(ext)s'),
        'quiet': False,
        'live_from_start': True,
        'hls_use_mpegts': True,
        'wait_for_video': 5,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

def test_live_strategy_4_combined(video_url, output_dir):
    """Strategy 4: Combined live stream approach"""
    print("🧪 Live Strategy 4: Combined approach")
    
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s_combined.%(ext)s'),
        'quiet': False,
        'force_ipv4': True,
        'nocheckcertificate': True,
        'live_from_start': True,
        'hls_use_mpegts': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        'user_agent': 'Mozilla/5.0 (Linux; Android 11; SM-G973F) AppleWebKit/537.36',
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        },
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

def test_live_strategy_5_info_only(video_url):
    """Strategy 5: Just extract info to debug the player response issue"""
    print("🧪 Live Strategy 5: Info extraction only")
    
    ydl_opts = {
        'quiet': False,
        'skip_download': True,  # Only extract info, don't download
        'writeinfojson': True,
        'outtmpl': 'live_info.%(ext)s',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        print(f"✅ Info extraction successful!")
        print(f"   Title: {info.get('title', 'Unknown')}")
        print(f"   Live Status: {info.get('live_status', 'unknown')}")
        print(f"   Is Live: {info.get('is_live', False)}")
        print(f"   Duration: {info.get('duration', 'Unknown')}")
        return info

def main():
    """Test the specific problematic live stream"""
    print("🔴 Live Stream Download Test")
    print("Testing the specific URL that's failing with 'player response' error")
    print("=" * 80)
    
    # The actual problematic URL
    test_url = "https://www.youtube.com/live/BBhZ9Ltpmdw?si=00AxZvig1fM-cUwz"
    
    print(f"🎯 Target URL: {test_url}")
    
    # Extract video ID
    video_id = get_video_id_from_url(test_url)
    print(f"📹 Video ID: {video_id}")
    
    if not video_id:
        print("❌ Failed to extract video ID")
        return
    
    # Try to get basic info first
    print("\n🔍 Step 1: Getting video info...")
    video_info = get_video_info_standalone(video_id)
    
    if video_info:
        print(f"✅ Video info extracted successfully:")
        print(f"   Title: {video_info['title']}")
        print(f"   Live Status: {video_info['live_status']}")
        print(f"   Was Live: {video_info['was_live']}")
        print(f"   Duration: {video_info['duration']} seconds")
    else:
        print("❌ Failed to get basic video info")
        return
    
    # Create output directory
    output_dir = "live_test_downloads"
    os.makedirs(output_dir, exist_ok=True)
    
    # Test strategies
    strategies = [
        test_live_strategy_5_info_only,  # Start with info-only to debug
        test_live_strategy_1_standard,
        test_live_strategy_2_android_client,
        test_live_strategy_3_live_options,
        test_live_strategy_4_combined,
    ]
    
    successful_strategies = []
    failed_strategies = []
    
    for i, strategy in enumerate(strategies, 1):
        print(f"\n{'='*20} Live Strategy {i}/{len(strategies)} {'='*20}")
        try:
            if strategy == test_live_strategy_5_info_only:
                strategy(test_url)
            else:
                strategy(test_url, output_dir)
            successful_strategies.append(f"Strategy {i}: {strategy.__name__}")
            print(f"✅ Live Strategy {i} SUCCEEDED!")
            
        except Exception as e:
            failed_strategies.append(f"Strategy {i}: {strategy.__name__} - {str(e)}")
            print(f"❌ Live Strategy {i} FAILED: {e}")
    
    # Results
    print(f"\n{'='*80}")
    print("📊 LIVE STREAM TEST RESULTS")
    print(f"{'='*80}")
    
    print(f"\n✅ Successful Strategies ({len(successful_strategies)}):")
    for success in successful_strategies:
        print(f"   {success}")
    
    print(f"\n❌ Failed Strategies ({len(failed_strategies)}):")
    for failure in failed_strategies:
        print(f"   {failure}")
    
    # Check downloaded files
    print(f"\n📁 Downloaded Files:")
    if os.path.exists(output_dir):
        files = os.listdir(output_dir)
        if files:
            for file in files:
                file_path = os.path.join(output_dir, file)
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"   {file} ({size_mb:.2f} MB)")
        else:
            print("   No files downloaded")
    
    success = len(successful_strategies) > 0
    print(f"\n🏁 FINAL RESULT: {'SUCCESS' if success else 'ALL STRATEGIES FAILED'}")
    
    if not success:
        print("\n💡 NEXT STEPS:")
        print("1. The 'Failed to extract player response' error persists")
        print("2. Try updating to yt-dlp nightly: yt-dlp --update-to nightly")
        print("3. This specific video might have enhanced protection")
        print("4. Use your project's audio transcription fallback instead")

if __name__ == "__main__":
    main()