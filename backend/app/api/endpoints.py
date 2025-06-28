"""
FastAPI endpoints for the ytFetch backend.
Orchestrates YouTube service and transcription service operations.
"""

import os
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Callable

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
from ..services.youtube_service import YouTubeService
from ..services.transcription_service import TranscriptionService

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


def format_transcript(segments: list, output_format: str) -> str:
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
        return ' '.join(segment.get('text', '').strip() for segment in segments if segment.get('text', '').strip())


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    services_status = {}
    
    # Check if API keys are configured
    services_status["groq"] = "configured" if settings.groq_api_key else "missing_api_key"
    services_status["openai"] = "configured" if settings.openai_api_key else "missing_api_key"
    services_status["temp_dir"] = "accessible" if os.access(ensure_temp_dir(), os.W_OK) else "not_writable"
    
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now().isoformat(),
        services=services_status
    )


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
                logger.debug(f"Received message from client {client_id}: {message}")
                
                # Echo back a simple acknowledgment
                await manager.send_progress(client_id, {
                    "type": "ack",
                    "message": "Connection active",
                    "client_id": client_id
                })
                
            except WebSocketDisconnect:
                logger.info(f"Client {client_id} disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop for client {client_id}: {e}")
                break
                
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for client {client_id}: {e}")
    finally:
        # Ensure cleanup happens regardless of how we exit
        await manager.disconnect(client_id)
        logger.info(f"WebSocket cleanup completed for client: {client_id}")


@router.post(
    "/api/v1/transcribe", 
    status_code=202,
    responses=ERROR_EXAMPLES
)
async def transcribe_video(
    request: TranscribeRequest, 
    background_tasks: BackgroundTasks,
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
    
    # Create unique job ID
    job_id = f"job_{video_id}_{int(time.time())}"
    
    # Schedule the transcription job as a background task
    background_tasks.add_task(
        run_transcription_job,
        request,
        job_id,
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
    manager: ConnectionManager
) -> None:
    """
    Execute the transcription job in the background and send progress updates via WebSocket.
    
    This function contains the original transcription logic but sends progress updates
    to connected WebSocket clients throughout the process.
    """
    start_time = time.time()
    audio_file_path = None
    
    def create_progress_callback() -> Callable[[str, float, str], None]:
        """Create a progress callback function for service methods."""
        def progress_callback(stage: str, progress: float, message: str) -> None:
            """Send progress update to WebSocket client."""
            progress_msg = create_progress_message(
                status=stage,
                progress=progress * 100,  # Convert to percentage
                message=message
            )
            # Schedule the WebSocket update in the event loop
            asyncio.create_task(manager.send_progress(job_id, progress_msg))
        
        return progress_callback
    
    try:
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
        
        # Step 3: Try to fetch existing transcript (fast path)
        await manager.send_progress(job_id, create_progress_message(
            status="processing",
            progress=20.0,
            message="Checking for existing transcript..."
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
                
                transcript_text = format_transcript(segments, request.output_format)
                
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
                
                logger.info(f"Transcript fetched successfully for {video_id} in {processing_metadata.transcription_time:.2f}s")
                
                # Send completion message with transcript
                await manager.send_progress(job_id, {
                    "type": "complete",
                    "status": "completed",
                    "progress": 100.0,
                    "message": "Transcription completed successfully",
                    "data": {
                        "transcript": transcript_text,
                        "video_metadata": video_metadata.dict(),
                        "processing_metadata": processing_metadata.dict(),
                        "format": request.output_format,
                        "provider": None,
                        "language": language or request.language
                    }
                })
                return
                
        except Exception as e:
            logger.info(f"Transcript fetch failed for {video_id}, falling back to audio transcription: {e}")
        
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
            await manager.send_progress(job_id, {
                "type": "error",
                "status": "error",
                "message": "Failed to download video audio",
                "error_code": "download_failed",
                "details": {"video_id": video_id, "error": str(e)}
            })
            return
        
        # Step 5: Transcribe audio
        await manager.send_progress(job_id, create_progress_message(
            status="transcribing",
            progress=60.0,
            message="Transcribing audio using AI..."
        ))
        
        transcription_start = time.time()
        
        try:
            # Initialize transcription service
            transcription_service = TranscriptionService(
                provider=request.provider,
                model="auto"  # Auto-select best model based on duration
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
                    "details": {"provider": request.provider}
                })
                return
            
            await manager.send_progress(job_id, create_progress_message(
                status="processing",
                progress=90.0,
                message="Formatting transcript..."
            ))
            
            transcription_time = time.time() - transcription_start
            segments = transcription_result['segments']
            transcript_text = format_transcript(segments, request.output_format)
            
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
            
            # Send completion message with transcript
            await manager.send_progress(job_id, {
                "type": "complete",
                "status": "completed",
                "progress": 100.0,
                "message": "Transcription completed successfully",
                "data": {
                    "transcript": transcript_text,
                    "video_metadata": video_metadata.dict(),
                    "processing_metadata": processing_metadata.dict(),
                    "format": request.output_format,
                    "provider": request.provider,
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
                "details": {"provider": request.provider, "error": str(e)}
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
async def get_video_info(video_id: str) -> Dict[str, Any]:
    """Get video information without transcription."""
    try:
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