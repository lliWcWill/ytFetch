#!/usr/bin/env python3
"""
Test script for youtube-transcript-api v1.1.0 with Webshare proxy integration
"""

import os
import sys
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from config_loader import get_webshare_credentials

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_webshare_integration():
    """Test the new youtube-transcript-api with Webshare proxy"""
    print("🧪 Testing youtube-transcript-api v1.1.0 with Webshare Integration")
    print("=" * 80)
    
    # Get Webshare credentials
    webshare_username, webshare_password = get_webshare_credentials()
    
    if not webshare_username or not webshare_password:
        print("❌ No Webshare credentials found!")
        print("Please update your config.yaml with:")
        print("webshare_username: 'your_username'")
        print("webshare_password: 'your_password'")
        return False
    
    print(f"✅ Webshare credentials found: {webshare_username}")
    
    # Test video that previously failed
    test_video_id = "BBhZ9Ltpmdw"  # The live stream that was failing
    print(f"🎯 Testing with video ID: {test_video_id}")
    
    try:
        # Import new v1.1.0 components
        from youtube_transcript_api.proxies import WebshareProxyConfig
        
        print("🔗 Setting up Webshare proxy configuration...")
        proxy_config = WebshareProxyConfig(
            proxy_username=webshare_username,
            proxy_password=webshare_password
        )
        
        # Create API instance with proxy
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
        print("✅ YouTubeTranscriptApi instance created with Webshare proxy")
        
        # Test fetching transcript
        print("📜 Attempting to fetch transcript...")
        transcript = ytt_api.fetch(test_video_id, languages=['en', 'en-US', 'en-GB'])
        
        if transcript and transcript.segments:
            print(f"✅ SUCCESS! Fetched {len(transcript.segments)} transcript segments")
            print(f"📝 Language: {transcript.language}")
            print(f"🔊 First segment: {transcript.segments[0]}")
            
            # Test different formats
            print("\n🎨 Testing different output formats...")
            
            # Test text format
            text_content = transcript.format_as('text')
            print(f"📄 Text format: {len(text_content)} characters")
            
            # Test SRT format
            srt_content = transcript.format_as('srt')
            print(f"🎬 SRT format: {len(srt_content)} characters")
            
            # Test JSON format
            json_content = transcript.format_as('json')
            print(f"📊 JSON format: {len(json_content)} characters")
            
            return True
        else:
            print("❌ No transcript segments returned")
            return False
            
    except ImportError as e:
        print(f"❌ Import error - youtube-transcript-api v1.1.0 not properly installed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during transcript fetch: {e}")
        print(f"Error type: {type(e)}")
        return False

def test_fallback_compatibility():
    """Test that the old API still works as fallback"""
    print("\n🔄 Testing fallback compatibility with old API...")
    
    test_video_id = "BBhZ9Ltpmdw"
    
    try:
        # Test old API method
        transcript_list = YouTubeTranscriptApi.list_transcripts(test_video_id)
        transcript_obj = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        segments = transcript_obj.fetch()
        
        if segments:
            print(f"✅ Fallback API works: {len(segments)} segments")
            return True
        else:
            print("❌ Fallback API returned no segments")
            return False
            
    except Exception as e:
        print(f"❌ Fallback API failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting Webshare Integration Tests")
    print("=" * 80)
    
    # Test 1: New API with Webshare
    test1_success = test_webshare_integration()
    
    # Test 2: Fallback compatibility
    test2_success = test_fallback_compatibility()
    
    # Results
    print("\n" + "=" * 80)
    print("📊 TEST RESULTS")
    print("=" * 80)
    print(f"🔗 Webshare Integration: {'✅ PASSED' if test1_success else '❌ FAILED'}")
    print(f"🔄 Fallback Compatibility: {'✅ PASSED' if test2_success else '❌ FAILED'}")
    
    overall_success = test1_success or test2_success
    print(f"\n🏁 OVERALL RESULT: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
    
    if test1_success:
        print("\n💡 RECOMMENDATION: The new Webshare integration is working!")
        print("   Your transcript success rate should be significantly improved.")
    elif test2_success:
        print("\n💡 RECOMMENDATION: Fallback API works, but add Webshare credentials for better reliability.")
    else:
        print("\n💡 RECOMMENDATION: Check your Webshare credentials and network connection.")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)