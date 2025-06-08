import os
import requests
import logging
import subprocess
import json
from pathlib import Path
from pydub import AudioSegment
from tqdm import tqdm
import yaml
import tempfile
import io
import time
from groq import Groq
import openai
import re

# Initialize logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define constants
MAX_FILE_SIZE_MB = 25  # Free tier limit for both Groq and OpenAI
MAX_CHUNK_SIZE_MB = 24  # Slightly less than the limit to account for overhead
CHUNK_OVERLAP_SECONDS = 5  # Add some overlap between chunks to maintain context
QUALITY_THRESHOLDS = {
    "avg_logprob": {
        "good": -0.1,
        "ok": -0.3,
        "poor": -0.5
    },
    "no_speech_prob": {
        "good": 0.1,
        "ok": 0.3,
        "poor": 0.5
    }
}
# Providers rate limits and thresholds
GROQ_RPM = 20  # Groq rate limit of 20 requests per minute
OPENAI_RPM = 7500  # OpenAI rate limit of 7500 requests per minute
FILE_SIZE_THRESHOLD_MB = 5  # Use OpenAI for files larger than this threshold

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
    
    # Initialize Groq client
    groq_api_key = config.get("groq", {}).get("api_key")
    if not groq_api_key or groq_api_key == "YOUR_GROQ_API_KEY_HERE":
        logger.warning("Groq API key is missing or invalid in config.yaml. Some functionality will be limited.")
        groq_client = None
    else:
        groq_client = Groq(api_key=groq_api_key)
        
    # Initialize OpenAI client
    openai_api_key = config.get("openai", {}).get("api_key")
    if not openai_api_key or openai_api_key == "YOUR_OPENAI_API_KEY_HERE":
        logger.warning("OpenAI API key is missing or invalid in config.yaml. Some functionality will be limited.")
        openai_client = None
    else:
        openai_client = openai.OpenAI(api_key=openai_api_key)
        
    return groq_client, openai_client

# Initialize global clients
groq_client, openai_client = initialize_clients()

# Track API usage to respect rate limits
api_usage = {
    "groq": {
        "last_minute_count": 0,
        "last_minute_start": time.time()
    },
    "openai": {
        "last_minute_count": 0,
        "last_minute_start": time.time()
    }
}

def update_api_usage(provider):
    """
    Update API usage tracking for rate limiting
    
    Args:
        provider (str): 'groq' or 'openai'
    
    Returns:
        bool: True if rate limit is not exceeded, False otherwise
    """
    current_time = time.time()
    
    # Reset counter if a minute has passed
    if current_time - api_usage[provider]["last_minute_start"] > 60:
        api_usage[provider]["last_minute_count"] = 1
        api_usage[provider]["last_minute_start"] = current_time
        return True
    
    # Increment counter
    api_usage[provider]["last_minute_count"] += 1
    
    # Check if rate limit is exceeded
    if provider == "groq" and api_usage["groq"]["last_minute_count"] > GROQ_RPM:
        logger.warning(f"Groq rate limit exceeded ({GROQ_RPM} RPM). Waiting...")
        return False
    elif provider == "openai" and api_usage["openai"]["last_minute_count"] > OPENAI_RPM:
        logger.warning(f"OpenAI rate limit exceeded ({OPENAI_RPM} RPM). Waiting...")
        return False
        
    return True

def preprocess_audio(input_file, output_file=None):
    """
    Preprocess audio file to 16kHz mono FLAC format as recommended by both Groq and OpenAI.
    
    Args:
        input_file (str): Path to input audio file
        output_file (str, optional): Path to output file. If None, creates a temp file.
        
    Returns:
        str: Path to the preprocessed audio file
    """
    if output_file is None:
        # Create a temporary file with .flac extension
        temp_dir = tempfile.gettempdir()
        output_file = os.path.join(temp_dir, f"{Path(input_file).stem}_processed.flac")
    
    try:
        # Use ffmpeg to convert audio to 16kHz mono FLAC
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-ar", "16000",  # 16kHz sample rate
            "-ac", "1",      # mono channel
            "-map", "0:a",   # select audio stream
            "-c:a", "flac",  # FLAC codec
            "-y",            # overwrite output file if exists
            output_file
        ]
        
        # Run ffmpeg process
        process = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if process.returncode != 0:
            logger.error(f"Error preprocessing audio: {process.stderr}")
            return None
            
        logger.info(f"Preprocessed audio saved to {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error preprocessing audio: {e}")
        return None

