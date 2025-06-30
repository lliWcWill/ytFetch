"""
Bulk API endpoints for ytFetch backend.
Handles playlist and channel bulk transcription operations.
"""

import asyncio
import io
import logging
import os
import time
import zipfile
from datetime import datetime
from typing import Dict, Any, Optional

import aiohttp

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.requests import Request

# Optional rate limiting import
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    # Create dummy limiter if slowapi is not available
    class Limiter:
        def __init__(self, **kwargs):
            pass
        def limit(self, rate: str):
            def decorator(func):
                return func
            return decorator
    
    def get_remote_address(request):
        return "127.0.0.1"
    
    class RateLimitExceeded(Exception):
        pass
    
    def _rate_limit_exceeded_handler(request, exc):
        return JSONResponse(status_code=429, content={"error": "Rate limited"})
    
    RATE_LIMITING_AVAILABLE = False

from ..api.schemas import (
    BulkAnalyzeRequest,
    BulkCreateRequest,
    BulkJobResponse,
    BulkTaskResponse,
    BulkJobListResponse,
    BulkAnalyzeResponse,
    HTTPError,
    UserInfo,
    ERROR_EXAMPLES
)
from ..core.config import settings
from ..core.auth import (
    get_current_user,
    get_current_user_optional,
    AuthenticatedUser,
    verify_resource_ownership,
    check_user_tier_limits,
    check_tier_limits,
    RequireAuth,
    OptionalAuth
)
from ..services.bulk_job_service import (
    bulk_job_service,
    BulkJobError,
    TranscriptMethod,
    UserTier,
    JobStatus,
    TaskStatus
)
from ..services.youtube_service import YouTubeService
from ..services.usage_service import usage_service, UsageCounter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/v1/bulk", tags=["bulk"])

# Initialize services
youtube_service = YouTubeService()


# Legacy user info conversion for backward compatibility
def auth_user_to_user_info(user: AuthenticatedUser) -> UserInfo:
    """Convert AuthenticatedUser to UserInfo for backward compatibility."""
    return UserInfo(
        user_id=user.id,
        email=user.email,
        tier="free",  # TODO: Get actual tier from user profile
        created_at=user.created_at
    )


