import os
import asyncio
import aiohttp
import logging
import subprocess
import time
from pathlib import Path
from pydub import AudioSegment
import yaml
import tempfile
from groq import Groq
import openai
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import multiprocessing
from typing import List, Dict, Tuple, Optional

# Initialize logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ULTRA-OPTIMIZED CONSTANTS FOR DEV TIER 🚀
MAX_FILE_SIZE_MB = 100  # Dev tier limit
MAX_CHUNK_SIZE_MB = 90  # Leave headroom for FLAC metadata
CHUNK_OVERLAP_SECONDS = 0.5  # Minimal overlap for maximum speed
CHUNK_DURATION_SECONDS = 60  # Default 60s for more parallelism!

# AGGRESSIVE CONCURRENCY FOR DEV TIER
MAX_CONCURRENT_REQUESTS = min(50, multiprocessing.cpu_count() * 5)  # Even more aggressive!
BATCH_SIZE = 10  # Process chunks in batches to avoid overwhelming

# Dev tier rate limits - UPDATED FOR MAXIMUM THROUGHPUT
GROQ_RPM_DEV = {
    "distil-whisper-large-v3-en": 100,
    "whisper-large-v3": 300,
    "whisper-large-v3-turbo": 400
}

# Audio processing optimization
OPTIMAL_SAMPLE_RATE = 16000  # Groq's preferred rate
OPTIMAL_CHANNELS = 1  # Mono for speech

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

def initialize_clients():
    """Initialize the API clients with keys from config"""
    config = load_config()
    if not config:
        return None, None
    
    groq_api_key = config.get("groq", {}).get("api_key")
    if not groq_api_key or groq_api_key == "YOUR_GROQ_API_KEY_HERE":
        logger.warning("Groq API key is missing or invalid in config.yaml.")
        groq_client = None
    else:
        groq_client = Groq(api_key=groq_api_key)
        
    openai_api_key = config.get("openai", {}).get("api_key")
    if not openai_api_key or openai_api_key == "YOUR_OPENAI_API_KEY_HERE":
        logger.warning("OpenAI API key is missing or invalid in config.yaml.")
        openai_client = None
    else:
        openai_client = openai.OpenAI(api_key=openai_api_key)
        
    return groq_client, openai_client

# Initialize global clients
groq_client, openai_client = initialize_clients()

