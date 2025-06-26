"""
Enhanced Audio Transcriber with Advanced Rate Limiting

This module integrates the advanced rate limiting, circuit breaker patterns,
and connection pooling to provide robust, loop-prevention transcription
optimized for Groq dev tier limits.
"""

import asyncio
import logging
import os
import random
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import concurrent.futures

import yaml
from groq import Groq
from pydub import AudioSegment

from .advanced_rate_limiter import (
    AdvancedRateLimiter, 
    SyncRateLimiter, 
    create_rate_limiter,
    GROQ_DEV_CONFIGS
)
from .connection_pool_manager import (
    OptimizedConnectionPool,
    GROQ_OPTIMIZED_CONFIG,
    get_global_pool
)

logger = logging.getLogger(__name__)

# Constants optimized for dev tier
MAX_FILE_SIZE_MB = 100
MAX_CHUNK_SIZE_MB = 90
CHUNK_OVERLAP_SECONDS = 0.5
OPTIMAL_SAMPLE_RATE = 16000
OPTIMAL_CHANNELS = 1


class EnhancedTranscriptionError(Exception):
    """Custom exception for transcription errors"""
    pass


class TranscriptionCircuitOpenError(EnhancedTranscriptionError):
    """Raised when circuit breaker is open"""
    pass


class TranscriptionRateLimitError(EnhancedTranscriptionError):
    """Raised when rate limit is exceeded"""
    pass


