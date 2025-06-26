import os
import asyncio
import aiohttp
import logging
import subprocess
import time
from pathlib import Path
from pydub import AudioSegment
import tempfile
from groq import Groq
import openai
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import multiprocessing
from typing import List, Dict, Tuple, Optional
import random  # Add this import

# Import the new config loader
from config_loader import load_config, get_api_key, get_performance_config, get_model_config

# Initialize logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load performance configuration
perf_config = get_performance_config()

# UPDATED CONSTANTS FOR BETTER LARGE FILE HANDLING
MAX_FILE_SIZE_MB = 100  # Dev tier limit
MAX_CHUNK_SIZE_MB = 90  # Leave headroom for FLAC metadata
CHUNK_OVERLAP_SECONDS = 0.5  # Minimal overlap for maximum speed
CHUNK_DURATION_SECONDS = 60  # Default 60s for more parallelism!

# CONSERVATIVE CONCURRENCY FOR LARGE FILES - Use config or defaults
MAX_CONCURRENT_REQUESTS = min(
    perf_config.get("max_concurrent_requests", 50), 
    multiprocessing.cpu_count() * 5
)  
BATCH_SIZE = 10  

# Dev tier rate limits
GROQ_RPM_DEV = {
    "distil-whisper-large-v3-en": 100,
    "whisper-large-v3": 300,
    "whisper-large-v3-turbo": 400
}

# Audio processing optimization
OPTIMAL_SAMPLE_RATE = 16000  
OPTIMAL_CHANNELS = 1

def initialize_clients():
    """Initialize the API clients with keys from config or Streamlit secrets"""
    # Get API keys using the new config loader
    groq_api_key = get_api_key("groq")
    openai_api_key = get_api_key("openai")
    
    # Initialize Groq client
    if not groq_api_key:
        logger.warning("Groq API key not found in config or secrets.")
        groq_client = None
    else:
        groq_client = Groq(api_key=groq_api_key)
        logger.info("Groq client initialized successfully")
        
    # Initialize OpenAI client
    if not openai_api_key:
        logger.warning("OpenAI API key not found in config or secrets.")
        openai_client = None
    else:
        openai_client = openai.OpenAI(api_key=openai_api_key)
        logger.info("OpenAI client initialized successfully")
        
    return groq_client, openai_client

# Initialize global clients
groq_client, openai_client = initialize_clients()