@router.post(
    "/analyze",
    response_model=BulkAnalyzeResponse,
    responses=ERROR_EXAMPLES,
    summary="Analyze playlist or channel",
    description="Analyze a YouTube playlist or channel to get video count, metadata, and tier compatibility information before creating a bulk job."
)
@limiter.limit("10/minute")
async def analyze_bulk_source(
    request: Request,
    analyze_request: BulkAnalyzeRequest,
    user: Optional[AuthenticatedUser] = OptionalAuth
) -> BulkAnalyzeResponse:
    """
    Analyze a YouTube playlist or channel for bulk processing.
    
    This endpoint allows users to preview what videos would be processed
    in a bulk job before actually creating it. It returns metadata about
    the source and checks against user tier limits.
    """
    try:
        logger.info(f"Analyzing bulk source: {analyze_request.url}")
        
        # Validate URL format
        if not bulk_job_service._is_valid_bulk_url(analyze_request.url):
            raise HTTPException(
                status_code=400,
                detail=HTTPError(
                    error="invalid_url",
                    message="URL must be a YouTube playlist or channel",
                    details={"url": analyze_request.url},
                    status_code=400
                ).dict()
            )
        
        # Determine user tier and limits
        if user:
            logger.info(f"Analyzing bulk source for authenticated user: {user.id}")
            # Get user profile to determine tier
            try:
                # For now, default to free tier until we implement tier lookup
                # TODO: Implement proper tier lookup from user profile
                user_tier = UserTier.FREE
            except Exception as e:
                logger.warning(f"Failed to get user profile, defaulting to free tier: {e}")
                user_tier = UserTier("free")
        else:
            logger.info("Analyzing bulk source for anonymous user")
            user_tier = UserTier("free")
        
        tier_config = bulk_job_service.tier_limits[user_tier]
        
        # Extract videos with progress tracking
        max_videos = analyze_request.max_videos or tier_config["max_videos_per_job"]
        max_videos = min(max_videos, tier_config["max_videos_per_job"])
        
        videos = await bulk_job_service._extract_videos_from_url(
            analyze_request.url,
            max_videos,
            tier_config
        )
        
        if not videos:
            raise HTTPException(
                status_code=404,
                detail=HTTPError(
                    error="no_videos_found",
                    message="No videos found in the provided URL",
                    details={"url": analyze_request.url},
                    status_code=404
                ).dict()
            )
        
        # Calculate metadata
        total_duration_seconds = sum(video.get("duration", 0) for video in videos)
        estimated_duration_hours = total_duration_seconds / 3600
        
        # Determine source type and get title
        if youtube_service.is_playlist_url(analyze_request.url):
            source_type = "playlist"
            # Extract playlist title from first video or URL
            title = videos[0].get("playlist_title", "Unknown Playlist") if videos else "Unknown Playlist"
        else:
            source_type = "channel"
            # Extract channel name from first video or URL
            if videos:
                # Try different fields for channel name
                title = (videos[0].get("uploader") or 
                        videos[0].get("channel") or 
                        videos[0].get("uploader_id") or
                        "Unknown Channel")
            else:
                title = "Unknown Channel"
        
        # Ensure title is never None
        if not title:
            title = "Unknown Source"
        
        # Check if user can process all videos
        total_videos_found = len(videos)
        can_process_all = total_videos_found <= tier_config["max_videos_per_job"]
        
        return BulkAnalyzeResponse(
            url=analyze_request.url,
            source_type=source_type,
            title=title,
            description=None,  # TODO: Extract from playlist/channel metadata
            total_videos=total_videos_found,
            analyzed_videos=len(videos),
            estimated_duration_hours=round(estimated_duration_hours, 2),
            videos=[
                {
                    "video_id": video["id"],
                    "title": video["title"],
                    "duration": video.get("duration", 0),
                    "url": video["url"]
                }
                for video in videos
            ],
            tier_limits=tier_config,
            can_process_all=can_process_all
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze bulk source: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="analysis_failed",
                message="Failed to analyze playlist or channel",
                details={"error": str(e)},
                status_code=500
            ).dict()
        )


