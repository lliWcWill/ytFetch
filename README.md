# ytFetch: YouTube Transcript & Multi-Provider Audio Transcription Toolkit

## Description
ytFetch is a comprehensive toolkit for extracting YouTube video transcripts and transcribing audio files using cutting-edge AI providers. This dual-component solution combines the convenience of YouTube's native transcript API with the power of **Groq** and **OpenAI's Whisper** models for high-quality audio transcription. Perfect for content creators, researchers, and developers who need reliable text extraction from video and audio sources.

## Features Overview 🌟

### YouTube Transcript Extraction
#### Command-Line Tool (`fetchTscript.py`)
- **Smart URL Parsing**: Supports all YouTube URL formats (`youtu.be`, `youtube.com/watch`, `/embed/`, `/v/`, `/shorts/`)
- **Intelligent Transcript Hierarchy**: Prioritizes manually-created → auto-generated → any available language
- **Automatic Fallback**: Downloads high-quality MP3 audio when transcripts aren't available
- **Multi-language Support**: Attempts English first, then falls back to any available language
- **Organized Output**: Saves files to `video_outputs/` directory

#### Web Interface (`appStreamlit.py`) 🆕

![Peek 2025-05-29 17-15](https://github.com/user-attachments/assets/0a7e36d8-af5c-4903-a731-899f22d06433)


- **User-Friendly GUI**: Beautiful Streamlit interface for transcript extraction
- **Multiple Export Formats**: Plain text (TXT), SubRip (SRT), WebVTT, and JSON
- **Real-time Feedback**: Shows transcript type (manual/auto-generated) and language
- **Debug Mode**: Optional detailed information for troubleshooting
- **Download Options**: One-click download in your preferred format
- **Video Metrics**: Displays segment count, duration, and character count

### Multi-Provider Audio Transcription (`transcribeVid.py`)
- **Dual-Provider Intelligence**: Seamlessly switches between **Groq** and **OpenAI** APIs based on file size and performance
- **Smart Chunking**: Automatically splits large files with configurable overlap for optimal processing
- **Quality Analysis**: Real-time confidence metrics and speech detection analysis
- **Professional Output**: Export options in TXT and SRT subtitle formats
- **Web Interface**: Beautiful Streamlit app with drag-and-drop functionality

## Installation & Setup ⚡

### Prerequisites
This tool requires **ffmpeg** for audio processing:

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Arch Linux  
sudo pacman -S ffmpeg

# macOS (Homebrew)
brew install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg

# Windows (Scoop)
scoop install ffmpeg
```

### Installation Steps
1. **Clone the repository**:
   ```bash
   git clone https://github.com/lliWcWill/ytFetch.git
   cd ytFetch
   ```

2. **Set up virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install youtube-transcript-api yt-dlp streamlit groq openai pydub tqdm pyyaml matplotlib pandas numpy
   ```

## Configuration 🔧

Set up your API keys in `config.yaml`:

1. **Copy the example config**:
   ```bash
   cp config.yaml.example config.yaml
   ```

2. **Add your API keys**:
   ```yaml
   groq:
     api_key: "your-groq-api-key-here"
   
   openai:
     api_key: "your-openai-api-key-here"
   ```

> **🔒 Security Note**: Your `config.yaml` is automatically ignored by git to protect your API keys!

## Usage Examples 🚀

### YouTube Transcript Extraction

#### Command-Line Tool
**Basic URL processing**:
```bash
python fetchTscript.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

**Interactive mode**:
```bash
python fetchTscript.py
# Enter URL when prompted
```

**Output**: Creates `video_outputs/transcript_VIDEO_ID.txt` or falls back to `video_outputs/audio_VIDEO_ID.mp3`

#### Web Interface 🆕
**Launch the Streamlit app**:
```bash
streamlit run appStreamlit.py
```

**Access at**: `http://localhost:8501`

**Features**:
- 📝 **Easy Input**: Just paste YouTube URL and click "Fetch Transcript"
- 🌐 **Format Selection**: Choose between TXT, SRT, WebVTT, or JSON output
- 📊 **Transcript Info**: See whether transcript is manual/auto-generated and language
- 💾 **Instant Download**: Download transcripts in your preferred format
- 🐛 **Debug Mode**: Toggle for detailed technical information

---

### Audio Transcription Web App

**Launch the Streamlit interface**:
```bash
streamlit run transcribeVid.py
```

**Access at**: `http://localhost:8501`

**Features**:
- 🎯 **Smart Provider Selection**: Auto-chooses optimal API based on file size
- 📊 **Real-time Quality Metrics**: Confidence scores and speech detection analysis  
- 📁 **Multiple Input Methods**: Drag-and-drop upload or file path input
- 🎭 **Format Support**: WAV, MP3, M4A, FLAC
- 📄 **Export Options**: Download as TXT or SRT subtitle files

---

### Advanced Usage Examples

**Large file processing with quality analysis**:
- Files **> 5MB**: Automatically uses OpenAI (higher rate limits, better quality)
- Files **≤ 5MB**: Uses Groq (faster, cost-effective)

**Multi-language transcription**:
```python
# In the web app, set language to "fr" for French, "es" for Spanish, etc.
```

**Batch processing workflow**:
1. Extract YouTube audio: `python fetchTscript.py [URL]`
2. If transcript unavailable → MP3 created automatically
3. Open web app: `streamlit run transcribeVid.py`
4. Upload the generated MP3 for high-quality transcription

## Provider Intelligence 🧠

### Automatic Provider Selection
- **Groq API**: Ultra-fast processing, 20 RPM limit, ideal for smaller files
- **OpenAI API**: Premium quality, 7,500 RPM limit, best for large/complex audio
- **Smart Switching**: Automatically handles rate limits and optimal routing

### Quality Assurance
- **Confidence Scoring**: Real-time analysis of transcription confidence
- **Speech Detection**: Identifies non-speech segments  
- **Error Handling**: Robust retry logic with exponential backoff
- **Chunk Overlap**: Maintains context across file segments

## File Structure 📁

```
ytFetch/
├── fetchTscript.py          # YouTube transcript extraction CLI
├── appStreamlit.py          # YouTube transcript extraction web interface
├── transcribeVid.py         # Multi-provider transcription web app
├── config.yaml.example      # Configuration template
├── config.yaml             # Your API keys (git-ignored)
├── video_outputs/          # Directory for transcript and audio outputs
├── CLAUDE.md               # Development documentation
├── README.md               # This file
└── .gitignore              # Protects sensitive files
```

## Troubleshooting 🔧

**Common Issues:**

1. **"No transcripts available"**: Video has disabled transcripts → Audio download fallback activated
2. **Rate limit errors**: API limits reached → Automatically switches providers or waits
3. **Large file failures**: File > 25MB → Automatic chunking with overlap
4. **ffmpeg not found**: Install ffmpeg using commands above
5. **API authentication errors**: Double-check your `config.yaml` keys

**Performance Tips:**
- Use Groq for quick transcriptions of shorter content
- Use OpenAI for highest quality on longer, complex audio
- Enable "Auto" mode for optimal provider selection

## Contributing 🤝

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch: `git checkout -b amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin amazing-feature`
5. Open a Pull Request

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments 🙏

- **OpenAI** for the powerful Whisper models and API
- **Groq** for lightning-fast transcription capabilities  
- **YouTube Transcript API** for seamless transcript access
- **yt-dlp** for robust YouTube audio extraction
- **Streamlit** for the beautiful web interface

## Feedback & Support 💬

Found a bug? Have a feature request? We'd love to hear from you!

- 🐛 **Report Issues**: [GitHub Issues](https://github.com/lliWcWill/ytFetch/issues)
- 💡 **Feature Requests**: Open an issue with the "enhancement" label
- 🚀 **Pull Requests**: Contributions are always welcome!

---

**Built with ❤️ for the content creation and research community**