def get_chunk_length_ms(file_path, max_size_mb=MAX_CHUNK_SIZE_MB):
    """
    Calculates the appropriate chunk length in milliseconds such that the exported file
    does not exceed max_size_mb.
    """
    try:
        audio = AudioSegment.from_file(file_path)
        if len(audio) == 0:
            return 0  # Handle empty audio files
        duration_ms = len(audio)
        max_size_bytes = max_size_mb * 1024 * 1024
        
        # Estimate chunk length based on desired size and total duration
        # This is an approximation, as actual size depends on audio content and format
        # We'll start with a reasonable guess (e.g., 60 seconds) and adjust
        
        chunk_length_ms = 60000  # Start with 60 seconds
        chunk_length_ms = min(chunk_length_ms, duration_ms)  # Don't exceed total duration
        
        # Estimate size of a chunk of this length exported to WAV format
        # Assuming 16kHz mono, 2 bytes per sample (16-bit)
        bytes_per_second = 16000 * 2
        estimated_size_bytes = (chunk_length_ms / 1000) * bytes_per_second
        
        # Adjust chunk length if estimated size is too large
        if estimated_size_bytes > max_size_bytes and bytes_per_second > 0:
            chunk_length_ms = int((max_size_bytes / bytes_per_second) * 1000)
            chunk_length_ms = max(chunk_length_ms, 1000)  # Ensure minimum chunk length (1 second)
            chunk_length_ms = min(chunk_length_ms, duration_ms)  # Don't exceed total duration

        # Ensure chunk length doesn't exceed the total audio duration
        chunk_length_ms = min(chunk_length_ms, duration_ms)

        logger.info(f"Calculated chunk length: {chunk_length_ms} ms")
        return chunk_length_ms
    except Exception as e:
        logger.error(f"Error calculating chunk length: {e}")
        return None

def split_audio_with_overlap(file_path, chunk_length_ms, overlap_seconds=CHUNK_OVERLAP_SECONDS):
    """
    Splits the audio file into smaller chunks with overlap, ensuring exported chunks
    don't exceed MAX_CHUNK_SIZE_MB.
    """
    try:
        audio = AudioSegment.from_file(file_path)
        chunks = []
        file_path = Path(file_path)  # Convert to Path object if it's a string
        overlap_ms = overlap_seconds * 1000
        
        # Use proper path handling to ensure correct file paths
        temp_dir = os.path.dirname(file_path) if os.path.dirname(file_path) else "."
        file_stem = os.path.basename(file_path.stem)
        
        start_ms = 0
        chunk_index = 1  # Start from 1 instead of 0
        while start_ms < len(audio):
            end_ms = min(start_ms + chunk_length_ms, len(audio))
            chunk = audio[start_ms:end_ms]
            
            # Export the chunk with proper path handling
            chunk_file_path = os.path.join(temp_dir, f"{file_stem}_chunk{chunk_index}.wav")
            chunk.export(chunk_file_path, format="wav")
            
            # Get file size in MB
            file_size_mb = os.path.getsize(chunk_file_path) / (1024 * 1024)
            
            # Debug logging
            logger.info(f"Created chunk file: {chunk_file_path} ({file_size_mb:.2f} MB)")
            
            # Check actual size of the exported file
            actual_size_bytes = os.path.getsize(chunk_file_path)
            actual_size_mb = actual_size_bytes / (1024 * 1024)
            
            if actual_size_mb > MAX_CHUNK_SIZE_MB:
                logger.warning(f"Chunk {chunk_index} ({actual_size_mb:.2f} MB) is larger than {MAX_CHUNK_SIZE_MB} MB. Reducing chunk size.")
                # If a chunk is too large, reduce its duration and try again
                new_chunk_length_ms = int((MAX_CHUNK_SIZE_MB / actual_size_mb) * chunk_length_ms)
                new_chunk_length_ms = max(new_chunk_length_ms, 1000)  # Ensure minimum chunk length
                new_chunk_length_ms = min(new_chunk_length_ms, len(audio) - start_ms)  # Don't exceed remaining duration
                
                if new_chunk_length_ms <= 0:
                    logger.error(f"Could not reduce chunk {chunk_index} to a valid size. Skipping.")
                    os.remove(chunk_file_path)  # Remove the oversized chunk file
                    start_ms += chunk_length_ms - overlap_ms  # Move forward
                    if start_ms < 0:
                        start_ms += chunk_length_ms
                    chunk_index += 1  # Increment chunk index
                    continue  # Skip to the next iteration
                
                # Update chunk_length_ms for the next iteration (or just recalculate)
                chunk_length_ms = new_chunk_length_ms
                
                # Recalculate end_ms with the new length
                end_ms = min(start_ms + chunk_length_ms, len(audio))
                chunk = audio[start_ms:end_ms]
                
                # Re-export the smaller chunk
                os.remove(chunk_file_path)  # Remove the previous oversized file
                chunk_file_path = os.path.join(temp_dir, f"{file_stem}_chunk{chunk_index}.wav")
                chunk.export(chunk_file_path, format="wav")
                actual_size_bytes = os.path.getsize(chunk_file_path)
                actual_size_mb = actual_size_bytes / (1024 * 1024)
                
                if actual_size_mb > MAX_CHUNK_SIZE_MB:
                    logger.error(f"Chunk {chunk_index} ({actual_size_mb:.2f} MB) is still larger than {MAX_CHUNK_SIZE_MB} MB after reduction. Skipping.")
                    os.remove(chunk_file_path)  # Remove the oversized chunk file
                    start_ms += chunk_length_ms - overlap_ms  # Move forward
                    if start_ms < 0:
                        start_ms += chunk_length_ms
                    chunk_index += 1  # Increment chunk index
                    continue  # Skip to the next iteration

            # Store chunk info with metadata
            chunks.append({
                "path": chunk_file_path,
                "size_mb": actual_size_mb,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": end_ms - start_ms
            })
            
            # Update start position for the next chunk, considering overlap
            start_ms += chunk_length_ms - overlap_ms
            if start_ms < 0:  # Handle cases where overlap is larger than chunk length
                start_ms += chunk_length_ms  # Move forward by full chunk length
            
            chunk_index += 1  # Increment chunk index
                
        return chunks
    except Exception as e:
        logger.error(f"Error splitting audio file with overlap: {e}")
        return []

