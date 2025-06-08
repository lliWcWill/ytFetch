import streamlit as st
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
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime
import re
from audio_transcriber import transcribe_audio_from_file, initialize_clients, load_config

# Set Streamlit page configuration
st.set_page_config(page_title="MultiProvider Transcribe", layout="wide")

# Load custom font
st.markdown('<link href="https://fonts.googleapis.com/css2?family=Source+Code+Pro&display=swap" rel="stylesheet">', unsafe_allow_html=True)

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

def transcribe_chunk(chunk_info, language="en", preferred_provider=None):
    """
    Transcribes a single audio chunk using the appropriate provider.
    
    Args:
        chunk_info (dict): Information about the chunk
        language (str): Language code (default: "en")
        preferred_provider (str, optional): Preferred provider if specified
    
    Returns:
        tuple: (transcription_text, quality_metrics) or (None, None) on failure
    """
    # Select provider
    provider = select_transcription_provider(chunk_info, preferred_provider)
    if not provider:
        return None, None
    
    # Get file path from chunk info
    audio_chunk_path = chunk_info["path"]
    
    # Check that the file exists
    if not os.path.exists(audio_chunk_path):
        logger.error(f"Chunk file not found: {audio_chunk_path}")
        return None, None
    
    # Use the selected provider
    if provider == "groq":
        logger.info(f"Using Groq for chunk {os.path.basename(audio_chunk_path)}")
        model = "distil-whisper-large-v3-en" if language == "en" else "whisper-large-v3"
        return transcribe_with_groq(audio_chunk_path, language, model)
    else:  # OpenAI
        logger.info(f"Using OpenAI for chunk {os.path.basename(audio_chunk_path)}")
        return transcribe_with_openai(audio_chunk_path, language)

