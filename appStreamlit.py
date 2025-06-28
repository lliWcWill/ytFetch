import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from youtube_transcript_api.formatters import SRTFormatter, WebVTTFormatter, JSONFormatter, TextFormatter
from urllib.parse import urlparse, parse_qs
import json # For pretty printing JSON output
import yt_dlp
import re
import time
import os
import tempfile
import logging
from audio_transcriber import transcribe_audio_from_file
import isodate
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import random

# Import the new config loader
from config_loader import load_config, get_api_key

# --- Configuration Loading ---

# Load configuration at startup
config = load_config()

# Check if essential API keys are available
if not get_api_key("groq") and not get_api_key("openai"):
    st.error("⚠️ No API keys found. Please configure your API keys in config.yaml or Streamlit secrets.")
    st.info("For Streamlit Cloud deployment, add secrets in the app settings.")
    st.stop()


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
            
            # Check if it's a live stream
            is_live = info.get('is_live', False)
            live_status = info.get('live_status', 'none')  # 'is_live', 'is_upcoming', 'was_live', 'none'
            
            return {
                'title': info.get('title', f'video_{video_id}'),
                'id': video_id,
                'url': video_url,
                'duration': info.get('duration', 0),  # Duration in seconds
                'is_live': is_live,
                'live_status': live_status,
                'was_live': live_status == 'was_live',
                'description': info.get('description', ''),
                'uploader': info.get('uploader', ''),
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
        if parsed_url.path.startswith('/live/'):
            # Handle live stream URLs like https://www.youtube.com/live/BBhZ9Ltpmdw
            return parsed_url.path.split('/')[2].split('?')[0]
    return None

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=10)
)
def fetch_transcript_segments(video_id):
    """
    Fetches transcript segments using youtube-transcript-api v1.1.0 with Webshare proxy support
    and robust retry logic with exponential backoff.
    """
    print(f"\n🔍 DEBUG: Attempting to fetch transcript for video_id: {video_id}")
    
    # Import the new v1.1.0 components
    try:
        from youtube_transcript_api.proxies import WebshareProxyConfig
        from config_loader import get_webshare_credentials
        
        # Get Webshare credentials
        webshare_username, webshare_password = get_webshare_credentials()
        
        # Create YouTubeTranscriptApi instance with proxy if available
        if webshare_username and webshare_password:
            print("🔗 DEBUG: Using Webshare proxy for enhanced reliability")
            proxy_config = WebshareProxyConfig(
                proxy_username=webshare_username,
                proxy_password=webshare_password
            )
            ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
        else:
            print("⚠️ DEBUG: No Webshare credentials found, using direct connection")
            ytt_api = YouTubeTranscriptApi()
        
        # Use new v1.1.0 API
        transcript = ytt_api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
        
        if not transcript or not transcript.segments:
            raise ValueError("Fetched transcript data is empty.")

        print("✅ DEBUG: Successfully fetched and validated transcript segments.")
        return transcript.segments, transcript.language, None

    except ImportError:
        # Fallback to old API if new version not available
        print("⚠️ DEBUG: Using fallback to old youtube-transcript-api")
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript_obj = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        fetched_segments = transcript_obj.fetch()

        if not fetched_segments:
            raise ValueError("Fetched transcript data is empty.")

        print("✅ DEBUG: Successfully fetched and validated transcript segments (fallback).")
        return fetched_segments, transcript_obj.language, None

    except Exception as e:
        print(f"💥 DEBUG: An error occurred. Tenacity will handle the retry. Error: {e}")
        raise e  # Re-raise the exception for tenacity to catch.

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