# NEW: Calculate optimal workers based on file size
def calculate_workers_for_file_size(duration_seconds: int, rpm_limit: int) -> int:
    """
    Calculate optimal number of workers based on file duration and rate limits.
    More conservative for larger files to avoid 503 errors.
    """
    if duration_seconds < 1800:  # < 30 minutes
        return min(10, rpm_limit // 10)
    elif duration_seconds < 7200:  # < 2 hours
        return min(5, rpm_limit // 15)
    elif duration_seconds < 14400:  # < 4 hours
        return min(3, rpm_limit // 20)
    else:  # 4+ hours - be very conservative
        return 2  # Only 2 workers for massive files

# NEW: Strict rate limiter without burst processing
class StrictRateLimiter:
    def __init__(self, rpm, conservative=False):
        self.rpm = rpm
        self.lock = threading.Lock()
        self.requests = []
        # For large files, be more conservative
        self.safety_factor = 0.5 if conservative else 0.8
        self.effective_rpm = int(rpm * self.safety_factor)
        logger.info(f"Rate limiter initialized: {self.effective_rpm} effective RPM (base: {rpm})")
        
    def wait_if_needed(self):
        """Strict rate limiting without burst allowance"""
        with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.requests = [t for t in self.requests if now - t < 60]
            
            if len(self.requests) >= self.effective_rpm:
                # Calculate wait time to next available slot
                oldest_request = self.requests[0]
                wait_time = 60.0 - (now - oldest_request) + 0.1  # Small buffer
                if wait_time > 0:
                    logger.debug(f"Rate limit wait: {wait_time:.2f}s")
                    time.sleep(wait_time)
                    return self.wait_if_needed()
                    
            self.requests.append(now)

# NEW: Select optimal model based on file size
def select_optimal_model(duration_seconds: int, language: str = "en") -> Tuple[str, int]:
    """
    Select the best model based on file size and language.
    For very large files, use models with higher rate limits.
    """
    # Get model preferences from config
    model_config = get_model_config()
    
    if duration_seconds > 14400:  # > 4 hours
        # Use turbo for better rate limits on massive files
        large_file_model = model_config.get("large_file_model", "whisper-large-v3-turbo")
        return large_file_model, GROQ_RPM_DEV.get(large_file_model, 400)
    elif duration_seconds > 7200:  # > 2 hours
        if language == "en":
            default_model = model_config.get("default", "distil-whisper-large-v3-en")
            return default_model, GROQ_RPM_DEV.get(default_model, 100)
        else:
            fallback_model = model_config.get("fallback", "whisper-large-v3")
            return fallback_model, GROQ_RPM_DEV.get(fallback_model, 300)
    else:
        # Default selection
        if language == "en":
            default_model = model_config.get("default", "distil-whisper-large-v3-en")
            return default_model, GROQ_RPM_DEV.get(default_model, 100)
        else:
            fallback_model = model_config.get("fallback", "whisper-large-v3")
            return fallback_model, GROQ_RPM_DEV.get(fallback_model, 300)

def estimate_chunk_size_mb(duration_seconds: int, sample_rate: int = 16000) -> float:
    """Estimate chunk size in MB for FLAC format"""
    uncompressed_size = duration_seconds * sample_rate * 2  
    compressed_size = uncompressed_size * 0.55  
    return compressed_size / (1024 * 1024)

def calculate_optimal_chunk_duration(file_duration_seconds: int, max_file_size_mb: float = 90) -> int:
    """
    DYNAMIC chunk duration calculator based on video length and Groq dev tier limits.
    """
    # VERY SHORT VIDEOS - Process in one gulp!
    if file_duration_seconds <= 180:  # 3 minutes or less
        estimated_size_mb = (file_duration_seconds * 16000 * 2 * 0.55) / (1024 * 1024)
        if estimated_size_mb < max_file_size_mb:
            logger.info(f"🎯 Short video ({file_duration_seconds}s) - processing in ONE chunk!")
            return file_duration_seconds  
    
    # SHORT VIDEOS (3-10 minutes) 
    if file_duration_seconds <= 600:
        target_chunks = min(10, max(5, file_duration_seconds // 60))
        chunk_duration = file_duration_seconds // target_chunks
        return max(45, chunk_duration) 
    
    # MEDIUM VIDEOS (10-30 minutes) 
    elif file_duration_seconds <= 1800:
        target_chunks = min(20, max(10, file_duration_seconds // 90))
        chunk_duration = file_duration_seconds // target_chunks
        return max(60, min(120, chunk_duration))  
    
    # LONG VIDEOS (30-60 minutes) 
    elif file_duration_seconds <= 3600:
        target_chunks = min(30, max(15, file_duration_seconds // 120))
        chunk_duration = file_duration_seconds // target_chunks
        return max(90, min(180, chunk_duration))  
    
    # VERY LONG VIDEOS (>60 minutes)
    else:
        # For 1-4 hour videos: 180-240 second chunks
        if file_duration_seconds <= 14400:  # Up to 4 hours
            target_chunks = min(60, max(30, file_duration_seconds // 240))
            chunk_duration = file_duration_seconds // target_chunks
            return max(120, min(240, chunk_duration))  
        # For 4-8 hour videos: 150-200 second chunks (smaller to avoid 503s)
        elif file_duration_seconds <= 28800:  # Up to 8 hours
            target_chunks = min(120, max(80, file_duration_seconds // 180))
            chunk_duration = file_duration_seconds // target_chunks
            return max(150, min(200, chunk_duration))  
        # For 8+ hour videos: 120-180 second chunks (even smaller)
        else:
            target_chunks = min(150, max(100, file_duration_seconds // 150))
            chunk_duration = file_duration_seconds // target_chunks
            return max(120, min(180, chunk_duration))  

def preprocess_audio_ultrafast(input_file: str, output_file: Optional[str] = None) -> Optional[str]:
    """
    Ultra-fast audio preprocessing with minimal overhead.
    """
    if output_file is None:
        temp_dir = tempfile.gettempdir()
        output_file = os.path.join(temp_dir, f"{Path(input_file).stem}_groq_optimized.flac")
    
    try:
        # Ultra-fast ffmpeg settings
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-ar", str(OPTIMAL_SAMPLE_RATE),
            "-ac", str(OPTIMAL_CHANNELS),
            "-map", "0:a:0",  
            "-c:a", "flac",
            "-compression_level", "0",  
            "-threads", "0",  
            "-y",
            "-loglevel", "error",  
            output_file
        ]
        
        start_time = time.time()
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {process.stderr}")
            return None
            
        elapsed = time.time() - start_time
        file_size = os.path.getsize(output_file) / (1024 * 1024)
        logger.info(f"Preprocessed in {elapsed:.2f}s → {output_file} ({file_size:.1f} MB)")
        return output_file
        
    except Exception as e:
        logger.error(f"Preprocessing error: {e}")
        return None

def split_audio_ultrafast(file_path: str, chunk_duration_seconds: int, 
                         overlap_seconds: float = CHUNK_OVERLAP_SECONDS) -> List[Dict]:
    """
    Ultra-fast audio splitting with parallel chunk creation.
    """
    try:
        # Get audio duration without loading entire file
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", 
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
            file_path
        ]
        duration_output = subprocess.check_output(probe_cmd, text=True)
        total_duration_seconds = float(duration_output.strip())
        
        chunks = []
        temp_dir = tempfile.gettempdir()
        file_stem = Path(file_path).stem
        
        # Calculate chunk positions
        chunk_positions = []
        start_seconds = 0
        chunk_index = 1
        
        while start_seconds < total_duration_seconds:
            end_seconds = min(start_seconds + chunk_duration_seconds, total_duration_seconds)
            chunk_positions.append({
                "index": chunk_index,
                "start": start_seconds,
                "end": end_seconds,
                "duration": end_seconds - start_seconds
            })
            start_seconds += chunk_duration_seconds - overlap_seconds
            chunk_index += 1
        
        logger.info(f"Splitting into {len(chunk_positions)} chunks of ~{chunk_duration_seconds}s each")
        
        # Create chunks in parallel using threading
        def create_chunk(pos):
            chunk_path = os.path.join(temp_dir, f"{file_stem}_chunk{pos['index']}.flac")
            
            # Ultra-fast chunk extraction
            cmd = [
                "ffmpeg",
                "-ss", str(pos['start']),  
                "-i", file_path,
                "-t", str(pos['duration']),  
                "-ar", str(OPTIMAL_SAMPLE_RATE),
                "-ac", str(OPTIMAL_CHANNELS),
                "-c:a", "flac",
                "-compression_level", "0",
                "-threads", "0",
                "-y",
                "-loglevel", "error",
                chunk_path
            ]
            
            start_time = time.time()
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if process.returncode == 0:
                size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
                elapsed = time.time() - start_time
                logger.debug(f"Chunk {pos['index']} created in {elapsed:.2f}s ({size_mb:.1f} MB)")
                
                return {
                    "path": chunk_path,
                    "size_mb": size_mb,
                    "start_ms": pos['start'] * 1000,
                    "end_ms": pos['end'] * 1000,
                    "duration_ms": pos['duration'] * 1000,
                    "index": pos['index']
                }
            else:
                logger.error(f"Failed to create chunk {pos['index']}")
                return None
        
        # Process chunks in parallel
        with ThreadPoolExecutor(max_workers=min(8, len(chunk_positions))) as executor:
            chunk_futures = [executor.submit(create_chunk, pos) for pos in chunk_positions]
            
            for future in as_completed(chunk_futures):
                result = future.result()
                if result:
                    chunks.append(result)
        
        # Sort by index to maintain order
        chunks.sort(key=lambda x: x['index'])
        return chunks
        
    except Exception as e:
        logger.error(f"Error splitting audio: {e}")
        return []

# IMPROVED: Transcribe chunk with better error handling
def transcribe_chunk_ultrafast(chunk_info: Dict, language: str = "en", 
                             model: str = "distil-whisper-large-v3-en",
                             rate_limiter: Optional[StrictRateLimiter] = None,
                             max_retries: int = 5) -> Tuple[int, Optional[str]]:
    """
    Ultra-fast chunk transcription with improved retry logic for 503 errors.
    """
    if groq_client is None:
        return chunk_info["index"], None
    
    base_delay = 5
    max_delay = 120  # Cap at 2 minutes
    
    for attempt in range(max_retries):
        # Rate limiting
        if rate_limiter:
            rate_limiter.wait_if_needed()
        
        try:
            start_time = time.time()
            
            with open(chunk_info["path"], "rb") as audio_file:
                transcription = groq_client.audio.transcriptions.create(
                    file=audio_file,
                    model=model,
                    prompt="",  
                    response_format="text",
                    language=language,
                    temperature=0.0,
                )
            
            elapsed = time.time() - start_time
            audio_duration = chunk_info["duration_ms"] / 1000
            speed_factor = audio_duration / elapsed if elapsed > 0 else 0
            
            logger.info(f"Chunk {chunk_info['index']}: {elapsed:.2f}s ({speed_factor:.0f}x realtime)")
            
            # Immediate cleanup on success
            try:
                os.remove(chunk_info["path"])
            except:
                pass
                
            return chunk_info["index"], transcription
            
        except Exception as e:
            error_str = str(e)
            
            # Handle 503 Service Unavailable specifically
            if "503" in error_str or "Service Unavailable" in error_str:
                # Exponential backoff with jitter
                wait_time = min(base_delay * (2 ** attempt) + random.uniform(0, 5), max_delay)
                
                if attempt < max_retries - 1:
                    logger.warning(f"Chunk {chunk_info['index']} got 503 (attempt {attempt + 1}), "
                                 f"waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    
                    # After multiple 503s, add cooldown
                    if attempt >= 2:  
                        logger.info("Adding cooldown period after multiple 503s...")
                        time.sleep(30)  
                else:
                    logger.error(f"Chunk {chunk_info['index']} failed after {max_retries} retries: {e}")
            else:
                logger.error(f"Chunk {chunk_info['index']} error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(base_delay)
                
        # Cleanup on final failure
        try:
            os.remove(chunk_info["path"])
        except:
            pass
            
    return chunk_info["index"], None

def transcribe_audio_ultrafast(file_path: str, language: str = "en", fast_mode: bool = True) -> Optional[str]:
    """
    Ultra-fast audio transcription optimized for Groq dev tier with improved large file handling.
    """
    try:
        total_start = time.time()
        
        # Preprocess audio
        logger.info("⚡ Preprocessing audio...")
        preprocessed_file = preprocess_audio_ultrafast(file_path)
        if not preprocessed_file:
            return None
        
        # Get duration and calculate optimal chunk size
        audio = AudioSegment.from_file(preprocessed_file)
        duration_seconds = len(audio) // 1000
        
        # Select optimal model based on file size
        model, rpm_limit = select_optimal_model(duration_seconds, language)
        
        logger.info(f"🚀 Starting transcription with {model}")
        logger.info(f"   Rate limit: {rpm_limit} RPM, Fast mode: {fast_mode}")
        
        # Special handling for MASSIVE videos
        if duration_seconds > 14400:  # Over 4 hours
            hours = duration_seconds / 3600
            logger.warning(f"⚠️  MASSIVE VIDEO DETECTED: {hours:.1f} hours!")
            logger.info("   Using conservative settings to avoid service errors...")
            logger.info("   This may take some time, but it will complete!")
        
        # Calculate optimal approach
        optimal_chunk_duration = calculate_optimal_chunk_duration(duration_seconds)
        
        # Check if we should process in one chunk 
        if optimal_chunk_duration >= duration_seconds:
            logger.info(f"⚡ Processing entire {duration_seconds}s video in ONE request!")
            
            # Create rate limiter
            rate_limiter = StrictRateLimiter(rpm_limit, conservative=False)
            
            # Single transcription
            file_size_mb = os.path.getsize(preprocessed_file) / (1024 * 1024)
            chunk_info = {
                "path": preprocessed_file,
                "size_mb": file_size_mb,
                "start_ms": 0,
                "end_ms": duration_seconds * 1000,
                "duration_ms": duration_seconds * 1000,
                "index": 1
            }
            
            _, transcription = transcribe_chunk_ultrafast(chunk_info, language, model, rate_limiter, max_retries=5)
            
            if not transcription:
                logger.error("Failed to transcribe audio")
                return None
                
            total_time = time.time() - total_start
            speed_factor = duration_seconds / total_time if total_time > 0 else 0
            
            logger.info("=" * 60)
            logger.info("🏁 TRANSCRIPTION COMPLETE - SINGLE CHUNK MODE")
            logger.info("=" * 60)
            logger.info(f"📝 Audio duration: {duration_seconds}s ({duration_seconds/60:.1f} min)")
            logger.info(f"⚡ Total time: {total_time:.2f}s")
            logger.info(f"🚀 Speed: {speed_factor:.1f}x realtime")
            logger.info("=" * 60)
            
            return transcription
        
        # For longer videos, continue with chunking strategy
        logger.info(f"📊 Audio: {duration_seconds}s, Chunk size: {optimal_chunk_duration}s")
        
        # Split audio
        split_start = time.time()
        overlap = 0.5 if fast_mode else 1.0  
        chunks = split_audio_ultrafast(preprocessed_file, optimal_chunk_duration, overlap)
        split_time = time.time() - split_start
        
        logger.info(f"✂️  Split into {len(chunks)} chunks in {split_time:.2f}s")
        
        # Cleanup preprocessed file early
        if preprocessed_file != file_path and os.path.exists(preprocessed_file):
            os.remove(preprocessed_file)
        
        # Create rate limiter - be conservative for large files
        conservative = duration_seconds > 7200  # 2+ hours
        rate_limiter = StrictRateLimiter(rpm_limit, conservative=conservative)
        
        # Calculate optimal workers - CONSERVATIVE FOR LARGE FILES
        optimal_workers = calculate_workers_for_file_size(duration_seconds, rpm_limit)
        
        logger.info(f"🔥 Transcribing with {optimal_workers} parallel workers...")
        
        # PARALLEL TRANSCRIPTION WITH BETTER ERROR HANDLING
        transcription_start = time.time()
        transcriptions = {}
        failed_chunks = []
        
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            # Submit all chunks
            futures = {
                executor.submit(
                    transcribe_chunk_ultrafast, 
                    chunk, 
                    language, 
                    model,
                    rate_limiter,
                    max_retries=5
                ): chunk for chunk in chunks
            }
            
            # Track progress
            completed = 0
            for future in as_completed(futures):
                chunk_index, transcription = future.result()
                completed += 1
                
                if transcription:
                    transcriptions[chunk_index] = transcription
                else:
                    failed_chunks.append(chunk_index)
                    logger.warning(f"Failed chunk: {chunk_index}")
                    
                # Progress update 
                progress = completed / len(chunks) * 100
                if completed % max(1, len(chunks) // 4) == 0:
                    elapsed = time.time() - transcription_start
                    eta = (elapsed / completed) * (len(chunks) - completed)
                    logger.info(f"   Progress: {progress:.0f}% ({completed}/{len(chunks)}) ETA: {eta:.1f}s")
                    
                    # Add cooldown if high failure rate
                    if len(failed_chunks) > len(chunks) * 0.1:  # >10% failure
                        logger.warning("High failure rate detected, adding cooldown...")
                        time.sleep(30)
        
        transcription_time = time.time() - transcription_start
        
        # Retry failed chunks with even more conservative settings
        if failed_chunks:
            logger.warning(f"Retrying {len(failed_chunks)} failed chunks...")
            time.sleep(60)  # Wait 1 minute before retrying
            
            # Retry with only 1 worker and longer delays
            retry_rate_limiter = StrictRateLimiter(rpm_limit // 2, conservative=True)
            
            for chunk_index in failed_chunks:
                chunk = next(c for c in chunks if c["index"] == chunk_index)
                _, transcription = transcribe_chunk_ultrafast(
                    chunk, language, model, retry_rate_limiter, max_retries=3
                )
                if transcription:
                    transcriptions[chunk_index] = transcription
        
        # Combine transcriptions
        full_transcription = " ".join(
            transcriptions.get(i, "") for i in range(1, len(chunks) + 1)
        ).strip()
        
        # Calculate performance metrics
        total_time = time.time() - total_start
        actual_speed_factor = duration_seconds / total_time if total_time > 0 else 0
        transcription_speed = duration_seconds / transcription_time if transcription_time > 0 else 0
        success_rate = len(transcriptions) / len(chunks) * 100
        
        # Performance report
        logger.info("=" * 60)
        logger.info("🏁 TRANSCRIPTION COMPLETE - PERFORMANCE REPORT")
        logger.info("=" * 60)
        logger.info(f"📝 Audio duration: {duration_seconds:,} seconds ({duration_seconds/60:.1f} minutes)")
        logger.info(f"⚡ Total time: {total_time:.2f} seconds")
        logger.info(f"🚀 Transcription time: {transcription_time:.2f} seconds")
        logger.info(f"📊 Preprocessing time: {split_time:.2f} seconds")
        logger.info(f"🔥 Overall speed: {actual_speed_factor:.1f}x realtime")
        logger.info(f"💨 Transcription speed: {transcription_speed:.1f}x realtime")
        logger.info(f"✅ Success rate: {success_rate:.1f}% ({len(transcriptions)}/{len(chunks)} chunks)")
        logger.info("=" * 60)
        
        return full_transcription
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return None

# Backward compatible function
def transcribe_audio_from_file(file_path: str, language: str = "en", progress_callback=None) -> Optional[str]:
    """
    Backward compatible ultra-fast transcription.
    Uses fast mode by default for maximum speed!
    
    Args:
        file_path: Path to audio file
        language: Language code (default: "en")
        progress_callback: Optional callback for progress updates (for compatibility)
    """
    # Log if progress_callback was provided (we don't use it in the optimized version)
    if progress_callback:
        logger.info("Note: progress_callback provided but not used in optimized transcription")
    
    return transcribe_audio_ultrafast(file_path, language, fast_mode=True)

# Performance testing function
def benchmark_transcription(file_path: str):
    """
    Benchmark transcription performance.
    """
    logger.info("🏃 Running transcription benchmark...")
    
    # Test with different configurations
    configs = [
        {"chunks": 180, "workers": 10},
        {"chunks": 300, "workers": 20},
        {"chunks": 600, "workers": 30},
    ]
    
    for config in configs:
        global CHUNK_DURATION_SECONDS, MAX_CONCURRENT_REQUESTS
        CHUNK_DURATION_SECONDS = config["chunks"]
        MAX_CONCURRENT_REQUESTS = config["workers"]
        
        logger.info(f"\nTesting: {config['chunks']}s chunks, {config['workers']} workers")
        start = time.time()
        result = transcribe_audio_ultrafast(file_path)
        elapsed = time.time() - start
        
        if result:
            logger.info(f"   Time: {elapsed:.2f}s")
            logger.info(f"   Words: {len(result.split())}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "benchmark":
        benchmark_transcription(sys.argv[2])
    elif len(sys.argv) > 1:
        result = transcribe_audio_from_file(sys.argv[1])
        if result:
            print(f"\nTranscription ({len(result.split())} words):")
            print("-" * 50)
            print(result[:500] + "..." if len(result) > 500 else result)