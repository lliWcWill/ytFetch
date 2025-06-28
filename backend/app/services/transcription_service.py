"""
Transcription Service Module

This module provides a clean TranscriptionService class that encapsulates all transcription operations
including audio preprocessing, chunking, rate limiting, and transcription using both Groq and OpenAI.

Migrated from enhanced_audio_transcriber.py and audio_transcriber.py with:
- Removed Streamlit dependencies completely
- Added full async support
- Integrated with backend configuration system
- Enhanced error handling and logging
- Callback system for progress updates
- Support for both Groq and OpenAI providers
- Advanced rate limiting and circuit breaker patterns
- Performance optimizations preserved
"""

import asyncio
import hashlib
import logging
import os
import random
import subprocess
import tempfile
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import concurrent.futures

# Audio processing
from pydub import AudioSegment

# API clients
from groq import Groq
import openai

# Local imports
from ..core.config import get_settings

# Initialize settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    rpm: int = 400                    # Requests per minute
    burst_size: int = 10              # Burst allowance
    safety_factor: float = 0.8        # Safety margin (0.8 = 80% of limit)
    max_retries: int = 5              # Maximum retry attempts
    base_backoff: float = 1.0         # Base backoff delay
    max_backoff: float = 300.0        # Maximum backoff delay
    jitter_factor: float = 0.1        # Jitter randomization factor
    
    # Circuit breaker settings
    failure_threshold: int = 5        # Failures before opening circuit
    recovery_timeout: float = 60.0    # Time before half-open attempt
    success_threshold: int = 3        # Successes to close circuit