def download_audio_as_mp3(video_id, output_dir="video_outputs", video_title=None, progress_placeholder=None, status_placeholder=None):
    """Download the audio of a YouTube video as MP3 using yt-dlp with robust fallback strategies."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Get video info including live status
    video_info = get_video_info(video_id)
    if not video_title:
        video_title = video_info['title']
    
    # Check live stream status
    is_live = video_info.get('is_live', False)
    live_status = video_info.get('live_status', 'none')
    
    # Handle different live stream states
    if status_placeholder:
        if is_live:
            status_placeholder.warning("🔴 **LIVE NOW** - Downloading from live stream...")
        elif live_status == 'is_upcoming':
            status_placeholder.error("📅 **UPCOMING** - This stream hasn't started yet. Please try again when it's live.")
            return None
        elif live_status == 'was_live':
            status_placeholder.info("📺 **RECORDED LIVE** - Downloading completed live stream...")
    
    # Sanitize title for filename
    safe_title = sanitize_filename(video_title)
    
    output_template = os.path.join(output_dir, f"{safe_title}.%(ext)s")
    final_mp3_path = os.path.join(output_dir, f"{safe_title}.mp3")
    
    # Track download progress
    download_info = {
        'downloaded_bytes': 0,
        'total_bytes': 0,
        'speed': 0,
        'eta': 0
    }
    
    def progress_hook(d):
        if d['status'] == 'downloading':
            download_info['downloaded_bytes'] = d.get('downloaded_bytes', 0)
            download_info['total_bytes'] = d.get('total_bytes', 1)
            download_info['speed'] = d.get('speed', 0)
            download_info['eta'] = d.get('eta', 0)
            
            # Update progress bar if provided
            if progress_placeholder and download_info['total_bytes'] > 0:
                progress = download_info['downloaded_bytes'] / download_info['total_bytes']
                progress_placeholder.progress(progress)
                
            # Update status text if provided
            if status_placeholder:
                if download_info['speed']:
                    speed_mb = download_info['speed'] / 1024 / 1024
                    percent = (download_info['downloaded_bytes'] / max(download_info['total_bytes'], 1)) * 100
                    status_placeholder.text(f"⬇️ Downloading audio: {percent:.1f}% ({speed_mb:.1f} MB/s)")
                    
        elif d['status'] == 'finished':
            if status_placeholder:
                status_placeholder.text("✅ Download complete! Processing audio file...")
            if progress_placeholder:
                progress_placeholder.progress(1.0)

    # Define fallback strategies based on successful test results
    def create_strategy_1_standard():
        """Strategy 1: Standard approach (most reliable)"""
        return {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            },
        }
    
    def create_strategy_2_live_optimized():
        """Strategy 2: Live stream optimized (best for live content)"""
        opts = create_strategy_1_standard()
        if is_live or live_status == 'was_live':
            opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'live_from_start': True,
                'hls_use_mpegts': True,
                'wait_for_video': 5,
            })
            if is_live:
                opts['fixup'] = 'never'
        return opts
    
    def create_strategy_3_android_client():
        """Strategy 3: Android client (good for restricted content)"""
        opts = create_strategy_1_standard()
        opts.update({
            'extractor_args': {'youtube': {'player_client': ['android']}},
            'user_agent': 'Mozilla/5.0 (Linux; Android 11; SM-G973F) AppleWebKit/537.36',
        })
        return opts
    
    def create_strategy_4_combined():
        """Strategy 4: Combined best practices"""
        opts = create_strategy_1_standard()
        opts.update({
            'force_ipv4': True,
            'nocheckcertificate': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        })
        if is_live or live_status == 'was_live':
            opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'live_from_start': True,
                'hls_use_mpegts': True,
            })
        return opts

    # Try strategies in order of reliability
    strategies = [
        ("Standard", create_strategy_1_standard),
        ("Live Optimized", create_strategy_2_live_optimized),
        ("Android Client", create_strategy_3_android_client),
        ("Combined", create_strategy_4_combined),
    ]
    
    for strategy_name, create_opts in strategies:
        try:
            if status_placeholder:
                if strategy_name != "Standard":
                    status_placeholder.text(f"🔄 Trying {strategy_name} strategy...")
                
            ydl_opts = create_opts()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            # Check if the mp3 file was actually created
            if os.path.exists(final_mp3_path):
                logging.info(f"Audio successfully downloaded using {strategy_name} strategy: {final_mp3_path}")
                if status_placeholder and strategy_name != "Standard":
                    status_placeholder.success(f"✅ Download successful using {strategy_name} strategy!")
                return final_mp3_path
            else:
                logging.warning(f"{strategy_name} strategy completed but MP3 file not found")
                continue
                
        except Exception as e:
            logging.warning(f"{strategy_name} strategy failed: {e}")
            
            # Check if it's a specific error we should handle
            if "403" in str(e) or "Forbidden" in str(e):
                if status_placeholder:
                    status_placeholder.warning(f"⚠️ {strategy_name} blocked by YouTube, trying next strategy...")
                continue
            elif "player response" in str(e).lower():
                if status_placeholder:
                    status_placeholder.warning(f"⚠️ {strategy_name} player response error, trying next strategy...")
                continue
            else:
                # For other errors, continue to next strategy
                continue
    
    # If all strategies failed
    logging.error("All download strategies failed")
    if status_placeholder:
        status_placeholder.error("❌ All download strategies failed. Try the troubleshooting steps in the sidebar.")
    
    # Check if it's a 403 error that persisted across all strategies
    raise Exception("All download strategies failed. Try updating yt-dlp or using the troubleshooting steps.")


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

# Sidebar with troubleshooting
with st.sidebar:
    st.header("🛠️ Settings & Troubleshooting")
    
    # Debug mode toggle
    st.session_state.debug_mode = st.checkbox("Enable Debug Mode", value=st.session_state.debug_mode)
    
    # 403 Error Troubleshooting
    with st.expander("⚠️ Fix 403 Forbidden Errors"):
        st.markdown("""
        If you're getting **403 Forbidden** errors, try these solutions:
        
        1. **Update yt-dlp** (most common fix):
        ```bash
        yt-dlp -U
        ```
        
        2. **Clear yt-dlp cache**:
        ```bash
        yt-dlp --rm-cache-dir
        ```
        
        3. **Alternative Solutions**:
        - Use a VPN to change your IP
        - Try again in a few minutes
        - Use the official transcript method instead
        
        4. **Browser Cookies** (advanced):
        - Export cookies from your browser
        - Some videos require authentication
        """)
        
        # Import yt_dlp_utils if available
        try:
            from yt_dlp_utils import update_yt_dlp, clear_yt_dlp_cache, get_yt_dlp_version
            
            st.markdown("---")
            st.markdown("**Quick Actions:**")
            
            # Show current version
            current_version = get_yt_dlp_version()
            st.info(f"Current yt-dlp version: {current_version}")
            
            # Update button
            if st.button("🔄 Update yt-dlp"):
                with st.spinner("Updating yt-dlp..."):
                    success, message = update_yt_dlp()
                    if success:
                        st.success("✅ yt-dlp updated successfully!")
                    else:
                        st.error(f"❌ Update failed: {message}")
            
            # Clear cache button
            if st.button("🧹 Clear yt-dlp Cache"):
                with st.spinner("Clearing cache..."):
                    success, message = clear_yt_dlp_cache()
                    if success:
                        st.success("✅ Cache cleared successfully!")
                        st.info(message)
                    else:
                        st.error(f"❌ Failed to clear cache: {message}")
                        
        except ImportError:
            st.info("Advanced troubleshooting tools not available in cloud deployment.")

# URL Input
url = st.text_input("Enter YouTube Video URL:", key="youtube_url_input")

# Transcription method selection
st.subheader("Choose Transcription Method")

# Custom CSS for orange Groq button
st.markdown("""
<style>
/* Style primary buttons with orange Groq theme */
div.stButton > button[data-testid="baseButton-primary"] {
    background-color: #FF6B35 !important;
    color: white !important;
    border: 1px solid #FF6B35 !important;
    font-weight: bold !important;
}