def load_config():
    """Load configuration from config.yaml file"""
    try:
        with open("config.yaml", "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        logger.error("config.yaml file not found. Please create it with your API keys.")
        return None
    except yaml.YAMLError:
        logger.error("Error parsing config.yaml. Please check its format.")
        return None


def initialize_groq_client():
    """Initialize Groq client with API key from config"""
    config = load_config()
    if not config:
        return None
    
    groq_api_key = config.get("groq", {}).get("api_key")
    if not groq_api_key or groq_api_key == "YOUR_GROQ_API_KEY_HERE":
        logger.warning("Groq API key is missing or invalid in config.yaml.")
        return None
    
    return Groq(api_key=groq_api_key)


# Global client initialization
groq_client = initialize_groq_client()


class EnhancedAudioTranscriber:
    """Enhanced audio transcriber with advanced rate limiting"""
    
    def __init__(self, model: str = "whisper-large-v3-turbo"):
        self.model = model
        self.groq_client = groq_client
        
        # Initialize rate limiter based on model
        self.rate_limiter = SyncRateLimiter(model)
        
        # Track transcription session metrics
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
        
        logger.info(f"Enhanced transcriber initialized with model: {model}")
    
    def select_optimal_model(self, duration_seconds: int, language: str = "en") -> str:
        """Select optimal model based on duration and language"""
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
        model_config = GROQ_DEV_CONFIGS.get(self.model)
        if not model_config:
            model_config = GROQ_DEV_CONFIGS["whisper-large-v3"]
        
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
        
        # Adjust based on rate limits - lower RPM = larger chunks
        rpm_factor = model_config.rpm / 400  # Normalize to turbo model
        adjusted_chunk = int(base_chunk / rpm_factor)
        
        # Ensure reasonable bounds
        return max(60, min(300, adjusted_chunk))
    
    def calculate_workers_for_duration(self, duration_seconds: int) -> int:
        """Calculate optimal number of workers based on duration"""
        model_config = GROQ_DEV_CONFIGS.get(self.model)
        if not model_config:
            model_config = GROQ_DEV_CONFIGS["whisper-large-v3"]
        
        base_workers = model_config.rpm // 60  # Conservative: 1 worker per RPM/60
        
        # Scale down for very large files to prevent 503 errors
        if duration_seconds > 14400:  # > 4 hours
            return max(2, base_workers // 4)
        elif duration_seconds > 7200:  # > 2 hours
            return max(3, base_workers // 3)
        elif duration_seconds > 3600:  # > 1 hour
            return max(4, base_workers // 2)
        else:
            return min(base_workers, 10)  # Cap at 10 for shorter files
    
    def preprocess_audio_optimized(self, input_file: str) -> Optional[str]:
        """Optimized audio preprocessing for Groq"""
        temp_dir = tempfile.gettempdir()
        output_file = os.path.join(temp_dir, f"{Path(input_file).stem}_groq_optimized.flac")
        
        try:
            cmd = [
                "ffmpeg",
                "-i", input_file,
                "-ar", str(OPTIMAL_SAMPLE_RATE),
                "-ac", str(OPTIMAL_CHANNELS),
                "-map", "0:a:0",
                "-c:a", "flac",
                "-compression_level", "0",  # Fastest compression
                "-threads", "0",
                "-y",
                "-loglevel", "error",
                output_file
            ]
            
            start_time = time.time()
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"FFmpeg preprocessing failed: {process.stderr}")
                return None
            
            elapsed = time.time() - start_time
            file_size = os.path.getsize(output_file) / (1024 * 1024)
            logger.info(f"Audio preprocessed in {elapsed:.2f}s → {file_size:.1f} MB")
            
            return output_file
            
        except Exception as e:
            logger.error(f"Audio preprocessing error: {e}")
            return None
    
    def split_audio_smart(self, file_path: str, chunk_duration: int) -> List[Dict]:
        """Smart audio splitting with overlap and size validation"""
        try:
            # Get total duration
            probe_cmd = [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            duration_output = subprocess.check_output(probe_cmd, text=True)
            total_duration = float(duration_output.strip())
            
            chunks = []
            temp_dir = tempfile.gettempdir()
            file_stem = Path(file_path).stem
            
            start_seconds = 0
            chunk_index = 1
            
            while start_seconds < total_duration:
                end_seconds = min(start_seconds + chunk_duration, total_duration)
                chunk_path = os.path.join(temp_dir, f"{file_stem}_chunk{chunk_index}.flac")
                
                # Create chunk with ffmpeg
                cmd = [
                    "ffmpeg",
                    "-ss", str(start_seconds),
                    "-i", file_path,
                    "-t", str(end_seconds - start_seconds),
                    "-ar", str(OPTIMAL_SAMPLE_RATE),
                    "-ac", str(OPTIMAL_CHANNELS),
                    "-c:a", "flac",
                    "-compression_level", "0",
                    "-threads", "0",
                    "-y",
                    "-loglevel", "error",
                    chunk_path
                ]
                
                process = subprocess.run(cmd, capture_output=True)
                
                if process.returncode == 0:
                    size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
                    
                    # Validate chunk size
                    if size_mb > MAX_CHUNK_SIZE_MB:
                        logger.warning(f"Chunk {chunk_index} too large: {size_mb:.1f}MB")
                        os.remove(chunk_path)
                        # Try with smaller duration
                        smaller_duration = chunk_duration // 2
                        end_seconds = min(start_seconds + smaller_duration, total_duration)
                        continue
                    
                    chunks.append({
                        "path": chunk_path,
                        "size_mb": size_mb,
                        "start_ms": start_seconds * 1000,
                        "end_ms": end_seconds * 1000,
                        "duration_ms": (end_seconds - start_seconds) * 1000,
                        "index": chunk_index
                    })
                    
                    logger.debug(f"Created chunk {chunk_index}: {size_mb:.1f}MB")
                else:
                    logger.error(f"Failed to create chunk {chunk_index}")
                
                start_seconds += chunk_duration - CHUNK_OVERLAP_SECONDS
                chunk_index += 1
            
            logger.info(f"Split audio into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Audio splitting error: {e}")
            return []
    
    def transcribe_chunk_with_rate_limiting(self, chunk_info: Dict, 
                                          max_retries: int = 5) -> Tuple[int, Optional[str]]:
        """Transcribe single chunk with advanced rate limiting"""
        if not self.groq_client:
            return chunk_info["index"], None
        
        chunk_index = chunk_info["index"]
        
        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                self.rate_limiter.wait_if_needed()
                
                start_time = time.time()
                
                with open(chunk_info["path"], "rb") as audio_file:
                    transcription = self.groq_client.audio.transcriptions.create(
                        file=audio_file,
                        model=self.model,
                        response_format="text",
                        temperature=0.0
                    )
                
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
                        time.sleep(wait_time)
                        continue
                
                elif "rate limit" in error_str.lower():
                    logger.warning(f"Chunk {chunk_index} hit rate limit")
                    self.rate_limiter.record_failure()
                    self.session_metrics["rate_limited_chunks"] += 1
                    
                    if attempt < max_retries - 1:
                        time.sleep(60)  # Wait 1 minute for rate limit reset
                        continue
                
                else:
                    logger.error(f"Chunk {chunk_index} error: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(5)  # Short wait for other errors
                        continue
        
        # Final failure cleanup
        self.session_metrics["failed_chunks"] += 1
        try:
            os.remove(chunk_info["path"])
        except:
            pass
        
        return chunk_index, None
    
    def transcribe_audio_enhanced(self, file_path: str, language: str = "en") -> Optional[str]:
        """Enhanced transcription with advanced rate limiting and error handling"""
        session_start = time.time()
        self.session_metrics["start_time"] = session_start
        
        try:
            logger.info("🚀 Starting enhanced transcription...")
            
            # Preprocess audio
            preprocessed_file = self.preprocess_audio_optimized(file_path)
            if not preprocessed_file:
                raise EnhancedTranscriptionError("Audio preprocessing failed")
            
            # Get audio duration
            audio = AudioSegment.from_file(preprocessed_file)
            duration_seconds = len(audio) // 1000
            self.session_metrics["total_duration"] = duration_seconds
            
            logger.info(f"Audio duration: {duration_seconds}s ({duration_seconds/60:.1f} min)")
            
            # Select optimal model if not specified
            if self.model == "auto":
                optimal_model = self.select_optimal_model(duration_seconds, language)
                logger.info(f"Auto-selected model: {optimal_model}")
                self.model = optimal_model
                self.rate_limiter = SyncRateLimiter(optimal_model)
            
            # Calculate optimal chunking strategy
            chunk_duration = self.calculate_optimal_chunk_duration(duration_seconds)
            logger.info(f"Using chunk duration: {chunk_duration}s")
            
            # Split audio into chunks
            chunks = self.split_audio_smart(preprocessed_file, chunk_duration)
            if not chunks:
                raise EnhancedTranscriptionError("Audio splitting failed")
            
            self.session_metrics["total_chunks"] = len(chunks)
            logger.info(f"Created {len(chunks)} chunks for processing")
            
            # Clean up preprocessed file
            if preprocessed_file != file_path:
                os.remove(preprocessed_file)
            
            # Calculate optimal worker count
            max_workers = self.calculate_workers_for_duration(duration_seconds)
            logger.info(f"Using {max_workers} parallel workers")
            
            # Process chunks in parallel
            transcriptions = {}
            failed_chunks = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all chunks
                future_to_chunk = {
                    executor.submit(self.transcribe_chunk_with_rate_limiting, chunk): chunk
                    for chunk in chunks
                }
                
                # Process results
                for future in concurrent.futures.as_completed(future_to_chunk):
                    chunk_index, transcription = future.result()
                    
                    if transcription:
                        transcriptions[chunk_index] = transcription
                    else:
                        failed_chunks.append(chunk_index)
                        logger.warning(f"Failed to transcribe chunk {chunk_index}")
            
            # Retry failed chunks with more conservative settings
            if failed_chunks:
                logger.warning(f"Retrying {len(failed_chunks)} failed chunks...")
                time.sleep(60)  # Cooldown before retry
                
                for chunk_index in failed_chunks:
                    chunk = next(c for c in chunks if c["index"] == chunk_index)
                    _, transcription = self.transcribe_chunk_with_rate_limiting(chunk, max_retries=3)
                    if transcription:
                        transcriptions[chunk_index] = transcription
            
            # Combine transcriptions in order
            full_transcription = " ".join(
                transcriptions.get(i, "") for i in range(1, len(chunks) + 1)
            ).strip()
            
            if not full_transcription:
                raise EnhancedTranscriptionError("No successful transcriptions")
            
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
            logger.info("=" * 60)
            
            return full_transcription
            
        except Exception as e:
            logger.error(f"Enhanced transcription failed: {e}")
            raise EnhancedTranscriptionError(f"Transcription failed: {e}")
        
        finally:
            # Cleanup any remaining temporary files
            temp_dir = tempfile.gettempdir()
            for file in Path(temp_dir).glob("*_groq_optimized.*"):
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


# Backward compatible function
def transcribe_audio_from_file(file_path: str, language: str = "en", 
                             progress_callback=None) -> Optional[str]:
    """
    Backward compatible enhanced transcription function
    
    Args:
        file_path: Path to audio file
        language: Language code (default: "en")
        progress_callback: Optional callback (not used in enhanced version)
    
    Returns:
        Transcribed text or None if failed
    """
    try:
        # Auto-select model based on file size
        audio = AudioSegment.from_file(file_path)
        duration_seconds = len(audio) // 1000
        
        transcriber = EnhancedAudioTranscriber("auto")
        result = transcriber.transcribe_audio_enhanced(file_path, language)
        
        # Log final metrics
        metrics = transcriber.get_session_metrics()
        logger.info(f"Session metrics: {metrics}")
        
        return result
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python enhanced_audio_transcriber.py <audio_file> [language]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    
    # Test enhanced transcription
    result = transcribe_audio_from_file(file_path, language)
    
    if result:
        print(f"\nTranscription successful ({len(result.split())} words):")
        print("-" * 50)
        print(result[:500] + "..." if len(result) > 500 else result)
    else:
        print("Transcription failed")
        sys.exit(1)