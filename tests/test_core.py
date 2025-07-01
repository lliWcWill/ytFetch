"""Unit tests for core functions in appStreamlit.py."""
import pytest
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import functions to test
from misc.appStreamlit import (
    get_video_id_from_url,
    sanitize_filename,
    parse_iso8601_duration,
    srt_time_to_seconds,
    parse_srt_to_segments
)


class TestGetVideoIdFromUrl:
    """Test cases for get_video_id_from_url function."""
    
    def test_standard_youtube_url(self):
        """Test standard youtube.com/watch URLs."""
        assert get_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert get_video_id_from_url("https://youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert get_video_id_from_url("http://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    
    def test_youtube_url_with_extra_params(self):
        """Test YouTube URLs with additional parameters."""
        assert get_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s") == "dQw4w9WgXcQ"
        assert get_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf") == "dQw4w9WgXcQ"
    
    def test_short_youtube_url(self):
        """Test youtu.be short URLs."""
        assert get_video_id_from_url("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert get_video_id_from_url("http://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert get_video_id_from_url("https://youtu.be/dQw4w9WgXcQ?t=42") == "dQw4w9WgXcQ"
    
    def test_embed_url(self):
        """Test YouTube embed URLs."""
        assert get_video_id_from_url("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
        assert get_video_id_from_url("https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1") == "dQw4w9WgXcQ"
    
    def test_mobile_url(self):
        """Test mobile YouTube URLs."""
        assert get_video_id_from_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    
    def test_shorts_url(self):
        """Test YouTube Shorts URLs."""
        assert get_video_id_from_url("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    
    def test_invalid_urls(self):
        """Test invalid URLs."""
        assert get_video_id_from_url("") is None
        assert get_video_id_from_url(None) is None
        assert get_video_id_from_url("https://www.google.com") is None
        assert get_video_id_from_url("not a url") is None
        assert get_video_id_from_url("https://youtube.com/") is None
    
    def test_url_with_whitespace(self):
        """Test URLs with whitespace."""
        assert get_video_id_from_url("  https://www.youtube.com/watch?v=dQw4w9WgXcQ  ") == "dQw4w9WgXcQ"


class TestSanitizeFilename:
    """Test cases for sanitize_filename function."""
    
    def test_normal_filename(self):
        """Test normal filenames."""
        assert sanitize_filename("My Video Title") == "My Video Title"
        assert sanitize_filename("Video_123") == "Video_123"
    
    def test_invalid_characters(self):
        """Test removal of invalid characters."""
        assert sanitize_filename('Title: "Special" <Characters>') == 'Title Special Characters'
        assert sanitize_filename("Path/To\\File|Name") == "PathToFileName"
        assert sanitize_filename("Question? Mark* Asterisk") == "Question Mark Asterisk"
    
    def test_multiple_spaces(self):
        """Test multiple spaces are reduced to single space."""
        assert sanitize_filename("Too    Many     Spaces") == "Too Many Spaces"
    
    def test_leading_trailing_spaces_dots(self):
        """Test removal of leading/trailing spaces and dots."""
        assert sanitize_filename("  .Title.  ") == "Title"
        assert sanitize_filename("...Dots...") == "Dots"
    
    def test_long_filename(self):
        """Test truncation of long filenames."""
        long_name = "A" * 250
        result = sanitize_filename(long_name)
        assert len(result) == 200
        assert result == "A" * 200
    
    def test_empty_filename(self):
        """Test empty filename."""
        assert sanitize_filename("") == ""
        assert sanitize_filename("   ") == ""
        assert sanitize_filename("...") == ""


class TestParseISO8601Duration:
    """Test cases for parse_iso8601_duration function."""
    
    def test_simple_durations(self):
        """Test simple ISO 8601 durations."""
        assert parse_iso8601_duration("PT1M") == 60
        assert parse_iso8601_duration("PT30S") == 30
        assert parse_iso8601_duration("PT1H") == 3600
    
    def test_combined_durations(self):
        """Test combined ISO 8601 durations."""
        assert parse_iso8601_duration("PT1H30M") == 5400  # 90 minutes
        assert parse_iso8601_duration("PT2H45M30S") == 9930  # 2h 45m 30s
        assert parse_iso8601_duration("PT10M15S") == 615  # 10m 15s
    
    def test_edge_cases(self):
        """Test edge cases."""
        assert parse_iso8601_duration("") == 0
        assert parse_iso8601_duration("PT0S") == 0
        assert parse_iso8601_duration("P0D") == 0
    
    def test_invalid_durations(self):
        """Test invalid duration strings."""
        assert parse_iso8601_duration("invalid") == 0
        assert parse_iso8601_duration("1H30M") == 0  # Missing PT prefix
        assert parse_iso8601_duration(None) == 0


class TestSrtTimeToSeconds:
    """Test cases for srt_time_to_seconds function."""
    
    def test_standard_srt_time(self):
        """Test standard SRT time format."""
        assert srt_time_to_seconds("00:00:00,000") == 0
        assert srt_time_to_seconds("00:00:10,500") == 10.5
        assert srt_time_to_seconds("00:01:00,000") == 60
        assert srt_time_to_seconds("01:00:00,000") == 3600
    
    def test_combined_times(self):
        """Test combined times."""
        assert srt_time_to_seconds("01:23:45,678") == 5025.678
        assert srt_time_to_seconds("00:02:30,250") == 150.25
    
    def test_invalid_format(self):
        """Test invalid formats."""
        assert srt_time_to_seconds("invalid") == 0
        assert srt_time_to_seconds("00:00") == 0
        assert srt_time_to_seconds("") == 0


class TestParseSrtToSegments:
    """Test cases for parse_srt_to_segments function."""
    
    def test_single_subtitle(self):
        """Test parsing single subtitle."""
        srt_text = """1
00:00:00,000 --> 00:00:05,000
Hello World"""
        
        segments = parse_srt_to_segments(srt_text)
        assert len(segments) == 1
        assert segments[0]['text'] == "Hello World"
        assert segments[0]['start'] == 0
        assert segments[0]['duration'] == 5
    
    def test_multiple_subtitles(self):
        """Test parsing multiple subtitles."""
        srt_text = """1
00:00:00,000 --> 00:00:05,000
First subtitle

2
00:00:05,000 --> 00:00:10,000
Second subtitle

3
00:00:10,000 --> 00:00:15,000
Third subtitle"""
        
        segments = parse_srt_to_segments(srt_text)
        assert len(segments) == 3
        assert segments[0]['text'] == "First subtitle"
        assert segments[1]['text'] == "Second subtitle"
        assert segments[2]['text'] == "Third subtitle"
        assert segments[1]['start'] == 5
        assert segments[2]['start'] == 10
    
    def test_multiline_text(self):
        """Test parsing multiline subtitle text."""
        srt_text = """1
00:00:00,000 --> 00:00:05,000
Line one
Line two"""
        
        segments = parse_srt_to_segments(srt_text)
        assert len(segments) == 1
        assert segments[0]['text'] == "Line one\nLine two"
    
    def test_html_tags_removal(self):
        """Test removal of HTML tags."""
        srt_text = """1
00:00:00,000 --> 00:00:05,000
<i>Italic text</i> and <b>bold text</b>"""
        
        segments = parse_srt_to_segments(srt_text)
        assert len(segments) == 1
        assert segments[0]['text'] == "Italic text and bold text"
    
    def test_empty_srt(self):
        """Test empty SRT text."""
        assert parse_srt_to_segments("") == []
        assert parse_srt_to_segments("   \n\n   ") == []
    
    def test_malformed_srt(self):
        """Test malformed SRT text."""
        srt_text = """This is not valid SRT format"""
        segments = parse_srt_to_segments(srt_text)
        assert len(segments) == 0  # Should handle gracefully