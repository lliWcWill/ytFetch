from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from urllib.parse import urlparse, parse_qs
import sys
import yt_dlp
import xml.etree.ElementTree
import os
import re
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_video_id_from_url(youtube_url):
    """Extracts video ID from various YouTube URL formats."""
    if not youtube_url:
        return None
    
    # Clean the URL - remove any whitespace
    youtube_url = youtube_url.strip()
    
    parsed_url = urlparse(youtube_url)
    
    # Handle youtu.be short URLs
    if parsed_url.hostname == 'youtu.be':
        # Extract ID from path, removing any query parameters
        video_id = parsed_url.path[1:].split('?')[0].split('&')[0]
        return video_id if video_id else None
    
    # Handle youtube.com URLs
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
        if parsed_url.path == '/watch':
            p = parse_qs(parsed_url.query)
            video_id_list = p.get('v', [])
            if video_id_list:
                # Return just the video ID, not including any additional parameters
                return video_id_list[0].split('&')[0]
        if parsed_url.path.startswith('/embed/'):
            return parsed_url.path.split('/')[2].split('?')[0]
        if parsed_url.path.startswith('/v/'):
            return parsed_url.path.split('/')[2].split('?')[0]
        if parsed_url.path.startswith('/shorts/'):
            return parsed_url.path.split('/')[2].split('?')[0]
    return None

def sanitize_filename(filename):
    """Sanitize a string to be used as a filename."""
    # Remove invalid characters for Windows/Unix filenames
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    # Limit length to avoid filesystem issues
    if len(filename) > 200:
        filename = filename[:200]
    return filename

def get_video_info(video_id):
    """Get video title and other info using yt-dlp."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,  # Get full info including title
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {
                'title': info.get('title', f'video_{video_id}'),
                'id': video_id,
                'url': video_url,
                'duration': info.get('duration', 0)
            }
    except Exception as e:
        print(f"Warning: Could not fetch video info: {e}")
        return {
            'title': f'video_{video_id}',
            'id': video_id,
            'url': video_url,
            'duration': 0
        }

def download_audio_as_mp3(video_id, output_dir=".", video_title=None):
    """
    Download audio using subprocess to avoid yt-dlp progress bug.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Get video title if not provided
    if not video_title:
        video_info = get_video_info(video_id)
        video_title = video_info['title']
    
    # Sanitize title for filename
    safe_title = sanitize_filename(video_title)
    
    # Let yt-dlp determine the extension
    output_template = os.path.join(output_dir, f"{safe_title}.%(ext)s")
    
    logger.info(f"🎵 Starting audio download for: {video_title}")
    print("⬇️  Downloading audio (this may take a moment)...")
    
    download_start_time = time.time()
    
    # Use subprocess to completely avoid the Python API bug
    import subprocess
    import sys
    
    # Build command
    cmd = [
        sys.executable, '-m', 'yt_dlp',
        # Format selection - prioritize non-fragmented formats
        '-f', 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio[protocol^=http][protocol!*=dash]/bestaudio',
        # Completely disable progress to avoid the bug
        '--no-progress',
        '--quiet',
        '--no-warnings',
        # Ensure single video only
        '--no-playlist',
        # Output
        '-o', output_template,
        # Additional options
        '--socket-timeout', '30',
        '--retries', '10',
        '--fragment-retries', '10',
        # URL
        video_url
    ]
    
    # Add cookies if available
    if os.path.exists('cookies.txt'):
        cmd.extend(['--cookies', 'cookies.txt'])
    
    try:
        # Run the command with output suppression
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore'  # Ignore encoding errors
        )
        
        if result.returncode != 0:
            # Check if it's the specific progress error
            if "Progress Value has invalid value" in result.stderr or "1024.000000" in result.stderr:
                logger.warning("Encountered progress bug, retrying with different format...")
                
                # Retry with explicit format IDs that are known to be non-fragmented
                format_ids = ['140', '139', '251', '171', '141']  # Common non-fragmented audio formats
                
                for fmt_id in format_ids:
                    logger.info(f"Trying format ID: {fmt_id}")
                    
                    retry_cmd = cmd.copy()
                    retry_cmd[2] = fmt_id  # Replace format selection
                    
                    retry_result = subprocess.run(
                        retry_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',
                        errors='ignore'
                    )
                    
                    if retry_result.returncode == 0:
                        print("✅ Download complete!")
                        break
                    elif "requested format not available" in retry_result.stderr.lower():
                        continue
                    else:
                        logger.debug(f"Format {fmt_id} failed: {retry_result.stderr[:100]}")
                else:
                    # All formats failed
                    logger.error("All format attempts failed")
                    logger.error(f"Last error: {retry_result.stderr}")
                    return None
            else:
                logger.error(f"Download failed: {result.stderr}")
                return None
        else:
            print("✅ Download complete!")
            
    except subprocess.TimeoutExpired:
        logger.error("Download timed out")
        return None
    except Exception as e:
        logger.error(f"Subprocess error: {e}")
        return None
    
    # Find the downloaded file
    downloaded_file = None
    for ext in ['m4a', 'mp3', 'webm', 'opus', 'ogg', 'wav']:
        potential_path = os.path.join(output_dir, f"{safe_title}.{ext}")
        if os.path.exists(potential_path):
            downloaded_file = potential_path
            break
            
    if downloaded_file:
        download_time = time.time() - download_start_time
        file_size_mb = os.path.getsize(downloaded_file) / 1024 / 1024
        
        logger.info(f"✅ Audio downloaded successfully!")
        logger.info(f"   File: {downloaded_file}")
        logger.info(f"   Size: {file_size_mb:.1f} MB")
        logger.info(f"   Time: {download_time:.1f} seconds")
        logger.info(f"   Speed: {file_size_mb/download_time:.1f} MB/s average")
        
        if not downloaded_file.endswith('.mp3'):
            logger.info(f"   Note: Downloaded as {downloaded_file.split('.')[-1].upper()} "
                      f"(no conversion needed - faster!)")
            
        return downloaded_file
    else:
        logger.error("Downloaded file not found!")
        
        # Last attempt: Use system yt-dlp if available
        logger.info("Trying system yt-dlp command...")
        try:
            simple_cmd = [
                'yt-dlp',
                '-x',  # Extract audio
                '--audio-format', 'best',
                '--no-progress',
                '-q',  # Quiet
                '-o', output_template,
                video_url
            ]
            
            subprocess.run(simple_cmd, check=True, capture_output=True)
            
            # Check again
            for ext in ['m4a', 'mp3', 'webm', 'opus', 'ogg', 'wav']:
                potential_path = os.path.join(output_dir, f"{safe_title}.{ext}")
                if os.path.exists(potential_path):
                    print("✅ Download complete via system yt-dlp!")
                    return potential_path
                    
        except Exception:
            pass
            
        return None

