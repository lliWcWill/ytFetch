import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from youtube_transcript_api.formatters import SRTFormatter, WebVTTFormatter, JSONFormatter, TextFormatter
from urllib.parse import urlparse, parse_qs
import json # For pretty printing JSON output

# --- Core Transcript Logic (adapted from your script) ---

def get_video_id_from_url(youtube_url):
    """Extracts video ID from various YouTube URL formats."""
    if not youtube_url:
        return None
    parsed_url = urlparse(youtube_url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
        if parsed_url.path == '/watch':
            p = parse_qs(parsed_url.query)
            video_id_list = p.get('v', [])
            if video_id_list:
                return video_id_list[0]
        if parsed_url.path.startswith('/embed/'):
            return parsed_url.path.split('/')[2]
        if parsed_url.path.startswith('/v/'):
            return parsed_url.path.split('/')[2]
        if parsed_url.path.startswith('/shorts/'):
            return parsed_url.path.split('/')[2]
    return None

def fetch_transcript_segments(video_id):
    """
    Fetches transcript segments for a given video ID.
    Returns a tuple: (segments_list, transcript_info, error_message)
    """
    if not video_id:
        return None, "", "Invalid Video ID."
    
    try:
        # Add timeout and retry logic for long videos
        import time
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Use a longer timeout for long videos
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    st.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise e
        
        transcript_obj = None
        transcript_info = ""
        
        # Get all available transcripts for debugging
        available_transcripts = list(transcript_list)
        debug_info = f"Available transcripts: {[(t.language, t.language_code, t.is_generated) for t in available_transcripts]}"
        
        # Prioritize English, then first available
        try:
            transcript_obj = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
            transcript_info = f"Manually created English transcript. {debug_info}"
        except NoTranscriptFound:
            try:
                transcript_obj = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                transcript_info = f"Auto-generated English transcript. {debug_info}"
            except NoTranscriptFound:
                if available_transcripts:
                    transcript_obj = available_transcripts[0]
                    transcript_info = f"Transcript in {transcript_obj.language} (code: {transcript_obj.language_code}), Generated: {transcript_obj.is_generated}. {debug_info}"
                else:
                    return None, "", f"No transcripts available for this video. {debug_info}"
        
        if not transcript_obj:
            return None, "", f"Could not select a transcript. {debug_info}"

        # Fetch segments with progress indication for long videos
        st.info("Fetching transcript segments (this might take a while for long videos)...")
        fetched_transcript = transcript_obj.fetch()
        
        # Handle the FetchedTranscript object - extract segments from the snippets property
        if hasattr(fetched_transcript, 'snippets'):
            # New API version returns FetchedTranscript object with snippets property
            fetched_segments = []
            for snippet in fetched_transcript.snippets:
                # Check if snippet is already a dict or if it's an object with attributes
                if isinstance(snippet, dict):
                    fetched_segments.append(snippet)
                else:
                    # Convert FetchedTranscriptSnippet objects to dictionaries
                    segment_dict = {
                        'text': snippet.text,
                        'start': snippet.start,
                        'duration': snippet.duration
                    }
                    fetched_segments.append(segment_dict)
        elif isinstance(fetched_transcript, list):
            # Old API version returns list directly - check if items are dicts or objects
            fetched_segments = []
            for item in fetched_transcript:
                if isinstance(item, dict):
                    fetched_segments.append(item)
                else:
                    # Convert objects to dictionaries
                    segment_dict = {
                        'text': getattr(item, 'text', ''),
                        'start': getattr(item, 'start', 0),
                        'duration': getattr(item, 'duration', 0)
                    }
                    fetched_segments.append(segment_dict)
        else:
            # Try to convert to list if it's iterable
            try:
                temp_list = list(fetched_transcript)
                fetched_segments = []
                for item in temp_list:
                    if isinstance(item, dict):
                        fetched_segments.append(item)
                    else:
                        segment_dict = {
                            'text': getattr(item, 'text', ''),
                            'start': getattr(item, 'start', 0),
                            'duration': getattr(item, 'duration', 0)
                        }
                        fetched_segments.append(segment_dict)
            except Exception as convert_error:
                return None, "", f"Could not convert transcript data to list: {convert_error}. Got type: {type(fetched_transcript)}. {debug_info}"
        
        # Validate segments
        if not fetched_segments:
            return None, "", f"Transcript object returned empty segments. {debug_info}"
        
        if not isinstance(fetched_segments, list):
            return None, "", f"Expected list of segments, got {type(fetched_segments)}. {debug_info}"
        
        if len(fetched_segments) == 0:
            return None, "", f"Transcript segments list is empty. {debug_info}"
        
        # Check if segments have the expected structure
        sample_segment = fetched_segments[0] if fetched_segments else {}
        if not isinstance(sample_segment, dict) or 'text' not in sample_segment:
            return None, "", f"Invalid segment structure. Sample: {sample_segment}. {debug_info}"
        
        return fetched_segments, transcript_info, None

    except TranscriptsDisabled:
        return None, "", f"Transcripts are disabled for video: {video_id}. This often happens with copyrighted content or creator settings."
    except NoTranscriptFound: # Should be caught by earlier logic, but as a fallback
        return None, "", f"No transcript found for video: {video_id}. The video may not have captions available."
    except VideoUnavailable:
        return None, "", f"Video {video_id} is unavailable (private, deleted, etc.)."
    except Exception as e:
        error_msg = str(e)
        if "HTTP Error 429" in error_msg:
            return None, "", f"Rate limit exceeded. Please wait a few minutes before trying again. Error: {error_msg}"
        elif "connection" in error_msg.lower():
            return None, "", f"Connection error. This might be due to network issues or IP blocking. Error: {error_msg}"
        elif "no element found" in error_msg.lower():
            return None, "", f"XML parsing error. This might be a temporary YouTube issue. Please try again in a moment. Error: {error_msg}"
        elif "line 1, column 0" in error_msg:
            return None, "", f"Empty response received. This might be a temporary YouTube issue. Please try again in a moment. Error: {error_msg}"
        else:
            return None, "", f"An unexpected error occurred: {error_msg}"

def format_segments(segments, output_format="txt"):
    """Formats fetched segments into the desired string format."""
    if not segments:
        return "No segments provided to format."
    
    if not isinstance(segments, list):
        return f"Expected list of segments, got {type(segments)}."
    
    if len(segments) == 0:
        return "Segments list is empty."

    try:
        # For very long videos, show progress
        if len(segments) > 1000:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
        # Convert segments to the format expected by the formatters
        # The formatters expect objects with .text, .start, .duration attributes
        # But we have dictionaries, so we need to convert them
        
        class TranscriptSegment:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration
        
        formatted_segments = []
        for segment in segments:
            if isinstance(segment, dict):
                # Convert dict to object format expected by formatters
                formatted_segment = TranscriptSegment(
                    text=segment.get('text', ''),
                    start=segment.get('start', 0),
                    duration=segment.get('duration', 0)
                )
                formatted_segments.append(formatted_segment)
            else:
                # Already in object format
                formatted_segments.append(segment)
            
        if output_format == "srt":
            formatter = SRTFormatter()
            if len(segments) > 1000:
                status_text.text("Formatting as SRT (this may take a while)...")
                progress_bar.progress(0.5)
            formatted_text = formatter.format_transcript(formatted_segments)
            if len(segments) > 1000:
                progress_bar.progress(1.0)
                status_text.empty()
                progress_bar.empty()
            return formatted_text
            
        elif output_format == "vtt":
            formatter = WebVTTFormatter()
            if len(segments) > 1000:
                status_text.text("Formatting as WebVTT (this may take a while)...")
                progress_bar.progress(0.5)
            formatted_text = formatter.format_transcript(formatted_segments)
            if len(segments) > 1000:
                progress_bar.progress(1.0)
                status_text.empty()
                progress_bar.empty()
            return formatted_text
            
        elif output_format == "json":
            if len(segments) > 1000:
                status_text.text("Formatting as JSON (this may take a while)...")
                progress_bar.progress(0.5)
            # For JSON, we can use the original dict format
            formatted_text = json.dumps(segments, indent=2, ensure_ascii=False)
            if len(segments) > 1000:
                progress_bar.progress(1.0)
                status_text.empty()
                progress_bar.empty()
            return formatted_text
            
        elif output_format == "txt":
            if len(segments) > 1000:
                status_text.text("Formatting as plain text (this may take a while)...")
                progress_bar.progress(0.5)
            
            # For plain text, we can do it manually to avoid formatter issues
            text_parts = []
            for segment in segments:
                if isinstance(segment, dict):
                    text_parts.append(segment.get('text', ''))
                else:
                    text_parts.append(getattr(segment, 'text', ''))
            
            formatted_text = ' '.join(text_parts)
            
            if len(segments) > 1000:
                progress_bar.progress(1.0)
                status_text.empty()
                progress_bar.empty()
            return formatted_text
        else:
            return f"Unsupported format: {output_format}"
            
    except Exception as e:
        return f"Error formatting transcript: {str(e)}"

# --- Streamlit App UI ---

st.set_page_config(page_title="YouTube Transcript Fetcher", layout="wide")
st.title("🎬 YouTube Transcript Fetcher")

# Initialize session state variables
if 'video_id' not in st.session_state:
    st.session_state.video_id = None
if 'fetched_segments' not in st.session_state:
    st.session_state.fetched_segments = None
if 'error_message' not in st.session_state:
    st.session_state.error_message = None
if 'selected_format' not in st.session_state:
    st.session_state.selected_format = "txt" # Default format
if 'transcript_type_info' not in st.session_state:
    st.session_state.transcript_type_info = ""
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False

# Debug mode toggle
st.session_state.debug_mode = st.checkbox("Enable Debug Mode", value=st.session_state.debug_mode)

# URL Input
url = st.text_input("Enter YouTube Video URL:", key="youtube_url_input")

if st.button("Fetch Transcript", key="fetch_button"):
    # Clear previous results
    st.session_state.video_id = None
    st.session_state.fetched_segments = None
    st.session_state.error_message = None
    st.session_state.transcript_type_info = ""

    if url:
        video_id = get_video_id_from_url(url)
        if video_id:
            st.session_state.video_id = video_id
            with st.spinner(f"Fetching transcript for Video ID: {video_id}... Please wait."):
                segments, transcript_info, error = fetch_transcript_segments(video_id)
                
                if error: # Error occurred
                    st.session_state.error_message = error
                    st.session_state.fetched_segments = None
                    st.session_state.transcript_type_info = ""
                else: # Successfully fetched segments
                    st.session_state.fetched_segments = segments
                    st.session_state.transcript_type_info = transcript_info
                    st.session_state.error_message = None
        else:
            st.session_state.error_message = "Could not extract Video ID from URL. Please enter a valid YouTube video URL."
    else:
        st.session_state.error_message = "Please enter a YouTube video URL."

# Display errors if any
if st.session_state.error_message:
    st.error(st.session_state.error_message)

# Display transcript and format options if segments are fetched
if st.session_state.fetched_segments:
    st.success(f"Transcript fetched successfully for Video ID: {st.session_state.video_id}!")
    if st.session_state.transcript_type_info:
        st.info(f"Transcript details: {st.session_state.transcript_type_info}")

    # Debug Information (only shown if debug mode is enabled)
    if st.session_state.debug_mode:
        st.markdown("---")
        st.subheader("🐛 Debug Information")
        st.write(f"**Type of fetched_segments:** `{type(st.session_state.fetched_segments)}`")
        st.write(f"**Is fetched_segments a list?** `{isinstance(st.session_state.fetched_segments, list)}`")
        st.write(f"**Is fetched_segments truthy?** `{bool(st.session_state.fetched_segments)}`")
        
        if isinstance(st.session_state.fetched_segments, list):
            st.write(f"**Number of segments:** `{len(st.session_state.fetched_segments)}`")
            st.write("**First 3 segments:**")
            st.json(st.session_state.fetched_segments[:3])
            
            # Show structure of individual segments
            if st.session_state.fetched_segments:
                first_segment = st.session_state.fetched_segments[0]
                st.write(f"**First segment type:** `{type(first_segment)}`")
                st.write(f"**First segment keys/attributes:** `{list(first_segment.keys()) if isinstance(first_segment, dict) else dir(first_segment)}`")
            
            # Additional debugging for long videos
            if len(st.session_state.fetched_segments) > 1000:
                st.warning(f"⚠️ Large transcript detected: {len(st.session_state.fetched_segments)} segments")
                st.write("**Segment distribution:**")
                first_time = st.session_state.fetched_segments[0].get('start', 0)
                last_segment = st.session_state.fetched_segments[-1]
                last_time = last_segment.get('start', 0) + last_segment.get('duration', 0)
                st.write(f"- Duration: {int(last_time // 3600)}h {int((last_time % 3600) // 60)}m {int(last_time % 60)}s")
                st.write(f"- Average segment length: {last_time / len(st.session_state.fetched_segments):.2f} seconds")
                
                # Check for potential issues
                empty_segments = sum(1 for seg in st.session_state.fetched_segments if not seg.get('text', '').strip())
                if empty_segments > 0:
                    st.warning(f"⚠️ Found {empty_segments} empty segments")
        else:
            st.write("**Value of fetched_segments:**")
            st.text(str(st.session_state.fetched_segments))
        st.markdown("---")

    st.subheader("📄 Formatted Transcript")

    format_options = ["txt", "srt", "vtt", "json"]
    # Use st.session_state.selected_format to make the radio button selection persistent
    selected_format = st.radio(
        "Choose output format:",
        options=format_options,
        index=format_options.index(st.session_state.selected_format), # Set default based on session state
        horizontal=True,
        key="format_selector"
    )
    
    # Update session state with the new selection
    st.session_state.selected_format = selected_format

    # Format and display the transcript based on selected format
    with st.spinner(f"Formatting transcript as {selected_format.upper()}..."):
        formatted_transcript_text = format_segments(st.session_state.fetched_segments, selected_format)
    
    # Check if formatting was successful
    if formatted_transcript_text.startswith("Error formatting transcript") or formatted_transcript_text == "No segments to format.":
        st.error(formatted_transcript_text)
        if st.session_state.debug_mode:
            st.write("**Debug:** Check the segments structure above for issues.")
    else:
        # Display the formatted transcript
        if selected_format == "json":
            st.code(formatted_transcript_text, language="json", line_numbers=True)
        elif selected_format in ["srt", "vtt"]:
            st.code(formatted_transcript_text, language="text", line_numbers=True)
        else: # txt
            st.text_area(
                label=f"{selected_format.upper()} Transcript (Scroll to see all content & copy from here)",
                value=formatted_transcript_text,
                height=400,
                key="transcript_display_area"
            )
        
        # Provide a download button
        file_extension = selected_format
        mime_type = "application/json" if selected_format == "json" else f"text/{selected_format}"
        
        st.download_button(
            label=f"📥 Download .{file_extension}",
            data=formatted_transcript_text,
            file_name=f"transcript_{st.session_state.video_id}.{file_extension}",
            mime=mime_type
        )

    # Additional helpful information
    if st.session_state.fetched_segments and isinstance(st.session_state.fetched_segments, list):
        total_duration = 0
        if st.session_state.fetched_segments:
            last_segment = st.session_state.fetched_segments[-1]
            if 'start' in last_segment and 'duration' in last_segment:
                total_duration = last_segment['start'] + last_segment['duration']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Segments", len(st.session_state.fetched_segments))
        with col2:
            st.metric("Video Duration", f"{int(total_duration // 60)}:{int(total_duration % 60):02d}")
        with col3:
            st.metric("Characters", len(formatted_transcript_text) if formatted_transcript_text else 0)

st.markdown("---")
st.caption("🚀 A Streamlit app to fetch and format YouTube video transcripts. Built with youtube-transcript-api.")