"""
Pydantic schemas for API request/response models.
Provides type safety and automatic validation.
"""

from typing import Dict, Optional, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class TranscribeRequest(BaseModel):
    """Request schema for video transcription."""
    
    url: str = Field(
        ..., 
        description="YouTube URL to transcribe",
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
    )
    output_format: str = Field(
        "txt",
        description="Output format for transcript",
        pattern="^(txt|srt|vtt|json)$",
        examples=["txt", "srt", "vtt", "json"]
    )
    method: Optional[str] = Field(
        None,
        description="Transcription method: unofficial (existing captions), groq (AI), or openai (AI)",
        pattern="^(unofficial|groq|openai)$",
        examples=["unofficial", "groq", "openai"]
    )
    provider: str = Field(
        "groq",
        description="Transcription provider to use (deprecated, use 'method' instead)",
        pattern="^(groq|openai)$", 
        examples=["groq", "openai"]
    )
    language: str = Field(
        "en",
        description="Audio language code (ISO 639-1)",
        min_length=2,
        max_length=5,
        examples=["en", "es", "fr", "de"]
    )
    client_id: Optional[str] = Field(
        None,
        description="Optional client identifier for progress tracking",
        max_length=255,
        examples=["client_123", "browser_session_abc"]
    )
    model: Optional[str] = Field(
        None,
        description="Whisper model to use for Groq transcription",
        examples=["whisper-large-v3-turbo", "whisper-large-v3", "distil-whisper-large-v3-en"]
    )


class ProgressUpdate(BaseModel):
    """Progress update schema for real-time transcription status."""
    
    stage: str = Field(
        ..., 
        description="Current processing stage",
        examples=["initializing", "downloading", "transcribing", "processing", "complete"]
    )
    progress: float = Field(
        ..., 
        description="Progress percentage as float between 0.0 and 1.0",
        ge=0.0,
        le=1.0,
        examples=[0.0, 0.25, 0.5, 0.75, 1.0]
    )
    message: str = Field(
        ..., 
        description="Human-readable progress message",
        examples=["Starting transcription...", "Downloading audio...", "Processing chunks 1/4", "Transcription complete"]
    )
    timestamp: datetime = Field(
        ..., 
        description="Timestamp when this progress update was generated",
        examples=["2024-01-15T10:30:00Z"]
    )


class VideoMetadata(BaseModel):
    """Video metadata information."""
    
    title: str = Field(..., description="Video title")
    duration: int = Field(..., description="Video duration in seconds")
    uploader: str = Field(..., description="Video uploader/channel name")
    upload_date: Optional[str] = Field(None, description="Upload date")
    view_count: Optional[int] = Field(None, description="Number of views")
    description: Optional[str] = Field(None, description="Video description")
    is_live: bool = Field(False, description="Whether video was/is live stream")
    live_status: str = Field("not_live", description="Live stream status")


class ProcessingMetadata(BaseModel):
    """Processing metadata and performance metrics."""
    
    processing_time: float = Field(..., description="Total processing time in seconds")
    download_time: Optional[float] = Field(None, description="Audio download time")
    transcription_time: Optional[float] = Field(None, description="Transcription time")
    download_strategy: Optional[str] = Field(None, description="Successful download strategy")
    file_size_mb: Optional[float] = Field(None, description="Audio file size in MB")
    audio_duration: Optional[float] = Field(None, description="Audio duration in seconds")
    chunks_processed: Optional[int] = Field(None, description="Number of audio chunks")
    source: str = Field(..., description="Transcript source: transcript_api or ai_transcription")


class TranscribeResponse(BaseModel):
    """Response schema for successful transcription."""
    
    transcript: str = Field(..., description="Complete transcript text")
    video_metadata: VideoMetadata = Field(..., description="Video information")
    processing_metadata: ProcessingMetadata = Field(..., description="Processing details")
    format: str = Field(..., description="Output format used")
    method: Optional[str] = Field(None, description="Transcription method used")
    provider: Optional[str] = Field(None, description="Transcription provider used (deprecated)")
    language: str = Field(..., description="Detected/specified language")


