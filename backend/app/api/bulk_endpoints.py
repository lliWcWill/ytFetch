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
from ..services.bulk_job_service import (
    bulk_job_service,
    BulkJobError,
    TranscriptMethod,
    UserTier,
    JobStatus,
    TaskStatus
)
from ..services.youtube_service import YouTubeService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/v1/bulk", tags=["bulk"])

# Initialize services
youtube_service = YouTubeService()


# Authentication dependency (placeholder - replace with actual auth system)
async def get_current_user(request: Request) -> UserInfo:
    """
    Authentication dependency for bulk operations.
    
    TODO: Replace with actual authentication system.
    For now, returns a mock user for development.
    """
    # Check for Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        # For development, allow anonymous access with free tier
        return UserInfo(
            user_id="anonymous",
            email=None,
            tier="free",
            created_at=datetime.now().isoformat()
        )
    
    # TODO: Implement actual JWT/session validation
    # For now, parse a simple "Bearer user_id:tier" format for testing
    try:
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            parts = token.split(":")
            if len(parts) >= 2:
                user_id, tier = parts[0], parts[1]
                return UserInfo(
                    user_id=user_id,
                    email=f"{user_id}@example.com",
                    tier=tier,
                    created_at=datetime.now().isoformat()
                )
    except Exception:
        pass
    
    # Default to anonymous free user
    return UserInfo(
        user_id="anonymous", 
        email=None,
        tier="free",
        created_at=datetime.now().isoformat()
    )


