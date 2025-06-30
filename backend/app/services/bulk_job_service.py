"""
Bulk Job Service Module

This module provides comprehensive bulk YouTube video processing functionality including:
- Creating and managing bulk jobs from playlist/channel URLs
- Processing video queues sequentially with rate limiting
- Real-time progress updates via Supabase
- Error handling and retry logic
- Integration with existing YouTube and Transcription services
- ZIP file generation for bulk downloads
- Webhook notifications

Key Features:
- Create bulk jobs from playlist/channel URLs
- Queue individual video tasks in database
- Process videos one by one with rate limiting (3-5 second delays)
- Update progress in real-time via Supabase
- Handle failed videos with retry logic
- Support different transcript methods (unofficial, groq, openai)
- Respect user tier limits
- Cleanup temporary files
- Generate ZIP files for bulk downloads
- Send webhook notifications when jobs complete

Integrated with:
- Supabase client for database operations
- YouTubeService for playlist extraction and video processing
- TranscriptionService for AI transcription
- Existing progress callback patterns
"""

import asyncio
import json
import logging
import os
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import aiofiles
import aiohttp
import asyncpg
from pydantic import BaseModel

# Local imports
from ..core.config import get_settings
from ..core.supabase import get_supabase_service, SupabaseError
from ..services.youtube_service import YouTubeService
from ..services.transcription_service import TranscriptionService