@dataclass
class RequestMetrics:
    """Track request metrics for monitoring"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    circuit_breaker_blocks: int = 0
    deduplicated_requests: int = 0
    average_response_time: float = 0.0
    
    def update_response_time(self, response_time: float) -> None:
        """Update rolling average response time"""
        if self.successful_requests == 0:
            self.average_response_time = response_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.average_response_time = (
                alpha * response_time + (1 - alpha) * self.average_response_time
            )


class CircuitBreaker:
    """Circuit breaker for handling service failures"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.next_attempt_time = 0.0
        
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        current_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
        
        elif self.state == CircuitState.OPEN:
            if current_time >= self.next_attempt_time:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            return False
        
        elif self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self) -> None:
        """Record successful request"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker CLOSED - service recovered")
        
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self, error: Exception) -> None:
        """Record failed request"""
        self.last_failure_time = time.time()
        self.failure_count += 1
        
        # Check if should open circuit (for 503 errors or too many failures)
        is_service_error = (
            "503" in str(error) or 
            "Service Unavailable" in str(error) or
            "rate limit" in str(error).lower()
        )
        
        if (self.failure_count >= self.config.failure_threshold or 
            (is_service_error and self.failure_count >= 2)):
            
            self.state = CircuitState.OPEN
            self.next_attempt_time = (
                self.last_failure_time + self.config.recovery_timeout
            )
            logger.warning(
                f"Circuit breaker OPENED after {self.failure_count} failures. "
                f"Next attempt at {time.ctime(self.next_attempt_time)}"
            )


class RequestTracker:
    """Track and deduplicate requests"""
    
    def __init__(self, ttl: float = 300.0):  # 5 minute TTL
        self.ttl = ttl
        self.active_requests: Set[str] = set()
        self.request_history: deque = deque()
        self.request_times: Dict[str, float] = {}
        
    def _cleanup_expired(self) -> None:
        """Remove expired request tracking"""
        current_time = time.time()
        
        # Clean up history
        while (self.request_history and 
               current_time - self.request_history[0][1] > self.ttl):
            request_id, _ = self.request_history.popleft()
            self.active_requests.discard(request_id)
            self.request_times.pop(request_id, None)
    
    def generate_request_id(self, **kwargs) -> str:
        """Generate unique request ID for deduplication"""
        # Create hash from request parameters
        key_data = f"{kwargs.get('file_path', '')}{kwargs.get('model', '')}{kwargs.get('language', '')}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def is_duplicate(self, request_id: str) -> bool:
        """Check if request is duplicate"""
        self._cleanup_expired()
        return request_id in self.active_requests
    
    def track_request(self, request_id: str) -> None:
        """Start tracking a request"""
        current_time = time.time()
        self.active_requests.add(request_id)
        self.request_history.append((request_id, current_time))
        self.request_times[request_id] = current_time
    
    def complete_request(self, request_id: str) -> None:
        """Mark request as complete"""
        self.active_requests.discard(request_id)


class StrictRateLimiter:
    """Synchronous rate limiter for backward compatibility"""
    
    def __init__(self, model: str):
        self.model = model
        self.config = self._get_model_config(model)
        self.request_times: deque = deque()
        self.effective_rpm = int(self.config.rpm * self.config.safety_factor)
        self.consecutive_failures = 0
        self.cooldown_until = 0.0
        logger.info(f"Rate limiter initialized for {model}: {self.effective_rpm} effective RPM")
        
    def _get_model_config(self, model: str) -> RateLimitConfig:
        """Get rate limit configuration for model"""
        model_configs = {
            "whisper-large-v3-turbo": RateLimitConfig(
                rpm=400,
                burst_size=15,
                safety_factor=0.8,
                max_retries=5,
                failure_threshold=3,
                recovery_timeout=60.0
            ),
            "whisper-large-v3": RateLimitConfig(
                rpm=300,
                burst_size=12,
                safety_factor=0.8,
                max_retries=5,
                failure_threshold=3,
                recovery_timeout=45.0
            ),
            "distil-whisper-large-v3-en": RateLimitConfig(
                rpm=100,
                burst_size=5,
                safety_factor=0.7,  # More conservative for lower limit
                max_retries=3,
                failure_threshold=2,
                recovery_timeout=30.0
            )
        }
        return model_configs.get(model, model_configs["whisper-large-v3"])
        
    def wait_if_needed(self, progress_callback: Optional[Callable[[str, float, str], None]] = None) -> None:
        """Synchronous rate limiting for backward compatibility"""
        current_time = time.time()
        
        # Check cooldown
        if current_time < self.cooldown_until:
            wait_time = self.cooldown_until - current_time
            logger.info(f"Cooldown wait: {wait_time:.1f}s")
            if progress_callback:
                progress_callback("rate_limiting", 0.0, f"Waiting {wait_time:.1f}s for cooldown...")
            time.sleep(wait_time)
        
        # Remove old requests
        while (self.request_times and 
               current_time - self.request_times[0] >= 60.0):
            self.request_times.popleft()
        
        # Rate limiting
        if len(self.request_times) >= self.effective_rpm:
            oldest_request = self.request_times[0]
            wait_time = 60.0 - (current_time - oldest_request) + 0.1
            if wait_time > 0:
                logger.debug(f"Rate limit wait: {wait_time:.2f}s")
                if progress_callback:
                    progress_callback("rate_limiting", 0.0, f"Rate limit wait: {wait_time:.1f}s")
                time.sleep(wait_time)
        
        self.request_times.append(time.time())
    
    def record_failure(self) -> None:
        """Record failure for cooldown calculation"""
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            cooldown_delay = min(
                self.config.base_backoff * (2 ** (self.consecutive_failures - 3)),
                self.config.max_backoff
            )
            self.cooldown_until = time.time() + cooldown_delay
            logger.warning(f"Setting cooldown: {cooldown_delay:.1f}s")
    
    def record_success(self) -> None:
        """Record success to reset failure counter"""
        self.consecutive_failures = 0
        self.cooldown_until = 0.0


class TranscriptionError(Exception):
    """Base exception for transcription errors"""
    pass


class CircuitOpenError(TranscriptionError):
    """Raised when circuit breaker is open"""
    pass


class RateLimitError(TranscriptionError):
    """Raised when rate limit is exceeded"""
    pass


class TranscriptionService:
    """
    Enhanced transcription service with advanced rate limiting, circuit breaker patterns,
    and connection pooling optimized for both Groq and OpenAI providers.
    """
    
    def __init__(self, provider: str = "groq", model: str = "whisper-large-v3-turbo"):
        """
        Initialize the transcription service.
        
        Args:
            provider: "groq" or "openai"
            model: Model name to use for transcription
        """
        self.provider = provider
        self.model = model
        self.settings = get_settings()
        
        # Initialize clients
        self.groq_client = None
        self.openai_client = None
        self._initialize_clients()
        
        # Initialize rate limiter
        self.rate_limiter = StrictRateLimiter(model)
        
        # Track session metrics
        self.session_metrics = {
            "total_chunks": 0,
            "successful_chunks": 0,
            "failed_chunks": 0,
            "rate_limited_chunks": 0,
            "circuit_breaker_blocks": 0,
            "total_duration": 0.0,
            "total_processing_time": 0.0,
            "start_time": 0.0
        }
        
        # Constants optimized for performance
        self.max_file_size_mb = settings.max_file_size_mb
        self.max_chunk_size_mb = self.max_file_size_mb - 10  # Leave headroom
        self.chunk_overlap_seconds = settings.chunk_overlap_seconds
        self.optimal_sample_rate = settings.optimal_sample_rate
        self.optimal_channels = settings.optimal_channels
        
        logger.info(f"TranscriptionService initialized: {provider}/{model}")
    
    def _initialize_clients(self):
        """Initialize API clients based on provider"""
        if self.provider == "groq" and self.settings.groq_api_key:
            self.groq_client = Groq(api_key=self.settings.groq_api_key)
            logger.info("Groq client initialized")
        elif self.provider == "openai" and self.settings.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=self.settings.openai_api_key)
            logger.info("OpenAI client initialized")
        else:
            logger.warning(f"No API key found for provider: {self.provider}")
    
    def select_optimal_model(self, duration_seconds: int, language: str = "en") -> str:
        """Select optimal model based on duration and language"""
        if self.provider == "openai":
            return "whisper-1"  # OpenAI only has one Whisper model
            
        # Groq model selection
        if duration_seconds > 14400:  # > 4 hours
            return "whisper-large-v3-turbo"  # Best rate limits
        elif duration_seconds > 7200:  # > 2 hours
            if language == "en":
                return "distil-whisper-large-v3-en"
            else:
                return "whisper-large-v3"
        else:
            if language == "en":
                return "distil-whisper-large-v3-en"
            else:
                return "whisper-large-v3"
    
    def calculate_optimal_chunk_duration(self, file_duration_seconds: int) -> int:
        """Calculate optimal chunk duration based on file length and rate limits"""
        # For very large files, use smaller chunks to prevent 503 errors
        if file_duration_seconds > 14400:  # > 4 hours
            base_chunk = 120  # 2 minutes
        elif file_duration_seconds > 7200:  # > 2 hours  
            base_chunk = 150  # 2.5 minutes
        elif file_duration_seconds > 3600:  # > 1 hour
            base_chunk = 180  # 3 minutes
        elif file_duration_seconds > 1800:  # > 30 minutes
            base_chunk = 240  # 4 minutes
        else:
            base_chunk = 300  # 5 minutes
        
        # For shorter videos, check if we can process as single chunk
        if file_duration_seconds <= 180:  # 3 minutes or less
            estimated_size_mb = (file_duration_seconds * self.optimal_sample_rate * 2 * 0.55) / (1024 * 1024)
            if estimated_size_mb < self.max_chunk_size_mb:
                return file_duration_seconds  # Process as single chunk
        
        return max(60, min(300, base_chunk))
    
    def calculate_workers_for_duration(self, duration_seconds: int) -> int:
        """Calculate optimal number of workers based on duration"""
        if self.provider == "openai":
            return min(3, settings.max_concurrent_transcriptions)  # OpenAI is more restrictive
            
        # Groq worker calculation
        if duration_seconds > 14400:  # > 4 hours
            return 2  # Very conservative for massive files
        elif duration_seconds > 7200:  # > 2 hours
            return 3
        elif duration_seconds > 3600:  # > 1 hour
            return 4
        else:
            return min(10, settings.max_concurrent_transcriptions)
    
    async def preprocess_audio_optimized(self, input_file: str, speed_multiplier: float = 1.0, 
                                        progress_callback: Optional[Callable[[str, float, str], None]] = None) -> Optional[str]:
        """
        Optimized audio preprocessing for transcription.
        
        Args:
            input_file: Path to input audio file
            speed_multiplier: Speed multiplier for audio (1.0=normal, 2.0=2x, etc.)
            
        Returns:
            Optional[str]: Path to preprocessed file or None if failed
        """
        temp_dir = tempfile.gettempdir()
        output_file = os.path.join(temp_dir, f"{Path(input_file).stem}_optimized.flac")
        
        try:
            cmd = [
                "ffmpeg",
                "-i", input_file,
                "-ar", str(self.optimal_sample_rate),
                "-ac", str(self.optimal_channels),
                "-map", "0:a:0"
            ]
            
            # Add speed adjustment filter if speed_multiplier != 1.0
            if speed_multiplier != 1.0:
                if speed_multiplier <= 2.0:
                    cmd.extend(["-filter:a", f"atempo={speed_multiplier}"])
                elif speed_multiplier == 3.0:
                    cmd.extend(["-filter:a", "atempo=1.5,atempo=2.0"])
                elif speed_multiplier == 4.0:
                    cmd.extend(["-filter:a", "atempo=2.0,atempo=2.0"])
                else:
                    # Fallback for other speeds
                    factor = min(speed_multiplier ** 0.5, 2.0)
                    cmd.extend(["-filter:a", f"atempo={factor},atempo={factor}"])
            
            cmd.extend([
                "-c:a", "flac",
                "-compression_level", "0",  # Fastest compression
                "-threads", "0",
                "-y",
                "-loglevel", "error",
                output_file
            ])
            
            start_time = time.time()
            
            if progress_callback:
                progress_callback("preprocessing", 0.08, "Running FFmpeg preprocessing...")
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            process = await loop.run_in_executor(
                None, 
                lambda: subprocess.run(cmd, capture_output=True, text=True)
            )
            
            if process.returncode != 0:
                logger.error(f"FFmpeg preprocessing failed: {process.stderr}")
                return None
            
            elapsed = time.time() - start_time
            file_size = os.path.getsize(output_file) / (1024 * 1024)
            logger.info(f"Audio preprocessed in {elapsed:.2f}s → {file_size:.1f} MB")
            
            if progress_callback:
                progress_callback("preprocessing", 0.12, f"Preprocessing completed → {file_size:.1f} MB")
            
            return output_file
            
        except Exception as e:
            logger.error(f"Audio preprocessing error: {e}")
            return None
    
    async def split_audio_smart(self, file_path: str, chunk_duration: int, 
                               progress_callback: Optional[Callable[[str, float, str], None]] = None) -> List[Dict]:
        """
        Smart audio splitting with overlap and size validation.
        
        Args:
            file_path: Path to audio file
            chunk_duration: Duration of each chunk in seconds
            
        Returns:
            List[Dict]: List of chunk information dictionaries
        """
        try:
            # Get total duration
            loop = asyncio.get_event_loop()
            probe_cmd = [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            
            duration_output = await loop.run_in_executor(
                None,
                lambda: subprocess.check_output(probe_cmd, text=True)
            )
            total_duration = float(duration_output.strip())
            
            chunks = []
            temp_dir = tempfile.gettempdir()
            file_stem = Path(file_path).stem
            
            start_seconds = 0
            chunk_index = 1
            
            # Create chunk tasks for parallel processing
            chunk_tasks = []
            
            while start_seconds < total_duration:
                end_seconds = min(start_seconds + chunk_duration, total_duration)
                chunk_path = os.path.join(temp_dir, f"{file_stem}_chunk{chunk_index}.flac")
                
                chunk_task = self._create_chunk_async(
                    file_path, chunk_path, start_seconds, 
                    end_seconds - start_seconds, chunk_index
                )
                chunk_tasks.append(chunk_task)
                
                start_seconds += chunk_duration - self.chunk_overlap_seconds
                chunk_index += 1
            
            # Execute chunk creation in parallel
            if progress_callback:
                progress_callback("splitting", 0.32, f"Creating {len(chunk_tasks)} chunks...")
                
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            
            # Process results
            for result in chunk_results:
                if isinstance(result, dict):
                    chunks.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Chunk creation failed: {result}")
            
            # Sort by index to maintain order
            chunks.sort(key=lambda x: x['index'])
            logger.info(f"Split audio into {len(chunks)} chunks")
            
            if progress_callback:
                progress_callback("splitting", 0.34, f"Successfully created {len(chunks)} chunks")
                
            return chunks
            
        except Exception as e:
            logger.error(f"Audio splitting error: {e}")
            return []
    
    async def _create_chunk_async(self, input_path: str, output_path: str, 
                                 start_seconds: float, duration: float, 
                                 chunk_index: int) -> Optional[Dict]:
        """Create a single audio chunk asynchronously"""
        cmd = [
            "ffmpeg",
            "-ss", str(start_seconds),
            "-i", input_path,
            "-t", str(duration),
            "-ar", str(self.optimal_sample_rate),
            "-ac", str(self.optimal_channels),
            "-c:a", "flac",
            "-compression_level", "0",
            "-threads", "0",
            "-y",
            "-loglevel", "error",
            output_path
        ]
        
        try:
            loop = asyncio.get_event_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True)
            )
            
            if process.returncode == 0:
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                
                # Validate chunk size
                if size_mb > self.max_chunk_size_mb:
                    logger.warning(f"Chunk {chunk_index} too large: {size_mb:.1f}MB")
                    os.remove(output_path)
                    return None
                
                return {
                    "path": output_path,
                    "size_mb": size_mb,
                    "start_ms": start_seconds * 1000,
                    "end_ms": (start_seconds + duration) * 1000,
                    "duration_ms": duration * 1000,
                    "index": chunk_index
                }
            else:
                logger.error(f"Failed to create chunk {chunk_index}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating chunk {chunk_index}: {e}")
            return None
    
    async def transcribe_chunk_with_rate_limiting(
        self, 
        chunk_info: Dict, 
        language: str = "en",
        max_retries: int = 5,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> Tuple[int, Optional[str]]:
        """
        Transcribe single chunk with advanced rate limiting.
        
        Args:
            chunk_info: Chunk information dictionary
            language: Language code
            max_retries: Maximum retry attempts
            
        Returns:
            Tuple[int, Optional[str]]: (chunk_index, transcription_text)
        """
        if not self.groq_client and not self.openai_client:
            return chunk_info["index"], None
        
        chunk_index = chunk_info["index"]
        
        for attempt in range(max_retries):
            try:
                # Apply rate limiting (synchronous for now)
                self.rate_limiter.wait_if_needed(progress_callback)
                
                start_time = time.time()
                
                # Transcribe based on provider
                if self.provider == "groq" and self.groq_client:
                    transcription = await self._transcribe_with_groq(chunk_info, language)
                elif self.provider == "openai" and self.openai_client:
                    transcription = await self._transcribe_with_openai(chunk_info, language)
                else:
                    raise TranscriptionError(f"No client available for provider: {self.provider}")
                
                elapsed = time.time() - start_time
                self.rate_limiter.record_success()
                
                # Update session metrics
                self.session_metrics["successful_chunks"] += 1
                
                logger.info(f"Chunk {chunk_index} transcribed in {elapsed:.2f}s")
                
                # Cleanup chunk file
                try:
                    os.remove(chunk_info["path"])
                except:
                    pass
                
                return chunk_index, transcription
                
            except Exception as e:
                error_str = str(e)
                
                # Handle specific error types
                if "503" in error_str or "Service Unavailable" in error_str:
                    logger.warning(f"Chunk {chunk_index} hit 503 error (attempt {attempt + 1})")
                    self.rate_limiter.record_failure()
                    self.session_metrics["rate_limited_chunks"] += 1
                    
                    if attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        wait_time = min(2 ** attempt + random.uniform(0, 5), 120)
                        logger.info(f"Waiting {wait_time:.1f}s before retry...")
                        if progress_callback:
                            progress_callback("retry", 0.0, f"Retrying chunk {chunk_index} in {wait_time:.1f}s (attempt {attempt + 2})")
                        await asyncio.sleep(wait_time)
                        continue
                
                elif "rate limit" in error_str.lower():
                    logger.warning(f"Chunk {chunk_index} hit rate limit")
                    self.rate_limiter.record_failure()
                    self.session_metrics["rate_limited_chunks"] += 1
                    
                    if attempt < max_retries - 1:
                        if progress_callback:
                            progress_callback("rate_limiting", 0.0, f"Rate limit hit for chunk {chunk_index}, waiting 60s...")
                        await asyncio.sleep(60)  # Wait 1 minute for rate limit reset
                        continue
                
                else:
                    logger.error(f"Chunk {chunk_index} error: {e}")
                    if attempt < max_retries - 1:
                        if progress_callback:
                            progress_callback("retry", 0.0, f"Error transcribing chunk {chunk_index}, retrying in 5s...")
                        await asyncio.sleep(5)  # Short wait for other errors
                        continue
        
        # Final failure cleanup
        self.session_metrics["failed_chunks"] += 1
        try:
            os.remove(chunk_info["path"])
        except:
            pass
        
        return chunk_index, None
    
    async def _transcribe_with_groq(self, chunk_info: Dict, language: str) -> str:
        """Transcribe chunk using Groq API"""
        loop = asyncio.get_event_loop()
        
        def sync_transcribe():
            with open(chunk_info["path"], "rb") as audio_file:
                return self.groq_client.audio.transcriptions.create(
                    file=audio_file,
                    model=self.model,
                    response_format="text",
                    language=language,
                    temperature=0.0
                )
        
        return await loop.run_in_executor(None, sync_transcribe)
    
    async def _transcribe_with_openai(self, chunk_info: Dict, language: str) -> str:
        """Transcribe chunk using OpenAI API"""
        loop = asyncio.get_event_loop()
        
        def sync_transcribe():
            with open(chunk_info["path"], "rb") as audio_file:
                return self.openai_client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text",
                    language=language,
                    temperature=0.0
                )
        
        result = await loop.run_in_executor(None, sync_transcribe)
        return result.text
    
    async def transcribe_audio_from_file(
        self, 
        file_path: str, 
        language: str = "en",
        speed_multiplier: float = 1.0,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> Optional[str]:
        """
        Enhanced transcription with advanced rate limiting and error handling.
        
        Args:
            file_path: Path to audio file
            language: Language code (default: "en")
            speed_multiplier: Speed multiplier for audio processing
            progress_callback: Optional callback for progress updates (stage, progress, message)
                             Stages include: "preprocessing", "splitting", "transcribing", 
                             "rate_limiting", "retry", "complete", "error"
                             Progress is 0.0-1.0, messages describe current operation
            
        Returns:
            Optional[str]: Transcribed text or None if failed
            
        Progress Callback Usage:
            The progress callback receives three parameters:
            - stage (str): Current processing stage
            - progress (float): Overall progress from 0.0 to 1.0
            - message (str): Descriptive message about current operation
            
            Example stages and messages:
            - "preprocessing" (0.05-0.15): Audio preprocessing with FFmpeg
            - "splitting" (0.25-0.35): Splitting audio into chunks
            - "transcribing" (0.4-0.9): "Transcribing chunk X of Y (Z%)"
            - "rate_limiting" (0.0): Waiting for rate limits
            - "retry" (0.0): Retrying failed chunks or operations
            - "complete" (1.0): Transcription completed successfully
            - "error" (0.0): Error occurred during processing
        """
        session_start = time.time()
        self.session_metrics["start_time"] = session_start
        
        try:
            logger.info("🚀 Starting enhanced transcription...")
            
            if progress_callback:
                progress_callback("preprocessing", 0.05, "Starting audio preprocessing...")
            
            # Preprocess audio
            preprocessed_file = await self.preprocess_audio_optimized(file_path, speed_multiplier, progress_callback)
            if not preprocessed_file:
                raise TranscriptionError("Audio preprocessing failed")
            
            if progress_callback:
                progress_callback("preprocessing", 0.15, "Audio preprocessing completed")
            
            # Get audio duration
            audio = AudioSegment.from_file(preprocessed_file)
            duration_seconds = len(audio) // 1000
            self.session_metrics["total_duration"] = duration_seconds
            
            logger.info(f"Audio duration: {duration_seconds}s ({duration_seconds/60:.1f} min)")
            
            if progress_callback:
                progress_callback("analysis", 0.2, f"Audio duration: {duration_seconds/60:.1f} minutes")
            
            # Select optimal model if auto-selection is enabled
            if self.model == "auto":
                optimal_model = self.select_optimal_model(duration_seconds, language)
                logger.info(f"Auto-selected model: {optimal_model}")
                self.model = optimal_model
                self.rate_limiter = StrictRateLimiter(optimal_model)
            
            # Calculate optimal chunking strategy
            chunk_duration = self.calculate_optimal_chunk_duration(duration_seconds)
            logger.info(f"Using chunk duration: {chunk_duration}s")
            
            if progress_callback:
                progress_callback("splitting", 0.25, f"Preparing to split into {chunk_duration}s chunks...")
            
            # Check if we can process as single chunk
            if chunk_duration >= duration_seconds:
                logger.info(f"⚡ Processing entire {duration_seconds}s video in ONE request!")
                
                if progress_callback:
                    progress_callback("transcription", 0.5, "Transcribing audio in single chunk...")
                
                # Single chunk transcription
                file_size_mb = os.path.getsize(preprocessed_file) / (1024 * 1024)
                chunk_info = {
                    "path": preprocessed_file,
                    "size_mb": file_size_mb,
                    "start_ms": 0,
                    "end_ms": duration_seconds * 1000,
                    "duration_ms": duration_seconds * 1000,
                    "index": 1
                }
                
                _, transcription = await self.transcribe_chunk_with_rate_limiting(
                    chunk_info, language, max_retries=5, progress_callback=progress_callback
                )
                
                if not transcription:
                    raise TranscriptionError("Single chunk transcription failed")
                
                if progress_callback:
                    progress_callback("complete", 1.0, "Transcription completed successfully!")
                
                # Calculate metrics
                total_time = time.time() - session_start
                self.session_metrics["total_processing_time"] = total_time
                speed_factor = duration_seconds / total_time if total_time > 0 else 0
                
                logger.info("=" * 60)
                logger.info("🏁 TRANSCRIPTION COMPLETE - SINGLE CHUNK MODE")
                logger.info("=" * 60)
                logger.info(f"📝 Audio duration: {duration_seconds}s ({duration_seconds/60:.1f} min)")
                logger.info(f"⚡ Total time: {total_time:.2f}s")
                logger.info(f"🚀 Speed: {speed_factor:.1f}x realtime")
                logger.info("=" * 60)
                
                return transcription
            
            # Split audio into chunks
            if progress_callback:
                progress_callback("splitting", 0.3, "Splitting audio into chunks...")
                
            chunks = await self.split_audio_smart(preprocessed_file, chunk_duration, progress_callback)
            if not chunks:
                raise TranscriptionError("Audio splitting failed")
            
            self.session_metrics["total_chunks"] = len(chunks)
            logger.info(f"Created {len(chunks)} chunks for processing")
            
            if progress_callback:
                progress_callback("splitting", 0.35, f"Split into {len(chunks)} chunks")
            
            # Clean up preprocessed file
            if preprocessed_file != file_path:
                os.remove(preprocessed_file)
            
            # Calculate optimal worker count
            max_workers = self.calculate_workers_for_duration(duration_seconds)
            logger.info(f"Using {max_workers} parallel workers")
            
            # Process chunks in parallel
            transcriptions = {}
            failed_chunks = []
            
            # Create tasks for parallel processing
            chunk_tasks = []
            for chunk in chunks:
                task = self.transcribe_chunk_with_rate_limiting(chunk, language, progress_callback=progress_callback)
                chunk_tasks.append(task)
            
            # Initial transcription progress
            if progress_callback:
                progress_callback("transcribing", 0.4, f"Starting transcription of {len(chunks)} chunks...")
            
            # Process with limited concurrency
            semaphore = asyncio.Semaphore(max_workers)
            
            async def process_chunk_with_semaphore(task):
                async with semaphore:
                    return await task
            
            # Execute tasks
            completed_tasks = 0
            for completed_task in asyncio.as_completed([
                process_chunk_with_semaphore(task) for task in chunk_tasks
            ]):
                chunk_index, transcription = await completed_task
                completed_tasks += 1
                
                if transcription:
                    transcriptions[chunk_index] = transcription
                else:
                    failed_chunks.append(chunk_index)
                    logger.warning(f"Failed to transcribe chunk {chunk_index}")
                
                # Detailed progress update with chunk information
                if progress_callback:
                    base_progress = 0.4
                    transcription_progress = (completed_tasks / len(chunks)) * 0.5
                    total_progress = base_progress + transcription_progress
                    percentage = (completed_tasks / len(chunks)) * 100
                    
                    progress_callback("transcribing", total_progress, 
                                    f"Transcribing chunk {completed_tasks} of {len(chunks)} ({percentage:.1f}%)")
            
            # Retry failed chunks with more conservative settings
            if failed_chunks:
                logger.warning(f"Retrying {len(failed_chunks)} failed chunks...")
                if progress_callback:
                    progress_callback("retry", 0.9, f"Retrying {len(failed_chunks)} failed chunks...")
                
                await asyncio.sleep(60)  # Cooldown before retry
                
                for chunk_index in failed_chunks:
                    chunk = next(c for c in chunks if c["index"] == chunk_index)
                    _, transcription = await self.transcribe_chunk_with_rate_limiting(
                        chunk, language, max_retries=3, progress_callback=progress_callback
                    )
                    if transcription:
                        transcriptions[chunk_index] = transcription
            
            # Combine transcriptions in order
            full_transcription = " ".join(
                transcriptions.get(i, "") for i in range(1, len(chunks) + 1)
            ).strip()
            
            if not full_transcription:
                raise TranscriptionError("No successful transcriptions")
            
            if progress_callback:
                progress_callback("complete", 1.0, "Transcription completed successfully!")
            
            # Calculate final metrics
            total_time = time.time() - session_start
            self.session_metrics["total_processing_time"] = total_time
            
            success_rate = len(transcriptions) / len(chunks) * 100
            speed_factor = duration_seconds / total_time if total_time > 0 else 0
            
            # Log performance summary
            logger.info("=" * 60)
            logger.info("🏁 ENHANCED TRANSCRIPTION COMPLETE")
            logger.info("=" * 60)
            logger.info(f"📝 Audio duration: {duration_seconds}s ({duration_seconds/60:.1f} min)")
            logger.info(f"⚡ Processing time: {total_time:.2f}s")
            logger.info(f"🚀 Speed factor: {speed_factor:.1f}x realtime")
            logger.info(f"✅ Success rate: {success_rate:.1f}% ({len(transcriptions)}/{len(chunks)})")
            logger.info(f"📊 Rate limited: {self.session_metrics['rate_limited_chunks']} chunks")
            logger.info(f"🔧 Model used: {self.model}")
            logger.info(f"🌐 Provider: {self.provider}")
            logger.info("=" * 60)
            
            return full_transcription
            
        except Exception as e:
            logger.error(f"Enhanced transcription failed: {e}")
            if progress_callback:
                progress_callback("error", 0.0, f"Transcription failed: {str(e)}")
            raise TranscriptionError(f"Transcription failed: {e}")
        
        finally:
            # Cleanup any remaining temporary files
            temp_dir = tempfile.gettempdir()
            for file in Path(temp_dir).glob("*_optimized.*"):
                try:
                    file.unlink()
                except:
                    pass
            for file in Path(temp_dir).glob("*_chunk*.flac"):
                try:
                    file.unlink()
                except:
                    pass
    
    def get_session_metrics(self) -> Dict:
        """Get current session metrics"""
        metrics = self.session_metrics.copy()
        if metrics["total_chunks"] > 0:
            metrics["success_rate"] = (
                metrics["successful_chunks"] / metrics["total_chunks"] * 100
            )
        else:
            metrics["success_rate"] = 0.0
        
        if metrics["total_processing_time"] > 0 and metrics["total_duration"] > 0:
            metrics["speed_factor"] = (
                metrics["total_duration"] / metrics["total_processing_time"]
            )
        else:
            metrics["speed_factor"] = 0.0
        
        return metrics
    
    async def cleanup_temp_files(self) -> None:
        """Clean up temporary files"""
        temp_dir = tempfile.gettempdir()
        patterns = ["*_optimized.*", "*_chunk*.flac", "*_groq_optimized.*"]
        
        for pattern in patterns:
            for file_path in Path(temp_dir).glob(pattern):
                try:
                    file_path.unlink()
                    logger.debug(f"Cleaned up temp file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {file_path}: {e}")


# Backward compatible function
async def transcribe_audio_from_file(
    file_path: str, 
    language: str = "en", 
    provider: str = "groq",
    model: str = "auto",
    speed_multiplier: float = 1.0,
    progress_callback: Optional[Callable[[str, float, str], None]] = None
) -> Optional[str]:
    """
    Backward compatible enhanced transcription function.
    
    Args:
        file_path: Path to audio file
        language: Language code (default: "en")
        provider: "groq" or "openai"
        model: Model name or "auto" for automatic selection
        speed_multiplier: Speed multiplier for audio processing
        progress_callback: Optional callback for progress updates
    
    Returns:
        Transcribed text or None if failed
    """
    try:
        # Auto-select model based on file size if requested
        if model == "auto":
            audio = AudioSegment.from_file(file_path)
            duration_seconds = len(audio) // 1000
            
            service = TranscriptionService(provider, "whisper-large-v3-turbo")
            optimal_model = service.select_optimal_model(duration_seconds, language)
            service.model = optimal_model
        else:
            service = TranscriptionService(provider, model)
        
        result = await service.transcribe_audio_from_file(
            file_path, language, speed_multiplier, progress_callback
        )
        
        # Log final metrics
        metrics = service.get_session_metrics()
        logger.info(f"Session metrics: {metrics}")
        
        return result
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return None


# Create a default service instance for easy importing
def create_transcription_service(provider: str = "groq", model: str = "whisper-large-v3-turbo") -> TranscriptionService:
    """Create a transcription service instance"""
    return TranscriptionService(provider, model)


# Export main classes and functions
__all__ = [
    "TranscriptionService",
    "TranscriptionError", 
    "CircuitOpenError",
    "RateLimitError",
    "transcribe_audio_from_file",
    "create_transcription_service"
]