def transcribe_with_groq(audio_chunk_path, language="en", model="distil-whisper-large-v3-en"):
    """
    Transcribes a single audio chunk using the Groq Whisper model.
    
    Args:
        audio_chunk_path (str): Path to audio chunk file
        language (str): Language code (default: "en")
        model (str): Model to use (default: "distil-whisper-large-v3-en")
    
    Returns:
        tuple: (transcription_text, quality_metrics) or (None, None) on failure
    """
    if groq_client is None:
        logger.error("Groq client not initialized. Cannot transcribe with Groq.")
        return None, None
        
    retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(retries):
        # Check rate limit
        if not update_api_usage("groq"):
            time.sleep(60 - (time.time() - api_usage["groq"]["last_minute_start"]) + 1)
            continue
            
        try:
            with open(audio_chunk_path, "rb") as audio_file:
                # First, try with json format which will give us a structured object
                transcription = groq_client.audio.transcriptions.create(
                    file=audio_file,
                    model=model,
                    prompt="Please transcribe the audio content accurately.",
                    response_format="json",  # Use simple json format
                    language=language,
                    temperature=0.0,
                )
                
                # For basic JSON responses, we don't get segment-level metrics but at least get the text
                # Create a simplified quality metrics structure
                quality_metrics = [{
                    "id": 0,
                    "start": 0,
                    "end": 0,
                    "text": transcription.text,
                    "avg_logprob": 0,  # Default values since not available
                    "no_speech_prob": 0,
                    "provider": "groq"
                }]
                
                return transcription.text, quality_metrics
                
        except Exception as e:
            logger.error(f"Groq transcription failed (attempt {attempt+1}/{retries}): {e}")
            
            # Try with text format as fallback
            try:
                with open(audio_chunk_path, "rb") as audio_file:
                    text_response = groq_client.audio.transcriptions.create(
                        file=audio_file,
                        model=model,
                        prompt="Please transcribe the audio content accurately.",
                        response_format="text",  # Plain text as fallback
                        language=language,
                        temperature=0.0,
                    )
                    
                    # For text responses, just return the text string directly
                    # Create minimal quality metrics
                    simple_metrics = [{
                        "id": 0,
                        "start": 0,
                        "end": 0,
                        "text": text_response,
                        "avg_logprob": 0,
                        "no_speech_prob": 0,
                        "provider": "groq"
                    }]
                    
                    return text_response, simple_metrics
            except Exception as inner_e:
                logger.error(f"Groq text format fallback also failed: {inner_e}")
            
            # Handle various error conditions
            if "rate limit" in str(e).lower() or "429" in str(e):
                # Rate limit error - wait longer
                longer_delay = retry_delay * 2
                logger.warning(f"Groq rate limit hit. Waiting {longer_delay} seconds...")
                time.sleep(longer_delay)
            elif "too large" in str(e).lower():
                # File size error - can't retry with same file
                logger.error("File too large for Groq processing.")
                return None, None
            elif "auth" in str(e).lower():
                # Authentication error - can't retry
                logger.error("Authentication error with Groq API.")
                return None, None
            else:
                # General error - standard retry
                if attempt < retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
            
    logger.error(f"Failed to transcribe chunk with Groq after {retries} attempts")
    return None, None