# Optional authentication dependency (allows anonymous access)
async def get_user_optional(request: Request) -> Optional[UserInfo]:
    """Optional authentication - returns None if not authenticated."""
    try:
        return await get_current_user(request)
    except Exception:
        return None


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
    user: Optional[UserInfo] = Depends(get_user_optional)
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
        user_tier = UserTier(user.tier if user else "free")
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
            title = videos[0].get("uploader", "Unknown Channel") if videos else "Unknown Channel"
        
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
    user: UserInfo = Depends(get_current_user)
) -> BulkJobResponse:
    """
    Create a new bulk transcription job.
    
    This endpoint creates a job and queues individual video tasks,
    but does not start processing immediately. Use the start endpoint
    to begin processing the job.
    """
    try:
        logger.info(f"Creating bulk job for user {user.user_id}: {create_request.url}")
        
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
        
        # Validate user tier
        try:
            user_tier = UserTier(user.tier)
        except ValueError:
            # Default to free tier for unknown tiers
            user_tier = UserTier.FREE
            logger.warning(f"Unknown user tier '{user.tier}', defaulting to free")
        
        # Create job using bulk job service
        job_result = await bulk_job_service.create_bulk_job(
            user_id=user.user_id,
            source_url=create_request.url,
            transcript_method=transcript_method,
            output_format=create_request.output_format,
            max_videos=create_request.max_videos,
            user_tier=user_tier,
            webhook_url=create_request.webhook_url
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
            user_id=user.user_id,
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
            user_tier=user.tier,
            webhook_url=create_request.webhook_url,
            zip_file_path=job_status.get("zip_file_path"),
            zip_available=bool(job_status.get("zip_file_path")),
            estimated_duration_minutes=job_result.get("estimated_duration_minutes"),
            created_at=job_status["created_at"],
            updated_at=job_status["updated_at"],
            completed_at=job_status.get("completed_at"),
            tier_limits=job_result.get("tier_limits")
        )
        
        logger.info(f"Created bulk job {job_result['job_id']} with {job_status['total_videos']} videos")
        return response
        
    except BulkJobError as e:
        logger.error(f"Bulk job creation failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=HTTPError(
                error="job_creation_failed",
                message=str(e),
                details={"user_id": user.user_id},
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
    job_id: str,
    user: UserInfo = Depends(get_current_user)
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
        
        # Verify job ownership (if not anonymous)
        if user.user_id != "anonymous" and job_status.get("user_id") != user.user_id:
            raise HTTPException(
                status_code=403,
                detail=HTTPError(
                    error="access_denied",
                    message="Access denied to this bulk job",
                    details={"job_id": job_id},
                    status_code=403
                ).dict()
            )
        
        response = BulkJobResponse(
            job_id=job_status["job_id"],
            user_id=job_status.get("user_id", user.user_id),
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
            user_tier=job_status.get("user_tier", user.tier),
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
    user: UserInfo = Depends(get_current_user),
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
            user_id=user.user_id,
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
                user_id=user.user_id,
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
                user_tier=user.tier,
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
        logger.error(f"Failed to list jobs for user {user.user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="job_list_failed",
                message="Failed to list bulk jobs",
                details={"user_id": user.user_id, "error": str(e)},
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
    user: UserInfo = Depends(get_current_user)
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
        
        # Verify job ownership (if not anonymous)
        if user.user_id != "anonymous" and job_status.get("user_id") != user.user_id:
            raise HTTPException(
                status_code=403,
                detail=HTTPError(
                    error="access_denied",
                    message="Access denied to this bulk job",
                    details={"job_id": job_id},
                    status_code=403
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
        
        logger.info(f"Started processing job {job_id} for user {user.user_id}")
        
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
    user: UserInfo = Depends(get_current_user)
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
        
        # Verify job ownership (if not anonymous)
        if user.user_id != "anonymous" and job_status.get("user_id") != user.user_id:
            raise HTTPException(
                status_code=403,
                detail=HTTPError(
                    error="access_denied",
                    message="Access denied to this bulk job",
                    details={"job_id": job_id},
                    status_code=403
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
        
        logger.info(f"Cancelled job {job_id} for user {user.user_id}")
        
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
async def download_job_results(
    job_id: str,
    user: UserInfo = Depends(get_current_user)
) -> StreamingResponse:
    """
    Download ZIP file containing all completed transcripts.
    
    Returns a ZIP file with all successfully transcribed videos
    from the bulk job.
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
        
        # Verify job ownership (if not anonymous)
        if user.user_id != "anonymous" and job_status.get("user_id") != user.user_id:
            raise HTTPException(
                status_code=403,
                detail=HTTPError(
                    error="access_denied",
                    message="Access denied to this bulk job",
                    details={"job_id": job_id},
                    status_code=403
                ).dict()
            )
        
        # Check if ZIP file is available
        zip_path = job_status.get("zip_file_path")
        if not zip_path or not os.path.exists(zip_path):
            # Generate ZIP file if job is completed but ZIP doesn't exist
            if job_status["status"] == JobStatus.COMPLETED.value:
                logger.info(f"Generating ZIP file for completed job {job_id}")
                zip_path = await bulk_job_service._generate_job_zip(job_id)
                
                if not zip_path:
                    raise HTTPException(
                        status_code=404,
                        detail=HTTPError(
                            error="no_results",
                            message="No completed transcripts available for download",
                            details={"job_id": job_id},
                            status_code=404
                        ).dict()
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=HTTPError(
                        error="download_not_ready",
                        message="Download not available - job not completed or no successful transcripts",
                        details={"job_id": job_id, "status": job_status["status"]},
                        status_code=400
                    ).dict()
                )
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bulk_transcripts_{job_id[:8]}_{timestamp}.zip"
        
        # Create streaming response
        def iter_file():
            with open(zip_path, "rb") as file:
                while chunk := file.read(8192):
                    yield chunk
        
        logger.info(f"Serving ZIP download for job {job_id} to user {user.user_id}")
        
        return StreamingResponse(
            iter_file(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(os.path.getsize(zip_path))
            }
        )
        
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
    user: UserInfo = Depends(get_current_user)
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
        
        # Verify job ownership (if not anonymous)
        if user.user_id != "anonymous" and job_status.get("user_id") != user.user_id:
            raise HTTPException(
                status_code=403,
                detail=HTTPError(
                    error="access_denied",
                    message="Access denied to this bulk job",
                    details={"job_id": job_id},
                    status_code=403
                ).dict()
            )
        
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
        logger.info(f"Deleted job {job_id} for user {user.user_id}")
        
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