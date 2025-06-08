import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from youtube_transcript_api.formatters import SRTFormatter, WebVTTFormatter, JSONFormatter, TextFormatter
from urllib.parse import urlparse, parse_qs
import json # For pretty printing JSON output
import yt_dlp
import re
import time
import yaml
import os
import tempfile
import logging
import googleapiclient.discovery
import googleapiclient.errors
import io
from googleapiclient.http import MediaIoBaseDownload
from audio_transcriber import transcribe_audio_from_file
import isodate
from auth_utils import get_credentials

# --- Configuration Loading ---

def load_config():
    """Load configuration from config.yaml file"""
    try:
        with open("config.yaml", "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        st.error("config.yaml file not found. Please create it with your API keys.")
        st.stop()
    except yaml.YAMLError:
        st.error("Error parsing config.yaml. Please check its format.")
        st.stop()

# Load configuration at startup
config = load_config()
youtube_api_key = config.get("youtube", {}).get("api_key")


# --- Core Transcript Logic (adapted from your script) ---

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

def parse_iso8601_duration(duration_str: str) -> int:
    """Converts an ISO 8601 duration string to total seconds using robust isodate library."""
    if not duration_str:
        return 0
        
    try:
        # isodate is the most robust way to handle this
        duration_obj = isodate.parse_duration(duration_str)
        return int(duration_obj.total_seconds())
    except (isodate.ISO8601Error, ValueError, AttributeError):
        # Fallback for simple cases if isodate fails
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            logging.warning(f"Failed to parse duration: {duration_str}")
            return 0
        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        seconds = int(match.group(3)) if match.group(3) else 0
        return hours * 3600 + minutes * 60 + seconds

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
                'duration': info.get('duration', 0)  # Duration in seconds
            }
    except Exception as e:
        st.warning(f"Could not fetch video info: {e}")
        return {
            'title': f'video_{video_id}',
            'id': video_id,
            'url': video_url,
            'duration': 0
        }

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