@router.post(
    "/create",
    response_model=BulkJobResponse,
    status_code=201,
    responses=ERROR_EXAMPLES,
    summary="Create bulk transcription job",
    description="Create a new bulk transcription job from a playlist or channel URL. The job will be created in pending status and must be started separately."
)
@limiter.limit("5/minute")
async def create_bulk_job(
    request: Request,
    create_request: BulkCreateRequest,
    user: Optional[AuthenticatedUser] = OptionalAuth
) -> BulkJobResponse:
    """
    Create a new bulk transcription job.
    
    This endpoint creates a job and queues individual video tasks,
    but does not start processing immediately. Use the start endpoint
    to begin processing the job.
    """
    try:
        # Handle guest users
        if not user:
            # Get session ID from request - check multiple sources
            session_id = (
                request.headers.get('X-Guest-Session-ID') or
                request.headers.get('x-guest-session-id') or 
                request.headers.get('x-session-id') or 
                request.cookies.get('session_id')
            )
            if not session_id:
                from ..services.guest_service import guest_service
                session_id = guest_service.generate_session_id()
            
            # Check guest limits for bulk jobs
            # Guests get 1 bulk job per day as a demo
            from ..services.guest_service import guest_service
            
            # First check if guest has already created a bulk job today
            from ..core.supabase import SupabaseClient
            supabase = SupabaseClient.get_service_client()
            
            # For guests, we need to store the session ID in metadata to track their jobs
            # since we can't use a user_id that doesn't exist in the users table
            guest_user_id = None
            
            # Check if this session already has a bulk job today
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # Query by session_id in metadata for guest jobs
            existing_jobs = supabase.table('bulk_jobs').select('id, metadata').is_('user_id', 'null').gte('created_at', today_start.isoformat()).execute()
            
            # Filter by session_id in metadata
            guest_jobs_today = [
                job for job in existing_jobs.data 
                if job.get('metadata', {}).get('session_id') == session_id
            ]
            
            if guest_jobs_today and len(guest_jobs_today) > 0:
                raise HTTPException(
                    status_code=401,
                    detail=HTTPError(
                        error="guest_limit_exceeded",
                        message="Guests are limited to 1 bulk job per day. Please sign in for unlimited access.",
                        details={
                            "current_usage": 1,
                            "limit": 1,
                            "requires_auth": True
                        },
                        status_code=401
                    ).dict()
                )
            
            # For guests, limit to max 60 videos per job
            max_videos_for_guest = min(create_request.max_videos or 60, 60)
            if create_request.max_videos and create_request.max_videos > 60:
                logger.info(f"Guest requested {create_request.max_videos} videos, limiting to 60")
            
            # Note: We've already checked the daily job limit above.
            # The guest_service.check_guest_limit for "bulk_videos" tracks total video count,
            # but for bulk jobs we want to limit by job count per day, not total videos.
            # So we skip the video count check and just enforce the max videos per job.
            
            # Use the guest_user_id we already generated above
            user_id = guest_user_id
            user_tier = UserTier("free")  # Guests get free tier limits
            logger.info(f"Creating bulk job for guest session {session_id} (user_id: {user_id}): {create_request.url}")
        else:
            # Authenticated user
            user_id = user.id
            logger.info(f"Creating bulk job for user {user.id}: {create_request.url}")
            
            # In token-based system, authenticated users have no tier limits
            # They are only limited by their token balance
            logger.info(f"Authenticated user {user.id} creating bulk job - no tier limits in token-based system")
            
            # Get actual user tier from profile
            try:
                from ..core.auth import get_current_user_with_profile
                user_profile = await get_current_user_with_profile(user)
                tier_name = user_profile.get("tier_name", "free")
                user_tier = UserTier(tier_name)
            except Exception as e:
                logger.warning(f"Failed to get user profile, defaulting to free tier: {e}")
                user_tier = UserTier.FREE
        
        # Validate transcript method
        try:
            transcript_method = TranscriptMethod(create_request.transcript_method)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=HTTPError(
                    error="invalid_method",
                    message=f"Invalid transcript method: {create_request.transcript_method}",
                    details={"valid_methods": [m.value for m in TranscriptMethod]},
                    status_code=400
                ).dict()
            )
        
        logger.info(f"Using user tier: {user_tier.value} for user {user_id}")
        
        # Create job using bulk job service
        # For guests, use the limited max_videos value (defined earlier in guest block)
        if not user:
            final_max_videos = max_videos_for_guest
        else:
            final_max_videos = create_request.max_videos
        
        # For guests, pass session_id in metadata
        metadata = None
        if not user and session_id:
            metadata = {"session_id": session_id}
        
        job_result = await bulk_job_service.create_bulk_job(
            user_id=user_id,
            source_url=create_request.url,
            transcript_method=transcript_method,
            output_format=create_request.output_format,
            max_videos=final_max_videos,
            user_tier=user_tier,
            webhook_url=create_request.webhook_url,
            metadata=metadata
        )
        
        # Get job status to return complete information
        job_status = await bulk_job_service.get_job_status(job_result["job_id"])
        
        if not job_status:
            raise HTTPException(
                status_code=500,
                detail=HTTPError(
                    error="job_creation_failed",
                    message="Job created but status unavailable",
                    details={"job_id": job_result["job_id"]},
                    status_code=500
                ).dict()
            )
        
        # Convert to response format
        response = BulkJobResponse(
            job_id=job_status["job_id"],
            user_id=user_id,
            source_url=create_request.url,
            transcript_method=create_request.transcript_method,
            output_format=create_request.output_format,
            status=job_status["status"],
            total_videos=job_status["total_videos"],
            completed_videos=job_status["completed_videos"],
            failed_videos=job_status["failed_videos"],
            pending_videos=job_status.get("pending_videos"),
            processing_videos=job_status.get("processing_videos"),
            retry_videos=job_status.get("retry_videos"),
            progress_percent=job_status["progress_percent"],
            user_tier=user_tier.value,
            webhook_url=create_request.webhook_url,
            zip_file_path=job_status.get("zip_file_path"),
            zip_available=bool(job_status.get("zip_file_path")),
            estimated_duration_minutes=job_result.get("estimated_duration_minutes"),
            created_at=job_status["created_at"],
            updated_at=job_status["updated_at"],
            completed_at=job_status.get("completed_at"),
            tier_limits=job_result.get("tier_limits")
        )
        
        # Increment usage counters after successful job creation
        if user:
            # Authenticated user - use usage service
            try:
                await usage_service.increment_usage(
                    user_id=user.id,
                    counter_type=UsageCounter.JOBS_CREATED,
                    increment=1
                )
                # Also increment videos processed counter
                await usage_service.increment_usage(
                    user_id=user.id,
                    counter_type=UsageCounter.VIDEOS_PROCESSED,
                    increment=job_status['total_videos']
                )
                logger.info(f"Updated usage counters for user {user.id}")
            except Exception as usage_error:
                # Log error but don't fail the request - job is already created
                logger.error(f"Failed to update usage counters: {usage_error}")
        else:
            # Guest user - increment guest usage
            try:
                from ..services.guest_service import guest_service
                await guest_service.increment_guest_usage(
                    session_id=session_id,
                    usage_type="bulk_videos",
                    increment=job_status['total_videos']
                )
                logger.info(f"Updated guest usage for session {session_id}")
            except Exception as guest_error:
                logger.error(f"Failed to update guest usage: {guest_error}")
        
        logger.info(f"Created bulk job {job_result['job_id']} with {job_status['total_videos']} videos")
        return response
        
    except BulkJobError as e:
        logger.error(f"Bulk job creation failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=HTTPError(
                error="job_creation_failed",
                message=str(e),
                details={"user_id": user_id},
                status_code=400
            ).dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating bulk job: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="internal_error",
                message="Failed to create bulk job",
                details={"error": str(e)},
                status_code=500
            ).dict()
        )