def transcribe_with_openai(audio_chunk_path, language="en", model="whisper-1"):
    """
    Transcribes a single audio chunk using the OpenAI Whisper model.
    
    Args:
        audio_chunk_path (str): Path to audio chunk file
        language (str): Language code (default: "en")
        model (str): Model to use (default: "whisper-1")
    
    Returns:
        tuple: (transcription_text, quality_metrics) or (None, None) on failure
    """
    if openai_client is None:
        logger.error("OpenAI client not initialized. Cannot transcribe with OpenAI.")
        return None, None
        
    retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(retries):
        # Check rate limit
        if not update_api_usage("openai"):
            time.sleep(60 - (time.time() - api_usage["openai"]["last_minute_start"]) + 1)
            continue
            
        try:
            with open(audio_chunk_path, "rb") as audio_file:
                # Try to get verbose json response with metrics when using the appropriate models
                try_verbose = model in ["gpt-4o-transcribe", "gpt-4o-mini-transcribe"]
                response_format = "verbose_json" if try_verbose else "json"
                
                transcription = openai_client.audio.transcriptions.create(
                    file=audio_file,
                    model=model,
                    prompt="Please transcribe the audio content accurately.",
                    response_format=response_format,
                    language=language if language else None  # OpenAI doesn't like empty string
                )
                
                # Check if we got a verbose response with segments
                if try_verbose and hasattr(transcription, "segments") and transcription.segments:
                    # Extract quality metrics from the segments
                    quality_metrics = []
                    
                    for segment in transcription.segments:
                        metrics = {
                            "id": segment.id,
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text,
                            "avg_logprob": segment.avg_logprob,
                            "no_speech_prob": segment.no_speech_prob,
                            "provider": "openai"
                        }
                        quality_metrics.append(metrics)
                else:
                    # For standard json responses, we just get the text
                    quality_metrics = [{
                        "id": 0,
                        "start": 0,
                        "end": 0,
                        "text": transcription.text,
                        "avg_logprob": 0,  # Default values since not available
                        "no_speech_prob": 0,
                        "provider": "openai"
                    }]
                
                return transcription.text, quality_metrics
                
        except Exception as e:
            logger.error(f"OpenAI transcription failed (attempt {attempt+1}/{retries}): {e}")
            
            # Handle various error conditions
            if "rate limit" in str(e).lower() or "429" in str(e):
                # Rate limit error - wait longer
                longer_delay = retry_delay * 2
                logger.warning(f"OpenAI rate limit hit. Waiting {longer_delay} seconds...")
                time.sleep(longer_delay)
            elif "too large" in str(e).lower():
                # File size error - can't retry with same file
                logger.error("File too large for OpenAI processing.")
                return None, None
            elif "auth" in str(e).lower() or "invalid api key" in str(e).lower():
                # Authentication error - can't retry
                logger.error("Authentication error with OpenAI API.")
                return None, None
            else:
                # General error - standard retry
                if attempt < retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
            
    logger.error(f"Failed to transcribe chunk with OpenAI after {retries} attempts")
    return None, None