# Ultra-fast thread-safe rate limiter
class OptimizedRateLimiter:
    def __init__(self, rpm):
        self.rpm = rpm
        self.lock = threading.Lock()
        self.requests = []
        self.burst_allowed = min(rpm // 4, 20)  # Allow burst processing
        
    def wait_if_needed(self):
        """Optimized rate limiting with burst support"""
        with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.requests = [t for t in self.requests if now - t < 60]
            
            # Allow burst processing for the first few requests
            if len(self.requests) < self.burst_allowed:
                self.requests.append(now)
                return
            
            if len(self.requests) >= self.rpm:
                # Calculate minimal wait time
                oldest_request = min(self.requests)
                wait_time = 60.01 - (now - oldest_request)  # Minimal buffer
                if wait_time > 0:
                    logger.debug(f"Rate limit pause: {wait_time:.2f}s")
                    time.sleep(wait_time)
                    return self.wait_if_needed()
                    
            self.requests.append(now)

def estimate_chunk_size_mb(duration_seconds: int, sample_rate: int = 16000) -> float:
    """Estimate chunk size in MB for FLAC format"""
    # FLAC compression ratio for speech is typically 50-60%
    uncompressed_size = duration_seconds * sample_rate * 2  # 16-bit mono
    compressed_size = uncompressed_size * 0.55  # Conservative estimate
    return compressed_size / (1024 * 1024)

def calculate_optimal_chunk_duration(file_duration_seconds: int, max_file_size_mb: float = 90) -> int:
    """
    DYNAMIC chunk duration calculator based on video length and Groq dev tier limits.
    
    Strategy:
    - Very short videos (<3 min): Process in ONE chunk (no splitting overhead!)
    - Short videos (3-10 min): Small chunks for parallelism
    - Medium videos (10-60 min): Balanced chunks
    - Long videos (>60 min): Larger chunks to avoid too many API calls
    """
    # VERY SHORT VIDEOS - Process in one gulp!
    if file_duration_seconds <= 180:  # 3 minutes or less
        # Check if it fits in file size limit (rough estimate)
        estimated_size_mb = (file_duration_seconds * 16000 * 2 * 0.55) / (1024 * 1024)
        if estimated_size_mb < max_file_size_mb:
            logger.info(f"🎯 Short video ({file_duration_seconds}s) - processing in ONE chunk!")
            return file_duration_seconds  # Return full duration - no splitting!
    
    # SHORT VIDEOS (3-10 minutes) - Optimize for parallelism
    if file_duration_seconds <= 600:
        # Target 5-10 chunks for good parallelism
        target_chunks = min(10, max(5, file_duration_seconds // 60))
        chunk_duration = file_duration_seconds // target_chunks
        return max(45, chunk_duration)  # At least 45 seconds per chunk
    
    # MEDIUM VIDEOS (10-30 minutes) - Balance parallelism and overhead
    elif file_duration_seconds <= 1800:
        # Target 15-20 chunks
        target_chunks = min(20, max(10, file_duration_seconds // 90))
        chunk_duration = file_duration_seconds // target_chunks
        return max(60, min(120, chunk_duration))  # 60-120 seconds per chunk
    
    # LONG VIDEOS (30-60 minutes) - Larger chunks but still parallel
    elif file_duration_seconds <= 3600:
        # Target 20-30 chunks
        target_chunks = min(30, max(15, file_duration_seconds // 120))
        chunk_duration = file_duration_seconds // target_chunks
        return max(90, min(180, chunk_duration))  # 90-180 seconds per chunk
    
    # VERY LONG VIDEOS (>60 minutes) - Avoid too many API calls
    else:
        # Target 30-40 chunks max
        target_chunks = min(40, max(20, file_duration_seconds // 180))
        chunk_duration = file_duration_seconds // target_chunks
        return max(120, min(300, chunk_duration))  # 120-300 seconds per chunk

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
            "-map", "0:a:0",  # First audio stream only
            "-c:a", "flac",
            "-compression_level", "0",  # Fastest
            "-threads", "0",  # Use all CPU cores
            "-y",
            "-loglevel", "error",  # Reduce output
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
                "-ss", str(pos['start']),  # Seek to start
                "-i", file_path,
                "-t", str(pos['duration']),  # Duration
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

def transcribe_chunk_ultrafast(chunk_info: Dict, language: str = "en", 
                             model: str = "distil-whisper-large-v3-en",
                             rate_limiter: Optional[OptimizedRateLimiter] = None) -> Tuple[int, Optional[str]]:
    """
    Ultra-fast chunk transcription with minimal overhead.
    """
    if groq_client is None:
        return chunk_info["index"], None
    
    # Rate limiting
    if rate_limiter:
        rate_limiter.wait_if_needed()
    
    try:
        start_time = time.time()
        
        with open(chunk_info["path"], "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=audio_file,
                model=model,
                prompt="",  # Empty prompt is faster
                response_format="text",
                language=language,
                temperature=0.0,
            )
        
        elapsed = time.time() - start_time
        audio_duration = chunk_info["duration_ms"] / 1000
        speed_factor = audio_duration / elapsed if elapsed > 0 else 0
        
        logger.info(f"Chunk {chunk_info['index']}: {elapsed:.2f}s ({speed_factor:.0f}x realtime)")
        
        # Immediate cleanup
        try:
            os.remove(chunk_info["path"])
        except:
            pass
            
        return chunk_info["index"], transcription
        
    except Exception as e:
        logger.error(f"Chunk {chunk_info['index']} error: {e}")
        try:
            os.remove(chunk_info["path"])
        except:
            pass
        return chunk_info["index"], None

def transcribe_audio_ultrafast(file_path: str, language: str = "en", fast_mode: bool = True, progress_callback=None) -> Optional[str]:
    """
    Ultra-fast audio transcription optimized for Groq dev tier.
    
    Args:
        file_path: Path to audio file
        language: Language code (default: "en")
        fast_mode: Use maximum speed optimizations (default: True)
        progress_callback: Optional callback function(stage, progress, message) for progress updates
    """
    try:
        total_start = time.time()
        
        # Select optimal model
        model = "distil-whisper-large-v3-en" if language == "en" else "whisper-large-v3-turbo"
        rpm_limit = GROQ_RPM_DEV.get(model, 100)
        
        logger.info(f"🚀 Starting ULTRA-FAST transcription with {model}")
        logger.info(f"   Rate limit: {rpm_limit} RPM, Fast mode: {fast_mode}")
        
        # Preprocess audio
        logger.info("⚡ Preprocessing audio...")
        if progress_callback:
            progress_callback("preprocessing", 0.0, "⚡ Preprocessing audio...")
        
        preprocessed_file = preprocess_audio_ultrafast(file_path)
        if not preprocessed_file:
            return None
        
        if progress_callback:
            progress_callback("preprocessing", 1.0, "✅ Audio preprocessing complete")
        
        # Get duration and calculate optimal chunk size
        audio = AudioSegment.from_file(preprocessed_file)
        duration_seconds = len(audio) // 1000
        
        # Calculate optimal approach
        optimal_chunk_duration = calculate_optimal_chunk_duration(duration_seconds)
        
        # Check if we should process in one chunk (no splitting!)
        if optimal_chunk_duration >= duration_seconds:
            logger.info(f"⚡ Processing entire {duration_seconds}s video in ONE request!")
            
            if progress_callback:
                progress_callback("transcribing", 0.0, f"⚡ Processing entire {duration_seconds}s audio in ONE request!")
            
            # No splitting needed - direct transcription
            transcription_start = time.time()
            
            # Create rate limiter
            rate_limiter = OptimizedRateLimiter(rpm_limit)
            
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
            
            _, transcription = transcribe_chunk_ultrafast(chunk_info, language, model, rate_limiter)
            
            transcription_time = time.time() - transcription_start
            
            if progress_callback:
                progress_callback("transcribing", 1.0, "✅ Transcription complete!")
            
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
            logger.info(f"🎯 Processed in ONE request - maximum efficiency!")
            logger.info("=" * 60)
            
            return transcription
        
        # For longer videos, continue with chunking strategy
        logger.info(f"📊 Audio: {duration_seconds}s, Chunk size: {optimal_chunk_duration}s")
        
        # Split audio
        split_start = time.time()
        if progress_callback:
            progress_callback("chunking", 0.0, f"✂️ Splitting audio into {optimal_chunk_duration}s chunks...")
        
        overlap = 0.5 if fast_mode else 1.0  # Minimal overlap for speed
        chunks = split_audio_ultrafast(preprocessed_file, optimal_chunk_duration, overlap)
        split_time = time.time() - split_start
        
        logger.info(f"✂️  Split into {len(chunks)} chunks in {split_time:.2f}s")
        if progress_callback:
            progress_callback("chunking", 1.0, f"✅ Split into {len(chunks)} chunks")
        
        # Log the chunking strategy for transparency
        if len(chunks) == 1:
            logger.info(f"📌 Strategy: Single chunk (no parallelism needed)")
        elif len(chunks) <= 5:
            logger.info(f"📌 Strategy: Few chunks ({len(chunks)}) for simple parallelism")
        elif len(chunks) <= 20:
            logger.info(f"📌 Strategy: Moderate chunks ({len(chunks)}) for balanced parallelism")
        else:
            logger.info(f"📌 Strategy: Many chunks ({len(chunks)}) for maximum parallelism")
        
        # Cleanup preprocessed file early
        if preprocessed_file != file_path and os.path.exists(preprocessed_file):
            os.remove(preprocessed_file)
        
        # Create rate limiter
        rate_limiter = OptimizedRateLimiter(rpm_limit)
        
        # ULTRA-FAST PARALLEL TRANSCRIPTION
        transcription_start = time.time()
        transcriptions = {}
        
        # Determine optimal worker count
        # Don't limit by chunk count - we want maximum parallelism!
        optimal_workers = min(
            MAX_CONCURRENT_REQUESTS,
            rpm_limit // 6,  # Leave headroom for rate limits
            30  # Practical limit for most systems
        )
        
        # But ensure we have at least as many workers as chunks
        optimal_workers = max(optimal_workers, min(len(chunks), 20))
        
        logger.info(f"🔥 Transcribing with {optimal_workers} parallel workers...")
        
        with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            # Submit all chunks
            futures = {
                executor.submit(
                    transcribe_chunk_ultrafast, 
                    chunk, 
                    language, 
                    model,
                    rate_limiter
                ): chunk for chunk in chunks
            }
            
            # Track progress
            completed = 0
            for future in as_completed(futures):
                chunk_index, transcription = future.result()
                completed += 1
                
                if transcription:
                    transcriptions[chunk_index] = transcription
                    
                # Progress update
                progress = completed / len(chunks)
                if progress_callback:
                    elapsed = time.time() - transcription_start
                    eta = (elapsed / completed) * (len(chunks) - completed) if completed > 0 else 0
                    progress_callback("transcribing", progress, 
                                    f"🎯 Transcribing: {progress*100:.0f}% ({completed}/{len(chunks)}) ETA: {eta:.1f}s")
                
                # Log update every 25%
                if completed % max(1, len(chunks) // 4) == 0:
                    logger.info(f"   Progress: {progress*100:.0f}% ({completed}/{len(chunks)}) ETA: {eta:.1f}s")
        
        transcription_time = time.time() - transcription_start
        
        # Combine transcriptions
        full_transcription = " ".join(
            transcriptions.get(i, "") for i in range(1, len(chunks) + 1)
        ).strip()
        
        # Calculate performance metrics
        total_time = time.time() - total_start
        actual_speed_factor = duration_seconds / total_time if total_time > 0 else 0
        transcription_speed = duration_seconds / transcription_time if transcription_time > 0 else 0
        
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
        logger.info(f"✅ Success rate: {len(transcriptions)}/{len(chunks)} chunks")
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
    """
    return transcribe_audio_ultrafast(file_path, language, fast_mode=True, progress_callback=progress_callback)

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