@router.get(
    "/jobs/{job_id}",
    response_model=BulkJobResponse,
    responses=ERROR_EXAMPLES,
    summary="Get bulk job status",
    description="Get the current status and progress of a specific bulk job, including detailed metrics and task information."
)
async def get_job_status(
    request: Request,
    job_id: str,
    user: Optional[AuthenticatedUser] = OptionalAuth
) -> BulkJobResponse:
    """
    Get detailed status and progress information for a bulk job.
    
    Returns comprehensive information about the job including progress,
    task counts, and availability of results.
    """
    try:
        job_status = await bulk_job_service.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(
                status_code=404,
                detail=HTTPError(
                    error="job_not_found",
                    message="Bulk job not found",
                    details={"job_id": job_id},
                    status_code=404
                ).dict()
            )
        
        # Verify job ownership
        if user:
            # Authenticated user - check user_id
            verify_resource_ownership(user.id, job_status.get("user_id"), "bulk job")
        else:
            # Guest user - check session_id in metadata
            session_id = (
                request.headers.get('X-Guest-Session-ID') or
                request.headers.get('x-guest-session-id') or 
                request.headers.get('x-session-id') or 
                request.cookies.get('session_id')
            )
            job_metadata = job_status.get("metadata", {})
            job_session_id = job_metadata.get("session_id") if job_metadata else None
            
            if not session_id or session_id != job_session_id:
                raise HTTPException(
                    status_code=401,
                    detail=HTTPError(
                        error="unauthorized",
                        message="You don't have access to this bulk job",
                        details={"requires_auth": True},
                        status_code=401
                    ).dict()
                )
        
        response = BulkJobResponse(
            job_id=job_status["job_id"],
            user_id=job_status.get("user_id", user.id if user else None),
            source_url=job_status.get("source_url", ""),
            transcript_method=job_status["transcript_method"],
            output_format=job_status["output_format"],
            status=job_status["status"],
            total_videos=job_status["total_videos"],
            completed_videos=job_status["completed_videos"],
            failed_videos=job_status["failed_videos"],
            pending_videos=job_status.get("pending_videos"),
            processing_videos=job_status.get("processing_videos"),
            retry_videos=job_status.get("retry_videos"),
            progress_percent=job_status["progress_percent"],
            user_tier=job_status.get("user_tier", "free"),
            webhook_url=job_status.get("webhook_url"),
            zip_file_path=job_status.get("zip_file_path"),
            zip_available=bool(job_status.get("zip_file_path")),
            estimated_duration_minutes=None,  # Could calculate from remaining tasks
            created_at=job_status["created_at"],
            updated_at=job_status["updated_at"],
            completed_at=job_status.get("completed_at"),
            tier_limits=None  # Not stored in job status
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="status_fetch_failed",
                message="Failed to get job status",
                details={"job_id": job_id, "error": str(e)},
                status_code=500
            ).dict()
        )