def fetch_transcript_segments(video_id):
    """
    Fetches transcript segments for a given video ID.
    Returns a tuple: (segments_list, transcript_info, error_message)
    """
    print(f"\n🔍 DEBUG: Starting fetch_transcript_segments for video_id: {video_id}")
    
    if not video_id:
        print("❌ DEBUG: Invalid video_id provided")
        return None, "", "Invalid Video ID."
    
    try:
        # Add timeout and retry logic with better error handling
        import time
        max_retries = 5  # Increased retries
        retry_delay = 3  # Start with longer delay
        
        print(f"🔄 DEBUG: Starting retry loop with max_retries={max_retries}, initial_delay={retry_delay}s")
        
        for attempt in range(max_retries):
            print(f"\n📍 DEBUG: Attempt {attempt + 1}/{max_retries}")
            try:
                # Clear any potential cache or session issues
                if attempt > 0:
                    print(f"⏱️  DEBUG: Waiting 0.5s before retry attempt...")
                    time.sleep(0.5)  # Small delay before retry
                    
                # Use a longer timeout for long videos
                print(f"🌐 DEBUG: Calling YouTubeTranscriptApi.list_transcripts({video_id})")
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                print(f"✅ DEBUG: Successfully got transcript_list object")
                
                # Verify we got valid data
                print(f"🔍 DEBUG: Testing transcript_list by converting to list...")
                test_list = list(transcript_list)
                print(f"📋 DEBUG: Found {len(test_list)} available transcripts: {[(t.language, t.language_code, t.is_generated) for t in test_list]}")
                
                if test_list:  # If we have transcripts, we're good
                    print(f"✅ DEBUG: Transcript list validation successful, re-fetching for processing...")
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)  # Re-fetch for iterator
                    break
                else:
                    print(f"❌ DEBUG: Empty transcript list received from YouTube")
                    raise Exception("Empty transcript list received")
                    
            except Exception as e:
                error_str = str(e).lower()
                print(f"💥 DEBUG: Exception in attempt {attempt + 1}: {type(e).__name__}: {str(e)}")
                print(f"🔍 DEBUG: Error string analysis - error_str: '{error_str}'")
                
                # Check for XML parsing errors specifically
                if "no element found" in error_str or "xml" in error_str:
                    print(f"🔴 DEBUG: Detected XML parsing error")
                    if attempt < max_retries - 1:
                        retry_msg = f"⚠️ YouTube returned empty response (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds..."
                        print(f"⏳ DEBUG: {retry_msg}")
                        with st.container():
                            st.warning(retry_msg)
                            progress_bar = st.progress(0)
                            for i in range(int(retry_delay)):
                                progress_bar.progress((i + 1) / retry_delay)
                                time.sleep(1)
                            progress_bar.empty()
                        retry_delay = min(retry_delay * 1.5, 10)  # Cap at 10 seconds
                        print(f"🔄 DEBUG: Next retry_delay will be {retry_delay}s")
                    else:
                        # On final attempt, try one more time with a long delay
                        print(f"🔴 DEBUG: Final attempt failed with XML error, trying extended delay...")
                        st.warning("❌ Final retry attempt with extended delay...")
                        progress_bar = st.progress(0)
                        for i in range(10):
                            progress_bar.progress((i + 1) / 10)
                            time.sleep(1)
                        progress_bar.empty()
                        raise e
                else:
                    # For other errors, use original retry logic
                    print(f"🟡 DEBUG: Non-XML error detected")
                    if attempt < max_retries - 1:
                        print(f"⏳ DEBUG: Retrying non-XML error in {retry_delay}s...")
                        st.warning(f"⚠️ Attempt {attempt + 1} failed: {str(e)[:100]}... Retrying in {retry_delay} seconds...")
                        progress_bar = st.progress(0)
                        for i in range(int(retry_delay)):
                            progress_bar.progress((i + 1) / retry_delay)
                            time.sleep(1)
                        progress_bar.empty()
                        retry_delay *= 2  # Exponential backoff
                        print(f"🔄 DEBUG: Next retry_delay will be {retry_delay}s")
                    else:
                        print(f"🔴 DEBUG: All retry attempts exhausted with non-XML error")
                        raise e
        
        print(f"🎯 DEBUG: Successfully exited retry loop, proceeding with transcript selection...")
        transcript_obj = None
        transcript_info = ""
        
        # Get all available transcripts for debugging
        print(f"🔍 DEBUG: Re-listing transcripts for selection...")
        available_transcripts = list(transcript_list)
        debug_info = f"Available transcripts: {[(t.language, t.language_code, t.is_generated) for t in available_transcripts]}"
        print(f"📋 DEBUG: {debug_info}")
        
        # Prioritize English, then first available
        print(f"🎯 DEBUG: Attempting to find manually created English transcript...")
        try:
            transcript_obj = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
            transcript_info = f"Manually created English transcript. {debug_info}"
            print(f"✅ DEBUG: Found manually created English transcript")
        except NoTranscriptFound:
            print(f"⚠️  DEBUG: No manually created English transcript, trying auto-generated...")
            try:
                transcript_obj = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                transcript_info = f"Auto-generated English transcript. {debug_info}"
                print(f"✅ DEBUG: Found auto-generated English transcript")
            except NoTranscriptFound:
                print(f"⚠️  DEBUG: No English transcripts found, using first available...")
                if available_transcripts:
                    transcript_obj = available_transcripts[0]
                    transcript_info = f"Transcript in {transcript_obj.language} (code: {transcript_obj.language_code}), Generated: {transcript_obj.is_generated}. {debug_info}"
                    print(f"✅ DEBUG: Using first available transcript: {transcript_obj.language} ({transcript_obj.language_code})")
                else:
                    print(f"❌ DEBUG: No transcripts available at all")
                    return None, "", f"No transcripts available for this video. {debug_info}"
        
        if not transcript_obj:
            print(f"❌ DEBUG: transcript_obj is None after selection process")
            return None, "", f"Could not select a transcript. {debug_info}"

        # Fetch segments with progress indication for long videos
        print(f"📥 DEBUG: About to fetch transcript data from selected transcript...")
        st.info("Fetching transcript segments (this might take a while for long videos)...")
        print(f"🌐 DEBUG: Calling transcript_obj.fetch()...")
        fetched_transcript = transcript_obj.fetch()
        print(f"✅ DEBUG: Successfully fetched transcript data, type: {type(fetched_transcript)}")
        
        # Handle the FetchedTranscript object - extract segments from the snippets property
        if hasattr(fetched_transcript, 'snippets'):
            # New API version returns FetchedTranscript object with snippets property
            fetched_segments = []
            for snippet in fetched_transcript.snippets:
                # Check if snippet is already a dict or if it's an object with attributes
                if isinstance(snippet, dict):
                    fetched_segments.append(snippet)
                else:
                    # Convert FetchedTranscriptSnippet objects to dictionaries
                    segment_dict = {
                        'text': snippet.text,
                        'start': snippet.start,
                        'duration': snippet.duration
                    }
                    fetched_segments.append(segment_dict)
        elif isinstance(fetched_transcript, list):
            # Old API version returns list directly - check if items are dicts or objects
            fetched_segments = []
            for item in fetched_transcript:
                if isinstance(item, dict):
                    fetched_segments.append(item)
                else:
                    # Convert objects to dictionaries
                    segment_dict = {
                        'text': getattr(item, 'text', ''),
                        'start': getattr(item, 'start', 0),
                        'duration': getattr(item, 'duration', 0)
                    }
                    fetched_segments.append(segment_dict)
        else:
            # Try to convert to list if it's iterable
            try:
                temp_list = list(fetched_transcript)
                fetched_segments = []
                for item in temp_list:
                    if isinstance(item, dict):
                        fetched_segments.append(item)
                    else:
                        segment_dict = {
                            'text': getattr(item, 'text', ''),
                            'start': getattr(item, 'start', 0),
                            'duration': getattr(item, 'duration', 0)
                        }
                        fetched_segments.append(segment_dict)
            except Exception as convert_error:
                return None, "", f"Could not convert transcript data to list: {convert_error}. Got type: {type(fetched_transcript)}. {debug_info}"
        
        # Validate segments
        if not fetched_segments:
            return None, "", f"Transcript object returned empty segments. {debug_info}"
        
        if not isinstance(fetched_segments, list):
            return None, "", f"Expected list of segments, got {type(fetched_segments)}. {debug_info}"
        
        if len(fetched_segments) == 0:
            return None, "", f"Transcript segments list is empty. {debug_info}"
        
        # Check if segments have the expected structure
        sample_segment = fetched_segments[0] if fetched_segments else {}
        if not isinstance(sample_segment, dict) or 'text' not in sample_segment:
            return None, "", f"Invalid segment structure. Sample: {sample_segment}. {debug_info}"
        
        return fetched_segments, transcript_info, None

    except TranscriptsDisabled:
        return None, "", f"Transcripts are disabled for video: {video_id}. This often happens with copyrighted content or creator settings."
    except NoTranscriptFound: # Should be caught by earlier logic, but as a fallback
        return None, "", f"No transcript found for video: {video_id}. The video may not have captions available."
    except VideoUnavailable:
        return None, "", f"Video {video_id} is unavailable (private, deleted, etc.)."
    except Exception as e:
        error_msg = str(e)
        if "HTTP Error 429" in error_msg:
            return None, "", f"Rate limit exceeded. Please wait a few minutes before trying again. Error: {error_msg}"
        elif "connection" in error_msg.lower():
            return None, "", f"Connection error. This might be due to network issues or IP blocking. Error: {error_msg}"
        elif "no element found" in error_msg.lower():
            return None, "", f"XML parsing error. This might be a temporary YouTube issue. Please try again in a moment. Error: {error_msg}"
        elif "line 1, column 0" in error_msg:
            return None, "", f"Empty response received. This might be a temporary YouTube issue. Please try again in a moment. Error: {error_msg}"
        else:
            return None, "", f"An unexpected error occurred: {error_msg}"