def analyze_transcription_quality(quality_metrics):
    """
    Analyzes transcription quality metrics and identifies potential issues.
    
    Args:
        quality_metrics (list): List of dictionaries with quality metrics for each segment
        
    Returns:
        dict: Analysis results with statistics and flagged segments
    """
    if not quality_metrics:
        return None
    
    # For simplified metrics (when detailed metrics aren't available),
    # just return basic structure
    if all(m.get("avg_logprob", 0) == 0 and m.get("no_speech_prob", 0) == 0 for m in quality_metrics):
        return {
            "avg_logprob": {
                "min": 0,
                "max": 0,
                "mean": 0,
                "median": 0
            },
            "no_speech_prob": {
                "min": 0,
                "max": 0,
                "mean": 0,
                "median": 0
            },
            "flagged_segments": [],
            "quality_available": False,
            "providers_used": list(set(m.get("provider", "unknown") for m in quality_metrics))
        }
    
    # Extract metrics for analysis
    avg_logprobs = [segment["avg_logprob"] for segment in quality_metrics]
    no_speech_probs = [segment["no_speech_prob"] for segment in quality_metrics]
    
    # Calculate statistics
    analysis = {
        "avg_logprob": {
            "min": min(avg_logprobs),
            "max": max(avg_logprobs),
            "mean": sum(avg_logprobs) / len(avg_logprobs),
            "median": sorted(avg_logprobs)[len(avg_logprobs) // 2]
        },
        "no_speech_prob": {
            "min": min(no_speech_probs),
            "max": max(no_speech_probs),
            "mean": sum(no_speech_probs) / len(no_speech_probs),
            "median": sorted(no_speech_probs)[len(no_speech_probs) // 2]
        },
        "flagged_segments": [],
        "quality_available": True,
        "providers_used": list(set(m.get("provider", "unknown") for m in quality_metrics))
    }
    
    # Flag problematic segments
    for segment in quality_metrics:
        issues = []
        
        # Check avg_logprob (confidence)
        if segment["avg_logprob"] < QUALITY_THRESHOLDS["avg_logprob"]["poor"]:
            issues.append("Very low confidence")
        elif segment["avg_logprob"] < QUALITY_THRESHOLDS["avg_logprob"]["ok"]:
            issues.append("Low confidence")
            
        # Check no_speech_prob
        if segment["no_speech_prob"] > QUALITY_THRESHOLDS["no_speech_prob"]["poor"]:
            issues.append("Likely not speech")
        elif segment["no_speech_prob"] > QUALITY_THRESHOLDS["no_speech_prob"]["ok"]:
            issues.append("May not be clear speech")
            
        if issues:
            analysis["flagged_segments"].append({
                "segment_id": segment["id"],
                "time": f"{segment['start']:.2f}s - {segment['end']:.2f}s",
                "text": segment["text"],
                "issues": issues,
                "metrics": {
                    "avg_logprob": segment["avg_logprob"],
                    "no_speech_prob": segment["no_speech_prob"]
                },
                "provider": segment.get("provider", "unknown")
            })
    
    return analysis


def display_quality_analysis(quality_analysis):
    """
    Displays quality analysis information in a user-friendly format.
    
    Args:
        quality_analysis (dict): Quality analysis results
    """
    if not quality_analysis:
        st.warning("No quality analysis available.")
        return None
    
    # Show which providers were used
    providers_used = quality_analysis.get("providers_used", [])
    if providers_used:
        providers_str = ", ".join(providers_used)
        st.info(f"Transcription providers used: {providers_str}")
    
    # Check if quality metrics were available
    quality_available = quality_analysis.get("quality_available", True)
    
    # Display overall stats
    with st.expander("Transcription Quality Metrics", expanded=True):
        if not quality_available:
            st.info("Detailed quality metrics are not available for this transcription. Using simplified model.")
            return None
            
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Confidence Metrics (avg_logprob)")
            st.write("Higher (closer to 0) is better:")
            metrics = quality_analysis["avg_logprob"]
            st.write(f"- Minimum: {metrics['min']:.4f}")
            st.write(f"- Maximum: {metrics['max']:.4f}")
            st.write(f"- Average: {metrics['mean']:.4f}")
            st.write(f"- Median: {metrics['median']:.4f}")
            
            # Add interpretation
            if metrics['mean'] > QUALITY_THRESHOLDS["avg_logprob"]["good"]:
                st.success("Overall confidence is good.")
            elif metrics['mean'] > QUALITY_THRESHOLDS["avg_logprob"]["ok"]:
                st.info("Overall confidence is acceptable.")
            else:
                st.warning("Overall confidence is low.")
                
        with col2:
            st.subheader("Speech Detection (no_speech_prob)")
            st.write("Lower is better:")
            metrics = quality_analysis["no_speech_prob"]
            st.write(f"- Minimum: {metrics['min']:.4f}")
            st.write(f"- Maximum: {metrics['max']:.4f}")
            st.write(f"- Average: {metrics['mean']:.4f}")
            st.write(f"- Median: {metrics['median']:.4f}")
            
            # Add interpretation
            if metrics['mean'] < QUALITY_THRESHOLDS["no_speech_prob"]["good"]:
                st.success("Speech detection is good.")
            elif metrics['mean'] < QUALITY_THRESHOLDS["no_speech_prob"]["ok"]:
                st.info("Speech detection is acceptable.")
            else:
                st.warning("Speech detection issues detected.")
    
    # Create a container for charts
    chart_container = st.container()
    
    # Display flagged segments
    if quality_analysis["flagged_segments"]:
        with st.expander("Potentially Problematic Segments", expanded=False):
            st.warning(f"Found {len(quality_analysis['flagged_segments'])} segments that may have quality issues:")
            
            for i, segment in enumerate(quality_analysis["flagged_segments"]):
                provider = segment.get("provider", "unknown")
                st.markdown(f"**Segment {i+1}:** Time {segment['time']} (Provider: {provider})")
                st.markdown(f"*\"{segment['text']}\"*")
                st.markdown(f"**Issues:** {', '.join(segment['issues'])}")
                st.markdown(f"**Metrics:** Confidence = {segment['metrics']['avg_logprob']:.4f}, No Speech Prob = {segment['metrics']['no_speech_prob']:.4f}")
                if i < len(quality_analysis["flagged_segments"]) - 1:
                    st.markdown("---")
    else:
        st.success("No problematic segments detected.")
    
    return chart_container

def generate_quality_charts(quality_metrics, chart_container):
    """
    Generates charts visualizing transcription quality metrics
    
    Args:
        quality_metrics (list): List of segment quality metrics
        chart_container: Streamlit container to display charts
    """
    if not quality_metrics:
        chart_container.warning("No quality metrics available for visualization.")
        return
        
    # Check if we have real quality metrics or just placeholder values
    if all(m.get("avg_logprob", 0) == 0 and m.get("no_speech_prob", 0) == 0 for m in quality_metrics):
        chart_container.info("Detailed quality metrics aren't available for charting with this model/format.")
        return
    
    # Extract data for plotting
    segment_ids = [f"Seg {m['id']}" for m in quality_metrics]
    avg_logprobs = [m["avg_logprob"] for m in quality_metrics]
    no_speech_probs = [m["no_speech_prob"] for m in quality_metrics]
    providers = [m.get("provider", "unknown") for m in quality_metrics]
    
    # Create dataframe for plotting
    df = pd.DataFrame({
        "Segment": segment_ids,
        "Confidence (avg_logprob)": avg_logprobs,
        "No Speech Probability": no_speech_probs,
        "Provider": providers
    })
    
    with chart_container:
        col1, col2 = st.columns(2)
        
        with col1:
            # Confidence chart (avg_logprob)
            fig, ax = plt.subplots(figsize=(10, 5))
            bars = ax.bar(df["Segment"], df["Confidence (avg_logprob)"], color='skyblue')
            
            # Add threshold lines
            ax.axhline(y=QUALITY_THRESHOLDS["avg_logprob"]["good"], color='green', linestyle='--', alpha=0.7, label='Good')
            ax.axhline(y=QUALITY_THRESHOLDS["avg_logprob"]["ok"], color='orange', linestyle='--', alpha=0.7, label='OK')
            ax.axhline(y=QUALITY_THRESHOLDS["avg_logprob"]["poor"], color='red', linestyle='--', alpha=0.7, label='Poor')
            
            # Color bars based on quality and provider
            for i, v in enumerate(df["Confidence (avg_logprob)"]):
                if v < QUALITY_THRESHOLDS["avg_logprob"]["poor"]:
                    color = 'red'
                elif v < QUALITY_THRESHOLDS["avg_logprob"]["ok"]:
                    color = 'orange'
                else:
                    color = 'green'
                    
                # Add provider-specific distinction
                if df["Provider"][i] == "openai":
                    # Use darker variant for OpenAI
                    color = {'red': 'darkred', 'orange': 'darkorange', 'green': 'darkgreen'}[color]
                    
                bars[i].set_color(color)
            
            ax.set_title('Transcription Confidence by Segment')
            ax.set_xlabel('Segment')
            ax.set_ylabel('Confidence (avg_logprob)')
            ax.set_ylim(min(df["Confidence (avg_logprob)"]) - 0.1, 0)
            ax.legend()
            
            if len(segment_ids) > 15:
                plt.xticks(rotation=90)
            
            st.pyplot(fig)
        
        with col2:
            # No Speech Probability chart
            fig, ax = plt.subplots(figsize=(10, 5))
            bars = ax.bar(df["Segment"], df["No Speech Probability"], color='lightgreen')
            
            # Add threshold lines
            ax.axhline(y=QUALITY_THRESHOLDS["no_speech_prob"]["good"], color='green', linestyle='--', alpha=0.7, label='Good')
            ax.axhline(y=QUALITY_THRESHOLDS["no_speech_prob"]["ok"], color='orange', linestyle='--', alpha=0.7, label='OK')
            ax.axhline(y=QUALITY_THRESHOLDS["no_speech_prob"]["poor"], color='red', linestyle='--', alpha=0.7, label='Poor')
            
            # Color bars based on quality and provider
            for i, v in enumerate(df["No Speech Probability"]):
                if v > QUALITY_THRESHOLDS["no_speech_prob"]["poor"]:
                    color = 'red'
                elif v > QUALITY_THRESHOLDS["no_speech_prob"]["ok"]:
                    color = 'orange'
                else:
                    color = 'green'
                    
                # Add provider-specific distinction
                if df["Provider"][i] == "openai":
                    # Use darker variant for OpenAI
                    color = {'red': 'darkred', 'orange': 'darkorange', 'green': 'darkgreen'}[color]
                    
                bars[i].set_color(color)
            
            ax.set_title('No Speech Probability by Segment')
            ax.set_xlabel('Segment')
            ax.set_ylabel('No Speech Probability')
            ax.set_ylim(0, max(1.0, max(df["No Speech Probability"]) + 0.1))
            ax.legend()
            
            if len(segment_ids) > 15:
                plt.xticks(rotation=90)
                
            st.pyplot(fig)
            
        # Add provider legend
        st.write("**Provider color coding:**")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("- Groq: Light colors")
        with col2:
            st.markdown("- OpenAI: Dark colors")

def format_srt_time(seconds):
    """
    Format seconds into SRT time format (HH:MM:SS,mmm)
    
    Args:
        seconds (float): Time in seconds
        
    Returns:
        str: Formatted time string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def main():
    """
    Main function to handle audio transcription with enhanced UI.
    """
    st.markdown("""
        <style>
        body {
            font-family: 'Source Code Pro', monospace;
            background-color: #f0f2f6;
            color: #333333;
        }
        h1 {
            color: #0056b3;
            text-align: center;
            margin-bottom: 30px;
        }
        .stUploader, .stTextInput, .stRadio {
            margin-bottom: 20px;
        }
        .stButton button {
            background-color: #0056b3;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        .stButton button:hover {
            background-color: #004085;
        }
        .stTextArea textarea {
            border-radius: 5px;
            padding: 10px;
            font-family: 'Source Code Pro', monospace;
        }
        .stProgress {
            margin-top: 20px;
        }
        .quality-good {
            color: green;
            font-weight: bold;
        }
        .quality-ok {
            color: orange;
            font-weight: bold;
        }
        .quality-poor {
            color: red;
            font-weight: bold;
        }
        .provider-groq {
            background-color: #f8f9fa;
            padding: 5px;
            border-radius: 3px;
            border-left: 3px solid #0056b3;
        }
        .provider-openai {
            background-color: #f8f9fa;
            padding: 5px;
            border-radius: 3px;
            border-left: 3px solid #108a00;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("MultiProvider Transcribe")
    st.write("Upload an audio file or enter the path to transcribe with OpenAI and Groq APIs.")
    
    # Check available providers
    available_providers = []
    if groq_client is not None:
        available_providers.append("groq")
    if openai_client is not None:
        available_providers.append("openai")
    if not available_providers:
        st.error("No transcription providers are available. Please configure at least one API key in config.yaml.")
        st.stop()
        
    # Provider selection - this is now just for UI display
    provider_options = ["auto"] + available_providers
    provider_descriptions = {
        "auto": "Auto (optimize for size/quality)",
        "groq": "Groq API",
        "openai": "OpenAI API"
    }
    
    st.write("## Provider Settings")
    col1, col2 = st.columns([1, 2])
    with col1:
        selected_provider = st.selectbox(
            "Select transcription provider:", 
            provider_options,
            format_func=lambda x: provider_descriptions.get(x, x)
        )
        
    with col2:
        st.markdown("""
        **Provider selection guide:**
        - **Auto**: Uses OpenAI for larger files, Groq for smaller ones (best overall)
        - **Groq**: Good for shorter, simpler audio (rate limit: 20 RPM)
        - **OpenAI**: Best for longer or complex audio (rate limit: 7,500 RPM)
        """)
    
    # Set global variables based on UI selection
    global FILE_SIZE_THRESHOLD_MB  # Proper global declaration before assignments
    if selected_provider == "openai":
        FILE_SIZE_THRESHOLD_MB = 0  # Always use OpenAI
    elif selected_provider == "groq":
        FILE_SIZE_THRESHOLD_MB = 999  # Always use Groq
    else:
        # Auto mode - use default threshold
        pass
        
    # Model selection UI - Just for display now
    if "groq" in available_providers:
        st.write("### Groq Model")
        groq_model_info = {
            "distil-whisper-large-v3-en": "English only (fastest, lowest cost)",
            "whisper-large-v3-turbo": "Multilingual (fast, good cost/performance)",
            "whisper-large-v3": "Multilingual (highest accuracy, higher cost)"
        }
        
        groq_model_options = list(groq_model_info.keys())
        groq_model_descriptions = [f"{k}: {v}" for k, v in groq_model_info.items()]
        
        st.selectbox(
            "Select Groq model:", 
            range(len(groq_model_options)), 
            format_func=lambda i: groq_model_descriptions[i],
            disabled=(selected_provider == "openai")
        )
        
    if "openai" in available_providers:
        st.write("### OpenAI Model")
        openai_model_info = {
            "whisper-1": "Standard Whisper (best for most cases)",
            "gpt-4o-mini-transcribe": "GPT-4o Mini Transcribe (enhanced features)",
            "gpt-4o-transcribe": "GPT-4o Transcribe (highest quality, most expensive)"
        }
        
        openai_model_options = list(openai_model_info.keys())
        openai_model_descriptions = [f"{k}: {v}" for k, v in openai_model_info.items()]
        
        st.selectbox(
            "Select OpenAI model:", 
            range(len(openai_model_options)), 
            format_func=lambda i: openai_model_descriptions[i],
            disabled=(selected_provider == "groq")
        )
    
    # Language selection
    language = st.text_input("Language code (e.g., 'en' for English, 'fr' for French):", "en")
    
    # File input options
    st.write("## Upload or select file")
    uploaded_file = st.file_uploader("Drag and drop an audio file here", type=["wav", "mp3", "m4a", "flac"])
    file_path = st.text_input("Or enter the file path")

    # Processing
    full_transcription = None
    quality_analysis = None

    if uploaded_file is not None:
        # Save the uploaded file temporarily
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                temp_path = tmp_file.name

            if st.button("Start Transcription"):
                with st.spinner(f"Processing audio using {'OpenAI' if selected_provider == 'openai' else 'Groq' if selected_provider == 'groq' else 'Auto'} mode..."):
                    full_transcription = transcribe_audio_from_file(
                        temp_path, 
                        language
                    )
                    quality_analysis = None  # Quality analysis not available with headless function
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)  # Remove the temporary file

    elif st.button("Start Transcription") and file_path:
        file_path = Path(file_path)
        if not file_path.exists() or not file_path.is_file() or file_path.suffix.lower() not in [".wav", ".mp3", ".m4a", ".flac"]:
            st.error("Invalid file path. Please provide a valid .wav, .mp3, .m4a, or .flac file.")
            return

        with st.spinner(f"Processing audio using {'OpenAI' if selected_provider == 'openai' else 'Groq' if selected_provider == 'groq' else 'Auto'} mode..."):
            full_transcription = transcribe_audio_from_file(
                file_path, 
                language
            )
            quality_analysis = None  # Quality analysis not available with headless function

    # Display results
    if full_transcription:
        st.write("## Transcription Results")
        st.text_area("Transcription", full_transcription, height=300)
        
        # Timestamp formatting
        if st.checkbox("Format timestamps (if present in transcription)"):
            formatted_text = re.sub(r'\[\d+:\d+\]', lambda m: f"\n\n**{m.group(0)}**\n\n", full_transcription)
            st.markdown(formatted_text)
        
        # Add download options
        col1, col2 = st.columns(2)
        
        # Prepare base filename from uploaded file or path
        if uploaded_file is not None:
            base_filename = uploaded_file.name.rsplit('.', 1)[0]  # Remove extension
        elif file_path:
            base_filename = Path(file_path).stem  # Get filename without extension
        else:
            base_filename = "transcription"
            
        with col1:
            st.download_button(
                label="Download as TXT",
                data=full_transcription,
                file_name=f"{base_filename}_transcription.txt",
                mime="text/plain"
            )
        
        with col2:
            # Create a simple SRT format for download
            try:
                lines = full_transcription.split('\n')
                srt_content = ""
                counter = 1
                
                for i, line in enumerate(lines):
                    if line.strip():
                        # Simple timing - we don't have actual timestamps so use index
                        start_time = format_srt_time(i * 5)  # 5 seconds per line
                        end_time = format_srt_time((i + 1) * 5)
                        
                        srt_content += f"{counter}\n"
                        srt_content += f"{start_time} --> {end_time}\n"
                        srt_content += f"{line}\n\n"
                        counter += 1
                
                st.download_button(
                    label="Download as SRT",
                    data=srt_content,
                    file_name=f"{base_filename}_transcription.srt",
                    mime="text/plain"
                )
            except Exception as e:
                st.warning(f"Could not generate SRT format: {e}")
        
        # Display quality analysis
        st.write("## Quality Analysis")
        chart_container = display_quality_analysis(quality_analysis)
        
        # Generate quality charts if we have real metrics (not placeholders)
        if quality_analysis and chart_container:
            quality_available = quality_analysis.get("quality_available", False)
            if quality_available and "flagged_segments" in quality_analysis:
                all_metrics = []
                # Reconstruct the metrics list from flagged segments and add any missing fields
                for segment in quality_analysis["flagged_segments"]:
                    metrics = {
                        "id": segment["segment_id"],
                        "start": float(segment["time"].split("s")[0]),
                        "end": float(segment["time"].split(" - ")[1].split("s")[0]),
                        "text": segment["text"],
                        "avg_logprob": segment["metrics"]["avg_logprob"],
                        "no_speech_prob": segment["metrics"]["no_speech_prob"],
                        "provider": segment.get("provider", "unknown")
                    }
                    all_metrics.append(metrics)
                
                generate_quality_charts(all_metrics, chart_container)

if __name__ == "__main__":
    main()