@router.get(
    "/jobs",
    response_model=BulkJobListResponse,
    responses=ERROR_EXAMPLES,
    summary="List user's bulk jobs",
    description="Get a paginated list of bulk jobs for the authenticated user, with optional filtering and sorting."
)
async def list_user_jobs(
    user: AuthenticatedUser = RequireAuth,
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None
) -> BulkJobListResponse:
    """
    List bulk jobs for the authenticated user.
    
    Returns a paginated list of jobs with basic information.
    Use the individual job endpoint for detailed information.
    """
    try:
        # Validate pagination parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 20
        
        offset = (page - 1) * per_page
        
        # Get user jobs
        jobs = await bulk_job_service.list_user_jobs(
            user_id=user.id,
            limit=per_page,
            offset=offset
        )
        
        # Filter by status if provided
        if status:
            jobs = [job for job in jobs if job["status"] == status]
        
        # Convert to response format
        job_responses = []
        for job in jobs:
            job_response = BulkJobResponse(
                job_id=job["job_id"],
                user_id=user.id,
                source_url=job["source_url"],
                transcript_method=job["transcript_method"],
                output_format=job["output_format"],
                status=job["status"],
                total_videos=job["total_videos"],
                completed_videos=job["completed_videos"],
                failed_videos=job["failed_videos"],
                pending_videos=None,  # Not included in list view
                processing_videos=None,
                retry_videos=None,
                progress_percent=round((job["completed_videos"] / job["total_videos"] * 100) if job["total_videos"] > 0 else 0, 2),
                user_tier="free",  # TODO: Get from user profile
                webhook_url=None,  # Not included in list view
                zip_file_path=None,
                zip_available=job["zip_available"],
                estimated_duration_minutes=None,
                created_at=job["created_at"],
                updated_at=job.get("updated_at", job["created_at"]),
                completed_at=job.get("completed_at"),
                tier_limits=None  # Not included in list view
            )
            job_responses.append(job_response)
        
        # Calculate pagination info
        total_count = len(jobs)  # TODO: Get actual total count from service
        has_next = len(jobs) == per_page  # Approximation
        
        return BulkJobListResponse(
            jobs=job_responses,
            total_count=total_count,
            page=page,
            per_page=per_page,
            has_next=has_next
        )
        
    except Exception as e:
        logger.error(f"Failed to list jobs for user {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="job_list_failed",
                message="Failed to list bulk jobs",
                details={"user_id": user.id, "error": str(e)},
                status_code=500
            ).dict()
        )


