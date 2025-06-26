"""
Performance Optimizations Package

This package contains advanced rate limiting, connection pooling, and 
transcription optimization modules for the YouTube Transcript Fetcher.
"""

from .advanced_rate_limiter import (
    AdvancedRateLimiter,
    SyncRateLimiter, 
    RateLimitConfig,
    create_rate_limiter,
    GROQ_DEV_CONFIGS
)

from .connection_pool_manager import (
    OptimizedConnectionPool,
    ConnectionPoolConfig,
    get_global_pool,
    optimized_post_multipart
)

from .enhanced_audio_transcriber import (
    EnhancedAudioTranscriber
)

__version__ = "1.0.0"
__all__ = [
    "AdvancedRateLimiter",
    "SyncRateLimiter", 
    "RateLimitConfig",
    "create_rate_limiter",
    "GROQ_DEV_CONFIGS",
    "OptimizedConnectionPool",
    "ConnectionPoolConfig", 
    "get_global_pool",
    "optimized_post_multipart",
    "EnhancedAudioTranscriber"
]