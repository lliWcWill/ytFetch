#!/usr/bin/env python3
"""
Enhanced test script with multiple yt-dlp fallback strategies
Based on research findings for "Failed to extract any player response" error
"""

import os
import sys
import logging
import yt_dlp
from misc.appStreamlit import get_video_id_from_url, get_video_info

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_strategy_1_standard(video_url, output_dir):
    """Strategy 1: Standard yt-dlp download"""
    print("🧪 Strategy 1: Standard yt-dlp")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'quiet': False,  # Show verbose output for debugging
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    
    return True

def test_strategy_2_force_ipv4(video_url, output_dir):
    """Strategy 2: Force IPv4 connection"""
    print("🧪 Strategy 2: Force IPv4")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s_ipv4.%(ext)s'),
        'quiet': False,
        'force_ipv4': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    
    return True

def test_strategy_3_no_cert_check(video_url, output_dir):
    """Strategy 3: Bypass SSL certificate verification"""
    print("🧪 Strategy 3: No certificate check")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s_nocert.%(ext)s'),
        'quiet': False,
        'nocheckcertificate': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    
    return True

def test_strategy_4_android_client(video_url, output_dir):
    """Strategy 4: Use Android player client"""
    print("🧪 Strategy 4: Android player client")
    
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
    
    return True

def test_strategy_5_cookies_chrome(video_url, output_dir):
    """Strategy 5: Use Chrome browser cookies"""
    print("🧪 Strategy 5: Chrome browser cookies")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s_cookies.%(ext)s'),
        'quiet': False,
        'cookiesfrombrowser': ('chrome',),
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    
    return True

def test_strategy_6_live_specific(video_url, output_dir):
    """Strategy 6: Live stream specific options"""
    print("🧪 Strategy 6: Live stream specific")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s_live.%(ext)s'),
        'quiet': False,
        'live_from_start': True,
        'wait_for_video': 5,
        'hls_use_mpegts': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    
    return True

def test_strategy_7_combined_best(video_url, output_dir):
    """Strategy 7: Combined best practices"""
    print("🧪 Strategy 7: Combined best practices")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s_combined.%(ext)s'),
        'quiet': False,
        'force_ipv4': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        'user_agent': 'Mozilla/5.0 (Linux; Android 11; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        },
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    
    return True

def run_fallback_test(video_url):
    """Run all fallback strategies until one succeeds"""
    print(f"\n🎯 Testing URL: {video_url}")
    print("=" * 80)
    
    # Create output directory
    output_dir = "fallback_test_downloads"
    os.makedirs(output_dir, exist_ok=True)
    
    strategies = [
        test_strategy_1_standard,
        test_strategy_2_force_ipv4,
        test_strategy_3_no_cert_check,
        test_strategy_4_android_client,
        test_strategy_5_cookies_chrome,
        test_strategy_6_live_specific,
        test_strategy_7_combined_best,
    ]
    
    successful_strategies = []
    failed_strategies = []
    
    for i, strategy in enumerate(strategies, 1):
        print(f"\n{'='*20} Strategy {i}/{len(strategies)} {'='*20}")
        try:
            strategy(video_url, output_dir)
            successful_strategies.append(f"Strategy {i}: {strategy.__name__}")
            print(f"✅ Strategy {i} SUCCEEDED!")
            
            # If we want to test all strategies, continue
            # If we want to stop at first success, break here
            # break  # Uncomment to stop at first success
            
        except Exception as e:
            failed_strategies.append(f"Strategy {i}: {strategy.__name__} - {str(e)}")
            print(f"❌ Strategy {i} FAILED: {e}")
    
    # Results summary
    print(f"\n{'='*80}")
    print("📊 RESULTS SUMMARY")
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
    
    return len(successful_strategies) > 0

def main():
    """Main test function"""
    print("🔧 yt-dlp Fallback Strategy Tester")
    print("Researching solutions for 'Failed to extract player response' error")
    print("=" * 80)
    
    # Test URL that's causing issues
    test_url = "https://youtu.be/Dp75wqOrtBs?si=GqKCVPdXtcXQO7Yi"
    
    # First, get basic video info
    try:
        video_id = get_video_id_from_url(test_url)
        print(f"📹 Video ID: {video_id}")
        
        video_info = get_video_info(video_id)
        print(f"📝 Title: {video_info.get('title', 'Unknown')}")
        print(f"🔴 Live Status: {video_info.get('live_status', 'unknown')}")
        print(f"⏱️  Duration: {video_info.get('duration', 0)} seconds")
        
    except Exception as e:
        print(f"⚠️  Could not get basic video info: {e}")
    
    # Run the fallback test
    success = run_fallback_test(test_url)
    
    print(f"\n🏁 FINAL RESULT: {'SUCCESS' if success else 'ALL STRATEGIES FAILED'}")
    
    if not success:
        print("\n💡 RECOMMENDATIONS:")
        print("1. Update yt-dlp to nightly build: yt-dlp --update-to nightly")
        print("2. Clear cache: yt-dlp --rm-cache-dir")
        print("3. Try using your project's audio transcription fallback")
        print("4. Check if video requires authentication")
        print("5. Report issue to yt-dlp GitHub with verbose logs")

if __name__ == "__main__":
    main()