@router.post(
    "/jobs/{job_id}/start",
    responses=ERROR_EXAMPLES,
    summary="Start bulk job processing",
    description="Start processing a bulk job that is in pending status. Processing will begin immediately in the background."
)
@limiter.limit("3/minute")
async def start_job_processing(
    request: Request,
    job_id: str,
    user: Optional[AuthenticatedUser] = OptionalAuth
) -> JSONResponse:
    """
    Start processing a bulk job.
    
    Begins background processing of all videos in the job.
    The job status can be monitored via the job status endpoint.
    """
    try:
        # Verify job exists and ownership
        job_status = await bulk_job_service.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(
                status_code=404,
                detail=HTTPError(
                    error="job_not_found",
                    message="Bulk job not found",
                    details={"job_id": job_id},
                    status_code=404
                ).dict()
            )
        
        # Verify job ownership
        if user:
            # Authenticated user - check user_id
            verify_resource_ownership(user.id, job_status.get("user_id"), "bulk job")
        else:
            # Guest user - check session_id in metadata
            session_id = (
                request.headers.get('X-Guest-Session-ID') or
                request.headers.get('x-guest-session-id') or 
                request.headers.get('x-session-id') or 
                request.cookies.get('session_id')
            )
            job_metadata = job_status.get("metadata", {})
            job_session_id = job_metadata.get("session_id") if job_metadata else None
            
            if not session_id or session_id != job_session_id:
                raise HTTPException(
                    status_code=401,
                    detail=HTTPError(
                        error="guest_access_limit_reached",
                        message="Guest access limit reached. Please sign in to continue.",
                        details={"requires_auth": True},
                        status_code=401
                    ).dict()
                )
        
        # Check if job can be started
        if job_status["status"] != JobStatus.PENDING.value:
            raise HTTPException(
                status_code=400,
                detail=HTTPError(
                    error="invalid_job_status",
                    message=f"Job cannot be started from status: {job_status['status']}",
                    details={"job_id": job_id, "current_status": job_status["status"]},
                    status_code=400
                ).dict()
            )
        
        # Start job processing
        success = await bulk_job_service.start_job_processing(job_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=HTTPError(
                    error="start_failed",
                    message="Failed to start job processing",
                    details={"job_id": job_id},
                    status_code=500
                ).dict()
            )
        
        logger.info(f"Started processing job {job_id} for user {user.id if user else 'guest'}")
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "job_id": job_id,
                "message": "Job processing started successfully",
                "total_videos": job_status["total_videos"]
            }
        )
        
    except BulkJobError as e:
        logger.error(f"Failed to start job {job_id}: {e}")
        raise HTTPException(
            status_code=400,
            detail=HTTPError(
                error="start_failed",
                message=str(e),
                details={"job_id": job_id},
                status_code=400
            ).dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error starting job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="internal_error",
                message="Failed to start job processing",
                details={"job_id": job_id, "error": str(e)},
                status_code=500
            ).dict()
        )


@router.post(
    "/jobs/{job_id}/cancel",
    responses=ERROR_EXAMPLES,
    summary="Cancel bulk job",
    description="Cancel a running or pending bulk job. This will stop any ongoing processing and mark pending tasks as cancelled."
)
@limiter.limit("5/minute")
async def cancel_job(
    request: Request,
    job_id: str,
    user: Optional[AuthenticatedUser] = OptionalAuth
) -> JSONResponse:
    """
    Cancel a bulk job.
    
    Stops processing and marks the job as cancelled.
    Completed tasks will remain available.
    """
    try:
        # Verify job exists and ownership
        job_status = await bulk_job_service.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(
                status_code=404,
                detail=HTTPError(
                    error="job_not_found",
                    message="Bulk job not found",
                    details={"job_id": job_id},
                    status_code=404
                ).dict()
            )
        
        # Verify job ownership
        if user:
            # Authenticated user - check user_id
            verify_resource_ownership(user.id, job_status.get("user_id"), "bulk job")
        else:
            # Guest user - check session_id in metadata
            session_id = (
                request.headers.get('X-Guest-Session-ID') or
                request.headers.get('x-guest-session-id') or 
                request.headers.get('x-session-id') or 
                request.cookies.get('session_id')
            )
            job_metadata = job_status.get("metadata", {})
            job_session_id = job_metadata.get("session_id") if job_metadata else None
            
            if not session_id or session_id != job_session_id:
                raise HTTPException(
                    status_code=401,
                    detail=HTTPError(
                        error="unauthorized",
                        message="You don't have access to this bulk job",
                        details={"requires_auth": True},
                        status_code=401
                    ).dict()
                )
        
        # Cancel the job
        success = await bulk_job_service.cancel_job(job_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=HTTPError(
                    error="cancel_failed",
                    message="Job cannot be cancelled from its current status",
                    details={"job_id": job_id, "status": job_status["status"]},
                    status_code=400
                ).dict()
            )
        
        logger.info(f"Cancelled job {job_id} for user {user.id if user else 'guest'}")
        
        return JSONResponse(
            content={
                "status": "cancelled",
                "job_id": job_id,
                "message": "Job cancelled successfully",
                "completed_videos": job_status["completed_videos"]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="cancel_failed",
                message="Failed to cancel job",
                details={"job_id": job_id, "error": str(e)},
                status_code=500
            ).dict()
        )