div.stButton > button[data-testid="baseButton-primary"]:hover {
    background-color: #E85A2B !important;
    border: 1px solid #E85A2B !important;
    color: white !important;
}

div.stButton > button[data-testid="baseButton-primary"]:active {
    background-color: #D94F24 !important;
    border: 1px solid #D94F24 !important;
    color: white !important;
}

div.stButton > button[data-testid="baseButton-primary"]:focus {
    background-color: #FF6B35 !important;
    border: 1px solid #FF6B35 !important;
    color: white !important;
    box-shadow: 0 0 0 0.2rem rgba(255, 107, 53, 0.25) !important;
}
</style>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    unofficial_button = st.button("📝 Unofficial Transcripts", 
                                 use_container_width=True, 
                                 help="Fetches existing YouTube transcripts (auto-generated or manual)")
    
with col2:
    groq_button = st.button("⚡ Groq AI Transcription", 
                           type="primary",
                           use_container_width=True,
                           help="Downloads audio and transcribes using Groq Dev Tier (super fast!)")

# TODO: Update Streamlit UI to show real-time progress tracking for Groq transcription method
# Current Groq method uses background transcription without UI progress updates
# Need to integrate with the improved audio_transcriber.py progress callbacks

# Handle button clicks
if unofficial_button or groq_button:
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
                    
                    # Handle different methods based on button clicked
                    if unofficial_button:
                        # Try unofficial method only
                        st.info("Tier 1: Attempting to fetch public transcript...")
                        try:
                            segments, lang, _ = fetch_transcript_segments(video_id)
                            if segments:
                                st.success("✅ Tier 1: Public transcript found!")
                                st.session_state.fetched_segments = segments
                                st.session_state.transcript_type_info = f"Fetched using: Unofficial Library ({lang})"
                                st.session_state.error_message = None
                                
                                # Cache the successful result
                                st.session_state.transcript_cache[video_id] = {
                                    'segments': segments,
                                    'info': f"Fetched using: Unofficial Library ({lang})",
                                    'video_info': st.session_state.video_info
                                }
                        except Exception as e:
                            st.error(f"⚠️ Unofficial transcript fetch failed: {e}")
                            st.session_state.error_message = "Could not fetch unofficial transcript. Try the Groq AI method."
                            st.session_state.fetched_segments = None
                            st.session_state.transcript_type_info = ""
                    
                    elif groq_button:
                        # Use Groq AI transcription directly
                        st.info("🤖 Using Groq Dev Tier AI transcription (super fast!)...")
                        
                        # Get video info for duration check
                        video_info = st.session_state.video_info
                        video_duration = video_info.get('duration', 0)
                        
                        # Create containers for the multi-stage process
                        stage_container = st.container()
                        with stage_container:
                            download_status = st.empty()
                            download_progress = st.empty()
                            transcription_status = st.empty()
                            transcription_progress = st.empty()
                        
                        try:
                            # Stage 1: Download audio with progress tracking
                            download_status.info("📥 Stage 1: Downloading video audio...")
                            download_progress.progress(0)
                            
                            audio_path = download_audio_as_mp3(
                                video_id, 
                                output_dir="video_outputs", 
                                video_title=video_info.get('title'),
                                progress_placeholder=download_progress,
                                status_placeholder=download_status
                            )
                            
                            if audio_path and os.path.exists(audio_path):
                                logging.info(f"Audio downloaded successfully: {audio_path}")
                                
                                # Show completion of download stage
                                download_status.success("✅ Audio download complete!")
                                download_progress.progress(1.0)
                                
                                # Small pause for visual feedback
                                time.sleep(0.5)
                                
                                # Stage 2: Transcription
                                transcription_status.info("🎯 Stage 2: Starting AI transcription...")
                                transcription_progress.progress(0)
                                
                                # Create progress callback
                                def update_transcription_progress(stage, progress, message):
                                    """Update UI based on transcription stage"""
                                    if stage == "preprocessing":
                                        # Map preprocessing to 0-20% of transcription progress
                                        transcription_progress.progress(progress * 0.2)
                                        transcription_status.info(f"🎯 Stage 2: {message}")
                                    elif stage == "chunking":
                                        # Map chunking to 20-30% of transcription progress
                                        transcription_progress.progress(0.2 + progress * 0.1)
                                        transcription_status.info(f"🎯 Stage 2: {message}")
                                    elif stage == "transcribing":
                                        # Map actual transcription to 30-100% of transcription progress
                                        transcription_progress.progress(0.3 + progress * 0.7)
                                        transcription_status.info(f"🎯 Stage 2: {message}")
                                
                                # Transcribe audio using the new optimized function
                                transcript = transcribe_audio_from_file(audio_path, language="en", 
                                                                      progress_callback=update_transcription_progress)
                                
                                # Clean up audio file
                                try:
                                    os.remove(audio_path)
                                    logging.info(f"Cleaned up temporary audio file: {audio_path}")
                                except Exception as cleanup_error:
                                    logging.warning(f"Failed to clean up audio file: {cleanup_error}")
                                
                                if transcript:
                                    # Complete the progress
                                    transcription_progress.progress(1.0)
                                    transcription_status.success("✅ Transcription complete!")
                                    
                                    # Add video title and URL to the transcript
                                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                                    video_title = video_info.get('title', f'video_{video_id}')
                                    
                                    # Prepend video info to transcript
                                    full_transcript = f"Video Title: {video_title}\n"
                                    full_transcript += f"YouTube URL: {video_url}\n"
                                    full_transcript += f"Video ID: {video_id}\n"
                                    full_transcript += "-" * 80 + "\n\n"
                                    full_transcript += transcript
                                    
                                    # Clear the progress indicators after a short delay
                                    time.sleep(1)
                                    download_status.empty()
                                    download_progress.empty()
                                    transcription_status.empty()
                                    transcription_progress.empty()
                                    
                                    st.success("✅ Groq AI transcription succeeded!")
                                    st.session_state.fetched_segments = [{"text": full_transcript, "start": 0, "duration": 0}]
                                    st.session_state.transcript_type_info = "Fetched using: Groq Dev Tier AI Transcription"
                                    st.session_state.error_message = None
                                    
                                    # Cache the result
                                    st.session_state.transcript_cache[video_id] = {
                                        'segments': st.session_state.fetched_segments,
                                        'info': "Fetched using: Groq Dev Tier AI Transcription",
                                        'video_info': st.session_state.video_info
                                    }
                                else:
                                    transcription_status.error("❌ Groq AI transcription produced empty results")
                                    st.session_state.error_message = "Groq transcription failed"
                                    st.session_state.fetched_segments = None
                                    st.session_state.transcript_type_info = ""
                            else:
                                download_status.error("❌ Audio download failed")
                                st.session_state.error_message = "Could not download audio"
                                st.session_state.fetched_segments = None
                                st.session_state.transcript_type_info = ""
                                
                        except Exception as e:
                            st.error(f"❌ Groq AI transcription error: {str(e)[:100]}")
                            st.session_state.error_message = f"Groq transcription error: {str(e)[:100]}"
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
    # Special handling for 403 errors
    if "403" in st.session_state.error_message or "Forbidden" in st.session_state.error_message:
        st.error("⚠️ **403 Forbidden Error** - YouTube is blocking the download")
        st.warning("""
        **Quick Solutions:**
        1. Check the sidebar for troubleshooting steps
        2. Try using the **"Fetch Unofficial Transcripts"** button instead
        3. Wait a few minutes and try again
        4. The video might be age-restricted or private
        """)
    else:
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