class HTTPError(BaseModel):
    """Standardized error response schema."""
    
    error: str = Field(..., description="Error type/category")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    status_code: int = Field(..., description="HTTP status code")


class HealthResponse(BaseModel):
    """Health check response schema."""
    
    status: str = Field("healthy", description="Service health status")
    version: str = Field(..., description="Application version")
    timestamp: str = Field(..., description="Current timestamp")
    services: Dict[str, str] = Field(..., description="Service status check")


# Bulk Operation Schemas

class BulkAnalyzeRequest(BaseModel):
    """Request schema for bulk analysis of playlist/channel."""
    
    url: str = Field(
        ..., 
        description="YouTube playlist or channel URL to analyze",
        examples=[
            "https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3",
            "https://www.youtube.com/@channel/videos"
        ]
    )
    max_videos: Optional[int] = Field(
        None,
        description="Maximum number of videos to analyze (respects tier limits)",
        ge=1,
        le=1000,
        examples=[10, 50, 100]
    )


class BulkCreateRequest(BaseModel):
    """Request schema for creating a bulk transcription job."""
    
    url: str = Field(
        ..., 
        description="YouTube playlist or channel URL to process",
        examples=[
            "https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3",
            "https://www.youtube.com/@channel/videos"
        ]
    )
    transcript_method: str = Field(
        "unofficial",
        description="Transcription method to use",
        pattern="^(unofficial|groq|openai)$",
        examples=["unofficial", "groq", "openai"]
    )
    output_format: str = Field(
        "txt",
        description="Output format for transcripts",
        pattern="^(txt|srt|vtt|json)$",
        examples=["txt", "srt", "vtt", "json"]
    )
    max_videos: Optional[int] = Field(
        None,
        description="Maximum number of videos to process (respects tier limits)",
        ge=1,
        le=1000,
        examples=[10, 50, 100]
    )
    webhook_url: Optional[str] = Field(
        None,
        description="Optional webhook URL for completion notification",
        examples=["https://example.com/webhook"]
    )


class BulkTaskResponse(BaseModel):
    """Response schema for individual bulk task information."""
    
    task_id: str = Field(..., description="Unique task identifier")
    video_id: str = Field(..., description="YouTube video ID")
    video_title: str = Field(..., description="Video title")
    video_url: str = Field(..., description="YouTube video URL")
    video_duration: int = Field(..., description="Video duration in seconds")
    status: str = Field(..., description="Task status")
    order_index: int = Field(..., description="Task order in the job")
    retry_count: int = Field(0, description="Number of retry attempts")
    transcript_text: Optional[str] = Field(None, description="Completed transcript")
    language: Optional[str] = Field(None, description="Detected language")
    processing_method: Optional[str] = Field(None, description="Processing method used")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: str = Field(..., description="Task creation timestamp")
    started_at: Optional[str] = Field(None, description="Task start timestamp")
    completed_at: Optional[str] = Field(None, description="Task completion timestamp")