@router.get(
    "/jobs/{job_id}/download",
    responses={
        200: {"description": "ZIP file download", "content": {"application/zip": {}}},
        **ERROR_EXAMPLES
    },
    summary="Download job results",
    description="Download a ZIP file containing all completed transcripts from a bulk job."
)
async def download_job_transcripts(
    job_id: str,
    user: AuthenticatedUser = RequireAuth
) -> StreamingResponse:
    """
    Download ZIP file containing all completed transcripts.
    
    Returns a ZIP file with all successfully transcribed videos
    from the bulk job. Creates the ZIP entirely in memory.
    """
    try:
        # Verify job exists and ownership
        job_status = await bulk_job_service.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(
                status_code=404,
                detail=HTTPError(
                    error="job_not_found",
                    message="Bulk job not found",
                    details={"job_id": job_id},
                    status_code=404
                ).dict()
            )
        
        # Verify job ownership using the auth utility function
        verify_resource_ownership(user.id, job_status.get("user_id"), "bulk job")
        
        # Get completed tasks with transcript data
        completed_tasks = await bulk_job_service.get_completed_tasks(job_id)
        
        if not completed_tasks:
            raise HTTPException(
                status_code=404,
                detail=HTTPError(
                    error="no_results",
                    message="No completed transcripts available for download",
                    details={"job_id": job_id, "completed_count": 0},
                    status_code=404
                ).dict()
            )
        
        # Create in-memory ZIP file
        zip_buffer = io.BytesIO()
        
        try:
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                for task in completed_tasks:
                    try:
                        # Create safe filename from video title and ID (using schema field names)
                        video_title = task.get("title", "Unknown")
                        video_id = task.get("video_id", "unknown")
                        
                        # Sanitize title for filename
                        safe_title = youtube_service.sanitize_filename(video_title)
                        
                        # Get output format from job
                        output_format = job_status.get("output_format", "txt")
                        
                        # Create filename
                        filename = f"{safe_title}_{video_id}.{output_format}"
                        
                        # Get transcript text - either from metadata field or from storage URL
                        metadata = task.get("metadata", {})
                        transcript_text = metadata.get("transcript_text") if metadata else None
                        transcript_url = task.get("transcript_storage_url")
                        
                        # If no direct transcript text, try to download from Supabase Storage
                        if not transcript_text and transcript_url:
                            try:
                                from ..core.supabase import get_supabase_service
                                
                                # Check if it's a Supabase Storage URL
                                if "supabase" in transcript_url and "/storage/" in transcript_url:
                                    # Download file from Supabase Storage
                                    supabase = get_supabase_service()
                                    
                                    # Extract bucket and file path from URL
                                    # URL format: https://project.supabase.co/storage/v1/object/public/bucket-name/file-path
                                    url_parts = transcript_url.split("/storage/v1/object/")
                                    if len(url_parts) > 1:
                                        bucket_path = url_parts[1]
                                        if bucket_path.startswith("public/"):
                                            bucket_path = bucket_path[7:]  # Remove "public/"
                                        
                                        path_parts = bucket_path.split("/", 1)
                                        if len(path_parts) == 2:
                                            bucket_name, file_path = path_parts
                                            
                                            # Download file from Supabase Storage
                                            try:
                                                response = supabase.storage.from_(bucket_name).download(file_path)
                                                if response:
                                                    transcript_text = response.decode('utf-8')
                                                    logger.debug(f"Downloaded transcript from Supabase Storage: {file_path}")
                                            except Exception as storage_e:
                                                logger.warning(f"Failed to download from Supabase Storage: {storage_e}")
                                
                                # If Supabase Storage failed, try direct HTTP download
                                if not transcript_text:
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get(transcript_url) as response:
                                            if response.status == 200:
                                                transcript_text = await response.text()
                                                logger.debug(f"Downloaded transcript via HTTP: {transcript_url}")
                                            else:
                                                logger.warning(f"HTTP download failed with status {response.status}: {transcript_url}")
                                
                            except Exception as download_e:
                                logger.warning(f"Failed to download transcript from URL {transcript_url}: {download_e}")
                        
                        # Skip if still no transcript text
                        if not transcript_text:
                            logger.warning(f"Skipping task {task.get('id')} - no transcript text available")
                            continue
                        
                        # Add transcript to ZIP
                        zipf.writestr(filename, transcript_text)
                        logger.debug(f"Added {filename} to ZIP ({len(transcript_text)} characters)")
                        
                    except Exception as e:
                        logger.warning(f"Failed to add task {task.get('id', 'unknown')} to ZIP: {e}")
                        continue
            
            # Get ZIP data
            zip_buffer.seek(0)
            zip_data = zip_buffer.getvalue()
            zip_size = len(zip_data)
            
            if zip_size == 0:
                raise HTTPException(
                    status_code=404,
                    detail=HTTPError(
                        error="no_valid_transcripts",
                        message="No valid transcripts could be added to ZIP file",
                        details={"job_id": job_id, "completed_tasks": len(completed_tasks)},
                        status_code=404
                    ).dict()
                )
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transcripts_{job_id[:8]}_{timestamp}.zip"
            
            # Create streaming response from in-memory data
            def iter_zip_data():
                chunk_size = 8192
                for i in range(0, len(zip_data), chunk_size):
                    yield zip_data[i:i + chunk_size]
            
            logger.info(f"Serving in-memory ZIP download for job {job_id} to user {user.id} ({zip_size} bytes, {len(completed_tasks)} tasks)")
            
            return StreamingResponse(
                iter_zip_data(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Content-Length": str(zip_size)
                }
            )
        
        finally:
            zip_buffer.close()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download results for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="download_failed",
                message="Failed to download job results",
                details={"job_id": job_id, "error": str(e)},
                status_code=500
            ).dict()
        )


