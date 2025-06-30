"""
YouTube Service Module

This module provides a clean YouTubeService class that encapsulates all YouTube operations
including video information retrieval, transcript fetching, audio downloading, 
playlist/channel extraction, and metadata retrieval.

Features:
- 4-method robust transcript fetching with fallbacks:
  * Method 1: New API (v1.1.0) with Webshare proxy
  * Method 2: New API (v1.1.0) direct connection  
  * Method 3: Old API with Webshare proxy (via http_proxy)
  * Method 4: Old API direct connection
- 6 enhanced audio download strategies for bypassing bot detection
- Playlist and channel video extraction with flat-mode optimization
- URL detection for playlists, channels, and individual videos
- Comprehensive metadata extraction for all content types
- Async support with progress callbacks for long operations
- Rate limiting respect and graceful handling of private/unavailable content
- Integrated with backend configuration system
- Comprehensive error handling and logging
- Graceful fallback between all methods

Migrated from appStreamlit.py with backend optimizations.
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
    Service class for YouTube operations including video info, transcripts, audio downloads,
    playlist/channel extraction, and comprehensive metadata retrieval.
    
    New Methods:
    - is_playlist_url(url): Check if URL is a YouTube playlist
    - is_channel_url(url): Check if URL is a YouTube channel
    - get_playlist_info(url): Get playlist metadata (title, description, video count)
    - get_channel_info(url): Get channel metadata (title, description, video count, subscribers)
    - extract_playlist_videos(url, max_videos): Extract all videos from a playlist
    - extract_channel_videos(url, max_videos): Extract videos from a channel
    
    All new methods support:
    - Async operation with progress callbacks
    - Flat extraction mode for fast metadata-only retrieval
    - Graceful handling of private/unavailable content
    - Rate limiting respect
    - Structured data output with video IDs, titles, durations
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

    def is_playlist_url(self, url: str) -> bool:
        """
        Check if URL is a YouTube playlist URL.
        
        Args:
            url: URL to check
            
        Returns:
            bool: True if URL is a playlist URL
        """
        if not url:
            return False
            
        try:
            parsed_url = urlparse(url.strip())
            
            if parsed_url.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
                # Check for playlist parameter
                query_params = parse_qs(parsed_url.query)
                if 'list' in query_params and query_params['list']:
                    return True
                # Check for playlist path
                if parsed_url.path.startswith('/playlist'):
                    return True
                    
        except Exception as e:
            logger.error(f"Error checking if URL is playlist: {e}")
            
        return False

    def is_channel_url(self, url: str) -> bool:
        """
        Check if URL is a YouTube channel URL.
        
        Args:
            url: URL to check
            
        Returns:
            bool: True if URL is a channel URL
        """
        if not url:
            return False
            
        try:
            parsed_url = urlparse(url.strip())
            
            if parsed_url.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
                # Check for various channel URL patterns
                if (parsed_url.path.startswith('/channel/') or
                    parsed_url.path.startswith('/c/') or
                    parsed_url.path.startswith('/@') or
                    parsed_url.path.startswith('/user/')):
                    return True
                    
        except Exception as e:
            logger.error(f"Error checking if URL is channel: {e}")
            
        return False

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

    async def get_playlist_info(self, playlist_url: str, progress_callback: Optional[Callable[[str, float, str], None]] = None) -> Dict[str, Any]:
        """
        Get playlist metadata using yt-dlp.
        
        Args:
            playlist_url: YouTube playlist URL
            progress_callback: Optional callback for progress updates (stage, progress, message)
            
        Returns:
            Dict[str, Any]: Playlist information including title, description, video count, etc.
        """
        if progress_callback:
            progress_callback("playlist_info", 0.0, "Fetching playlist information...")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Get flat list for fast metadata extraction
            'playlist_items': '1',  # Only get first video to extract playlist metadata quickly
        }
        
        try:
            if progress_callback:
                progress_callback("playlist_info", 0.3, "Extracting playlist metadata...")
            
            # Run yt-dlp in thread to avoid blocking async context
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, 
                lambda: self._extract_playlist_info_sync(playlist_url, ydl_opts)
            )
            
            if progress_callback:
                progress_callback("playlist_info", 0.7, "Processing playlist metadata...")
            
            if info:
                if progress_callback:
                    progress_callback("playlist_info", 1.0, f"Retrieved info for playlist: {info.get('title', 'Unknown')}")
                
                return {
                    'title': info.get('title', 'Unknown Playlist'),
                    'id': info.get('id', ''),
                    'url': playlist_url,
                    'description': info.get('description', ''),
                    'uploader': info.get('uploader', ''),
                    'uploader_id': info.get('uploader_id', ''),
                    'video_count': info.get('playlist_count', 0),
                    'view_count': info.get('view_count', 0),
                    'thumbnail': info.get('thumbnail', ''),
                }
                
        except Exception as e:
            logger.warning(f"Could not fetch playlist info for {playlist_url}: {e}")
            if progress_callback:
                progress_callback("playlist_info", 1.0, f"Failed to fetch playlist info: {str(e)[:50]}...")
            
        # Return minimal info on failure
        if progress_callback:
            progress_callback("playlist_info", 1.0, "Using fallback playlist information")
        
        return {
            'title': 'Unknown Playlist',
            'id': '',
            'url': playlist_url,
            'description': '',
            'uploader': '',
            'uploader_id': '',
            'video_count': 0,
            'view_count': 0,
            'thumbnail': '',
        }

    async def get_channel_info(self, channel_url: str, progress_callback: Optional[Callable[[str, float, str], None]] = None) -> Dict[str, Any]:
        """
        Get channel metadata using yt-dlp.
        
        Args:
            channel_url: YouTube channel URL
            progress_callback: Optional callback for progress updates (stage, progress, message)
            
        Returns:
            Dict[str, Any]: Channel information including title, description, video count, etc.
        """
        if progress_callback:
            progress_callback("channel_info", 0.0, "Fetching channel information...")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Get flat list for fast metadata extraction
            'playlist_items': '1',  # Only get first video to extract channel metadata quickly
        }
        
        try:
            if progress_callback:
                progress_callback("channel_info", 0.3, "Extracting channel metadata...")
            
            # Run yt-dlp in thread to avoid blocking async context
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, 
                lambda: self._extract_playlist_info_sync(channel_url, ydl_opts)
            )
            
            if progress_callback:
                progress_callback("channel_info", 0.7, "Processing channel metadata...")
            
            if info:
                if progress_callback:
                    progress_callback("channel_info", 1.0, f"Retrieved info for channel: {info.get('title', 'Unknown')}")
                
                return {
                    'title': info.get('title', 'Unknown Channel'),
                    'id': info.get('id', ''),
                    'url': channel_url,
                    'description': info.get('description', ''),
                    'uploader': info.get('uploader', ''),
                    'uploader_id': info.get('uploader_id', ''),
                    'video_count': info.get('playlist_count', 0),
                    'view_count': info.get('view_count', 0),
                    'subscriber_count': info.get('subscriber_count', 0),
                    'thumbnail': info.get('thumbnail', ''),
                }
                
        except Exception as e:
            logger.warning(f"Could not fetch channel info for {channel_url}: {e}")
            if progress_callback:
                progress_callback("channel_info", 1.0, f"Failed to fetch channel info: {str(e)[:50]}...")
            
        # Return minimal info on failure
        if progress_callback:
            progress_callback("channel_info", 1.0, "Using fallback channel information")
        
        return {
            'title': 'Unknown Channel',
            'id': '',
            'url': channel_url,
            'description': '',
            'uploader': '',
            'uploader_id': '',
            'video_count': 0,
            'view_count': 0,
            'subscriber_count': 0,
            'thumbnail': '',
        }

    async def extract_playlist_videos(
        self, 
        playlist_url: str, 
        max_videos: Optional[int] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract all videos from a YouTube playlist URL using flat extraction for speed.
        
        Args:
            playlist_url: YouTube playlist URL
            max_videos: Optional maximum number of videos to extract
            progress_callback: Optional callback for progress updates (stage, progress, message)
            
        Returns:
            List[Dict[str, Any]]: List of video information dictionaries
        """
        if progress_callback:
            progress_callback("playlist_extraction", 0.0, "Starting playlist video extraction...")
        
        # Set up playlist items range if max_videos specified
        playlist_items = f"1:{max_videos}" if max_videos else None
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Fast flat extraction - only metadata, no streams
            'playlist_items': playlist_items,
        }
        
        try:
            if progress_callback:
                progress_callback("playlist_extraction", 0.2, "Extracting playlist metadata...")
            
            # Run yt-dlp in thread to avoid blocking async context
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, 
                lambda: self._extract_playlist_info_sync(playlist_url, ydl_opts)
            )
            
            if progress_callback:
                progress_callback("playlist_extraction", 0.6, "Processing video entries...")
            
            videos = []
            if info and 'entries' in info:
                total_entries = len(info['entries'])
                
                for i, entry in enumerate(info['entries']):
                    if entry is None:  # Skip unavailable/private videos
                        continue
                        
                    try:
                        # Extract duration if available
                        duration = 0
                        if 'duration' in entry and entry['duration']:
                            duration = entry['duration']
                        elif 'duration_string' in entry:
                            duration = self._parse_duration_string(entry['duration_string'])
                        
                        video_info = {
                            'id': entry.get('id', ''),
                            'title': entry.get('title', f"Video {i+1}"),
                            'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}" if entry.get('id') else '',
                            'duration': duration,
                            'duration_string': entry.get('duration_string', ''),
                            'uploader': entry.get('uploader') or channel_name,
                            'channel': entry.get('channel') or channel_name,
                            'channel_id': entry.get('channel_id') or channel_id,
                            'view_count': entry.get('view_count', 0),
                            'thumbnail': entry.get('thumbnail', ''),
                            'description': entry.get('description', ''),
                            'upload_date': entry.get('upload_date', ''),
                            'availability': entry.get('availability', 'public'),
                        }
                        videos.append(video_info)
                        
                        # Update progress
                        if progress_callback and total_entries > 0:
                            progress = 0.6 + (i / total_entries) * 0.35
                            progress_callback("playlist_extraction", progress, f"Processed {i+1}/{total_entries} videos")
                            
                    except Exception as e:
                        logger.warning(f"Error processing playlist entry {i}: {e}")
                        continue
            
            if progress_callback:
                progress_callback("playlist_extraction", 1.0, f"Extracted {len(videos)} videos from playlist")
            
            logger.info(f"Successfully extracted {len(videos)} videos from playlist")
            return videos
            
        except Exception as e:
            logger.error(f"Error extracting playlist videos: {e}")
            if progress_callback:
                progress_callback("playlist_extraction", 1.0, f"Failed to extract playlist: {str(e)[:50]}...")
            return []

    async def extract_channel_videos(
        self, 
        channel_url: str, 
        max_videos: Optional[int] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract videos from a YouTube channel URL using flat extraction for speed.
        
        Args:
            channel_url: YouTube channel URL  
            max_videos: Optional maximum number of videos to extract
            progress_callback: Optional callback for progress updates (stage, progress, message)
            
        Returns:
            List[Dict[str, Any]]: List of video information dictionaries
        """
        if progress_callback:
            progress_callback("channel_extraction", 0.0, "Starting channel video extraction...")
        
        # Convert channel URL to uploads playlist URL
        # YouTube channels have their uploads in a special playlist
        uploads_url = channel_url
        
        # If it's a channel URL, we need to get the uploads playlist
        # yt-dlp can handle this by appending /videos to channel URLs
        if self.is_channel_url(channel_url):
            # Ensure the URL ends with /videos to get the uploads tab
            if not channel_url.rstrip('/').endswith('/videos'):
                uploads_url = channel_url.rstrip('/') + '/videos'
        
        # Set up playlist items range if max_videos specified
        playlist_items = f"1:{max_videos}" if max_videos else None
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',  # Extract videos in playlist mode
            'playlist_items': playlist_items,
        }
        
        try:
            if progress_callback:
                progress_callback("channel_extraction", 0.2, "Extracting channel uploads...")
            
            # Run yt-dlp in thread to avoid blocking async context
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, 
                lambda: self._extract_playlist_info_sync(uploads_url, ydl_opts)
            )
            
            if progress_callback:
                progress_callback("channel_extraction", 0.6, "Processing video entries...")
            
            videos = []
            if info and 'entries' in info:
                total_entries = len(info['entries'])
                logger.info(f"Found {total_entries} entries in channel extraction")
                
                # Extract channel name from the playlist info
                channel_name = info.get('uploader') or info.get('channel') or info.get('uploader_id') or ''
                channel_id = info.get('channel_id') or info.get('uploader_id') or ''
                
                for i, entry in enumerate(info['entries']):
                    if entry is None:  # Skip unavailable/private videos
                        continue
                    
                    # Log entry type to debug if we're getting playlists instead of videos
                    entry_type = entry.get('_type', 'unknown')
                    if entry_type != 'url' and 'id' not in entry:
                        logger.warning(f"Skipping non-video entry {i}: type={entry_type}, title={entry.get('title', 'N/A')}")
                        continue
                        
                    try:
                        # Extract duration if available
                        duration = 0
                        if 'duration' in entry and entry['duration']:
                            duration = entry['duration']
                        elif 'duration_string' in entry:
                            duration = self._parse_duration_string(entry['duration_string'])
                        
                        video_info = {
                            'id': entry.get('id', ''),
                            'title': entry.get('title', f"Video {i+1}"),
                            'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}" if entry.get('id') else '',
                            'duration': duration,
                            'duration_string': entry.get('duration_string', ''),
                            'uploader': entry.get('uploader') or channel_name,
                            'channel': entry.get('channel') or channel_name,
                            'channel_id': entry.get('channel_id') or channel_id,
                            'view_count': entry.get('view_count', 0),
                            'thumbnail': entry.get('thumbnail', ''),
                            'description': entry.get('description', ''),
                            'upload_date': entry.get('upload_date', ''),
                            'availability': entry.get('availability', 'public'),
                        }
                        videos.append(video_info)
                        
                        # Update progress
                        if progress_callback and total_entries > 0:
                            progress = 0.6 + (i / total_entries) * 0.35
                            progress_callback("channel_extraction", progress, f"Processed {i+1}/{total_entries} videos")
                            
                    except Exception as e:
                        logger.warning(f"Error processing channel entry {i}: {e}")
                        continue
            
            if progress_callback:
                progress_callback("channel_extraction", 1.0, f"Extracted {len(videos)} videos from channel")
            
            # If no videos found and we used /videos URL, try alternative approach
            if len(videos) == 0 and uploads_url != channel_url:
                logger.warning(f"No videos found with /videos URL, trying alternative extraction")
                if progress_callback:
                    progress_callback("channel_extraction", 0.8, "Trying alternative extraction method...")
                
                # Try with the original URL and different options
                alt_ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True,
                    'playlist_items': playlist_items,
                    'playlistend': max_videos if max_videos else 50,  # Limit to reasonable number
                }
                
                try:
                    alt_info = await loop.run_in_executor(
                        None,
                        lambda: self._extract_playlist_info_sync(channel_url + '/videos', alt_ydl_opts)
                    )
                    
                    if alt_info and 'entries' in alt_info:
                        for entry in alt_info['entries']:
                            if entry and entry.get('id') and entry.get('_type', '') != 'playlist':
                                videos.append({
                                    'id': entry.get('id', ''),
                                    'title': entry.get('title', 'Unknown'),
                                    'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                                    'duration': entry.get('duration', 0),
                                    'duration_string': entry.get('duration_string', ''),
                                    'uploader': entry.get('uploader', ''),
                                    'view_count': entry.get('view_count', 0),
                                    'thumbnail': entry.get('thumbnail', ''),
                                    'description': entry.get('description', ''),
                                    'upload_date': entry.get('upload_date', ''),
                                    'availability': entry.get('availability', 'public'),
                                })
                except Exception as alt_e:
                    logger.warning(f"Alternative extraction also failed: {alt_e}")
            
            logger.info(f"Successfully extracted {len(videos)} videos from channel")
            
            # Add channel metadata to the result
            if videos and channel_name:
                for video in videos:
                    if not video.get('uploader'):
                        video['uploader'] = channel_name
                    if not video.get('channel'):
                        video['channel'] = channel_name
                        
            return videos
            
        except Exception as e:
            logger.error(f"Error extracting channel videos: {e}")
            if progress_callback:
                progress_callback("channel_extraction", 1.0, f"Failed to extract channel: {str(e)[:50]}...")
            return []

    def _parse_duration_string(self, duration_str: str) -> int:
        """
        Parse duration string (e.g., "3:45", "1:23:45") to seconds.
        
        Args:
            duration_str: Duration string in various formats
            
        Returns:
            int: Duration in seconds
        """
        if not duration_str:
            return 0
            
        try:
            # Handle format like "1:23:45" or "3:45" or "45"
            parts = duration_str.split(':')
            if len(parts) == 1:
                # Just seconds
                return int(parts[0])
            elif len(parts) == 2:
                # Minutes:seconds
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                # Hours:minutes:seconds
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except (ValueError, IndexError):
            logger.warning(f"Could not parse duration string: {duration_str}")
            
        return 0

    def _extract_playlist_info_sync(self, url: str, ydl_opts: dict) -> Optional[dict]:
        """Synchronous playlist/channel info extraction for use in thread executor."""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"yt-dlp playlist extraction failed: {e}")
            return None

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=10)
    )
    async def fetch_transcript_segments(self, video_id: str, progress_callback: Optional[Callable[[str, float, str], None]] = None) -> Tuple[Optional[List[Dict]], Optional[str], Optional[str]]:
        """
        Fetch transcript segments using robust 4-method fallback strategy.
        
        Method 1: New API (v1.1.0) with Webshare proxy
        Method 2: New API (v1.1.0) direct connection  
        Method 3: Old API with Webshare proxy (via http_proxy)
        Method 4: Old API direct connection
        
        Args:
            video_id: YouTube video ID
            progress_callback: Optional callback for progress updates (stage, progress, message)
            
        Returns:
            Tuple[Optional[List[Dict]], Optional[str], Optional[str]]: 
                (segments, language, error_message)
        """
        logger.info(f"Attempting to fetch transcript for video_id: {video_id}")
        
        if progress_callback:
            progress_callback("transcript", 0.0, "Initializing 4-method transcript fetch...")
        
        # Get Webshare credentials from settings
        webshare_username, webshare_password = self._get_webshare_credentials()
        
        # Method 1: Try new API (v1.1.0) with Webshare proxy
        if webshare_username and webshare_password:
            try:
                if progress_callback:
                    progress_callback("transcript", 0.1, "Method 1: New API with Webshare proxy...")
                
                result = await self._try_new_api_with_proxy(video_id, webshare_username, webshare_password, progress_callback)
                if result[0] is not None:  # Success
                    if progress_callback:
                        progress_callback("transcript", 1.0, f"Method 1 successful! Found {len(result[0])} segments")
                    return result
                    
            except Exception as e:
                logger.warning(f"Method 1 (new API + proxy) failed: {e}")
                if progress_callback:
                    progress_callback("transcript", 0.2, f"Method 1 failed: {str(e)[:50]}...")
        
        # Method 2: Try new API (v1.1.0) direct connection
        try:
            if progress_callback:
                progress_callback("transcript", 0.25, "Method 2: New API direct connection...")
            
            result = await self._try_new_api_direct(video_id, progress_callback)
            if result[0] is not None:  # Success
                if progress_callback:
                    progress_callback("transcript", 1.0, f"Method 2 successful! Found {len(result[0])} segments")
                return result
                
        except Exception as e:
            logger.warning(f"Method 2 (new API direct) failed: {e}")
            if progress_callback:
                progress_callback("transcript", 0.5, f"Method 2 failed: {str(e)[:50]}...")
        
        # Method 3: Try old API with Webshare proxy (via http_proxy)
        if webshare_username and webshare_password:
            try:
                if progress_callback:
                    progress_callback("transcript", 0.6, "Method 3: Old API with Webshare proxy...")
                
                result = await self._try_old_api_with_proxy(video_id, webshare_username, webshare_password, progress_callback)
                if result[0] is not None:  # Success
                    if progress_callback:
                        progress_callback("transcript", 1.0, f"Method 3 successful! Found {len(result[0])} segments")
                    return result
                    
            except Exception as e:
                logger.warning(f"Method 3 (old API + proxy) failed: {e}")
                if progress_callback:
                    progress_callback("transcript", 0.75, f"Method 3 failed: {str(e)[:50]}...")
        
        # Method 4: Try old API direct connection (last resort)
        try:
            if progress_callback:
                progress_callback("transcript", 0.8, "Method 4: Old API direct connection...")
            
            result = await self._try_old_api_direct(video_id, progress_callback)
            if result[0] is not None:  # Success
                if progress_callback:
                    progress_callback("transcript", 1.0, f"Method 4 successful! Found {len(result[0])} segments")
                return result
                
        except Exception as e:
            logger.error(f"Method 4 (old API direct) failed: {e}")
            if progress_callback:
                progress_callback("transcript", 1.0, f"All 4 methods failed. Last error: {str(e)[:50]}...")
        
        # All methods failed
        error_msg = "All 4 transcript fetch methods failed"
        logger.error(error_msg)
        return None, None, error_msg

    async def _try_new_api_with_proxy(self, video_id: str, webshare_username: str, webshare_password: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Tuple[Optional[List[Dict]], Optional[str], Optional[str]]:
        """Method 1: New API (v1.1.0) with Webshare proxy."""
        try:
            from youtube_transcript_api.proxies import WebshareProxyConfig
            
            if progress_callback:
                progress_callback("transcript", 0.15, "Method 1: Setting up Webshare proxy config...")
            
            logger.info("Method 1: Using new API with Webshare proxy")
            proxy_config = WebshareProxyConfig(
                proxy_username=webshare_username,
                proxy_password=webshare_password,
                retries_when_blocked=3
            )
            ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
            
            if progress_callback:
                progress_callback("transcript", 0.18, "Method 1: Fetching transcript via proxy...")
            
            transcript = ytt_api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
            
            if not transcript or not transcript.snippets:
                raise ValueError("Method 1: Fetched transcript data is empty")
            
            # Convert to dict format
            segments = []
            for snippet in transcript.snippets:
                segments.append({
                    'text': snippet.text,
                    'start': snippet.start,
                    'duration': snippet.duration
                })
            
            logger.info("Method 1: Successfully fetched transcript with new API + proxy")
            return segments, transcript.language, None
            
        except ImportError:
            raise Exception("New API v1.1.0 with proxy support not available")
        except Exception as e:
            raise Exception(f"Method 1 error: {e}")

    async def _try_new_api_direct(self, video_id: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Tuple[Optional[List[Dict]], Optional[str], Optional[str]]:
        """Method 2: New API (v1.1.0) direct connection."""
        try:
            # Try to import new API components to confirm v1.1.0 is available
            from youtube_transcript_api.proxies import WebshareProxyConfig
            
            if progress_callback:
                progress_callback("transcript", 0.35, "Method 2: Connecting directly to YouTube...")
            
            logger.info("Method 2: Using new API direct connection")
            ytt_api = YouTubeTranscriptApi()
            
            if progress_callback:
                progress_callback("transcript", 0.4, "Method 2: Fetching transcript directly...")
            
            transcript = ytt_api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
            
            if not transcript or not transcript.snippets:
                raise ValueError("Method 2: Fetched transcript data is empty")
            
            # Convert to dict format
            segments = []
            for snippet in transcript.snippets:
                segments.append({
                    'text': snippet.text,
                    'start': snippet.start,
                    'duration': snippet.duration
                })
            
            logger.info("Method 2: Successfully fetched transcript with new API direct")
            return segments, transcript.language, None
            
        except ImportError:
            raise Exception("New API v1.1.0 not available")
        except Exception as e:
            raise Exception(f"Method 2 error: {e}")

    async def _try_old_api_with_proxy(self, video_id: str, webshare_username: str, webshare_password: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Tuple[Optional[List[Dict]], Optional[str], Optional[str]]:
        """Method 3: Old API with Webshare proxy via environment variables."""
        import os
        
        if progress_callback:
            progress_callback("transcript", 0.65, "Method 3: Setting up proxy environment...")
        
        # Store original proxy settings
        original_http_proxy = os.environ.get('http_proxy')
        original_https_proxy = os.environ.get('https_proxy')
        
        try:
            # Set up proxy via environment variables for old API
            proxy_url = f"http://{webshare_username}:{webshare_password}@p.webshare.io:80"
            os.environ['http_proxy'] = proxy_url
            os.environ['https_proxy'] = proxy_url
            
            if progress_callback:
                progress_callback("transcript", 0.68, "Method 3: Using old API with proxy...")
            
            logger.info("Method 3: Using old API with Webshare proxy via environment")
            
            # Use old API method
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript_obj = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            
            if progress_callback:
                progress_callback("transcript", 0.72, "Method 3: Fetching segments...")
            
            fetched_segments = transcript_obj.fetch()
            
            if not fetched_segments:
                raise ValueError("Method 3: Fetched transcript data is empty")
            
            logger.info("Method 3: Successfully fetched transcript with old API + proxy")
            return fetched_segments, transcript_obj.language, None
            
        except Exception as e:
            raise Exception(f"Method 3 error: {e}")
        finally:
            # Restore original proxy settings
            if original_http_proxy is not None:
                os.environ['http_proxy'] = original_http_proxy
            else:
                os.environ.pop('http_proxy', None)
                
            if original_https_proxy is not None:
                os.environ['https_proxy'] = original_https_proxy  
            else:
                os.environ.pop('https_proxy', None)

    async def _try_old_api_direct(self, video_id: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Tuple[Optional[List[Dict]], Optional[str], Optional[str]]:
        """Method 4: Old API direct connection."""
        try:
            if progress_callback:
                progress_callback("transcript", 0.85, "Method 4: Using old API direct...")
            
            logger.info("Method 4: Using old API direct connection")
            
            # Use old API method
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript_obj = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            
            if progress_callback:
                progress_callback("transcript", 0.9, "Method 4: Fetching segments...")
            
            fetched_segments = transcript_obj.fetch()
            
            if not fetched_segments:
                raise ValueError("Method 4: Fetched transcript data is empty")
            
            logger.info("Method 4: Successfully fetched transcript with old API direct")
            return fetched_segments, transcript_obj.language, None
            
        except Exception as e:
            raise Exception(f"Method 4 error: {e}")

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
        
        # Strategy 0: Latest 2025 method with browser cookies
        try:
            if progress_callback:
                progress_callback("downloading", 0.15, "Strategy 0: Trying latest 2025 method with browser cookies...")
                
            result = await self._download_with_strategy_2025(
                video_url, output_dir, safe_title, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("downloading", 1.0, "Downloaded with 2025 method!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("downloading", 0.2, f"Strategy 0 failed: {str(e)[:100]}...")
        
        # Strategy 1: yt-dlp with cookie file (if available)
        if cookie_file:
            try:
                if progress_callback:
                    progress_callback("downloading", 0.3, "Strategy 1: yt-dlp with cookie authentication...")
                    
                result = await self._download_with_strategy_1(
                    video_url, output_dir, safe_title, cookie_file, final_mp3_path, progress_callback
                )
                if result:
                    if progress_callback:
                        progress_callback("downloading", 1.0, "Downloaded with cookie authentication!")
                    return result
                    
            except Exception as e:
                if progress_callback:
                    progress_callback("downloading", 0.3, f"Cookie strategy failed: {str(e)[:100]}...")
        
        # Strategy 2: yt-dlp with advanced anti-bot headers
        try:
            if progress_callback:
                progress_callback("downloading", 0.4, "Strategy 2: yt-dlp with anti-bot headers...")
                
            result = await self._download_with_strategy_2(
                video_url, output_dir, safe_title, cookie_file, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("downloading", 1.0, "Downloaded with iOS client simulation!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("downloading", 0.4, f"Strategy 2 failed: {str(e)[:100]}...")
        
        # Strategy 3: yt-dlp with TV client
        try:
            if progress_callback:
                progress_callback("downloading", 0.5, "Strategy 3: yt-dlp with TV client...")
                
            result = await self._download_with_strategy_3(
                video_url, output_dir, safe_title, cookie_file, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("downloading", 1.0, "Downloaded with TV client!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("downloading", 0.5, f"Strategy 3 failed: {str(e)[:100]}...")
        
        # Strategy 4: pytube fallback
        try:
            if progress_callback:
                progress_callback("downloading", 0.6, "Strategy 4: Trying pytube...")
                
            result = await self._download_with_strategy_4(
                video_url, output_dir, safe_title, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("downloading", 1.0, "Downloaded with pytube!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("downloading", 0.6, f"Strategy 4 failed: {str(e)[:100]}...")
        
        # Strategy 5: yt-dlp with embedded client
        try:
            if progress_callback:
                progress_callback("downloading", 0.7, "Strategy 5: yt-dlp with embedded client...")
                
            result = await self._download_with_strategy_5(
                video_url, output_dir, safe_title, cookie_file, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("downloading", 1.0, "Downloaded with embedded client!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("downloading", 0.7, f"Strategy 5 failed: {str(e)[:100]}...")
        
        # Strategy 6: moviepy + youtube-dl fallback
        try:
            if progress_callback:
                progress_callback("downloading", 0.8, "Strategy 6: Trying moviepy extraction...")
                
            result = await self._download_with_strategy_6(
                video_url, output_dir, safe_title, final_mp3_path, progress_callback
            )
            if result:
                if progress_callback:
                    progress_callback("downloading", 1.0, "Downloaded with moviepy!")
                return result
                
        except Exception as e:
            if progress_callback:
                progress_callback("downloading", 0.8, f"Strategy 6 failed: {str(e)[:100]}...")
        
        # All strategies failed
        if progress_callback:
            progress_callback("downloading", 0.9, "All enhanced download strategies failed!")
        
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

    async def _download_with_strategy_2025(self, video_url: str, output_dir: str, safe_title: str,
                                          final_mp3_path: str, progress_callback: Optional[Callable[[str, float, str], None]]) -> Optional[str]:
        """Strategy 2025: Latest method with browser cookies and format selection."""
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
            # Use cookies from browser automatically
            'cookiesfrombrowser': ('chrome',),  # Try Chrome first, can also use 'firefox', 'edge'
            # Latest 2025 extractor args
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android', 'ios'],
                    'skip': ['dash', 'hls'],  # Skip problematic formats
                    'formats': 'missing_pot',  # Handle missing PO tokens
                }
            },
            # Update yt-dlp before downloading
            'update': True,
            # Force IPv4 to avoid IPv6 issues
            'source_address': '0.0.0.0',
            # Latest user agent
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        }
        
        # Add progress hook if callback provided
        if progress_callback:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    percent = d.get('_percent_str', '0%').strip('%')
                    try:
                        progress_callback("downloading", float(percent) / 100, f"Downloading: {percent}%")
                    except:
                        pass
            ydl_opts['progress_hooks'] = [progress_hook]
        
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            return final_mp3_path if os.path.exists(final_mp3_path) else None
        except Exception as e:
            logger.error(f"Strategy 2025 failed: {e}")
            raise

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

    def _get_webshare_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get Webshare proxy credentials from settings.
        
        Returns:
            Tuple[Optional[str], Optional[str]]: (username, password) or (None, None) if not found
        """
        username = self.settings.webshare_username
        password = self.settings.webshare_password
        
        if username and password:
            logger.info("Webshare credentials found in settings")
            return username, password
        else:
            logger.warning("No Webshare credentials found in settings")
            return None, None

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