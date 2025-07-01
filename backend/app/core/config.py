"""
Configuration management using Pydantic Settings.
Loads configuration from environment variables.
"""

import os
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys (Optional - not all are required)
    groq_api_key: Optional[str] = Field(None, description="Groq API key for transcription")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key for transcription")
    
    # Optional API Keys
    youtube_api_key: Optional[str] = Field(None, description="YouTube Data API key")
    webshare_username: Optional[str] = Field(None, description="Webshare proxy username")
    webshare_password: Optional[str] = Field(None, description="Webshare proxy password")
    
    # Supabase Configuration
    supabase_url: Optional[str] = Field(None, description="Supabase project URL")
    supabase_anon_key: Optional[str] = Field(None, description="Supabase anonymous key")
    supabase_service_role_key: Optional[str] = Field(None, description="Supabase service role key")
    
    # Stripe Configuration
    stripe_secret_key: Optional[str] = Field(None, description="Stripe secret API key")
    stripe_publishable_key: Optional[str] = Field(None, description="Stripe publishable API key")
    stripe_webhook_secret: Optional[str] = Field(None, description="Stripe webhook secret")
    
    # Stripe Price IDs
    stripe_price_starter: Optional[str] = Field(None, description="Stripe price ID for starter package")
    stripe_price_popular: Optional[str] = Field(None, description="Stripe price ID for popular package")
    stripe_price_volume: Optional[str] = Field(None, description="Stripe price ID for volume package")
    
    # Server Configuration
    debug: bool = Field(False, description="Enable debug mode")
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    app_secret_key: Optional[str] = Field(None, description="Application secret key for hashing")
    
    # CORS Configuration
    cors_origins: List[str] = Field(
        ["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins"
    )
    
    # File Storage
    temp_dir: str = Field("/tmp/ytfetch", description="Temporary file directory")
    max_file_size_mb: int = Field(100, description="Maximum file size in MB")
    
    # Performance & Rate Limiting
    max_concurrent_transcriptions: int = Field(
        3, description="Maximum concurrent transcription tasks"
    )
    groq_rpm_limit: int = Field(100, description="Groq requests per minute limit")
    
    # Audio Processing
    optimal_sample_rate: int = Field(16000, description="Optimal sample rate for speech")
    optimal_channels: int = Field(1, description="Mono audio for transcription")
    chunk_duration_seconds: int = Field(60, description="Audio chunk duration")
    chunk_overlap_seconds: float = Field(0.5, description="Audio chunk overlap")
    
    # Stripe Configuration
    stripe_secret_key: Optional[str] = Field(None, description="Stripe secret API key")
    stripe_publishable_key: Optional[str] = Field(None, description="Stripe publishable key")
    stripe_webhook_secret: Optional[str] = Field(None, description="Stripe webhook endpoint secret")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


def ensure_temp_dir() -> str:
    """Ensure temporary directory exists and return path."""
    os.makedirs(settings.temp_dir, exist_ok=True)
    return settings.temp_dir