# Initialize settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Bulk job status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskStatus(str, Enum):
    """Individual task status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"
    SKIPPED = "skipped"


class TranscriptMethod(str, Enum):
    """Supported transcript methods"""
    UNOFFICIAL = "unofficial"
    GROQ = "groq"
    OPENAI = "openai"


class UserTier(str, Enum):
    """User tier definitions for rate limiting"""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class BulkJobConfig(BaseModel):
    """Configuration for bulk job processing"""
    max_videos_per_job: int = 100
    rate_limit_delay_seconds: float = 4.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 10.0
    webhook_timeout_seconds: int = 30
    zip_compression_level: int = 6
    temp_cleanup_delay_seconds: int = 300  # 5 minutes


class BulkJobMetrics(BaseModel):
    """Metrics tracking for bulk jobs"""
    total_videos: int = 0
    completed_videos: int = 0
    failed_videos: int = 0
    skipped_videos: int = 0
    retry_videos: int = 0
    processing_time_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    success_rate: float = 0.0


class BulkJobError(Exception):
    """Base exception for bulk job processing errors"""
    pass


class BulkJobService:
    """
    Service for handling bulk YouTube video processing jobs.
    
    Features:
    - Create jobs from playlist/channel URLs
    - Queue and process videos sequentially
    - Real-time progress updates via Supabase
    - Rate limiting and retry logic
    - User tier limits enforcement
    - ZIP file generation
    - Webhook notifications
    """

    def __init__(self):
        """Initialize the bulk job service."""
        self.settings = get_settings()
        self.config = BulkJobConfig()
        
        # Initialize services
        self.youtube_service = YouTubeService()
        
        # Rate limiting configuration per user tier
        self.tier_limits = {
            UserTier.FREE: {
                "max_videos_per_job": 60,
                "max_concurrent_jobs": 1,
                "rate_limit_delay": 5.0,
                "daily_limit": 60
            },
            UserTier.BASIC: {
                "max_videos_per_job": 25,
                "max_concurrent_jobs": 2,
                "rate_limit_delay": 4.0,
                "daily_limit": 50
            },
            UserTier.PRO: {
                "max_videos_per_job": 100,
                "max_concurrent_jobs": 3,
                "rate_limit_delay": 3.0,
                "daily_limit": 200
            },
            UserTier.ENTERPRISE: {
                "max_videos_per_job": 500,
                "max_concurrent_jobs": 5,
                "rate_limit_delay": 3.0,
                "daily_limit": 1000
            }
        }
        
        # Active jobs tracking
        self.active_jobs: Set[str] = set()
        
        logger.info("BulkJobService initialized")

    async def create_bulk_job(
        self,
        user_id: Optional[str],
        source_url: str,
        transcript_method: TranscriptMethod = TranscriptMethod.UNOFFICIAL,
        output_format: str = "txt",
        max_videos: Optional[int] = None,
        user_tier: UserTier = UserTier.FREE,
        webhook_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Create a new bulk processing job from a playlist or channel URL.
        
        Args:
            user_id: User identifier
            source_url: YouTube playlist or channel URL
            transcript_method: Method to use for transcription
            output_format: Output format (txt, srt, vtt, json)
            max_videos: Maximum number of videos to process (respects tier limits)
            user_tier: User's subscription tier
            webhook_url: Optional webhook URL for completion notification
            metadata: Optional metadata dict (used for guest session tracking)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict containing job information
            
        Raises:
            BulkJobError: If job creation fails
        """
        try:
            if progress_callback:
                progress_callback("job_creation", 0.0, "Creating bulk job...")
            
            # Validate source URL
            if not self._is_valid_bulk_url(source_url):
                raise BulkJobError("URL must be a YouTube playlist or channel")
            
            # Check user tier limits
            tier_config = self.tier_limits.get(user_tier, self.tier_limits[UserTier.FREE])
            await self._check_user_limits(user_id, user_tier, tier_config)
            
            # Extract videos from source URL
            if progress_callback:
                progress_callback("job_creation", 0.2, "Extracting videos from source...")
            
            videos = await self._extract_videos_from_url(source_url, max_videos, tier_config, progress_callback)
            
            if not videos:
                raise BulkJobError("No videos found in the provided URL")
            
            # Apply tier video limit
            max_allowed = tier_config["max_videos_per_job"]
            if len(videos) > max_allowed:
                videos = videos[:max_allowed]
                logger.warning(f"Limited videos to {max_allowed} for tier {user_tier}")
            
            if progress_callback:
                progress_callback("job_creation", 0.5, f"Found {len(videos)} videos, creating job...")
            
            # Create job in database
            job_id = str(uuid.uuid4())
            
            # Determine source type and name/description
            if self.youtube_service.is_playlist_url(source_url):
                source_type = "playlist"
                # Extract playlist ID from URL
                import re
                playlist_match = re.search(r'list=([\w-]+)', source_url)
                source_id = playlist_match.group(1) if playlist_match else None
            else:
                source_type = "channel"
                # Extract channel info from URL
                import re
                channel_match = re.search(r'/@([\w-]+)|/c/([\w-]+)|/channel/([\w-]+)|/user/([\w-]+)', source_url)
                source_id = channel_match.group(1) if channel_match else None
            
            # Use first video title or source URL as job name
            job_name = f"Bulk {source_type} job - {len(videos)} videos"
            if videos and videos[0].get("title"):
                job_name = f"{source_type.capitalize()}: {videos[0].get('playlist_title', videos[0].get('uploader', 'Unknown'))}"
            
            job_data = {
                "id": job_id,
                "job_id": job_id,  # Also set job_id column
                "type": source_type,  # Add required type field
                # Removed 'name' field as it doesn't exist in the deployed table
                # "description": f"Processing {len(videos)} videos from {source_type}",
                "source_url": source_url,
                # "source_id": source_id,
                "status": JobStatus.PENDING.value,
                "total_videos": len(videos),
                # Don't set these as they'll be updated by triggers
                # "processed_videos": 0,
                # "successful_videos": 0,
                # "failed_videos": 0,
                # "progress_percentage": 0.0,
                "transcript_method": transcript_method.value,
                "output_format": output_format,
                "tier": user_tier.value,  # Changed from user_tier to tier
                "webhook_url": webhook_url,
                "metadata": metadata,  # Add metadata for guest session tracking
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Only add user_id if it's not None (for guest users it will be None)
            if user_id is not None:
                job_data["user_id"] = user_id
            
            # Insert job into database
            supabase = get_supabase_service()
            job_result = supabase.table("bulk_jobs").insert(job_data).execute()
            
            if not job_result.data:
                raise BulkJobError("Failed to create job in database")
            
            if progress_callback:
                progress_callback("job_creation", 0.7, "Creating video tasks...")
            
            # Create individual video tasks
            tasks = []
            for i, video in enumerate(videos):
                task_data = {
                    "id": str(uuid.uuid4()),
                    "job_id": job_id,
                    "video_id": video["id"],
                    "video_title": video["title"],  # Changed from title to video_title
                    "video_url": video["url"],
                    "duration": int(video.get("duration", 0)),  # Ensure duration is an integer
                    "status": TaskStatus.PENDING.value,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                tasks.append(task_data)
            
            # Batch insert tasks
            if tasks:
                tasks_result = supabase.table("video_tasks").insert(tasks).execute()
                if not tasks_result.data:
                    # Cleanup job if task creation fails
                    supabase.table("bulk_jobs").delete().eq("id", job_id).execute()
                    raise BulkJobError("Failed to create video tasks")
            
            if progress_callback:
                progress_callback("job_creation", 1.0, f"Bulk job created successfully with {len(videos)} videos")
            
            logger.info(f"Created bulk job {job_id} with {len(videos)} videos for user {user_id}")
            
            return {
                "job_id": job_id,
                "total_videos": len(videos),
                "status": JobStatus.PENDING.value,
                "estimated_duration_minutes": len(videos) * tier_config["rate_limit_delay"] / 60,
                "tier_limits": tier_config,
                "created_at": job_data["created_at"],
                "source_url": source_url,
                "transcript_method": transcript_method.value,
                "output_format": output_format
            }
            
        except Exception as e:
            error_msg = f"Failed to create bulk job: {str(e)}"
            logger.error(error_msg)
            if progress_callback:
                progress_callback("job_creation", 0.0, f"Error: {error_msg}")
            raise BulkJobError(error_msg)

    async def start_job_processing(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> bool:
        """
        Start processing a bulk job.
        
        Args:
            job_id: Job identifier to process
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if processing started successfully
            
        Raises:
            BulkJobError: If job processing fails to start
        """
        try:
            if job_id in self.active_jobs:
                raise BulkJobError(f"Job {job_id} is already being processed")
            
            # Get job details
            supabase = get_supabase_service()
            job_result = supabase.table("bulk_jobs").select("*").eq("id", job_id).execute()
            
            if not job_result.data:
                raise BulkJobError(f"Job {job_id} not found")
            
            job = job_result.data[0]
            
            if job["status"] != JobStatus.PENDING.value:
                raise BulkJobError(f"Job {job_id} is not in pending status")
            
            # Mark job as processing
            self.active_jobs.add(job_id)
            await self._update_job_status(job_id, JobStatus.PROCESSING, progress_callback)
            
            # Start processing in background
            asyncio.create_task(self._process_job_videos(job_id, progress_callback))
            
            logger.info(f"Started processing job {job_id}")
            return True
            
        except Exception as e:
            self.active_jobs.discard(job_id)
            error_msg = f"Failed to start job processing: {str(e)}"
            logger.error(error_msg)
            raise BulkJobError(error_msg)

    async def _process_job_videos(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> None:
        """
        Process all videos in a bulk job sequentially with rate limiting.
        
        Args:
            job_id: Job identifier
            progress_callback: Optional callback for progress updates
        """
        start_time = time.time()
        
        try:
            supabase = get_supabase_service()
            
            # Get job details
            job_result = supabase.table("bulk_jobs").select("*").eq("id", job_id).execute()
            if not job_result.data:
                raise BulkJobError(f"Job {job_id} not found")
            
            job = job_result.data[0]
            transcript_method = TranscriptMethod(job["transcript_method"])
            output_format = job["output_format"]
            user_tier = UserTier(job.get("tier", job.get("user_tier", "free")))
            tier_config = self.tier_limits[user_tier]
            
            # Get pending tasks
            tasks_result = supabase.table("video_tasks").select("*").eq("job_id", job_id).eq("status", TaskStatus.PENDING.value).order("created_at").execute()
            
            if not tasks_result.data:
                logger.warning(f"No pending tasks found for job {job_id}")
                await self._complete_job(job_id, progress_callback)
                return
            
            tasks = tasks_result.data
            total_tasks = len(tasks)
            completed_count = 0
            failed_count = 0
            
            if progress_callback:
                progress_callback("processing", 0.0, f"Starting to process {total_tasks} videos...")
            
            # Process each video task
            for i, task in enumerate(tasks):
                try:
                    # Check if job has been cancelled
                    job_check = supabase.table("bulk_jobs").select("status").eq("id", job_id).execute()
                    if job_check.data and job_check.data[0]["status"] == JobStatus.CANCELLED.value:
                        logger.info(f"Job {job_id} was cancelled, stopping processing")
                        break
                    
                    if progress_callback:
                        progress = (i / total_tasks) * 0.9  # Leave 10% for finalization
                        progress_callback("processing", progress, f"Processing video {i+1} of {total_tasks}: {task['title'][:50]}...")
                    
                    # Update task status to processing
                    await self._update_task_status(task["id"], TaskStatus.PROCESSING)
                    
                    # Process individual video
                    success = await self._process_individual_video(
                        task, transcript_method, output_format, progress_callback
                    )
                    
                    if success:
                        completed_count += 1
                        await self._update_task_status(task["id"], TaskStatus.COMPLETED)
                        logger.info(f"Completed task {task['id']} for video {task['video_id']}")
                    else:
                        failed_count += 1
                        await self._update_task_status(task["id"], TaskStatus.FAILED)
                        logger.warning(f"Failed task {task['id']} for video {task['video_id']}")
                    
                    # Update job progress
                    await self._update_job_progress(job_id, completed_count, failed_count)
                    
                    # Rate limiting delay
                    if i < total_tasks - 1:  # Don't delay after the last task
                        delay = tier_config["rate_limit_delay"]
                        if progress_callback:
                            progress_callback("rate_limiting", progress, f"Rate limiting delay: {delay}s...")
                        await asyncio.sleep(delay)
                
                except Exception as e:
                    logger.error(f"Error processing task {task['id']}: {e}")
                    failed_count += 1
                    await self._update_task_status(task["id"], TaskStatus.FAILED)
                    await self._update_job_progress(job_id, completed_count, failed_count)
            
            # Retry failed tasks if configured
            if failed_count > 0:
                await self._retry_failed_tasks(job_id, progress_callback)
            
            # Generate ZIP file if there are completed tasks
            zip_path = None
            if completed_count > 0:
                if progress_callback:
                    progress_callback("finalizing", 0.9, "Generating ZIP file...")
                zip_path = await self._generate_job_zip(job_id, progress_callback)
            
            # Complete the job
            await self._complete_job(job_id, progress_callback, zip_path)
            
            # Send webhook notification if configured
            if job["webhook_url"]:
                await self._send_webhook_notification(job, completed_count, failed_count, zip_path)
            
            processing_time = time.time() - start_time
            logger.info(f"Completed job {job_id}: {completed_count} successful, {failed_count} failed in {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            await self._update_job_status(job_id, JobStatus.FAILED, progress_callback)
            if progress_callback:
                progress_callback("error", 0.0, f"Job processing failed: {str(e)}")
        finally:
            self.active_jobs.discard(job_id)

    async def _process_individual_video(
        self,
        task: Dict[str, Any],
        transcript_method: TranscriptMethod,
        output_format: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> bool:
        """
        Process a single video task.
        
        Args:
            task: Task data from database
            transcript_method: Transcription method to use
            output_format: Output format for transcript
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if processing was successful
        """
        try:
            video_id = task["video_id"]
            video_url = task["video_url"]
            
            if progress_callback:
                progress_callback("video_processing", 0.0, f"Starting video {video_id}...")
            
            # Get video information
            video_info = await self.youtube_service.get_video_info(video_id, progress_callback)
            
            # Choose processing method based on transcript_method
            if transcript_method == TranscriptMethod.UNOFFICIAL:
                # Use unofficial transcript API
                segments, language, error = await self.youtube_service.fetch_transcript_segments(video_id, progress_callback)
                
                if segments:
                    # Format transcript
                    transcript_text = self.youtube_service.format_segments(segments, output_format)
                    
                    # Store result in database
                    await self._store_task_result(task["id"], transcript_text, language, "youtube_transcript_api")
                    return True
                else:
                    logger.warning(f"No transcript found for video {video_id}: {error}")
                    return False
            
            elif transcript_method in [TranscriptMethod.GROQ, TranscriptMethod.OPENAI]:
                # Use AI transcription
                return await self._process_with_ai_transcription(task, transcript_method, output_format, progress_callback)
            
            else:
                logger.error(f"Unsupported transcript method: {transcript_method}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing video {task['video_id']}: {e}")
            await self._store_task_error(task["id"], str(e))
            return False

    async def _process_with_ai_transcription(
        self,
        task: Dict[str, Any],
        transcript_method: TranscriptMethod,
        output_format: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> bool:
        """
        Process video using AI transcription (Groq or OpenAI).
        
        Args:
            task: Task data from database
            transcript_method: AI transcription method
            output_format: Output format for transcript
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if processing was successful
        """
        audio_file_path = None
        
        try:
            video_id = task["video_id"]
            
            if progress_callback:
                progress_callback("ai_transcription", 0.0, f"Downloading audio for {video_id}...")
            
            # Download audio
            audio_file_path = await self.youtube_service.download_audio_as_mp3_enhanced(
                video_id, 
                output_dir=self.settings.temp_dir,
                video_title=task["title"],
                progress_callback=progress_callback
            )
            
            if not audio_file_path or not os.path.exists(audio_file_path):
                logger.error(f"Failed to download audio for video {video_id}")
                return False
            
            if progress_callback:
                progress_callback("ai_transcription", 0.3, f"Transcribing audio with {transcript_method.value}...")
            
            # Initialize transcription service
            provider = "groq" if transcript_method == TranscriptMethod.GROQ else "openai"
            transcription_service = TranscriptionService(provider=provider)
            
            # Transcribe audio
            result = await transcription_service.transcribe_audio_from_file(
                audio_file_path,
                language="en",
                progress_callback=progress_callback
            )
            
            if not result:
                logger.error(f"Transcription failed for video {video_id}")
                return False
            
            # Extract transcript text
            if isinstance(result, dict) and "segments" in result:
                # Format segments into requested output format
                transcript_text = self.youtube_service.format_segments(result["segments"], output_format)
                download_strategy = result.get("download_strategy", "unknown")
            else:
                # Backward compatibility - result is just text
                transcript_text = str(result)
                download_strategy = "ai_transcription"
            
            # Store result in database
            await self._store_task_result(task["id"], transcript_text, "en", download_strategy)
            
            if progress_callback:
                progress_callback("ai_transcription", 1.0, f"Completed transcription for {video_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"AI transcription failed for video {task['video_id']}: {e}")
            await self._store_task_error(task["id"], str(e))
            return False
        finally:
            # Cleanup audio file
            if audio_file_path and os.path.exists(audio_file_path):
                try:
                    os.remove(audio_file_path)
                    logger.debug(f"Cleaned up audio file: {audio_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup audio file {audio_file_path}: {e}")

    async def _extract_videos_from_url(
        self,
        source_url: str,
        max_videos: Optional[int],
        tier_config: Dict[str, Any],
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """Extract videos from playlist or channel URL."""
        try:
            if self.youtube_service.is_playlist_url(source_url):
                videos = await self.youtube_service.extract_playlist_videos(
                    source_url, max_videos, progress_callback
                )
            elif self.youtube_service.is_channel_url(source_url):
                videos = await self.youtube_service.extract_channel_videos(
                    source_url, max_videos, progress_callback
                )
            else:
                raise BulkJobError("URL must be a YouTube playlist or channel")
            
            # Apply tier limits
            max_allowed = tier_config["max_videos_per_job"]
            if max_videos:
                max_allowed = min(max_allowed, max_videos)
            
            return videos[:max_allowed] if len(videos) > max_allowed else videos
            
        except Exception as e:
            logger.error(f"Failed to extract videos from {source_url}: {e}")
            raise BulkJobError(f"Failed to extract videos: {str(e)}")

    async def _check_user_limits(
        self,
        user_id: Optional[str],
        user_tier: UserTier,
        tier_config: Dict[str, Any]
    ) -> None:
        """Check if user has exceeded their tier limits."""
        # Skip limit checks for guest users (None user_id)
        # The database trigger handles guest limits
        if user_id is None:
            return
            
        try:
            supabase = get_supabase_service()
            
            # Check concurrent jobs
            active_jobs_result = supabase.table("bulk_jobs").select("id").eq("user_id", user_id).eq("status", JobStatus.PROCESSING.value).execute()
            
            if len(active_jobs_result.data) >= tier_config["max_concurrent_jobs"]:
                raise BulkJobError(f"Maximum concurrent jobs limit reached for tier {user_tier.value}")
            
            # Check daily limit
            today = datetime.now(timezone.utc).date().isoformat()
            daily_jobs_result = supabase.table("bulk_jobs").select("total_videos").eq("user_id", user_id).gte("created_at", f"{today}T00:00:00Z").execute()
            
            daily_videos = sum(job.get("total_videos", 0) for job in daily_jobs_result.data)
            
            if daily_videos >= tier_config["daily_limit"]:
                raise BulkJobError(f"Daily video processing limit reached for tier {user_tier.value}")
                
        except SupabaseError as e:
            logger.error(f"Failed to check user limits: {e}")
            # Don't block job creation on database errors, but log the issue
            logger.warning("Proceeding with job creation despite limit check failure")

    def _is_valid_bulk_url(self, url: str) -> bool:
        """Check if URL is valid for bulk processing."""
        return (
            self.youtube_service.is_playlist_url(url) or 
            self.youtube_service.is_channel_url(url)
        )

    async def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> None:
        """Update job status in database."""
        try:
            supabase = get_supabase_service()
            update_data = {
                "status": status.value,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            supabase.table("bulk_jobs").update(update_data).eq("id", job_id).execute()
            
            if progress_callback:
                progress_callback("status_update", 0.0, f"Job status updated to {status.value}")
                
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")

    async def _update_task_status(
        self,
        task_id: str,
        status: TaskStatus
    ) -> None:
        """Update task status in database."""
        try:
            supabase = get_supabase_service()
            update_data = {
                "status": status.value,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if status == TaskStatus.PROCESSING:
                update_data["started_at"] = datetime.now(timezone.utc).isoformat()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                update_data["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            supabase.table("video_tasks").update(update_data).eq("id", task_id).execute()
            
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")

    async def _update_job_progress(
        self,
        job_id: str,
        completed_count: int,
        failed_count: int
    ) -> None:
        """Update job progress in database."""
        try:
            supabase = get_supabase_service()
            update_data = {
                "completed_videos": completed_count,
                "failed_videos": failed_count,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            supabase.table("bulk_jobs").update(update_data).eq("id", job_id).execute()
            
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")

    async def _store_task_result(
        self,
        task_id: str,
        transcript_text: str,
        language: str,
        method: str
    ) -> None:
        """Store successful task result in database."""
        try:
            supabase = get_supabase_service()
            # Store transcript content in the proper transcript_content column
            # Map method names to database constraint values
            method_mapping = {
                "youtube_transcript_api": "unofficial",
                "unofficial": "unofficial",
                "groq": "groq", 
                "openai": "openai"
            }
            db_method = method_mapping.get(method, "unofficial")
            
            update_data = {
                "status": TaskStatus.COMPLETED.value,
                "transcript_content": transcript_text,
                "transcript_method": db_method,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            supabase.table("video_tasks").update(update_data).eq("id", task_id).execute()
            
        except Exception as e:
            logger.error(f"Failed to store task result: {e}")

    async def _store_task_error(
        self,
        task_id: str,
        error_message: str
    ) -> None:
        """Store task error in database."""
        try:
            supabase = get_supabase_service()
            update_data = {
                "status": TaskStatus.FAILED.value,
                "error_message": error_message,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            supabase.table("video_tasks").update(update_data).eq("id", task_id).execute()
            
        except Exception as e:
            logger.error(f"Failed to store task error: {e}")

    async def _retry_failed_tasks(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> None:
        """Retry failed tasks up to configured retry limit."""
        try:
            supabase = get_supabase_service()
            
            # Get failed tasks that haven't exceeded retry limit
            failed_tasks_result = supabase.table("video_tasks").select("*").eq("job_id", job_id).eq("status", TaskStatus.FAILED.value).lt("retry_count", self.config.retry_attempts).execute()
            
            if not failed_tasks_result.data:
                return
            
            failed_tasks = failed_tasks_result.data
            
            if progress_callback:
                progress_callback("retry", 0.0, f"Retrying {len(failed_tasks)} failed tasks...")
            
            for task in failed_tasks:
                try:
                    # Increment retry count
                    new_retry_count = task["retry_count"] + 1
                    supabase.table("video_tasks").update({
                        "retry_count": new_retry_count,
                        "status": TaskStatus.RETRY_PENDING.value,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }).eq("id", task["id"]).execute()
                    
                    # Wait before retry
                    await asyncio.sleep(self.config.retry_delay_seconds)
                    
                    # Get job details for retry
                    job_result = supabase.table("bulk_jobs").select("*").eq("id", job_id).execute()
                    if job_result.data:
                        job = job_result.data[0]
                        transcript_method = TranscriptMethod(job["transcript_method"])
                        output_format = job["output_format"]
                        
                        # Retry the task
                        success = await self._process_individual_video(
                            task, transcript_method, output_format, progress_callback
                        )
                        
                        if not success:
                            # Mark as permanently failed
                            supabase.table("video_tasks").update({
                                "status": TaskStatus.FAILED.value,
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            }).eq("id", task["id"]).execute()
                
                except Exception as e:
                    logger.error(f"Error retrying task {task['id']}: {e}")
                    
        except Exception as e:
            logger.error(f"Error during retry process: {e}")

    async def _generate_job_zip(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> Optional[str]:
        """Generate ZIP file containing all completed transcripts."""
        try:
            supabase = get_supabase_service()
            
            # Get completed tasks
            completed_tasks_result = supabase.table("video_tasks").select("*").eq("job_id", job_id).eq("status", TaskStatus.COMPLETED.value).execute()
            
            if not completed_tasks_result.data:
                logger.warning(f"No completed tasks found for job {job_id}")
                return None
            
            completed_tasks = completed_tasks_result.data
            
            if progress_callback:
                progress_callback("zip_generation", 0.0, f"Creating ZIP file with {len(completed_tasks)} transcripts...")
            
            # Create ZIP file
            zip_filename = f"bulk_job_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_path = os.path.join(self.settings.temp_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=self.config.zip_compression_level) as zipf:
                for i, task in enumerate(completed_tasks):
                    try:
                        # Create filename
                        safe_title = self.youtube_service.sanitize_filename(task["title"])
                        
                        # Get job details for output format
                        job_result = supabase.table("bulk_jobs").select("output_format").eq("id", job_id).execute()
                        output_format = job_result.data[0]["output_format"] if job_result.data else "txt"
                        
                        filename = f"{safe_title}_{task['video_id']}.{output_format}"
                        
                        # Add transcript to ZIP (read from transcript_content column)
                        transcript_text = task.get("transcript_content")
                        if transcript_text:
                            zipf.writestr(filename, transcript_text)
                        
                        # Update progress
                        if progress_callback:
                            progress = (i + 1) / len(completed_tasks)
                            progress_callback("zip_generation", progress, f"Added {i+1}/{len(completed_tasks)} files to ZIP")
                    
                    except Exception as e:
                        logger.warning(f"Failed to add task {task['id']} to ZIP: {e}")
            
            # Store ZIP file path in job
            supabase.table("bulk_jobs").update({
                "zip_file_path": zip_path,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", job_id).execute()
            
            if progress_callback:
                progress_callback("zip_generation", 1.0, f"ZIP file created: {zip_filename}")
            
            logger.info(f"Created ZIP file for job {job_id}: {zip_path}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Failed to generate ZIP file for job {job_id}: {e}")
            return None

    async def _complete_job(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
        zip_path: Optional[str] = None
    ) -> None:
        """Mark job as completed and perform cleanup."""
        try:
            supabase = get_supabase_service()
            
            # Get final task counts
            tasks_result = supabase.table("video_tasks").select("status").eq("job_id", job_id).execute()
            
            completed_count = sum(1 for task in tasks_result.data if task["status"] == TaskStatus.COMPLETED.value)
            failed_count = sum(1 for task in tasks_result.data if task["status"] == TaskStatus.FAILED.value)
            
            # Update job status
            update_data = {
                "status": JobStatus.COMPLETED.value,
                "completed_videos": completed_count,
                "failed_videos": failed_count,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if zip_path:
                update_data["zip_file_path"] = zip_path
            
            supabase.table("bulk_jobs").update(update_data).eq("id", job_id).execute()
            
            if progress_callback:
                progress_callback("complete", 1.0, f"Job completed: {completed_count} successful, {failed_count} failed")
            
            # Schedule cleanup of temporary files
            asyncio.create_task(self._cleanup_job_temp_files(job_id))
            
            logger.info(f"Job {job_id} completed: {completed_count} successful, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Failed to complete job {job_id}: {e}")

    async def _send_webhook_notification(
        self,
        job: Dict[str, Any],
        completed_count: int,
        failed_count: int,
        zip_path: Optional[str] = None
    ) -> None:
        """Send webhook notification when job completes."""
        if not job.get("webhook_url"):
            return
        
        try:
            webhook_data = {
                "job_id": job["id"],
                "user_id": job["user_id"],
                "status": "completed",
                "total_videos": job["total_videos"],
                "completed_videos": completed_count,
                "failed_videos": failed_count,
                "success_rate": (completed_count / job["total_videos"]) * 100 if job["total_videos"] > 0 else 0,
                "zip_available": zip_path is not None,
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    job["webhook_url"],
                    json=webhook_data,
                    timeout=aiohttp.ClientTimeout(total=self.config.webhook_timeout_seconds)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Webhook notification sent successfully for job {job['id']}")
                    else:
                        logger.warning(f"Webhook notification failed with status {response.status} for job {job['id']}")
                        
        except Exception as e:
            logger.error(f"Failed to send webhook notification for job {job['id']}: {e}")

    async def _cleanup_job_temp_files(self, job_id: str) -> None:
        """Clean up temporary files associated with a job."""
        try:
            # Wait for the configured delay before cleanup
            await asyncio.sleep(self.config.temp_cleanup_delay_seconds)
            
            # Clean up any remaining temporary files
            temp_patterns = [
                f"*{job_id}*",
                "*_optimized.*",
                "*_chunk*.flac"
            ]
            
            for pattern in temp_patterns:
                for file_path in Path(self.settings.temp_dir).glob(pattern):
                    try:
                        if file_path.is_file():
                            file_path.unlink()
                            logger.debug(f"Cleaned up temp file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
                        
        except Exception as e:
            logger.error(f"Error during temp file cleanup for job {job_id}: {e}")

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status and progress of a bulk job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dict containing job status and metrics, or None if not found
        """
        try:
            supabase = get_supabase_service()
            
            # Get job details
            job_result = supabase.table("bulk_jobs").select("*").eq("id", job_id).execute()
            
            if not job_result.data:
                return None
            
            job = job_result.data[0]
            
            # Get task statistics
            tasks_result = supabase.table("video_tasks").select("status").eq("job_id", job_id).execute()
            
            task_counts = {
                TaskStatus.PENDING.value: 0,
                TaskStatus.PROCESSING.value: 0,
                TaskStatus.COMPLETED.value: 0,
                TaskStatus.FAILED.value: 0,
                TaskStatus.RETRY_PENDING.value: 0,
                TaskStatus.SKIPPED.value: 0
            }
            
            for task in tasks_result.data:
                status = task["status"]
                task_counts[status] = task_counts.get(status, 0) + 1
            
            # Calculate metrics
            total_videos = job["total_videos"]
            completed_videos = task_counts[TaskStatus.COMPLETED.value]
            failed_videos = task_counts[TaskStatus.FAILED.value]
            progress_percent = (completed_videos / total_videos * 100) if total_videos > 0 else 0
            
            return {
                "job_id": job_id,
                "status": job["status"],
                "total_videos": total_videos,
                "completed_videos": completed_videos,
                "failed_videos": failed_videos,
                "pending_videos": task_counts[TaskStatus.PENDING.value],
                "processing_videos": task_counts[TaskStatus.PROCESSING.value],
                "retry_videos": task_counts[TaskStatus.RETRY_PENDING.value],
                "progress_percent": round(progress_percent, 2),
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
                "completed_at": job.get("completed_at"),
                "zip_file_path": job.get("zip_file_path"),
                "webhook_url": job.get("webhook_url"),
                "user_tier": job.get("user_tier", "free"),
                "transcript_method": job.get("transcript_method", "unofficial"),
                "output_format": job.get("output_format", "txt"),
                "source_url": job.get("source_url", ""),
                "user_id": job.get("user_id"),
                "metadata": job.get("metadata", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            return None

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running bulk job.
        
        Args:
            job_id: Job identifier to cancel
            
        Returns:
            True if job was cancelled successfully
        """
        try:
            supabase = get_supabase_service()
            
            # Check if job exists and is cancellable
            job_result = supabase.table("bulk_jobs").select("status").eq("id", job_id).execute()
            
            if not job_result.data:
                return False
            
            job_status = job_result.data[0]["status"]
            
            if job_status not in [JobStatus.PENDING.value, JobStatus.PROCESSING.value]:
                return False
            
            # Update job status
            supabase.table("bulk_jobs").update({
                "status": JobStatus.CANCELLED.value,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", job_id).execute()
            
            # Cancel any pending tasks (use 'failed' since 'skipped' isn't in constraint)
            supabase.table("video_tasks").update({
                "status": TaskStatus.FAILED.value,
                "error_message": "Job cancelled by user",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("job_id", job_id).eq("status", TaskStatus.PENDING.value).execute()
            
            # Remove from active jobs
            self.active_jobs.discard(job_id)
            
            logger.info(f"Job {job_id} cancelled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    async def list_user_jobs(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List bulk jobs for a specific user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            
        Returns:
            List of job dictionaries
        """
        try:
            supabase = get_supabase_service()
            
            jobs_result = supabase.table("bulk_jobs").select("*").eq("user_id", user_id).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            
            jobs = []
            for job in jobs_result.data:
                # Get task counts for each job
                tasks_result = supabase.table("video_tasks").select("status").eq("job_id", job["id"]).execute()
                
                completed_count = sum(1 for task in tasks_result.data if task["status"] == TaskStatus.COMPLETED.value)
                failed_count = sum(1 for task in tasks_result.data if task["status"] == TaskStatus.FAILED.value)
                
                jobs.append({
                    "job_id": job["id"],
                    "status": job["status"],
                    "total_videos": job["total_videos"],
                    "completed_videos": completed_count,
                    "failed_videos": failed_count,
                    "source_url": job["source_url"],
                    "transcript_method": job["transcript_method"],
                    "output_format": job["output_format"],
                    "created_at": job["created_at"],
                    "completed_at": job.get("completed_at"),
                    "zip_available": bool(job.get("zip_file_path"))
                })
            
            return jobs
            
        except Exception as e:
            logger.error(f"Failed to list jobs for user {user_id}: {e}")
            return []

    async def get_job_metrics(self, job_id: str) -> Optional[BulkJobMetrics]:
        """
        Get detailed metrics for a bulk job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            BulkJobMetrics object or None if job not found
        """
        try:
            job_status = await self.get_job_status(job_id)
            
            if not job_status:
                return None
            
            total_videos = job_status["total_videos"]
            completed_videos = job_status["completed_videos"]
            failed_videos = job_status["failed_videos"]
            
            # Calculate processing time
            created_at = datetime.fromisoformat(job_status["created_at"].replace('Z', '+00:00'))
            
            if job_status["status"] == JobStatus.COMPLETED.value and job_status.get("completed_at"):
                completed_at = datetime.fromisoformat(job_status["completed_at"].replace('Z', '+00:00'))
                processing_time = (completed_at - created_at).total_seconds()
            else:
                processing_time = (datetime.now(timezone.utc) - created_at).total_seconds()
            
            # Calculate success rate
            success_rate = (completed_videos / total_videos * 100) if total_videos > 0 else 0
            
            # Estimate remaining time
            if job_status["status"] == JobStatus.PROCESSING.value and completed_videos > 0:
                avg_time_per_video = processing_time / completed_videos
                remaining_videos = total_videos - completed_videos - failed_videos
                estimated_remaining = avg_time_per_video * remaining_videos
            else:
                estimated_remaining = 0.0
            
            return BulkJobMetrics(
                total_videos=total_videos,
                completed_videos=completed_videos,
                failed_videos=failed_videos,
                skipped_videos=0,  # Would need to query database for this
                retry_videos=job_status["retry_videos"],
                processing_time_seconds=processing_time,
                estimated_remaining_seconds=estimated_remaining,
                success_rate=round(success_rate, 2)
            )
            
        except Exception as e:
            logger.error(f"Failed to get job metrics for {job_id}: {e}")
            return None

    async def get_completed_tasks(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all completed video tasks for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            List of completed task dictionaries
        """
        try:
            supabase = get_supabase_service()
            
            # Get completed tasks with transcript data
            # Note: Using video_tasks table as per schema
            tasks_result = supabase.table("video_tasks").select("*").eq("job_id", job_id).eq("status", TaskStatus.COMPLETED.value).execute()
            
            if not tasks_result.data:
                logger.warning(f"No completed tasks found for job {job_id}")
                return []
            
            return tasks_result.data
            
        except Exception as e:
            logger.error(f"Failed to get completed tasks for job {job_id}: {e}")
            return []

    async def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """
        Clean up old completed jobs and their associated files.
        
        Args:
            days_old: Age threshold in days for cleanup
            
        Returns:
            Number of jobs cleaned up
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            cutoff_iso = cutoff_date.isoformat()
            
            supabase = get_supabase_service()
            
            # Get old completed jobs
            old_jobs_result = supabase.table("bulk_jobs").select("id, zip_file_path").eq("status", JobStatus.COMPLETED.value).lt("completed_at", cutoff_iso).execute()
            
            cleaned_count = 0
            
            for job in old_jobs_result.data:
                try:
                    job_id = job["id"]
                    
                    # Delete ZIP file if it exists
                    if job.get("zip_file_path") and os.path.exists(job["zip_file_path"]):
                        os.remove(job["zip_file_path"])
                        logger.info(f"Deleted ZIP file for job {job_id}")
                    
                    # Delete tasks
                    supabase.table("video_tasks").delete().eq("job_id", job_id).execute()
                    
                    # Delete job
                    supabase.table("bulk_jobs").delete().eq("id", job_id).execute()
                    
                    cleaned_count += 1
                    logger.info(f"Cleaned up old job {job_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to cleanup job {job['id']}: {e}")
            
            logger.info(f"Cleaned up {cleaned_count} old jobs")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0


# Create a default instance for easy importing
bulk_job_service = BulkJobService()

# Export main classes and functions
__all__ = [
    "BulkJobService",
    "BulkJobError",
    "JobStatus", 
    "TaskStatus",
    "TranscriptMethod",
    "UserTier",
    "BulkJobConfig",
    "BulkJobMetrics",
    "bulk_job_service"
]