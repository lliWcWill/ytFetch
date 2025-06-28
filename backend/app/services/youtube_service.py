"""
YouTube Service Module

This module provides a clean YouTubeService class that encapsulates all YouTube operations
including video information retrieval, transcript fetching, and audio downloading.

Migrated from appStreamlit.py with:
- Removed Streamlit dependencies
- Added async support where appropriate
- Integrated with backend configuration system
- Enhanced error handling and logging
- Support for all 6 enhanced download strategies
"""

import os
import re
import json
import time
import logging
import tempfile
import asyncio
import isodate
import yt_dlp
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Optional, Tuple, Any, Callable
from pathlib import Path

# YouTube transcript API imports
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from youtube_transcript_api.formatters import SRTFormatter, WebVTTFormatter, JSONFormatter, TextFormatter

# Retry logic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Local imports
from ..core.config import get_settings

# Initialize settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)


class YouTubeService:
    """
    Service class for YouTube operations including video info, transcripts, and audio downloads.
    """
    
    def __init__(self):
        """Initialize the YouTube service."""
        self.settings = get_settings()
        self.temp_dir = self.settings.temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a string to be used as a filename.
        
        Args:
            filename: The filename string to sanitize
            
        Returns:
            str: Sanitized filename safe for filesystem use
        """
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

    def get_video_id_from_url(self, youtube_url: str) -> Optional[str]:
        """
        Extract video ID from various YouTube URL formats.
        
        Args:
            youtube_url: YouTube URL in any supported format
            
        Returns:
            Optional[str]: Video ID if found, None otherwise
        """
        if not youtube_url:
            return None
        
        # Clean the URL - remove any whitespace
        youtube_url = youtube_url.strip()
        
        try:
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
                    
        except Exception as e:
            logger.error(f"Error parsing YouTube URL '{youtube_url}': {e}")
            
        return None

    async def get_video_info(self, video_id: str, progress_callback: Optional[Callable[[str, float, str], None]] = None) -> Dict[str, Any]:
        """
        Get video title and other info using yt-dlp.
        
        Args:
            video_id: YouTube video ID
            progress_callback: Optional callback for progress updates (stage, progress, message)
            
        Returns:
            Dict[str, Any]: Video information including title, duration, live status, etc.
        """
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        if progress_callback:
            progress_callback("video_info", 0.0, "Fetching video information...")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,  # Get full info including title
        }
        
        try:
            if progress_callback:
                progress_callback("video_info", 0.3, "Extracting metadata from YouTube...")
            
            # Run yt-dlp in thread to avoid blocking async context
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, 
                lambda: self._extract_video_info_sync(video_url, ydl_opts)
            )
            
            if progress_callback:
                progress_callback("video_info", 0.7, "Processing video metadata...")
            
            if info:
                # Check if it's a live stream
                is_live = info.get('is_live', False)
                live_status = info.get('live_status', 'none')  # 'is_live', 'is_upcoming', 'was_live', 'none'
                
                if progress_callback:
                    progress_callback("video_info", 1.0, f"Retrieved info for: {info.get('title', 'Unknown')}")
                
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
            logger.warning(f"Could not fetch video info for {video_id}: {e}")
            if progress_callback:
                progress_callback("video_info", 1.0, f"Failed to fetch video info: {str(e)[:50]}...")
            
        # Return minimal info on failure
        if progress_callback:
            progress_callback("video_info", 1.0, "Using fallback video information")
        
        return {
            'title': f'video_{video_id}',
            'id': video_id,
            'url': video_url,
            'duration': 0,
            'is_live': False,
            'live_status': 'none',
            'was_live': False,
            'description': '',
            'uploader': '',
        }

    def _extract_video_info_sync(self, video_url: str, ydl_opts: dict) -> Optional[dict]:
        """Synchronous video info extraction for use in thread executor."""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(video_url, download=False)
        except Exception as e:
            logger.error(f"yt-dlp extraction failed: {e}")
            return None

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=10)
    )
    async def fetch_transcript_segments(self, video_id: str, progress_callback: Optional[Callable[[str, float, str], None]] = None) -> Tuple[Optional[List[Dict]], Optional[str], Optional[str]]:
        """
        Fetch transcript segments using youtube-transcript-api v1.1.0 with Webshare proxy support
        and robust retry logic with exponential backoff.
        
        Args:
            video_id: YouTube video ID
            progress_callback: Optional callback for progress updates (stage, progress, message)
            
        Returns:
            Tuple[Optional[List[Dict]], Optional[str], Optional[str]]: 
                (segments, language, error_message)
        """
        logger.info(f"Attempting to fetch transcript for video_id: {video_id}")
        
        if progress_callback:
            progress_callback("transcript", 0.0, "Initializing transcript fetch...")
        
        try:
            # Import the new v1.1.0 components if available
            from youtube_transcript_api.proxies import WebshareProxyConfig
            
            if progress_callback:
                progress_callback("transcript", 0.1, "Loading transcript API configuration...")
            
            # Import webshare credentials function
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
            from config_loader import get_webshare_credentials
            
            # Get Webshare credentials
            webshare_username, webshare_password = get_webshare_credentials()
            
            if progress_callback:
                progress_callback("transcript", 0.2, "Setting up connection method...")
            
            # Try with Webshare proxy first, fallback to direct connection
            transcript = None
            
            if webshare_username and webshare_password:
                try:
                    if progress_callback:
                        progress_callback("transcript", 0.3, "Connecting via Webshare proxy...")
                    
                    logger.info("Using Webshare proxy for enhanced reliability")
                    proxy_config = WebshareProxyConfig(
                        proxy_username=webshare_username,
                        proxy_password=webshare_password,
                        retries_when_blocked=3
                    )
                    ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
                    
                    if progress_callback:
                        progress_callback("transcript", 0.6, "Fetching transcript via proxy...")
                    
                    transcript = ytt_api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
                    logger.info("Webshare proxy successful!")
                    
                except Exception as proxy_error:
                    if progress_callback:
                        progress_callback("transcript", 0.4, "Proxy failed, trying direct connection...")
                    
                    logger.warning(f"Webshare proxy failed ({proxy_error}), falling back to direct connection")
                    ytt_api = YouTubeTranscriptApi()
                    transcript = ytt_api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
                    logger.info("Direct connection successful!")
            else:
                if progress_callback:
                    progress_callback("transcript", 0.3, "Using direct connection to YouTube...")
                
                logger.info("No Webshare credentials found, using direct connection")
                ytt_api = YouTubeTranscriptApi()
                
                if progress_callback:
                    progress_callback("transcript", 0.6, "Fetching transcript directly...")
                
                transcript = ytt_api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
                logger.info("Direct connection successful!")
            
            if progress_callback:
                progress_callback("transcript", 0.8, "Validating transcript data...")
            
            if not transcript or not transcript.snippets:
                raise ValueError("Fetched transcript data is empty.")

            logger.info("Successfully fetched and validated transcript segments.")
            
            if progress_callback:
                progress_callback("transcript", 0.9, "Converting transcript format...")
            
            # Convert FetchedTranscriptSnippet objects to dict format for compatibility
            segments = []
            for snippet in transcript.snippets:
                segments.append({
                    'text': snippet.text,
                    'start': snippet.start,
                    'duration': snippet.duration
                })
            
            if progress_callback:
                progress_callback("transcript", 1.0, f"Transcript ready! Found {len(segments)} segments")
            
            return segments, transcript.language, None

        except ImportError:
            # Fallback to old API if new version not available
            if progress_callback:
                progress_callback("transcript", 0.3, "Using fallback transcript API...")
            
            logger.info("Using fallback to old youtube-transcript-api")
            try:
                if progress_callback:
                    progress_callback("transcript", 0.5, "Fetching with legacy API...")
                
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript_obj = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                fetched_segments = transcript_obj.fetch()

                if progress_callback:
                    progress_callback("transcript", 0.8, "Validating fallback transcript...")

                if not fetched_segments:
                    raise ValueError("Fetched transcript data is empty.")

                logger.info("Successfully fetched and validated transcript segments (fallback).")
                
                if progress_callback:
                    progress_callback("transcript", 1.0, f"Fallback successful! Found {len(fetched_segments)} segments")
                
                return fetched_segments, transcript_obj.language, None
                
            except Exception as fallback_error:
                logger.error(f"Fallback transcript fetch failed: {fallback_error}")
                if progress_callback:
                    progress_callback("transcript", 1.0, f"Fallback failed: {str(fallback_error)[:50]}...")
                return None, None, str(fallback_error)

        except Exception as e:
            logger.error(f"Transcript fetch error. Tenacity will handle the retry. Error: {e}")
            if progress_callback:
                progress_callback("transcript", 0.5, f"Retrying transcript fetch... Error: {str(e)[:50]}...")
            raise e  # Re-raise the exception for tenacity to catch

    async def download_audio_as_mp3_enhanced(
        self, 
        video_id: str, 
        output_dir: Optional[str] = None,
        video_title: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> Optional[str]:
        """
        Enhanced download with multiple fallback strategies including all 6 strategies from original.
        
        Args:
            video_id: YouTube video ID
            output_dir: Output directory for downloaded file
            video_title: Video title for filename (will fetch if not provided)
            progress_callback: Optional callback for progress updates (stage, progress, message)
            
        Returns:
            Optional[str]: Path to downloaded MP3 file or None if failed
        """
        if output_dir is None:
            output_dir = self.temp_dir
            
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Get video info if title not provided
        if not video_title:
            if progress_callback:
                progress_callback("setup", 0.05, "Getting video information...")
            video_info = await self.get_video_info(video_id, progress_callback)
            video_title = video_info['title']
        
        safe_title = self.sanitize_filename(video_title)
        final_mp3_path = os.path.join(output_dir, f"{safe_title}.mp3")
        
        # Check for cookie file
        cookie_file = None
        if os.path.exists("cookies.txt"):
            cookie_file = "cookies.txt"
            if progress_callback:
                progress_callback("setup", 0.1, "Found cookie file for authentication")
        
        if progress_callback:
            progress_callback("setup", 0.2, "Trying enhanced download strategies...")
        
        # Strategy 1: yt-dlp with cookie file (if available)
        if cookie_file:
            try:
                if progress_callback:
                    progress_callback("download", 0.3, "Strategy 1: yt-dlp with cookie authentication...")
                    
                result = await self._download_with_strategy_1(
                    video_url, output_dir, safe_title, cookie_file, final_mp3_path, progress_callback
                )
                if result:
                    if progress_callback:
                        progress_callback("download", 1.0, "Downloaded with cookie authentication!")
                    return result
                    
            except Exception as e:
                if progress_callback:
                    progress_callback("download", 0.3, f"Cookie strategy failed: {str(e)[:100]}...")
        
        # Strategy 2: yt-dlp with advanced anti-bot headers
        try:
            if progress_callback:
                progress_callback("download", 0.4, "Strategy 2: yt-dlp with anti-bot headers...")
                
            result = await self._download_with_strategy_2(
                video_url, output_dir, safe_title, cookie_file, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("download", 1.0, "Downloaded with iOS client simulation!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("download", 0.4, f"Strategy 2 failed: {str(e)[:100]}...")
        
        # Strategy 3: yt-dlp with TV client
        try:
            if progress_callback:
                progress_callback("download", 0.5, "Strategy 3: yt-dlp with TV client...")
                
            result = await self._download_with_strategy_3(
                video_url, output_dir, safe_title, cookie_file, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("download", 1.0, "Downloaded with TV client!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("download", 0.5, f"Strategy 3 failed: {str(e)[:100]}...")
        
        # Strategy 4: pytube fallback
        try:
            if progress_callback:
                progress_callback("download", 0.6, "Strategy 4: Trying pytube...")
                
            result = await self._download_with_strategy_4(
                video_url, output_dir, safe_title, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("download", 1.0, "Downloaded with pytube!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("download", 0.6, f"Strategy 4 failed: {str(e)[:100]}...")
        
        # Strategy 5: yt-dlp with embedded client
        try:
            if progress_callback:
                progress_callback("download", 0.7, "Strategy 5: yt-dlp with embedded client...")
                
            result = await self._download_with_strategy_5(
                video_url, output_dir, safe_title, cookie_file, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("download", 1.0, "Downloaded with embedded client!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("download", 0.7, f"Strategy 5 failed: {str(e)[:100]}...")
        
        # Strategy 6: moviepy + youtube-dl fallback
        try:
            if progress_callback:
                progress_callback("download", 0.8, "Strategy 6: Trying moviepy extraction...")
                
            result = await self._download_with_strategy_6(
                video_url, output_dir, safe_title, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("download", 1.0, "Downloaded with moviepy!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("download", 0.8, f"Strategy 6 failed: {str(e)[:100]}...")
        
        # All strategies failed
        if progress_callback:
            progress_callback("download", 0.9, "All enhanced download strategies failed!")
        
        logger.error("All enhanced download strategies failed")
        return None

    async def _download_with_strategy_1(self, video_url: str, output_dir: str, safe_title: str, 
                                      cookie_file: str, final_mp3_path: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Optional[str]:
        """Strategy 1: yt-dlp with cookie file."""
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(output_dir, f"{safe_title}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'cookies': cookie_file,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }
        
        # Add progress hook if callback provided
        if progress_callback:
            ydl_opts['progress_hooks'] = [self._create_progress_hook(progress_callback, "Cookie Auth")]
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._download_sync(video_url, ydl_opts))
        
        return final_mp3_path if os.path.exists(final_mp3_path) else None

    async def _download_with_strategy_2(self, video_url: str, output_dir: str, safe_title: str,
                                      cookie_file: Optional[str], final_mp3_path: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Optional[str]:
        """Strategy 2: yt-dlp with advanced anti-bot headers."""
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(output_dir, f"{safe_title}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android_creator'],
                    'player_skip': ['webpage', 'configs'],
                    'include_dash_manifest': False,
                }
            },
            'user_agent': 'com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)',
            'http_headers': {
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Origin': 'https://www.youtube.com',
                'Referer': 'https://www.youtube.com/',
                'X-YouTube-Client-Name': '5',
                'X-YouTube-Client-Version': '19.29.1',
            },
        }
        
        if cookie_file:
            ydl_opts['cookies'] = cookie_file
        
        # Add progress hook if callback provided
        if progress_callback:
            ydl_opts['progress_hooks'] = [self._create_progress_hook(progress_callback, "iOS Client")]
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._download_sync(video_url, ydl_opts))
        
        return final_mp3_path if os.path.exists(final_mp3_path) else None

    async def _download_with_strategy_3(self, video_url: str, output_dir: str, safe_title: str,
                                      cookie_file: Optional[str], final_mp3_path: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Optional[str]:
        """Strategy 3: yt-dlp with TV client."""
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(output_dir, f"{safe_title}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv_embedded'],
                    'player_skip': ['webpage'],
                }
            },
            'user_agent': 'Mozilla/5.0 (ChromiumStylePlatform) Cobalt/40.13031-qa (unlike Gecko) v8/8.8.278.8-jit gles Starboard/12',
        }
        
        if cookie_file:
            ydl_opts['cookies'] = cookie_file
        
        # Add progress hook if callback provided
        if progress_callback:
            ydl_opts['progress_hooks'] = [self._create_progress_hook(progress_callback, "TV Client")]
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._download_sync(video_url, ydl_opts))
        
        return final_mp3_path if os.path.exists(final_mp3_path) else None

    async def _download_with_strategy_4(self, video_url: str, output_dir: str, safe_title: str,
                                      final_mp3_path: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Optional[str]:
        """Strategy 4: pytube fallback."""
        try:
            from pytube import YouTube
            from pydub import AudioSegment
            
            loop = asyncio.get_event_loop()
            
            # Download with pytube in thread
            def download_pytube():
                if progress_callback:
                    progress_callback("downloading", 0.1, "PyTube: Initializing YouTube object...")
                
                yt = YouTube(video_url)
                
                if progress_callback:
                    progress_callback("downloading", 0.2, "PyTube: Finding audio stream...")
                
                audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()
                
                if audio_stream:
                    if progress_callback:
                        progress_callback("downloading", 0.3, "PyTube: Starting download...")
                    
                    temp_path = audio_stream.download(output_path=output_dir, filename=f"{safe_title}_temp.mp4")
                    
                    if progress_callback:
                        progress_callback("downloading", 0.7, "PyTube: Converting to MP3...")
                    
                    # Convert to MP3 using pydub
                    audio = AudioSegment.from_file(temp_path, format="mp4")
                    audio.export(final_mp3_path, format="mp3", bitrate="192k")
                    
                    if progress_callback:
                        progress_callback("downloading", 0.9, "PyTube: Cleaning up temporary files...")
                    
                    # Cleanup temp file
                    os.remove(temp_path)
                    
                    if progress_callback:
                        progress_callback("downloading", 1.0, "PyTube: Download and conversion completed!")
                    
                    return True
                return False
            
            success = await loop.run_in_executor(None, download_pytube)
            return final_mp3_path if success and os.path.exists(final_mp3_path) else None
            
        except ImportError:
            if progress_callback:
                progress_callback("downloading", 0.0, "PyTube: Library not available")
            logger.warning("pytube not available")
            return None

    async def _download_with_strategy_5(self, video_url: str, output_dir: str, safe_title: str,
                                      cookie_file: Optional[str], final_mp3_path: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Optional[str]:
        """Strategy 5: yt-dlp with embedded client."""
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(output_dir, f"{safe_title}.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web_embedded'],
                    'player_skip': ['webpage'],
                }
            },
        }
        
        if cookie_file:
            ydl_opts['cookies'] = cookie_file
        
        # Add progress hook if callback provided
        if progress_callback:
            ydl_opts['progress_hooks'] = [self._create_progress_hook(progress_callback, "Embedded Client")]
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._download_sync(video_url, ydl_opts))
        
        return final_mp3_path if os.path.exists(final_mp3_path) else None

    async def _download_with_strategy_6(self, video_url: str, output_dir: str, safe_title: str,
                                      final_mp3_path: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Optional[str]:
        """Strategy 6: moviepy + youtube-dl fallback."""
        try:
            from moviepy.editor import VideoFileClip
            
            if progress_callback:
                progress_callback("downloading", 0.1, "MoviePy: Setting up video download...")
            
            # Try to download video first with basic yt-dlp
            temp_video_path = os.path.join(output_dir, f"{safe_title}_temp.%(ext)s")
            
            ydl_opts = {
                'format': 'worst[height<=480]/worst',  # Low quality for faster download
                'outtmpl': temp_video_path,
                'quiet': True,
                'no_warnings': True,
                'user_agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36',
            }
            
            # Add progress hook if callback provided
            if progress_callback:
                ydl_opts['progress_hooks'] = [self._create_progress_hook(progress_callback, "MoviePy Download")]
            
            if progress_callback:
                progress_callback("downloading", 0.2, "MoviePy: Starting video download...")
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._download_sync(video_url, ydl_opts))
            
            if progress_callback:
                progress_callback("downloading", 0.6, "MoviePy: Locating downloaded video...")
            
            # Find the actual downloaded file
            downloaded_files = [f for f in os.listdir(output_dir) if f.startswith(f"{safe_title}_temp")]
            if downloaded_files:
                temp_video_file = os.path.join(output_dir, downloaded_files[0])
                
                if progress_callback:
                    progress_callback("downloading", 0.7, "MoviePy: Extracting audio from video...")
                
                # Extract audio with moviepy in thread
                def extract_audio():
                    video_clip = VideoFileClip(temp_video_file)
                    audio_clip = video_clip.audio
                    
                    if progress_callback:
                        progress_callback("downloading", 0.8, "MoviePy: Converting to MP3...")
                    
                    audio_clip.write_audiofile(final_mp3_path, codec='mp3', bitrate='192k', verbose=False, logger=None)
                    
                    if progress_callback:
                        progress_callback("downloading", 0.9, "MoviePy: Cleaning up...")
                    
                    # Cleanup
                    audio_clip.close()
                    video_clip.close()
                    os.remove(temp_video_file)
                    
                    if progress_callback:
                        progress_callback("downloading", 1.0, "MoviePy: Audio extraction completed!")
                    
                    return True
                
                success = await loop.run_in_executor(None, extract_audio)
                return final_mp3_path if success and os.path.exists(final_mp3_path) else None
                
        except ImportError:
            if progress_callback:
                progress_callback("downloading", 0.0, "MoviePy: Library not available")
            logger.warning("moviepy not available")
            
        return None

    def _create_progress_hook(self, progress_callback: Optional[Callable[[str, float, str], None]], strategy_name: str):
        """Create a yt-dlp progress hook that integrates with our progress callback."""
        def progress_hook(d):
            if not progress_callback:
                return
                
            if d['status'] == 'downloading':
                # Extract progress information
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                if total > 0:
                    progress_percent = min(downloaded / total, 1.0)
                    
                    # Format speed and ETA for display
                    speed_str = ""
                    if speed:
                        if speed > 1024*1024:
                            speed_str = f" at {speed/(1024*1024):.1f} MB/s"
                        elif speed > 1024:
                            speed_str = f" at {speed/1024:.1f} KB/s"
                        else:
                            speed_str = f" at {speed:.0f} B/s"
                    
                    eta_str = ""
                    if eta:
                        eta_str = f" (ETA: {eta//60}:{eta%60:02d})"
                    
                    message = f"{strategy_name}: {downloaded/(1024*1024):.1f}/{total/(1024*1024):.1f} MB{speed_str}{eta_str}"
                    progress_callback("downloading", progress_percent, message)
                else:
                    # Indeterminate progress
                    size_str = f"{downloaded/(1024*1024):.1f} MB" if downloaded > 0 else "downloading"
                    progress_callback("downloading", 0.5, f"{strategy_name}: {size_str}...")
                    
            elif d['status'] == 'finished':
                filename = d.get('filename', 'audio file')
                progress_callback("downloading", 1.0, f"{strategy_name}: Download completed - {filename}")
                
            elif d['status'] == 'error':
                error_msg = str(d.get('error', 'Unknown error'))
                progress_callback("downloading", 0.0, f"{strategy_name}: Error - {error_msg[:50]}...")
        
        return progress_hook

    def _download_sync(self, video_url: str, ydl_opts: dict) -> None:
        """Synchronous download helper for use in thread executor."""
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

    def parse_srt_to_segments(self, srt_text: str) -> List[Dict[str, Any]]:
        """
        Parse SRT format text into segments compatible with existing format.
        
        Args:
            srt_text: SRT formatted text
            
        Returns:
            List[Dict[str, Any]]: List of transcript segments
        """
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
                start_seconds = self._srt_time_to_seconds(start_time_str)
                end_seconds = self._srt_time_to_seconds(end_time_str)
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

    def _srt_time_to_seconds(self, time_str: str) -> float:
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
        
        return 0.0

    def format_segments(self, segments: List[Dict[str, Any]], output_format: str = "txt") -> str:
        """
        Format fetched segments into the desired string format.
        
        Args:
            segments: List of transcript segments
            output_format: Output format ('txt', 'srt', 'vtt', 'json')
            
        Returns:
            str: Formatted transcript text
        """
        if not segments:
            return "No segments provided to format."
        
        if not isinstance(segments, list):
            return f"Expected list of segments, got {type(segments)}."
        
        if len(segments) == 0:
            return "Segments list is empty."

        try:
            # Convert segments to the format expected by the formatters
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
                return formatter.format_transcript(formatted_segments)
                
            elif output_format == "vtt":
                formatter = WebVTTFormatter()
                return formatter.format_transcript(formatted_segments)
                
            elif output_format == "json":
                # For JSON, we can use the original dict format
                return json.dumps(segments, indent=2, ensure_ascii=False)
                
            elif output_format == "txt":
                # For plain text, we can do it manually
                text_parts = []
                for segment in segments:
                    if isinstance(segment, dict):
                        text_parts.append(segment.get('text', ''))
                    else:
                        text_parts.append(getattr(segment, 'text', ''))
                
                return ' '.join(text_parts)
            else:
                return f"Unsupported format: {output_format}"
                
        except Exception as e:
            logger.error(f"Error formatting transcript: {e}")
            return f"Error formatting transcript: {str(e)}"

    def _parse_iso8601_duration(self, duration_str: str) -> int:
        """Convert an ISO 8601 duration string to total seconds using robust isodate library."""
        if not duration_str:
            return 0
            
        try:
            # isodate is the most robust way to handle this
            duration_obj = isodate.parse_duration(duration_str)
            return int(duration_obj.total_seconds())
        except (isodate.ISO8601Error, ValueError, AttributeError):
            # Fallback for simple cases if isodate fails
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
            if not match:
                logger.warning(f"Failed to parse duration: {duration_str}")
                return 0
            hours = int(match.group(1)) if match.group(1) else 0
            minutes = int(match.group(2)) if match.group(2) else 0
            seconds = int(match.group(3)) if match.group(3) else 0
            return hours * 3600 + minutes * 60 + seconds

    async def cleanup_temp_files(self, file_patterns: Optional[List[str]] = None) -> None:
        """
        Clean up temporary files in the service's temp directory.
        
        Args:
            file_patterns: Optional list of file patterns to remove. If None, removes all temp files.
        """
        try:
            if file_patterns:
                for pattern in file_patterns:
                    for file_path in Path(self.temp_dir).glob(pattern):
                        if file_path.is_file():
                            file_path.unlink()
                            logger.info(f"Cleaned up temp file: {file_path}")
            else:
                # Clean all files in temp directory
                for file_path in Path(self.temp_dir).iterdir():
                    if file_path.is_file():
                        file_path.unlink()
                        logger.info(f"Cleaned up temp file: {file_path}")
                        
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")


# Create a default instance for easy importing
youtube_service = YouTubeService()