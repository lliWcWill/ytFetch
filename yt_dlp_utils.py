"""
yt-dlp Utilities for handling 403 errors and updates
"""

import subprocess
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def update_yt_dlp():
    """Update yt-dlp to the latest version"""
    try:
        # Try to update yt-dlp
        result = subprocess.run(
            ["yt-dlp", "-U"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info("yt-dlp updated successfully")
            return True, result.stdout
        else:
            logger.error(f"Failed to update yt-dlp: {result.stderr}")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp update timed out")
        return False, "Update timed out"
    except Exception as e:
        logger.error(f"Error updating yt-dlp: {e}")
        return False, str(e)


def clear_yt_dlp_cache():
    """Clear yt-dlp cache to fix potential 403 errors"""
    try:
        # Method 1: Use yt-dlp command
        result = subprocess.run(
            ["yt-dlp", "--rm-cache-dir"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info("yt-dlp cache cleared successfully via command")
            
        # Method 2: Manual cache directory removal
        cache_paths = [
            Path.home() / ".cache" / "yt-dlp",
            Path.home() / ".cache" / "youtube-dl",
            Path.home() / "AppData" / "Local" / "yt-dlp" / "Cache",  # Windows
        ]
        
        cleared_paths = []
        for cache_path in cache_paths:
            if cache_path.exists():
                try:
                    shutil.rmtree(cache_path)
                    cleared_paths.append(str(cache_path))
                    logger.info(f"Cleared cache directory: {cache_path}")
                except Exception as e:
                    logger.warning(f"Could not clear {cache_path}: {e}")
        
        return True, f"Cache cleared successfully. Removed: {', '.join(cleared_paths) if cleared_paths else 'No manual paths found'}"
        
    except Exception as e:
        logger.error(f"Error clearing yt-dlp cache: {e}")
        return False, str(e)


def get_yt_dlp_version():
    """Get current yt-dlp version"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return "Unknown"
            
    except Exception as e:
        logger.error(f"Error getting yt-dlp version: {e}")
        return "Error"


def create_cookies_file(cookies_content: str, temp_dir: str = None) -> str:
    """
    Create a temporary cookies file for yt-dlp
    
    Args:
        cookies_content: Netscape format cookies content
        temp_dir: Directory to store the cookies file
        
    Returns:
        Path to the created cookies file
    """
    import tempfile
    
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        cookies_path = os.path.join(temp_dir, "cookies.txt")
    else:
        fd, cookies_path = tempfile.mkstemp(suffix=".txt", prefix="yt_dlp_cookies_")
        os.close(fd)
    
    with open(cookies_path, 'w') as f:
        f.write(cookies_content)
    
    return cookies_path


def get_alternative_yt_dlp_opts(include_cookies: bool = False, cookies_path: str = None):
    """
    Get alternative yt-dlp options for bypassing 403 errors
    
    Args:
        include_cookies: Whether to include cookie options
        cookies_path: Path to cookies file
        
    Returns:
        Dictionary of yt-dlp options
    """
    opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        # Enhanced headers
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'referer': 'https://www.youtube.com/',
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
        },
        # Use different player clients
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web', 'ios'],  # Try multiple clients
                'player_skip': ['configs', 'initial_data'],  # Skip some data to speed up
            }
        },
        # Additional options
        'nocheckcertificate': True,  # Sometimes helps with SSL issues
        'geo_bypass': True,  # Bypass geographic restrictions
        'geo_bypass_country': 'US',  # Pretend to be from US
    }
    
    # Add cookie options if requested
    if include_cookies and cookies_path and os.path.exists(cookies_path):
        opts['cookiefile'] = cookies_path
    elif include_cookies:
        # Try to extract from browser
        opts['cookiesfrombrowser'] = ('chrome',)  # Can be 'firefox', 'edge', etc.
    
    return opts