class BulkJobResponse(BaseModel):
    """Response schema for bulk job information."""
    
    job_id: str = Field(..., description="Unique job identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    source_url: str = Field(..., description="Source playlist/channel URL")
    transcript_method: str = Field(..., description="Transcription method")
    output_format: str = Field(..., description="Output format")
    status: str = Field(..., description="Job status")
    total_videos: int = Field(..., description="Total number of videos")
    completed_videos: int = Field(0, description="Number of completed videos")
    failed_videos: int = Field(0, description="Number of failed videos")
    pending_videos: Optional[int] = Field(None, description="Number of pending videos")
    processing_videos: Optional[int] = Field(None, description="Number of currently processing videos")
    retry_videos: Optional[int] = Field(None, description="Number of videos pending retry")
    progress_percent: float = Field(0.0, description="Overall progress percentage")
    user_tier: str = Field(..., description="User subscription tier")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")
    zip_file_path: Optional[str] = Field(None, description="Path to ZIP file when completed")
    zip_available: bool = Field(False, description="Whether ZIP download is available")
    estimated_duration_minutes: Optional[float] = Field(None, description="Estimated completion time")
    created_at: str = Field(..., description="Job creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    completed_at: Optional[str] = Field(None, description="Job completion timestamp")
    tier_limits: Optional[Dict[str, Any]] = Field(None, description="Applicable tier limits")


class BulkJobListResponse(BaseModel):
    """Response schema for list of bulk jobs."""
    
    jobs: List[BulkJobResponse] = Field(..., description="List of bulk jobs")
    total_count: int = Field(..., description="Total number of jobs for user")
    page: int = Field(1, description="Current page number")
    per_page: int = Field(20, description="Items per page")
    has_next: bool = Field(False, description="Whether there are more pages")


class BulkAnalyzeResponse(BaseModel):
    """Response schema for bulk analysis results."""
    
    url: str = Field(..., description="Source URL that was analyzed")
    source_type: str = Field(..., description="Type of source (playlist or channel)")
    title: str = Field(..., description="Playlist or channel title")
    description: Optional[str] = Field(None, description="Playlist or channel description")
    total_videos: int = Field(..., description="Total number of videos found")
    analyzed_videos: int = Field(..., description="Number of videos analyzed (limited by max_videos)")
    estimated_duration_hours: float = Field(..., description="Estimated total duration in hours")
    videos: List[Dict[str, Any]] = Field(..., description="Video metadata list")
    tier_limits: Dict[str, Any] = Field(..., description="Applicable tier limits for user")
    can_process_all: bool = Field(..., description="Whether user can process all videos found")


# User tier and authentication schemas

class UserInfo(BaseModel):
    """User information schema for authenticated requests."""
    
    user_id: str = Field(..., description="Unique user identifier")
    email: Optional[str] = Field(None, description="User email")
    tier: str = Field("free", description="User subscription tier")
    created_at: Optional[str] = Field(None, description="User creation timestamp")


# Error response examples for documentation
ERROR_EXAMPLES = {
    400: {
        "description": "Bad Request - Invalid input",
        "content": {
            "application/json": {
                "example": {
                    "error": "invalid_url",
                    "message": "Invalid YouTube URL format",
                    "details": {"url": "not-a-valid-url"},
                    "status_code": 400
                }
            }
        }
    },
    401: {
        "description": "Unauthorized - Authentication required",
        "content": {
            "application/json": {
                "example": {
                    "error": "unauthorized",
                    "message": "Authentication required for bulk operations",
                    "status_code": 401
                }
            }
        }
    },
    403: {
        "description": "Forbidden - Access denied or rate limited",
        "content": {
            "application/json": {
                "example": {
                    "error": "rate_limited",
                    "message": "Daily video processing limit exceeded for your tier",
                    "details": {"tier": "free", "limit": 10},
                    "status_code": 403
                }
            }
        }
    },
    404: {
        "description": "Not Found - Resource not found",
        "content": {
            "application/json": {
                "example": {
                    "error": "job_not_found", 
                    "message": "Bulk job not found or not accessible",
                    "details": {"job_id": "invalid_id"},
                    "status_code": 404
                }
            }
        }
    },
    429: {
        "description": "Too Many Requests - Rate limit exceeded",
        "content": {
            "application/json": {
                "example": {
                    "error": "too_many_requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "details": {"retry_after": 60},
                    "status_code": 429
                }
            }
        }
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "example": {
                    "error": "bulk_job_failed",
                    "message": "Failed to process bulk job",
                    "details": {"job_id": "job_123", "reason": "service_error"},
                    "status_code": 500
                }
            }
        }
    }
}