def select_transcription_provider(chunk_info, preferred_provider=None):
    """
    Selects the appropriate transcription provider based on file size, rate limits, and preferences.
    
    Args:
        chunk_info (dict): Information about the chunk
        preferred_provider (str, optional): User's preferred provider if any
    
    Returns:
        str: 'openai' or 'groq'
    """
    # If only one provider is available, use that
    if groq_client is None and openai_client is not None:
        return "openai"
    elif openai_client is None and groq_client is not None:
        return "groq"
    elif groq_client is None and openai_client is None:
        logger.error("No transcription providers available. Please configure at least one API key.")
        return None
    
    # Honor user preference if specified
    if preferred_provider in ["openai", "groq"]:
        return preferred_provider
    
    # Use OpenAI for larger files (higher quality, higher rate limits)
    if chunk_info["size_mb"] > FILE_SIZE_THRESHOLD_MB:
        return "openai"
    
    # Check rate limits - if Groq is approaching limit, use OpenAI
    current_time = time.time()
    if (current_time - api_usage["groq"]["last_minute_start"] <= 60 and 
        api_usage["groq"]["last_minute_count"] >= GROQ_RPM * 0.8):
        return "openai"
    
    # Default to Groq for smaller files to save OpenAI credits
    return "groq"

def transcribe_audio_from_file(file_path, language="en"):
    """
    Process the audio file: preprocess, split if necessary, transcribe, and analyze quality.
    This is the headless version without Streamlit dependencies.
    
    Args:
        file_path (str): Path to the audio file
        language (str): Language code (default: "en")
        
    Returns:
        str: Full transcription text or None on failure
    """
    try:
        # Preprocess the audio file
        logger.info("Preprocessing audio for optimal transcription...")
        preprocessed_file = preprocess_audio(file_path)
        
        if not preprocessed_file:
            logger.error("Failed to preprocess audio file.")
            return None
            
        logger.info("Audio preprocessing complete.")
        
        # Get audio information
        audio = AudioSegment.from_file(preprocessed_file)
        duration_seconds = len(audio) // 1000
        logger.info(f"The audio file is {duration_seconds} seconds long.")
        
        # For longer files, apply 10-minute limit as per spec
        if duration_seconds > 600:  # 10 minutes
            logger.warning(f"Audio is longer than 10 minutes ({duration_seconds}s). Aborting transcription.")
            return None

        # Get chunk length and split audio
        chunk_length_ms = get_chunk_length_ms(preprocessed_file)
        if chunk_length_ms is None or chunk_length_ms <= 0:
            logger.error("Could not determine valid chunk length.")
            return None

        chunks = split_audio_with_overlap(preprocessed_file, chunk_length_ms)
        if not chunks:
            logger.error("Failed to split audio file into chunks.")
            return None

        # Process each chunk
        all_transcriptions = []
        
        # Show what chunks are available
        logger.info(f"Generated {len(chunks)} chunks for processing.")
        
        for i, chunk in enumerate(chunks):
            chunk_num = i + 1
            logger.info(f"Transcribing chunk {chunk_num} of {len(chunks)}...")
            
            # Check that the chunk file exists before trying to transcribe
            if not os.path.exists(chunk["path"]):
                logger.warning(f"Chunk file not found: {chunk['path']}. Skipping.")
                continue
                
            # Determine provider based on file size
            if chunk["size_mb"] > FILE_SIZE_THRESHOLD_MB and openai_client is not None:
                provider = "openai"
            elif groq_client is not None:
                provider = "groq"
            elif openai_client is not None:
                provider = "openai"
            else:
                logger.error("No transcription providers available.")
                return None
                
            # Transcribe the chunk with the selected provider
            if provider == "openai":
                transcribed_text, quality_metrics = transcribe_with_openai(chunk["path"], language)
            else:  # groq
                transcribed_text, quality_metrics = transcribe_with_groq(chunk["path"], language)
            
            if transcribed_text:
                all_transcriptions.append(transcribed_text)
            else:
                logger.warning(f"Failed to transcribe chunk {chunk_num}. Skipping.")
                
            # Clean up chunk file after transcription
            try:
                os.remove(chunk["path"])
                logger.info(f"Removed chunk file: {chunk['path']}")
            except Exception as e:
                logger.warning(f"Failed to remove chunk file {chunk['path']}: {e}")

        # Clean up preprocessed file
        if preprocessed_file != file_path and os.path.exists(preprocessed_file):
            os.remove(preprocessed_file)
        
        logger.info("Transcription complete!")
        
        return "\n".join(all_transcriptions)

    except Exception as e:
        logger.error(f"An error occurred during audio processing: {e}")
        return None