def fetch_transcript_with_retry(video_id, max_retries=5):
    """
    Fetch transcript with robust retry logic for handling XML parsing errors.
    Returns: (transcript_obj, transcript_info, error_message)
    """
    retry_delay = 3  # Start with 3 seconds
    
    for attempt in range(max_retries):
        try:
            # Small delay before retry attempts
            if attempt > 0:
                print(f"Retry attempt {attempt + 1}/{max_retries}...")
                time.sleep(0.5)
            
            # Fetch available transcripts
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Verify we got valid data by testing list conversion
            test_list = list(transcript_list)
            if not test_list:
                raise Exception("Empty transcript list received from YouTube")
            
            # Re-fetch for iterator (since we consumed it above)
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Find the best available transcript
            transcript_obj = None
            transcript_info = ""
            
            # Prioritize English transcripts
            try:
                transcript_obj = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
                transcript_info = "Found manually created English transcript."
                print(transcript_info)
            except NoTranscriptFound:
                print("No manually created English transcript found. Trying generated English transcript...")
                try:
                    transcript_obj = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                    transcript_info = "Found generated English transcript."
                    print(transcript_info)
                except NoTranscriptFound:
                    print("No English transcript found (manual or generated). Trying to fetch the first available transcript...")
                    available_transcripts = list(transcript_list)
                    if available_transcripts:
                        transcript_obj = available_transcripts[0]
                        transcript_info = f"Found transcript in language: {transcript_obj.language} (code: {transcript_obj.language_code}), Generated: {transcript_obj.is_generated}"
                        print(transcript_info)
                    else:
                        return None, "", "No transcripts available for this video."
            
            if not transcript_obj:
                return None, "", "Could not select a transcript."
            
            # Try to fetch the actual transcript data
            print(f"Fetching transcript data for language: {transcript_obj.language} ({transcript_obj.language_code})...")
            transcript_data = transcript_obj.fetch()
            
            # Verify we got actual data
            if not transcript_data:
                raise Exception("Empty transcript data received")
            
            # Success! Return the data
            return transcript_obj, transcript_info, None
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Handle XML parsing errors specifically
            if "no element found" in error_str or "xml" in error_str or "empty" in error_str:
                if attempt < max_retries - 1:
                    print(f"⚠️  YouTube returned empty response (attempt {attempt + 1}/{max_retries})")
                    print(f"   Waiting {retry_delay} seconds before retry...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 10)  # Cap at 10 seconds
                else:
                    print(f"❌ Final attempt failed. YouTube may be experiencing issues.")
                    print(f"   Waiting 10 seconds for final retry...")
                    time.sleep(10)
                    return None, "", f"Failed to fetch transcript after {max_retries} attempts: {str(e)}"
            else:
                # For other errors, fail faster
                if attempt < max_retries - 1:
                    print(f"⚠️  Error: {str(e)[:100]}...")
                    print(f"   Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return None, "", f"Failed after {max_retries} attempts: {str(e)}"
    
    return None, "", f"Failed to fetch transcript after {max_retries} attempts"

def fetch_and_save_transcript(video_url, output_dir="."):
    video_id = get_video_id_from_url(video_url)

    if not video_id:
        print(f"Error: Could not extract video ID from URL: {video_url}")
        return

    print(f"Fetching transcript for video ID: {video_id}...")
    
    # Get video info including title
    video_info = get_video_info(video_id)
    video_title = video_info['title']
    safe_title = sanitize_filename(video_title)
    
    print(f"Video title: {video_title}")
    if video_info.get('duration'):
        print(f"Video duration: {video_info['duration']} seconds ({video_info['duration']/60:.1f} minutes)")
    
    os.makedirs(output_dir, exist_ok=True)

    # Use the new robust retry logic
    print("🔄 Attempting to fetch transcript (with automatic retries for reliability)...")
    transcript_obj, transcript_info, error = fetch_transcript_with_retry(video_id)
    
    if error:
        print(f"❌ {error}")
        print("🎵 Falling back to OPTIMIZED audio download...")
        audio_path = download_audio_as_mp3(video_id, output_dir=output_dir, video_title=video_title)
        if audio_path:
            print(f"✅ Audio ready for transcription: {audio_path}")
        return audio_path
    
    if not transcript_obj:
        print("❌ No transcript could be selected for fetching. Falling back to audio download...")
        audio_path = download_audio_as_mp3(video_id, output_dir=output_dir, video_title=video_title)
        return audio_path

    try:
        # transcript_obj is a Transcript object. .fetch() returns List[FetchedTranscriptSnippet]
        transcript_data = transcript_obj.fetch() 

        full_transcript_text = ""
        for entry in transcript_data: # entry is a FetchedTranscriptSnippet object
            # CORRECTED LINE: Access 'text' attribute using dot notation
            full_transcript_text += entry.text + " " 
            
        output_filename = os.path.join(output_dir, f"{safe_title}_transcript.txt")

        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(full_transcript_text.strip())
        
        print(f"✅ Transcript successfully saved to: {output_filename}")
        return output_filename

    except TranscriptsDisabled:
        print(f"❌ Transcripts are disabled for video: {video_id}. Falling back to audio download...")
        return download_audio_as_mp3(video_id, output_dir=output_dir, video_title=video_title)
    except NoTranscriptFound:
        print(f"❌ No transcript found for video: {video_id}. Falling back to audio download...")
        return download_audio_as_mp3(video_id, output_dir=output_dir, video_title=video_title)
    except VideoUnavailable:
        print(f"❌ Video {video_id} is unavailable (private, deleted, etc.).")
        return None
    except xml.etree.ElementTree.ParseError as e: 
        print(f"❌ Failed to parse transcript data ({e}). Falling back to audio download...")
        return download_audio_as_mp3(video_id, output_dir=output_dir, video_title=video_title)
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}. Falling back to audio download...")
        return download_audio_as_mp3(video_id, output_dir=output_dir, video_title=video_title)

if __name__ == "__main__":
    script_output_directory = "video_outputs" 
    
    try:
        if len(sys.argv) > 1:
            video_url_input = sys.argv[1]
        else:
            video_url_input = input("Enter the YouTube video URL: ").strip()
        
        if video_url_input:
            fetch_and_save_transcript(video_url_input, output_dir=script_output_directory)
        else:
            print("No URL provided.")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(0)