def parse_srt_to_segments(srt_text):
    """Parse SRT format text into segments compatible with existing format."""
    import re
    
    segments = []
    
    # Split by double newlines to get individual subtitle blocks
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    
    for block in blocks:
        if not block.strip():
            continue
            
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
            
        # Skip the sequence number (first line)
        # Parse timestamp (second line)
        timestamp_line = lines[1]
        # Format: "00:00:00,000 --> 00:00:05,000"
        timestamp_match = re.match(r'([0-9:,]+)\s*-->\s*([0-9:,]+)', timestamp_line)
        
        if timestamp_match:
            start_time_str = timestamp_match.group(1)
            end_time_str = timestamp_match.group(2)
            
            # Convert timestamp to seconds
            start_seconds = srt_time_to_seconds(start_time_str)
            end_seconds = srt_time_to_seconds(end_time_str)
            duration = end_seconds - start_seconds
            
            # Join remaining lines as text
            text = '\n'.join(lines[2:]).strip()
            # Remove HTML tags that might be in SRT
            text = re.sub(r'<[^>]+>', '', text)
            
            if text:  # Only add if there's actual text
                segments.append({
                    'text': text,
                    'start': start_seconds,
                    'duration': duration
                })
    
    return segments

def srt_time_to_seconds(time_str):
    """Convert SRT timestamp format (HH:MM:SS,mmm) to seconds."""
    # Replace comma with dot for milliseconds
    time_str = time_str.replace(',', '.')
    
    # Split into parts
    parts = time_str.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_and_ms = float(parts[2])
        
        total_seconds = hours * 3600 + minutes * 60 + seconds_and_ms
        return total_seconds
    
    return 0