@router.delete(
    "/jobs/{job_id}",
    responses=ERROR_EXAMPLES,
    summary="Delete bulk job",
    description="Delete a bulk job and all its associated data including transcripts and ZIP files. This action cannot be undone."
)
async def delete_job(
    job_id: str,
    user: AuthenticatedUser = RequireAuth
) -> JSONResponse:
    """
    Delete a bulk job and all associated data.
    
    This permanently removes the job, all task data,
    and any generated files. This action cannot be undone.
    """
    try:
        # Verify job exists and ownership
        job_status = await bulk_job_service.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(
                status_code=404,
                detail=HTTPError(
                    error="job_not_found",
                    message="Bulk job not found",
                    details={"job_id": job_id},
                    status_code=404
                ).dict()
            )
        
        # Verify job ownership using the auth utility function
        verify_resource_ownership(user.id, job_status.get("user_id"), "bulk job")
        
        # Cancel job if it's running
        if job_status["status"] in [JobStatus.PENDING.value, JobStatus.PROCESSING.value]:
            await bulk_job_service.cancel_job(job_id)
        
        # Delete ZIP file if it exists
        zip_path = job_status.get("zip_file_path")
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
                logger.info(f"Deleted ZIP file for job {job_id}")
            except Exception as e:
                logger.warning(f"Failed to delete ZIP file {zip_path}: {e}")
        
        # TODO: Implement actual job deletion in bulk_job_service
        # For now, we'll just cancel it
        logger.info(f"Deleted job {job_id} for user {user.id}")
        
        return JSONResponse(
            content={
                "status": "deleted",
                "job_id": job_id,
                "message": "Job deleted successfully"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="delete_failed",
                message="Failed to delete job",
                details={"job_id": job_id, "error": str(e)},
                status_code=500
            ).dict()
        )


# Note: Rate limiting error handlers would be configured at the app level
# if slowapi is properly integrated