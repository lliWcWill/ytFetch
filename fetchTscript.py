from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from urllib.parse import urlparse, parse_qs
import sys
import yt_dlp
import xml.etree.ElementTree # Retained for now, though direct issue was not with XML parsing itself.
import os

def get_video_id_from_url(youtube_url):
    """Extracts video ID from various YouTube URL formats."""
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

def download_audio_as_mp3(video_id, output_dir="."):
    """Download the audio of a YouTube video as MP3 using yt-dlp."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    os.makedirs(output_dir, exist_ok=True)
    
    output_template = os.path.join(output_dir, f"audio_{video_id}.%(ext)s")
    final_mp3_path = os.path.join(output_dir, f"audio_{video_id}.mp3")

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_template,
        'quiet': False,
        'no_warnings': False,
        'progress': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        # Check if the mp3 file was actually created, as yt-dlp handles the conversion.
        if os.path.exists(final_mp3_path):
             print(f"Audio successfully downloaded to: {final_mp3_path}")
        else:
             # Fallback to check for webm if mp3 conversion failed for some reason, though ydl should error.
             webm_path = os.path.join(output_dir, f"audio_{video_id}.webm")
             if os.path.exists(webm_path):
                print(f"Audio downloaded (but not converted to MP3): {webm_path}")
             else:
                print(f"Audio download attempted. Target file {final_mp3_path} not found.")

    except yt_dlp.utils.DownloadError as e:
        print(f"Error downloading audio: {e}")
    except Exception as e:
        print(f"Unexpected error while downloading audio: {e}")

def fetch_and_save_transcript(video_url, output_dir="."):
    video_id = get_video_id_from_url(video_url)

    if not video_id:
        print(f"Error: Could not extract video ID from URL: {video_url}")
        return

    print(f"Fetching transcript for video ID: {video_id}...")
    
    os.makedirs(output_dir, exist_ok=True)

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        transcript_obj = None # Renamed to avoid confusion with 'transcript_data'
        try:
            transcript_obj = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
            print("Found manually created English transcript.")
        except NoTranscriptFound:
            print("No manually created English transcript found. Trying generated English transcript...")
            try:
                transcript_obj = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                print("Found generated English transcript.")
            except NoTranscriptFound:
                print("No English transcript found (manual or generated). Trying to fetch the first available transcript...")
                # transcript_list is iterable, yielding Transcript objects
                available_transcripts = list(transcript_list) # Convert iterator to list to safely access first element
                if available_transcripts:
                    transcript_obj = available_transcripts[0] # Get the first Transcript object
                    print(f"Found transcript in language: {transcript_obj.language} (code: {transcript_obj.language_code}), Generated: {transcript_obj.is_generated}")
        
        if not transcript_obj:
            print("No transcript could be selected for fetching. Falling back to audio download...")
            download_audio_as_mp3(video_id, output_dir=output_dir)
            return

        print(f"Fetching transcript data for language: {transcript_obj.language} ({transcript_obj.language_code})...")
        # transcript_obj is a Transcript object. .fetch() returns List[FetchedTranscriptSnippet]
        transcript_data = transcript_obj.fetch() 

        full_transcript_text = ""
        for entry in transcript_data: # entry is a FetchedTranscriptSnippet object
            # CORRECTED LINE: Access 'text' attribute using dot notation
            full_transcript_text += entry.text + " " 
            
        output_filename = os.path.join(output_dir, f"transcript_{video_id}.txt")

        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(full_transcript_text.strip())
        
        print(f"Transcript successfully saved to: {output_filename}")

    except TranscriptsDisabled:
        print(f"Error: Transcripts are disabled for video: {video_id}. Falling back to audio download...")
        download_audio_as_mp3(video_id, output_dir=output_dir)
    except NoTranscriptFound:
        print(f"Error: No transcript found for video: {video_id} (list_transcripts was empty or find_transcript failed). Falling back to audio download...")
        download_audio_as_mp3(video_id, output_dir=output_dir)
    except VideoUnavailable:
        print(f"Error: Video {video_id} is unavailable (private, deleted, etc.).")
    except xml.etree.ElementTree.ParseError as e: 
        print(f"Error: Failed to parse transcript data ({e}). This might indicate an issue with the library or an unexpected format. Falling back to audio download...")
        download_audio_as_mp3(video_id, output_dir=output_dir)
    except Exception as e:
        print(f"An unexpected error occurred: {e}. Falling back to audio download...")
        download_audio_as_mp3(video_id, output_dir=output_dir)

if __name__ == "__main__":
    script_output_directory = "video_outputs" 
    
    try:
        if len(sys.argv) > 1:
            video_url_input = sys.argv[1]
        else:
            video_url_input = input("Enter the YouTube video URL: ").strip()
        
        if video_url_input:
            fetch_and_save_transcript(video_url_input, output_dir=script_output_directory)
        else:
            print("No URL provided.")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(0)