def format_segments(segments, output_format="txt"):
    """Formats fetched segments into the desired string format."""
    if not segments:
        return "No segments provided to format."
    
    if not isinstance(segments, list):
        return f"Expected list of segments, got {type(segments)}."
    
    if len(segments) == 0:
        return "Segments list is empty."

    try:
        # For very long videos, show progress
        if len(segments) > 1000:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
        # Convert segments to the format expected by the formatters
        # The formatters expect objects with .text, .start, .duration attributes
        # But we have dictionaries, so we need to convert them
        
        class TranscriptSegment:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration
        
        formatted_segments = []
        for segment in segments:
            if isinstance(segment, dict):
                # Convert dict to object format expected by formatters
                formatted_segment = TranscriptSegment(
                    text=segment.get('text', ''),
                    start=segment.get('start', 0),
                    duration=segment.get('duration', 0)
                )
                formatted_segments.append(formatted_segment)
            else:
                # Already in object format
                formatted_segments.append(segment)
            
        if output_format == "srt":
            formatter = SRTFormatter()
            if len(segments) > 1000:
                status_text.text("Formatting as SRT (this may take a while)...")
                progress_bar.progress(0.5)
            formatted_text = formatter.format_transcript(formatted_segments)
            if len(segments) > 1000:
                progress_bar.progress(1.0)
                status_text.empty()
                progress_bar.empty()
            return formatted_text
            
        elif output_format == "vtt":
            formatter = WebVTTFormatter()
            if len(segments) > 1000:
                status_text.text("Formatting as WebVTT (this may take a while)...")
                progress_bar.progress(0.5)
            formatted_text = formatter.format_transcript(formatted_segments)
            if len(segments) > 1000:
                progress_bar.progress(1.0)
                status_text.empty()
                progress_bar.empty()
            return formatted_text
            
        elif output_format == "json":
            if len(segments) > 1000:
                status_text.text("Formatting as JSON (this may take a while)...")
                progress_bar.progress(0.5)
            # For JSON, we can use the original dict format
            formatted_text = json.dumps(segments, indent=2, ensure_ascii=False)
            if len(segments) > 1000:
                progress_bar.progress(1.0)
                status_text.empty()
                progress_bar.empty()
            return formatted_text
            
        elif output_format == "txt":
            if len(segments) > 1000:
                status_text.text("Formatting as plain text (this may take a while)...")
                progress_bar.progress(0.5)
            
            # For plain text, we can do it manually to avoid formatter issues
            text_parts = []
            for segment in segments:
                if isinstance(segment, dict):
                    text_parts.append(segment.get('text', ''))
                else:
                    text_parts.append(getattr(segment, 'text', ''))
            
            formatted_text = ' '.join(text_parts)
            
            if len(segments) > 1000:
                progress_bar.progress(1.0)
                status_text.empty()
                progress_bar.empty()
            return formatted_text
        else:
            return f"Unsupported format: {output_format}"
            
    except Exception as e:
        return f"Error formatting transcript: {str(e)}"

