"""
FastAPI endpoints for the ytFetch backend.
Orchestrates YouTube service and transcription service operations.
"""

import os
import time
import logging
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Callable, Optional, Union

from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import JSONResponse

from ..api.schemas import (
    TranscribeRequest,
    TranscribeResponse,
    HTTPError,
    HealthResponse,
    VideoMetadata,
    ProcessingMetadata,
    ProgressUpdate,
    ERROR_EXAMPLES
)
from ..core.config import settings, ensure_temp_dir
from ..core.websockets import connection_manager, ConnectionManager, create_progress_message
from ..core.supabase import SupabaseClient
from ..core.auth import (
    get_current_user, 
    get_current_user_optional, 
    AuthenticatedUser,
    GuestUser,
    verify_resource_ownership,
    RequireAuth,
    OptionalAuth,
    UserOrGuest
)
from ..services.youtube_service import YouTubeService
from ..services.transcription_service import TranscriptionService
from ..services.usage_service import usage_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize services
youtube_service = YouTubeService()


def cleanup_temp_file(file_path: str) -> None:
    """Background task to clean up temporary audio files."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


def format_transcript(segments: list, output_format: str, video_metadata: Optional[dict] = None) -> str:
    """Format transcript segments into requested output format."""
    if not segments:
        return ""
    
    if output_format == "json":
        import json
        return json.dumps(segments, indent=2)
    
    elif output_format == "srt":
        srt_content = []
        for i, segment in enumerate(segments, 1):
            start_time = segment.get('start', 0)
            duration = segment.get('duration', 0)
            end_time = start_time + duration
            
            # Convert seconds to SRT time format
            start_srt = f"{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{int(start_time%60):02d},{int((start_time%1)*1000):03d}"
            end_srt = f"{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d},{int((end_time%1)*1000):03d}"
            
            srt_content.extend([
                str(i),
                f"{start_srt} --> {end_srt}",
                segment.get('text', '').strip(),
                ""
            ])
        return '\n'.join(srt_content)
    
    elif output_format == "vtt":
        vtt_content = ["WEBVTT", ""]
        for segment in segments:
            start_time = segment.get('start', 0)
            duration = segment.get('duration', 0)
            end_time = start_time + duration
            
            # Convert seconds to WebVTT time format
            start_vtt = f"{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{start_time%60:06.3f}"
            end_vtt = f"{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{end_time%60:06.3f}"
            
            vtt_content.extend([
                f"{start_vtt} --> {end_vtt}",
                segment.get('text', '').strip(),
                ""
            ])
        return '\n'.join(vtt_content)
    
    else:  # txt format (default)
        transcript_text = ' '.join(segment.get('text', '').strip() for segment in segments if segment.get('text', '').strip())
        
        # Add header with video info if metadata is provided
        if video_metadata:
            header = ""
            if 'title' in video_metadata:
                header += f"Video Title: {video_metadata['title']}\n"
            if 'url' in video_metadata:
                header += f"YouTube URL: {video_metadata['url']}\n"
            elif 'video_id' in video_metadata:
                header += f"YouTube URL: https://www.youtube.com/watch?v={video_metadata['video_id']}\n"
            if 'video_id' in video_metadata:
                header += f"Video ID: {video_metadata['video_id']}\n"
            
            if header:
                header += "-" * 80 + "\n\n"
                transcript_text = header + transcript_text
        
        return transcript_text


@router.get("/api/v1/guest/usage")
async def get_guest_usage(
    user: Union[AuthenticatedUser, GuestUser] = UserOrGuest
) -> Dict[str, Any]:
    """
    Get current usage information for the user (guest or authenticated).
    
    Returns usage limits and current consumption.
    """
    if isinstance(user, GuestUser):
        # Get guest usage
        from ..services.guest_service import guest_service
        usage_summary = await guest_service.get_guest_usage_summary(user.session_id)
        
        # Log the usage summary for debugging
        logger.info(f"Guest usage summary for {user.session_id}: {usage_summary}")
        
        return {
            "is_guest": True,
            "session_id": user.session_id,
            "usage": usage_summary.get("usage", {
                "unofficial": {"used": 0, "limit": 10, "remaining": 10},
                "groq": {"used": 0, "limit": 10, "remaining": 10},
                "bulk": {"used": 0, "limit": 50, "remaining": 50}
            }),
            "first_use_at": usage_summary.get("first_use_at"),
            "last_use_at": usage_summary.get("last_use_at"),
            "is_new_guest": usage_summary.get("is_new_guest", True),
            "message": "Sign up for a free account to get more transcriptions and features!"
        }
    else:
        # Get authenticated user usage
        usage_summary = await usage_service.get_usage_summary(user.id)
        
        # Transform authenticated user usage to match guest format for frontend compatibility
        # This ensures the frontend GuestUsageDisplay component works for both guests and free tier users
        user_tier = usage_summary.get("tier", "free")
        
        if user_tier == "free":
            # For free tier users, provide usage in the same format as guests
            # Map the authenticated user's usage to the guest format
            jobs_usage = usage_summary.get("usage", {}).get("jobs_created", {})
            videos_usage = usage_summary.get("usage", {}).get("videos_processed", {})
            
            return {
                "is_guest": False,
                "user_id": user.id,
                "email": user.email,
                "tier": user_tier,
                "usage": {
                    "unofficial": {
                        "used": videos_usage.get("used", 0),
                        "limit": min(videos_usage.get("limit", 20), 20),  # Cap at 20 for free tier
                        "remaining": min(videos_usage.get("remaining", 20), 20)
                    },
                    "groq": {
                        "used": jobs_usage.get("used", 0),
                        "limit": min(jobs_usage.get("limit", 20), 20),  # Cap at 20 for free tier
                        "remaining": min(jobs_usage.get("remaining", 20), 20)
                    },
                    "bulk": {
                        "used": 0,
                        "limit": 100,
                        "remaining": 100
                    }
                },
                "limits": usage_summary.get("limits", {}),
                "subscription": usage_summary.get("subscription", {})
            }
        else:
            # For paid tiers, return the original structure (component won't display for them anyway)
            return {
                "is_guest": False,
                "user_id": user.id,
                "email": user.email,
                "tier": user_tier,
                "usage": usage_summary.get("usage", {}),
                "limits": usage_summary.get("limits", {}),
                "subscription": usage_summary.get("subscription", {})
            }


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    services_status = {}
    
    # Check if API keys are configured
    services_status["groq"] = "configured" if settings.groq_api_key else "missing_api_key"
    services_status["openai"] = "configured" if settings.openai_api_key else "missing_api_key"
    services_status["temp_dir"] = "accessible" if os.access(ensure_temp_dir(), os.W_OK) else "not_writable"
    
    # Check Supabase status
    supabase_health = SupabaseClient.health_check()
    if supabase_health["configured"]:
        if supabase_health["anon_client"] and supabase_health["service_client"]:
            services_status["supabase"] = "fully_configured"
        elif supabase_health["anon_client"]:
            services_status["supabase"] = "anon_only"
        else:
            services_status["supabase"] = "configured_but_unavailable"
    else:
        services_status["supabase"] = "not_configured"
    
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now().isoformat(),
        services=services_status
    )


@router.get("/api/v1/supabase/health")
async def supabase_health_check() -> Dict[str, Any]:
    """Detailed Supabase health check endpoint."""
    health = SupabaseClient.health_check()
    
    # Add timestamp and configuration details
    health["timestamp"] = datetime.now().isoformat()
    health["url_configured"] = bool(settings.supabase_url)
    health["anon_key_configured"] = bool(settings.supabase_anon_key)
    health["service_key_configured"] = bool(settings.supabase_service_role_key)
    
    return health


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, manager: ConnectionManager = Depends(lambda: connection_manager)):
    """
    WebSocket endpoint for real-time progress updates during transcription.
    
    Clients can connect to receive live updates about transcription progress,
    including download status, processing stages, and completion notifications.
    """
    try:
        # Accept the connection and add to manager
        await manager.connect(websocket, client_id)
        logger.info(f"WebSocket connection established for client: {client_id}")
        
        # Keep connection alive until client disconnects
        while True:
            try:
                # Wait for any message from client (ping/pong, etc.)
                message = await websocket.receive_text()
                logger.info(f"Received message from client {client_id}: {message}")
                
                # Parse the message and handle different types
                try:
                    msg_data = json.loads(message)
                    if msg_data.get('type') == 'ping':
                        # Respond to ping with pong
                        await manager.send_progress(client_id, {
                            "type": "pong",
                            "message": "Connection active",
                            "client_id": client_id
                        })
                    else:
                        # Echo back a simple acknowledgment for other messages
                        await manager.send_progress(client_id, {
                            "type": "ack",
                            "message": "Message received",
                            "client_id": client_id,
                            "received": msg_data
                        })
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client {client_id}: {message}")
                
            except WebSocketDisconnect:
                logger.info(f"Client {client_id} disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop for client {client_id}: {e}")
                break
                
    except WebSocketDisconnect:
        # Client disconnected before entering the loop
        logger.info(f"Client {client_id} disconnected during connection setup")
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for client {client_id}: {e}")
    finally:
        # Ensure cleanup happens regardless of how we exit
        try:
            await manager.disconnect(client_id)
            logger.info(f"WebSocket cleanup completed for client: {client_id}")
        except Exception as cleanup_error:
            logger.error(f"Error during WebSocket cleanup for client {client_id}: {cleanup_error}")


@router.post(
    "/api/v1/transcribe", 
    status_code=202,
    responses=ERROR_EXAMPLES
)
async def transcribe_video(
    request: TranscribeRequest, 
    background_tasks: BackgroundTasks,
    user: Union[AuthenticatedUser, GuestUser] = UserOrGuest,
    manager: ConnectionManager = Depends(lambda: connection_manager)
) -> JSONResponse:
    """
    Start a YouTube video transcription job.
    
    This endpoint immediately returns 202 Accepted and starts the transcription
    process in the background. Clients should connect to the WebSocket endpoint
    to receive real-time progress updates.
    
    Returns:
        202 Accepted with job_id for tracking progress via WebSocket
    """
    # Extract video ID for initial validation
    video_id = youtube_service.get_video_id_from_url(request.url)
    
    if not video_id:
        raise HTTPException(
            status_code=400,
            detail=HTTPError(
                error="invalid_url",
                message="Invalid YouTube URL format",
                details={"url": request.url},
                status_code=400
            ).dict()
        )
    
    # Create unique job ID including user ID for security
    job_id = f"job_{user.id[:8]}_{video_id}_{int(time.time())}"
    
    logger.info(f"Creating transcription job {job_id} for user {user.id}, video: {request.url}, method: {request.method}")
    
    # Schedule the transcription job as a background task with user context
    background_tasks.add_task(
        run_transcription_job,
        request,
        job_id,
        user,
        manager
    )
    
    logger.info(f"Transcription job {job_id} scheduled for video: {request.url}")
    
    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "job_id": job_id,
            "video_id": video_id,
            "message": "Transcription job started. Connect to WebSocket for progress updates.",
            "websocket_url": f"/ws/{job_id}"
        }
    )


async def run_transcription_job(
    request: TranscribeRequest, 
    job_id: str,
    user: Union[AuthenticatedUser, GuestUser],
    manager: ConnectionManager
) -> None:
    """
    Execute the transcription job in the background and send progress updates via WebSocket.
    
    This function contains the original transcription logic but sends progress updates
    to connected WebSocket clients throughout the process.
    """
    logger.info(f"Starting transcription job {job_id} for user {user.id} with method: {request.method}")
    start_time = time.time()
    audio_file_path = None
    
    # Check guest limits if user is a guest
    if isinstance(user, GuestUser):
        from ..services.guest_service import guest_service
        
        # Map method to usage type
        usage_type = guest_service.get_usage_type_for_method(request.method or "groq")
        
        # Check if guest can perform this action
        check_result = await guest_service.check_and_increment_if_allowed(
            session_id=user.session_id,
            usage_type=usage_type,
            ip_address=None,  # IP will be handled at API Gateway level
            requested_count=1
        )
        
        if not check_result["allowed"]:
            # Send error via WebSocket
            await manager.send_progress(job_id, {
                "type": "error",
                "status": "error",
                "message": check_result.get("upgrade_message", check_result["reason"]),
                "error_code": "guest_limit_exceeded",
                "details": {
                    "usage": check_result["usage"],
                    "requires_auth": check_result["requires_auth"]
                }
            })
            logger.warning(f"Guest {user.session_id} exceeded {usage_type} limit")
            return
        
        logger.info(f"Guest {user.session_id} usage recorded: {check_result['usage']}")
    
    # TODO: Log the transcription job in database for audit and tracking
    # This would integrate with the bulk job service for unified job management
    
    def create_progress_callback() -> Callable[[str, float, str], None]:
        """Create a progress callback function for service methods."""
        # Get the current event loop
        loop = asyncio.get_event_loop()
        
        def progress_callback(stage: str, progress: float, message: str) -> None:
            """Send progress update to WebSocket client."""
            progress_msg = create_progress_message(
                status=stage,
                progress=progress * 100,  # Convert to percentage
                message=message
            )
            # Schedule the WebSocket update in the event loop safely
            try:
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        manager.send_progress(job_id, progress_msg),
                        loop
                    )
                else:
                    # Fallback if loop is not running
                    logger.warning(f"Event loop not running, cannot send progress for {job_id}")
            except Exception as e:
                logger.error(f"Error sending progress update: {e}")
        
        return progress_callback
    
    try:
        # Small delay to allow WebSocket connection to establish
        await asyncio.sleep(0.2)
        
        # Send initial progress
        await manager.send_progress(job_id, create_progress_message(
            status="initializing",
            progress=0.0,
            message="Starting transcription job..."
        ))
        
        # Step 1: Extract video ID (already done in main endpoint)
        logger.info(f"Processing transcription job {job_id} for: {request.url}")
        video_id = youtube_service.get_video_id_from_url(request.url)
        
        # Step 2: Get video information
        await manager.send_progress(job_id, create_progress_message(
            status="initializing",
            progress=10.0,
            message="Fetching video information..."
        ))
        
        try:
            video_info = await youtube_service.get_video_info(video_id)
        except Exception as e:
            logger.error(f"Failed to get video info for {video_id}: {e}")
            await manager.send_progress(job_id, {
                "type": "error",
                "status": "error",
                "message": "Video not found or is private",
                "error_code": "video_not_found",
                "details": {"video_id": video_id, "error": str(e)}
            })
            return
        
        video_metadata = VideoMetadata(
            title=video_info.get('title', 'Unknown'),
            duration=video_info.get('duration', 0),
            uploader=video_info.get('uploader', 'Unknown'),
            upload_date=video_info.get('upload_date'),
            view_count=video_info.get('view_count'),
            description=video_info.get('description'),
            is_live=video_info.get('is_live', False),
            live_status=video_info.get('live_status', 'not_live')
        )
        
        # Determine processing method - use method field if provided, otherwise fall back to provider for backward compatibility
        if request.method:
            processing_method = request.method
            logger.info(f"Processing method selected (explicit): {processing_method}")
        else:
            # Backward compatibility: if no method specified, use provider for AI transcription
            processing_method = request.provider
            logger.info(f"Processing method selected (backward compatibility): {processing_method}")
        
        # For AI transcription, determine which provider to use
        # If method is groq/openai, use that as provider; otherwise use provider field
        if processing_method in ["groq", "openai"]:
            ai_provider = processing_method
        else:
            ai_provider = request.provider
        
        # Step 3: Handle method-specific routing
        if processing_method == "unofficial":
            # UNOFFICIAL METHOD: Only try transcript fetching, fail if not available
            await manager.send_progress(job_id, create_progress_message(
                status="processing",
                progress=20.0,
                message="Fetching existing YouTube transcript..."
            ))
            
            transcript_fetch_start = time.time()
            try:
                # Create progress callback for transcript fetching
                progress_callback = create_progress_callback()
                segments, language, error = await youtube_service.fetch_transcript_segments(
                    video_id, 
                    progress_callback=progress_callback
                )
                
                if segments:
                    await manager.send_progress(job_id, create_progress_message(
                        status="processing",
                        progress=90.0,
                        message="Formatting transcript..."
                    ))
                    
                    # Create video metadata dict for formatting
                    format_metadata = {
                        'title': video_metadata.title,
                        'video_id': video_id,
                        'url': request.url
                    }
                    
                    # Generate all formats
                    formatted_transcripts = {
                        'txt': format_transcript(segments, 'txt', format_metadata),
                        'srt': format_transcript(segments, 'srt', format_metadata),
                        'vtt': format_transcript(segments, 'vtt', format_metadata),
                        'json': format_transcript(segments, 'json', format_metadata)
                    }
                    
                    # Get the requested format
                    transcript_text = formatted_transcripts[request.output_format]
                    
                    processing_metadata = ProcessingMetadata(
                        processing_time=time.time() - start_time,
                        download_time=None,
                        transcription_time=time.time() - transcript_fetch_start,
                        download_strategy=None,
                        file_size_mb=None,
                        audio_duration=video_metadata.duration,
                        chunks_processed=None,
                        source="transcript_api"
                    )
                    
                    logger.info(f"Unofficial transcript fetched successfully for {video_id} in {processing_metadata.transcription_time:.2f}s")
                    logger.info(f"Transcript length: {len(transcript_text)} characters")
                    logger.info(f"First 200 chars of transcript: {transcript_text[:200]}...")
                    
                    # Send completion message with all transcript formats
                    await manager.send_progress(job_id, {
                        "type": "complete",
                        "status": "completed",
                        "progress": 100.0,
                        "message": "Unofficial transcript fetched successfully",
                        "data": {
                            "transcript": transcript_text,  # Current format
                            "all_formats": formatted_transcripts,  # All available formats
                            "video_metadata": video_metadata.dict(),
                            "processing_metadata": processing_metadata.dict(),
                            "format": request.output_format,
                            "provider": None,
                            "language": language or request.language
                        }
                    })
                    return
                else:
                    # No transcript found - this is an error for unofficial method
                    await manager.send_progress(job_id, {
                        "type": "error",
                        "status": "error",
                        "message": "No unofficial transcript available for this video",
                        "error_code": "no_transcript_available",
                        "details": {"video_id": video_id, "method": "unofficial"}
                    })
                    return
                    
            except Exception as e:
                logger.error(f"Unofficial transcript fetch failed for {video_id}: {e}")
                await manager.send_progress(job_id, {
                    "type": "error",
                    "status": "error",
                    "message": "Failed to fetch unofficial transcript",
                    "error_code": "transcript_fetch_failed",
                    "details": {"video_id": video_id, "method": "unofficial", "error": str(e)}
                })
                return
        
        elif processing_method in ["groq", "openai"]:
            # AI TRANSCRIPTION METHOD: Skip transcript fetching, go directly to audio download + AI
            logger.info(f"Using {processing_method} AI transcription method - skipping transcript fetch")
            await manager.send_progress(job_id, create_progress_message(
                status="processing",
                progress=20.0,
                message=f"Using {processing_method.upper()} AI transcription - preparing for audio download..."
            ))
            # Skip to Step 4 (audio download and transcription)
            
        else:
            # This should never happen with current schema validation, but handle gracefully
            logger.error(f"Unknown processing method: {processing_method}")
            await manager.send_progress(job_id, {
                "type": "error",
                "status": "error", 
                "message": f"Unknown processing method: {processing_method}",
                "error_code": "invalid_method",
                "details": {"method": processing_method}
            })
            return
        
        # Step 4: Download audio and transcribe (slow path)
        await manager.send_progress(job_id, create_progress_message(
            status="downloading",
            progress=30.0,
            message="Downloading audio from video..."
        ))
        
        download_start = time.time()
        
        try:
            # Create progress callback for download
            progress_callback = create_progress_callback()
            audio_file_path = await youtube_service.download_audio_as_mp3_enhanced(
                video_id=video_id,
                output_dir=ensure_temp_dir(),
                video_title=video_metadata.title,
                progress_callback=progress_callback
            )
            
            if not audio_file_path or not os.path.exists(audio_file_path):
                await manager.send_progress(job_id, {
                    "type": "error",
                    "status": "error",
                    "message": "Failed to download audio. Video may be restricted or unavailable.",
                    "error_code": "download_failed",
                    "details": {"video_id": video_id}
                })
                return
            
            download_time = time.time() - download_start
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
            logger.info(f"Audio downloaded successfully: {file_size_mb:.1f}MB in {download_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Audio download failed for {video_id}: {e}")
            error_msg = str(e)
            
            # Provide helpful error messages based on common issues
            if "Sign in" in error_msg or "authentication" in error_msg.lower():
                error_msg = "YouTube requires authentication. Please ensure Chrome is logged into YouTube, or try the unofficial transcript method."
            elif "403" in error_msg:
                error_msg = "Access forbidden. The video may be private, age-restricted, or region-locked."
            elif "404" in error_msg:
                error_msg = "Video not found. Please check the URL."
            else:
                error_msg = f"Failed to download video audio: {error_msg[:200]}"
                
            await manager.send_progress(job_id, {
                "type": "error",
                "status": "error",
                "message": error_msg,
                "error_code": "download_failed",
                "details": {"video_id": video_id, "error": str(e), "method": processing_method}
            })
            return
        
        # Step 5: Transcribe audio
        await manager.send_progress(job_id, create_progress_message(
            status="transcribing",
            progress=60.0,
            message=f"Transcribing audio using {processing_method.upper()} AI..."
        ))
        
        transcription_start = time.time()
        
        try:
            # Initialize transcription service
            # Use the model from request if provided, otherwise auto-select
            model_to_use = request.model if request.model else "auto"
            transcription_service = TranscriptionService(
                provider=ai_provider,
                model=model_to_use
            )
            
            # Create progress callback for transcription
            progress_callback = create_progress_callback()
            
            # Transcribe audio
            transcription_result = await transcription_service.transcribe_audio_from_file(
                audio_file_path,
                language=request.language,
                progress_callback=progress_callback
            )
            
            if not transcription_result or not transcription_result.get('segments'):
                await manager.send_progress(job_id, {
                    "type": "error",
                    "status": "error",
                    "message": "Transcription produced no results",
                    "error_code": "transcription_failed",
                    "details": {"provider": ai_provider}
                })
                return
            
            await manager.send_progress(job_id, create_progress_message(
                status="processing",
                progress=90.0,
                message="Formatting transcript..."
            ))
            
            transcription_time = time.time() - transcription_start
            segments = transcription_result['segments']
            
            # Create video metadata dict for formatting
            format_metadata = {
                'title': video_metadata.title,
                'video_id': video_id,
                'url': request.url
            }
            
            # Generate all formats
            formatted_transcripts = {
                'txt': format_transcript(segments, 'txt', format_metadata),
                'srt': format_transcript(segments, 'srt', format_metadata),
                'vtt': format_transcript(segments, 'vtt', format_metadata),
                'json': format_transcript(segments, 'json', format_metadata)
            }
            
            # Get the requested format
            transcript_text = formatted_transcripts[request.output_format]
            
            # Schedule cleanup of temporary audio file
            if audio_file_path and os.path.exists(audio_file_path):
                try:
                    os.remove(audio_file_path)
                    logger.info(f"Cleaned up temporary file: {audio_file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {audio_file_path}: {e}")
            
            processing_metadata = ProcessingMetadata(
                processing_time=time.time() - start_time,
                download_time=download_time,
                transcription_time=transcription_time,
                download_strategy=transcription_result.get('download_strategy'),
                file_size_mb=file_size_mb,
                audio_duration=transcription_result.get('audio_duration', video_metadata.duration),
                chunks_processed=transcription_result.get('chunks_processed'),
                source="ai_transcription"
            )
            
            logger.info(f"Transcription completed for {video_id}: {transcription_time:.2f}s, {processing_metadata.chunks_processed} chunks")
            
            # Send completion message with all transcript formats
            await manager.send_progress(job_id, {
                "type": "complete",
                "status": "completed",
                "progress": 100.0,
                "message": "Transcription completed successfully",
                "data": {
                    "transcript": transcript_text,  # Current format
                    "all_formats": formatted_transcripts,  # All available formats
                    "video_metadata": video_metadata.dict(),
                    "processing_metadata": processing_metadata.dict(),
                    "format": request.output_format,
                    "provider": ai_provider,
                    "language": request.language
                }
            })
            
        except Exception as e:
            logger.error(f"Transcription failed for {video_id}: {e}")
            # Cleanup audio file on transcription failure
            if audio_file_path and os.path.exists(audio_file_path):
                cleanup_temp_file(audio_file_path)
            
            await manager.send_progress(job_id, {
                "type": "error",
                "status": "error",
                "message": "Failed to transcribe audio",
                "error_code": "transcription_failed",
                "details": {"provider": ai_provider, "error": str(e)}
            })
            
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error in transcription job {job_id}: {e}")
        
        # Cleanup audio file on unexpected error
        if audio_file_path and os.path.exists(audio_file_path):
            cleanup_temp_file(audio_file_path)
        
        await manager.send_progress(job_id, {
            "type": "error",
            "status": "error",
            "message": "An unexpected error occurred",
            "error_code": "internal_error",
            "details": {"error": str(e)}
        })


# Additional utility endpoints
@router.get("/api/v1/video-info/{video_id}")
async def get_video_info(
    video_id: str,
    user: AuthenticatedUser = RequireAuth
) -> Dict[str, Any]:
    """Get video information without transcription."""
    try:
        logger.info(f"User {user.id} requested video info for: {video_id}")
        video_info = await youtube_service.get_video_info(video_id)
        return video_info
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=HTTPError(
                error="video_not_found",
                message="Video not found or is private",
                details={"video_id": video_id, "error": str(e)},
                status_code=404
            ).dict()
        )


@router.get("/api/v1/usage")
async def get_usage_summary(
    user: AuthenticatedUser = RequireAuth
) -> Dict[str, Any]:
    """
    Get user's usage summary and tier information.
    
    Returns comprehensive usage statistics including:
    - Current tier and limits
    - Monthly usage for all tracked metrics
    - Remaining quota
    - Subscription status
    """
    try:
        logger.info(f"User {user.id} requested usage summary")
        summary = await usage_service.get_usage_summary(user.id)
        
        if "error" in summary:
            raise HTTPException(
                status_code=404,
                detail=HTTPError(
                    error="usage_not_found",
                    message=summary.get("error", "Failed to get usage summary"),
                    details={"user_id": user.id},
                    status_code=404
                ).dict()
            )
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get usage summary for user {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=HTTPError(
                error="usage_fetch_failed",
                message="Failed to fetch usage summary",
                details={"user_id": user.id, "error": str(e)},
                status_code=500
            ).dict()
        )