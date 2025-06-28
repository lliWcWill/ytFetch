#!/usr/bin/env python3
"""
CLI wrapper for YouTube transcript fetching and audio transcription
Usage: python transcribe_cli.py <URL_or_FILE> [--output FORMAT] [--provider PROVIDER]
"""

import argparse
import sys
import os
from pathlib import Path
from audio_transcriber import transcribe_audio_from_file
from appStreamlit import get_video_id_from_url, fetch_transcript_segments, download_audio_as_mp3_enhanced, get_video_info, format_segments


def transcribe_url(url, output_format="txt", provider="groq"):
    """Transcribe a YouTube URL"""
    print(f"🎬 Processing YouTube URL: {url}")
    
    # Extract video ID
    video_id = get_video_id_from_url(url)
    if not video_id:
        print("❌ Error: Invalid YouTube URL")
        return None
    
    print(f"📹 Video ID: {video_id}")
    
    # Get video info
    video_info = get_video_info(video_id)
    print(f"📝 Title: {video_info['title']}")
    print(f"⏱️  Duration: {video_info['duration']} seconds")
    
    # Try transcript first
    try:
        print("🔍 Attempting to fetch existing transcript...")
        segments, language, error = fetch_transcript_segments(video_id)
        if segments:
            print(f"✅ Found transcript in {language}")
            formatted_text = format_segments(segments, output_format)
            return formatted_text
    except Exception as e:
        print(f"⚠️ Transcript fetch failed: {e}")
    
    # Fallback to audio transcription
    print("🎵 Downloading audio for transcription...")
    
    # Use enhanced download with status messages
    class CLIStatusPlaceholder:
        def info(self, msg): print(f"ℹ️  {msg}")
        def text(self, msg): print(f"   {msg}")
        def warning(self, msg): print(f"⚠️  {msg}")
        def success(self, msg): print(f"✅ {msg}")
        def error(self, msg): print(f"❌ {msg}")
    
    status = CLIStatusPlaceholder()
    audio_path = download_audio_as_mp3_enhanced(
        video_id, 
        video_title=video_info.get('title'),
        status_placeholder=status
    )
    
    if not audio_path:
        print("❌ Error: Could not download audio")
        return None
    
    print(f"📁 Audio saved to: {audio_path}")
    print(f"🤖 Transcribing with {provider}...")
    
    # Transcribe audio
    result = transcribe_audio_from_file(audio_path, provider=provider)
    
    # Clean up audio file
    os.remove(audio_path)
    
    if result and 'segments' in result:
        segments = result['segments']
        formatted_text = format_segments(segments, output_format)
        return formatted_text
    else:
        print("❌ Error: Transcription failed")
        return None


def transcribe_file(file_path, output_format="txt", provider="groq"):
    """Transcribe a local audio/video file"""
    print(f"🎵 Processing local file: {file_path}")
    
    if not os.path.exists(file_path):
        print("❌ Error: File not found")
        return None
    
    print(f"🤖 Transcribing with {provider}...")
    result = transcribe_audio_from_file(file_path, provider=provider)
    
    if result and 'segments' in result:
        segments = result['segments']
        formatted_text = format_segments(segments, output_format)
        return formatted_text
    else:
        print("❌ Error: Transcription failed")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe YouTube videos or local audio files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Transcribe YouTube video to text
  python transcribe_cli.py "https://www.youtube.com/watch?v=VIDEO_ID"
  
  # Transcribe to SRT format with OpenAI
  python transcribe_cli.py "https://youtu.be/VIDEO_ID" --output srt --provider openai
  
  # Transcribe local audio file
  python transcribe_cli.py "/path/to/audio.mp3" --output vtt
  
  # Output to file
  python transcribe_cli.py "URL" --output json > transcript.json
        """
    )
    
    parser.add_argument(
        "input", 
        help="YouTube URL or path to local audio/video file"
    )
    
    parser.add_argument(
        "--output", "-o",
        choices=["txt", "srt", "vtt", "json"],
        default="txt",
        help="Output format (default: txt)"
    )
    
    parser.add_argument(
        "--provider", "-p", 
        choices=["groq", "openai"],
        default="groq",
        help="Transcription provider for audio (default: groq)"
    )
    
    parser.add_argument(
        "--save", "-s",
        help="Save output to file instead of printing to stdout"
    )
    
    args = parser.parse_args()
    
    # Determine input type
    if args.input.startswith(('http://', 'https://', 'www.')):
        # YouTube URL
        result = transcribe_url(args.input, args.output, args.provider)
    else:
        # Local file
        result = transcribe_file(args.input, args.output, args.provider)
    
    if result:
        if args.save:
            # Save to file
            with open(args.save, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"✅ Transcript saved to: {args.save}")
        else:
            # Print to stdout
            print("\n" + "="*60)
            print("TRANSCRIPT")
            print("="*60)
            print(result)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()