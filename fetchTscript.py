from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from urllib.parse import urlparse, parse_qs
import sys
import yt_dlp
import xml.etree.ElementTree
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
    output_filename = os.path.join(output_dir, f"audio_{video_id}.mp3")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': f"audio_{video_id}.%(ext)s",
        'quiet': False,
        'no_warnings': False,
        'progress': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print(f"Audio successfully downloaded to: {output_filename}")
    except yt_dlp.utils.DownloadError as e:
        print(f"Error downloading audio: {e}")
    except Exception as e:
        print(f"Unexpected error while downloading audio: {e}")

def fetch_and_save_transcript(video_url):
    video_id = get_video_id_from_url(video_url)

    if not video_id:
        print(f"Error: Could not extract video ID from URL: {video_url}")
        return

    print(f"Fetching transcript for video ID: {video_id}...")

    try:
        # Fetch the transcript (tries to get a manually created one first, then auto-generated)
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to find English first, then any available
        transcript = None
        try:
            transcript = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
            except NoTranscriptFound:
                print("No English transcript found. Trying to fetch the first available transcript...")
                for available_transcript in transcript_list:
                    transcript = available_transcript
                    print(f"Found transcript in language: {transcript.language_code}")
                    break
        
        if not transcript:
            print("No transcript could be fetched for this video. Falling back to audio download...")
            download_audio_as_mp3(video_id)
            return

        # Fetch the actual transcript data
        transcript_data = transcript.fetch()

        full_transcript_text = ""
        for entry in transcript_data:
            full_transcript_text += entry['text'] + " "

        # Create a filename
        output_filename = f"transcript_{video_id}.txt"

        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(full_transcript_text.strip())
        
        print(f"Transcript successfully saved to: {output_filename}")

    except TranscriptsDisabled:
        print(f"Error: Transcripts are disabled for video: {video_id}. Falling back to audio download...")
        download_audio_as_mp3(video_id)
    except NoTranscriptFound:
        print(f"Error: No transcript found for video: {video_id}. Falling back to audio download...")
        download_audio_as_mp3(video_id)
    except VideoUnavailable:
        print(f"Error: Video {video_id} is unavailable (private, deleted, etc.).")
    except xml.etree.ElementTree.ParseError as e:
        print(f"Error: Failed to parse transcript data ({e}). Falling back to audio download...")
        download_audio_as_mp3(video_id)
    except Exception as e:
        print(f"An unexpected error occurred: {e}. Falling back to audio download...")
        download_audio_as_mp3(video_id)

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            video_url_input = sys.argv[1]
        else:
            video_url_input = input("Enter the YouTube video URL: ").strip()
        
        if video_url_input:
            fetch_and_save_transcript(video_url_input)
        else:
            print("No URL provided.")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(0)