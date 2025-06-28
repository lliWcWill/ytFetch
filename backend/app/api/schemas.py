"""
Pydantic schemas for API request/response models.
Provides type safety and automatic validation.
"""

from typing import Dict, Optional, Any
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
    provider: str = Field(
        "groq",
        description="Transcription provider to use",
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
    provider: Optional[str] = Field(None, description="Transcription provider used")
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
    404: {
        "description": "Not Found - Video not found",
        "content": {
            "application/json": {
                "example": {
                    "error": "video_not_found", 
                    "message": "Video not found or is private",
                    "details": {"video_id": "invalid_id"},
                    "status_code": 404
                }
            }
        }
    },
    403: {
        "description": "Forbidden - Access denied",
        "content": {
            "application/json": {
                "example": {
                    "error": "access_denied",
                    "message": "Video is age-restricted or region-blocked",
                    "status_code": 403
                }
            }
        }
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "example": {
                    "error": "transcription_failed",
                    "message": "Failed to transcribe audio",
                    "details": {"provider": "groq", "reason": "api_error"},
                    "status_code": 500
                }
            }
        }
    }
}