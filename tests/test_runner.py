# test_runner.py
import yaml
import sys
import os

# Add the current directory to Python path to import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the orchestrator function directly
try:
    from misc.appStreamlit import get_transcript_with_fallback
except ImportError:
    print("❌ ERROR: Could not import get_transcript_with_fallback from appStreamlit")
    print("    Make sure appStreamlit.py exists and the function is defined")
    sys.exit(1)

def load_api_key():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
        return config.get("youtube", {}).get("api_key")

def run_test(video_id, expected_method):
    print(f"\n--- TESTING VIDEO ID: {video_id} ---")
    print(f"    EXPECTED METHOD: {expected_method}")
    api_key = load_api_key()
    
    transcript, method_used, failure_reasons = get_transcript_with_fallback(video_id, api_key)
    
    if transcript and method_used == expected_method:
        print(f"✅ PASS: Transcript found using the correct method: '{method_used}'")
        print(f"    Transcript snippet: '{transcript[:100]}...'")
    elif method_used != expected_method:
        print(f"❌ FAIL: Used method '{method_used}' but expected '{expected_method}'")
        if failure_reasons:
            print(f"    Failure reasons: {failure_reasons}")
    else:
        print(f"❌ FAIL: No transcript found. Final status: '{method_used}'")
        if failure_reasons:
            print(f"    Failure reasons: {failure_reasons}")

if __name__ == "__main__":
    # Define your test cases here
    test_cases = {
        # Tier 1 Success: Video with known manual captions
        "dQw4w9WgXcQ": "Official YouTube API",
        
        # Tier 2 Success: Video with only auto-captions (your original problem case)
        "aR6CzM0x-g0": "Unofficial Transcript Library",
        
        # Tier 3 Success: Video with captions disabled, < 10 mins
        # You may need to upload a short, unlisted video with captions turned off for this test
        "YOUR_TEST_VIDEO_ID_NO_CAPTIONS": "AI Audio Transcription",
        
        # Tier 3 Skip (Duration): Video with no captions, > 10 mins
        "kL8Bfl_c4dY": "All methods failed", # Example: A long gaming stream with no captions
        
        # Total Failure: A known private or deleted video
        "invalid_or_private_id": "All methods failed",
    }
    
    print("🧪 Starting Multi-Tiered Transcript Fetching System Tests")
    print("=" * 60)
    
    for video_id, expected in test_cases.items():
        run_test(video_id, expected)
    
    print("\n" + "=" * 60)
    print("🏁 Testing Complete")