def download_audio_as_mp3(video_id, output_dir="video_outputs", video_title=None):
    """Download the audio of a YouTube video as MP3 using yt-dlp."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Get video title if not provided
    if not video_title:
        video_info = get_video_info(video_id)
        video_title = video_info['title']
    
    # Sanitize title for filename
    safe_title = sanitize_filename(video_title)
    
    output_template = os.path.join(output_dir, f"{safe_title}.%(ext)s")
    final_mp3_path = os.path.join(output_dir, f"{safe_title}.mp3")

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        # Check if the mp3 file was actually created
        if os.path.exists(final_mp3_path):
            logging.info(f"Audio successfully downloaded to: {final_mp3_path}")
            return final_mp3_path
        else:
            logging.error(f"Audio download failed. Target file {final_mp3_path} not found.")
            return None
            
    except Exception as e:
        logging.error(f"Error downloading audio: {e}")
        return None

def get_transcript_with_fallback(video_id, api_key, credentials=None):
    """
    Tries to fetch a transcript using a cascading fallback strategy.
    Returns a tuple: (transcript_text, method_used, failure_reasons)
    """
    failure_reasons = []
    
    # --- TIER 1: Try Official YouTube Data API v3 ---
    if credentials:
        logging.info("TIER 1: Attempting to fetch with Official YouTube API (Authenticated)...")
        st.info("Tier 1: Attempting to fetch with Official YouTube API (Authenticated)...")
        
        with st.spinner("🔍 Tier 1: Checking for official manual captions (OAuth2)..."):
            try:
                youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
                captions_request = youtube.captions().list(part="snippet", videoId=video_id)
                captions_response = captions_request.execute()

                if captions_response.get("items"):
                    logging.info("Success: Found manually uploaded caption track(s).")
                    # Prefer manual captions over auto-generated
                    manual_captions = [item for item in captions_response["items"] 
                                     if item["snippet"].get("trackKind") != "ASR"]
                    
                    if manual_captions:
                        caption_id = manual_captions[0]["id"]
                        logging.info(f"Using manual caption track: {caption_id}")
                    else:
                        caption_id = captions_response["items"][0]["id"]
                        logging.info(f"Using first available caption track: {caption_id}")
                    
                    download_request = youtube.captions().download(id=caption_id, tfmt="srt")
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, download_request)
                    
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                    
                    fh.seek(0)
                    transcript = fh.read().decode('utf-8')
                    st.success("✅ Tier 1: Official YouTube API (OAuth2) succeeded!")
                    return (transcript, "Official YouTube API (OAuth2)", [])
                else:
                    failure_reason = "No manual captions found via Official API (OAuth2)"
                    failure_reasons.append(failure_reason)
                    logging.info(failure_reason)
                    st.warning(f"⚠️ Tier 1: {failure_reason}")

            except googleapiclient.errors.HttpError as e:
                failure_reason = f"Official API (OAuth2) HTTP Error: {str(e)[:100]}"
                failure_reasons.append(failure_reason)
                logging.error(f"Official API failed with HTTP Error: {e}")
                st.warning(f"⚠️ Tier 1: {failure_reason}...")
            except Exception as e:
                failure_reason = f"Official API (OAuth2) unexpected error: {str(e)[:100]}"
                failure_reasons.append(failure_reason)
                logging.error(f"Unexpected error with official API: {e}")
                st.warning(f"⚠️ Tier 1: {failure_reason}...")
    else:
        st.info("Tier 1 Skipped: User is not authenticated.")
        failure_reasons.append("Tier 1 skipped: No OAuth2 authentication")

    # --- TIER 2: Try Unofficial youtube-transcript-api Library ---
    logging.info("TIER 2: Attempting to fetch with unofficial library...")
    
    # Retry logic for unofficial library
    max_attempts = 3
    retry_delay = 3  # seconds
    
    for attempt in range(max_attempts):
        with st.spinner(f"🔍 Tier 2: Searching for auto-generated transcripts (attempt {attempt + 1}/{max_attempts})..."):
            segments, info, error = fetch_transcript_segments(video_id)
            if segments:
                logging.info("Success: Found auto-generated transcript.")
                transcript = format_segments(segments, "txt")
                st.success("✅ Tier 2: Unofficial transcript API succeeded!")
                return (transcript, "Unofficial Transcript Library", failure_reasons)
            else:
                failure_reason = f"Unofficial API failed (attempt {attempt + 1}): {error[:100] if error else 'Unknown error'}"
                logging.info(f"Unofficial library failed on attempt {attempt + 1}. Error: {error}")
                
                if attempt < max_attempts - 1:  # Not the last attempt
                    st.warning(f"⚠️ Tier 2: {failure_reason}... Retrying in {retry_delay} seconds...")
                    # Show a progress bar for the wait time
                    progress_bar = st.progress(0)
                    for i in range(retry_delay):
                        progress_bar.progress((i + 1) / retry_delay)
                        time.sleep(1)
                    progress_bar.empty()
                else:  # Last attempt
                    failure_reasons.append(f"Unofficial API failed after {max_attempts} attempts: {error[:100] if error else 'Unknown error'}")
                    st.warning(f"⚠️ Tier 2: All {max_attempts} attempts failed...")

    # --- TIER 3: Try Audio Transcription via AI ---
    logging.info("TIER 3: Attempting audio transcription as a last resort...")
    
    # Get video duration first
    video_info = get_video_info(video_id)
    video_duration = video_info.get('duration', 0)
    
    if video_duration <= 600:  # 10 minutes
        logging.info(f"Video duration ({video_duration}s) is within the limit. Proceeding.")
        
        with st.spinner("🔍 Tier 3: Preparing for AI audio transcription..."):
            try:
                # Download audio to temporary file
                with st.spinner("⬇️ Downloading audio for transcription..."):
                    audio_path = download_audio_as_mp3(video_id, output_dir="video_outputs", 
                                                     video_title=video_info.get('title'))
                
                if audio_path and os.path.exists(audio_path):
                    logging.info(f"Audio downloaded successfully: {audio_path}")
                    
                    # Transcribe audio
                    with st.spinner("🤖 Transcribing audio with AI..."):
                        transcript = transcribe_audio_from_file(audio_path, language="en")
                    
                    # Clean up audio file
                    try:
                        os.remove(audio_path)
                        logging.info(f"Cleaned up temporary audio file: {audio_path}")
                    except Exception as cleanup_error:
                        logging.warning(f"Failed to clean up audio file: {cleanup_error}")
                    
                    if transcript:
                        # Add video title and URL to the transcript
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        video_title = video_info.get('title', f'video_{video_id}')
                        
                        # Prepend video info to transcript
                        full_transcript = f"Video Title: {video_title}\n"
                        full_transcript += f"YouTube URL: {video_url}\n"
                        full_transcript += f"Video ID: {video_id}\n"
                        full_transcript += "-" * 80 + "\n\n"
                        full_transcript += transcript
                        
                        st.success("✅ Tier 3: AI audio transcription succeeded!")
                        return (full_transcript, "AI Audio Transcription", failure_reasons)
                    else:
                        failure_reason = "AI transcription produced empty results"
                        failure_reasons.append(failure_reason)
                        logging.error("Audio transcription returned empty result")
                        st.error(f"❌ Tier 3: {failure_reason}")
                else:
                    failure_reason = "Audio download failed"
                    failure_reasons.append(failure_reason)
                    logging.error("Audio download failed")
                    st.error(f"❌ Tier 3: {failure_reason}")
                    
            except Exception as e:
                failure_reason = f"Audio transcription error: {str(e)[:100]}"
                failure_reasons.append(failure_reason)
                logging.error(f"Audio transcription failed: {e}")
                st.error(f"❌ Tier 3: {failure_reason}...")
    else:
        failure_reason = f"Video too long ({video_duration//60}:{video_duration%60:02d}) - exceeds 10-minute limit for AI transcription"
        failure_reasons.append(failure_reason)
        logging.info(f"Video is longer than 10 minutes ({video_duration}s). Skipping audio transcription.")
        st.warning(f"⚠️ Tier 3: {failure_reason}")

    # If all methods fail - provide specific failure summary
    failure_summary = generate_failure_summary(failure_reasons, video_duration)
    st.error(failure_summary)
    return (None, "All methods failed", failure_reasons)

def generate_failure_summary(failure_reasons, video_duration):
    """Generate a specific failure message based on what went wrong."""
    if not failure_reasons:
        return "❌ Could not retrieve a transcript for this video."
    
    summary = "❌ Could not retrieve a transcript. "
    
    # Check if all standard methods failed and AI was skipped due to duration
    duration_skipped = any("exceeds 10-minute limit" in reason for reason in failure_reasons)
    api_failures = [r for r in failure_reasons if "exceeds 10-minute limit" not in r]
    
    if duration_skipped and api_failures:
        summary += "No manual or auto-generated transcripts were found, and AI transcription was skipped because the video is longer than the 10-minute limit."
    elif len(api_failures) >= 2 and not duration_skipped:
        summary += "Manual and auto-generated transcript methods failed, and AI transcription was unsuccessful."
    elif "Official API" in failure_reasons[0] and "Unofficial API" in failure_reasons[1]:
        summary += "Both official and unofficial transcript APIs failed."
    else:
        summary += "All available transcript methods failed."
    
    return summary

# --- Streamlit App UI ---

st.set_page_config(page_title="YouTube Transcript Fetcher", layout="wide")
st.title("🎬 YouTube Transcript Fetcher")

# --- CORRECTED Authentication Sidebar ---
st.sidebar.title("Authentication")

# Initialize credentials in the session state if they don't exist.
# This happens only ONCE per session.
if 'credentials' not in st.session_state:
    st.session_state.credentials = None

# Let get_credentials() manage the flow. It will return an auth_url
# if the user needs to log in, and it will handle the redirect itself.
auth_url = get_credentials()

# The UI now simply READS the state to decide what to show.
# It does NOT change the state itself.
if st.session_state.get('credentials'):
    # STATE 1: User is successfully authenticated.
    st.sidebar.success("✅ Authenticated with Google")
else:
    # STATE 2: User is NOT authenticated.
    if auth_url:
        # Show the login button if we have a URL for it.
        st.sidebar.link_button("Authenticate with Google", auth_url, use_container_width=True)
        st.sidebar.info("Authenticate to enable fetching of official, manually-uploaded transcripts (Tier 1).")
    else:
        # This state occurs during the redirect or if there's an error.
        st.sidebar.warning("Awaiting authentication...")

# Initialize session state variables
if 'video_id' not in st.session_state:
    st.session_state.video_id = None
if 'fetched_segments' not in st.session_state:
    st.session_state.fetched_segments = None
if 'error_message' not in st.session_state:
    st.session_state.error_message = None
if 'selected_format' not in st.session_state:
    st.session_state.selected_format = "txt" # Default format
if 'transcript_type_info' not in st.session_state:
    st.session_state.transcript_type_info = ""
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False
if 'video_info' not in st.session_state:
    st.session_state.video_info = None
if 'transcript_cache' not in st.session_state:
    st.session_state.transcript_cache = {}  # Cache transcripts by video ID

# Debug mode toggle
st.session_state.debug_mode = st.checkbox("Enable Debug Mode", value=st.session_state.debug_mode)

# URL Input with form for Enter key support
with st.form(key="url_form"):
    url = st.text_input("Enter YouTube Video URL:", key="youtube_url_input")
    col1, col2 = st.columns([1, 5])
    with col1:
        submit_button = st.form_submit_button("Fetch Transcript", use_container_width=True)
    with col2:
        st.caption("💡 Tip: Press Enter to fetch transcript")

if submit_button:
    print(f"\n🎬 DEBUG: ===== SUBMIT BUTTON PRESSED =====")
    print(f"🔗 DEBUG: Input URL: '{url}'")
    
    if url:
        print(f"🔍 DEBUG: Extracting video_id from URL...")
        video_id = get_video_id_from_url(url)
        print(f"🎯 DEBUG: Extracted video_id: '{video_id}'")
        
        if video_id:
            print(f"✅ DEBUG: Valid video_id extracted")
            # Check if this is the same video as before
            if st.session_state.video_id == video_id and st.session_state.fetched_segments:
                print(f"💾 DEBUG: Found same video in session state with existing segments")
                st.info("Using cached transcript for this video.")
            else:
                print(f"🔄 DEBUG: New video or no existing segments, proceeding with fetch...")
                # Clear previous results for new video
                st.session_state.video_id = video_id
                st.session_state.fetched_segments = None
                st.session_state.error_message = None
                st.session_state.transcript_type_info = ""
                st.session_state.video_info = None

                # Check cache first
                print(f"🗄️  DEBUG: Checking transcript cache for video_id: {video_id}")
                if video_id in st.session_state.transcript_cache:
                    print(f"💾 DEBUG: Found cached data for this video")
                    st.info("Loading transcript from cache...")
                    cached_data = st.session_state.transcript_cache[video_id]
                    st.session_state.fetched_segments = cached_data['segments']
                    st.session_state.transcript_type_info = cached_data['info']
                    st.session_state.video_info = cached_data['video_info']
                    st.session_state.error_message = None
                else:
                    print(f"🆕 DEBUG: No cached data found, fetching fresh transcript...")
                    
                    # Get video info first
                    print(f"📹 DEBUG: Fetching video information...")
                    with st.spinner("Fetching video information..."):
                        st.session_state.video_info = get_video_info(video_id)
                        print(f"✅ DEBUG: Video info retrieved: {st.session_state.video_info}")
                        
                    # Create containers for progress updates
                    status_container = st.empty()
                    progress_container = st.empty()
                    
                    status_container.info("🔄 Attempting to fetch transcript (with automatic retries for reliability)...")
                    
                    print(f"🚀 DEBUG: Starting transcript fetch process with multi-tier fallback...")
                    
                    # Use the new multi-tier orchestrator
                    transcript_text, method_used, failure_reasons = get_transcript_with_fallback(
                        video_id, 
                        youtube_api_key, 
                        credentials=st.session_state.get('credentials')
                    )
                    print(f"🏁 DEBUG: get_transcript_with_fallback returned - method: {method_used}")
                    
                    if transcript_text: # Success
                        print(f"✅ DEBUG: Successfully fetched transcript using: {method_used}")
                        status_container.success(f"✅ Transcript fetched successfully using {method_used}!")
                        progress_container.empty()
                        time.sleep(1)  # Brief pause to show success
                        status_container.empty()
                        
                        # Convert transcript text to segments format for compatibility
                        # For non-segment based methods, create a single segment
                        if method_used == "Official YouTube API":
                            # SRT format - parse into segments
                            segments = parse_srt_to_segments(transcript_text)
                        elif method_used == "AI Audio Transcription":
                            # Plain text - create single segment
                            segments = [{"text": transcript_text, "start": 0, "duration": 0}]
                        else:
                            # This shouldn't happen as Tier 2 already returns segments
                            # But fallback to single segment
                            segments = [{"text": transcript_text, "start": 0, "duration": 0}]
                        
                        st.session_state.fetched_segments = segments
                        st.session_state.transcript_type_info = f"Fetched using: {method_used}"
                        st.session_state.error_message = None
                        
                        # Cache the successful result
                        st.session_state.transcript_cache[video_id] = {
                            'segments': segments,
                            'info': f"Fetched using: {method_used}",
                            'video_info': st.session_state.video_info
                        }
                    else: # All methods failed
                        print(f"❌ DEBUG: All transcript methods failed")
                        print(f"❌ DEBUG: Failure reasons: {failure_reasons}")
                        status_container.empty()
                        progress_container.empty()
                        # Error message is already displayed by the orchestrator function
                        st.session_state.error_message = None  # Don't duplicate error message
                        st.session_state.fetched_segments = None
                        st.session_state.transcript_type_info = ""
        else:
            st.session_state.error_message = "Could not extract Video ID from URL. Please check the URL format and try again."
            # Show what video ID was extracted for debugging
            if st.session_state.debug_mode:
                st.error(f"Debug: Failed to extract video ID from: {url}")
    else:
        st.session_state.error_message = "Please enter a YouTube video URL."

# Display errors if any
if st.session_state.error_message:
    st.error(st.session_state.error_message)

# Display transcript and format options if segments are fetched
if st.session_state.fetched_segments:
    st.success(f"Transcript fetched successfully for Video ID: {st.session_state.video_id}!")
    
    # Display video info
    if st.session_state.video_info:
        st.markdown(f"### 📹 {st.session_state.video_info['title']}")
        st.markdown(f"🔗 [Watch on YouTube]({st.session_state.video_info['url']})")
    
    if st.session_state.transcript_type_info:
        st.info(f"Transcript details: {st.session_state.transcript_type_info}")

    # Debug Information (only shown if debug mode is enabled)
    if st.session_state.debug_mode:
        st.markdown("---")
        st.subheader("🐛 Debug Information")
        st.write(f"**Type of fetched_segments:** `{type(st.session_state.fetched_segments)}`")
        st.write(f"**Is fetched_segments a list?** `{isinstance(st.session_state.fetched_segments, list)}`")
        st.write(f"**Is fetched_segments truthy?** `{bool(st.session_state.fetched_segments)}`")
        
        if isinstance(st.session_state.fetched_segments, list):
            st.write(f"**Number of segments:** `{len(st.session_state.fetched_segments)}`")
            st.write("**First 3 segments:**")
            st.json(st.session_state.fetched_segments[:3])
            
            # Show structure of individual segments
            if st.session_state.fetched_segments:
                first_segment = st.session_state.fetched_segments[0]
                st.write(f"**First segment type:** `{type(first_segment)}`")
                st.write(f"**First segment keys/attributes:** `{list(first_segment.keys()) if isinstance(first_segment, dict) else dir(first_segment)}`")
            
            # Additional debugging for long videos
            if len(st.session_state.fetched_segments) > 1000:
                st.warning(f"⚠️ Large transcript detected: {len(st.session_state.fetched_segments)} segments")
                st.write("**Segment distribution:**")
                first_time = st.session_state.fetched_segments[0].get('start', 0)
                last_segment = st.session_state.fetched_segments[-1]
                last_time = last_segment.get('start', 0) + last_segment.get('duration', 0)
                st.write(f"- Duration: {int(last_time // 3600)}h {int((last_time % 3600) // 60)}m {int(last_time % 60)}s")
                st.write(f"- Average segment length: {last_time / len(st.session_state.fetched_segments):.2f} seconds")
                
                # Check for potential issues
                empty_segments = sum(1 for seg in st.session_state.fetched_segments if not seg.get('text', '').strip())
                if empty_segments > 0:
                    st.warning(f"⚠️ Found {empty_segments} empty segments")
        else:
            st.write("**Value of fetched_segments:**")
            st.text(str(st.session_state.fetched_segments))
        st.markdown("---")

    st.subheader("📄 Formatted Transcript")

    format_options = ["txt", "srt", "vtt", "json"]
    # Use st.session_state.selected_format to make the radio button selection persistent
    selected_format = st.radio(
        "Choose output format:",
        options=format_options,
        index=format_options.index(st.session_state.selected_format), # Set default based on session state
        horizontal=True,
        key="format_selector"
    )
    
    # Update session state with the new selection
    st.session_state.selected_format = selected_format

    # Format and display the transcript based on selected format
    with st.spinner(f"Formatting transcript as {selected_format.upper()}..."):
        formatted_transcript_text = format_segments(st.session_state.fetched_segments, selected_format)
    
    # Check if formatting was successful
    if formatted_transcript_text.startswith("Error formatting transcript") or formatted_transcript_text == "No segments to format.":
        st.error(formatted_transcript_text)
        if st.session_state.debug_mode:
            st.write("**Debug:** Check the segments structure above for issues.")
    else:
        # Display the formatted transcript
        if selected_format == "json":
            st.code(formatted_transcript_text, language="json", line_numbers=True)
        elif selected_format in ["srt", "vtt"]:
            st.code(formatted_transcript_text, language="text", line_numbers=True)
        else: # txt
            st.text_area(
                label=f"{selected_format.upper()} Transcript (Scroll to see all content & copy from here)",
                value=formatted_transcript_text,
                height=400,
                key="transcript_display_area"
            )
        
        # Provide a download button
        file_extension = selected_format
        mime_type = "application/json" if selected_format == "json" else f"text/{selected_format}"
        
        # Prepare filename using video title
        if st.session_state.video_info:
            safe_title = sanitize_filename(st.session_state.video_info['title'])
            filename = f"{safe_title}_transcript.{file_extension}"
        else:
            filename = f"transcript_{st.session_state.video_id}.{file_extension}"
            
        # Add header to text formats (txt, srt, vtt)
        download_content = formatted_transcript_text
        # Only add header if not already present (AI transcription adds it)
        if selected_format in ["txt", "srt", "vtt"] and st.session_state.video_info:
            # Check if the transcript already starts with video info (from AI transcription)
            if not formatted_transcript_text.startswith("Video Title:"):
                header = f"Video Title: {st.session_state.video_info['title']}\n"
                header += f"YouTube URL: {st.session_state.video_info['url']}\n"
                header += f"Video ID: {st.session_state.video_id}\n"
                header += "-" * 80 + "\n\n"
                download_content = header + formatted_transcript_text
        
        st.download_button(
            label=f"📥 Download .{file_extension}",
            data=download_content,
            file_name=filename,
            mime=mime_type
        )

    # Additional helpful information
    if st.session_state.fetched_segments and isinstance(st.session_state.fetched_segments, list):
        total_duration = 0
        if st.session_state.fetched_segments:
            last_segment = st.session_state.fetched_segments[-1]
            if 'start' in last_segment and 'duration' in last_segment:
                total_duration = last_segment['start'] + last_segment['duration']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Segments", len(st.session_state.fetched_segments))
        with col2:
            st.metric("Video Duration", f"{int(total_duration // 60)}:{int(total_duration % 60):02d}")
        with col3:
            st.metric("Characters", len(formatted_transcript_text) if formatted_transcript_text else 0)

st.markdown("---")
st.caption("🚀 A Streamlit app to fetch and format YouTube video transcripts. Built with youtube-transcript-api.")