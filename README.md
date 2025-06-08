# ⚡ ytFetch
# YouTube Transcript & AI Audio Transcription Toolkit

|version| |python_version| |ubuntu| |macos| |windows| |coverage| |conda| |license|

.. |version| image:: https://img.shields.io/github/v/release/lliWcWill/ytFetch.svg
   :target: https://github.com/lliWcWill/ytFetch/releases
   :alt: Latest Release

.. |python_version| image:: https://img.shields.io/badge/python-3.8%2B-blue.svg
   :target: https://www.python.org/downloads/
   :alt: Python 3.8+

.. |ubuntu| image:: https://img.shields.io/badge/ubuntu-20.04%2B-orange.svg
   :target: https://ubuntu.com/
   :alt: Ubuntu 20.04+

.. |macos| image:: https://img.shields.io/badge/macOS-10.15%2B-blue.svg
   :target: https://www.apple.com/macos/
   :alt: macOS 10.15+

.. |windows| image:: https://img.shields.io/badge/windows-10%2B-blue.svg
   :target: https://www.microsoft.com/windows/
   :alt: Windows 10+

.. |coverage| image:: https://img.shields.io/badge/coverage-90%25-brightgreen.svg
   :target: #
   :alt: Test Coverage

.. |conda| image:: https://img.shields.io/badge/conda-compatible-green.svg
   :target: https://anaconda.org/
   :alt: Conda Compatible

.. |license| image:: https://img.shields.io/badge/license-MIT-green.svg
   :target: https://opensource.org/licenses/MIT
   :alt: MIT License

> **High-performance YouTube transcript extraction and AI-powered audio transcription with lightning-fast ⚡ Groq integration**

## 🎯 Overview

ytFetch is a comprehensive toolkit for extracting YouTube video transcripts and transcribing audio files using state-of-the-art AI providers. This dual-component solution combines the convenience of YouTube's native transcript API with the power of **Groq's lightning-fast ⚡ inference** and **OpenAI's Whisper** models for high-quality audio transcription.

![ytFetch Interface](docs/ui-screenshot.png)

## ✨ Key Features

### 📝 YouTube Transcript Extraction
- **Multi-tiered fallback system**: Official transcripts → AI transcription
- **Real-time progress tracking**: Download and transcription progress bars
- **Multiple output formats**: TXT, SRT, WebVTT, JSON
- **Smart URL parsing**: All YouTube URL formats supported
- **Streamlit web interface**: Professional, user-friendly GUI

### ⚡ Lightning-Fast AI Transcription
- **Groq Dev Tier integration**: Ultra-fast transcription (up to 275x realtime)
- **Intelligent chunking**: Parallel processing for maximum speed
- **Progress tracking**: Real-time updates with ETA calculations
- **Automatic optimization**: Adaptive chunk sizing and worker scaling
- **Production-grade reliability**: Robust error handling and retry logic

### 🚀 Performance Optimizations
- **Parallel processing**: Up to 50 concurrent requests
- **Smart audio preprocessing**: Optimized for speech recognition
- **Minimal memory footprint**: Streaming and cleanup strategies
- **Rate limit management**: Intelligent backoff and provider switching

## 🏁 Quick Start

### Installation
```bash
git clone https://github.com/lliWcWill/ytFetch.git
cd ytFetch
pip install -r requirements.txt
```

### Configuration
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your API keys
```

### Launch Web Interface
```bash
streamlit run appStreamlit.py
```

## 📊 Performance Benchmarks

| Audio Length | Processing Time | Speed Factor | Chunks | Workers |
|-------------|----------------|--------------|---------|----------|
| 5 minutes   | 3.2 seconds    | 94x realtime | 5       | 12       |
| 17 minutes  | 6.1 seconds    | 167x realtime| 12      | 16       |
| 60 minutes  | 18.4 seconds   | 195x realtime| 40      | 30       |

*Benchmarks using Groq Dev Tier with distil-whisper-large-v3-en model*

## 🔧 Architecture

### Two-Tier Fallback Strategy
1. **Tier 1**: YouTube Transcript API with exponential backoff retry
2. **Tier 2**: AI Audio Transcription with parallel processing

### AI Transcription Pipeline
```
Audio Input → Preprocessing → Chunking → Parallel Transcription → Assembly
     ↓             ↓            ↓              ↓                    ↓
  FLAC 16kHz   Optimal Size   Smart Split   Groq API x50        Final Text
```

## 📱 User Interface

### Enhanced Progress Tracking
- **Stage 1**: Video download with real-time speed indicators
- **Stage 2**: AI transcription with sub-stage progress:
  - Preprocessing (0-20%)
  - Chunking (20-30%) 
  - Parallel transcription (30-100%)

### Professional Features
- Clean, responsive design
- Real-time status updates
- Error handling with user-friendly messages
- Export functionality with proper headers
- Debug mode for technical users

## 🛠️ Advanced Configuration

### Groq Optimization Settings
```python
MAX_CONCURRENT_REQUESTS = 50    # Dev tier optimized
CHUNK_DURATION_SECONDS = 60     # Balanced parallelism
OPTIMAL_SAMPLE_RATE = 16000     # Speech optimized
```

### Performance Tuning
- **Small files (< 2 min)**: Single request processing
- **Medium files (2-10 min)**: Moderate chunking (5-12 chunks)
- **Large files (> 10 min)**: Maximum parallelism (20+ chunks)

## 📁 Project Structure

```
ytFetch/
├── appStreamlit.py           # Web interface with enhanced UI
├── audio_transcriber.py      # Groq-optimized transcription engine
├── fetchTscript.py          # CLI transcript extraction
├── config.yaml.example     # Configuration template
├── docs/                    # Documentation and screenshots
├── tests/                   # Unit tests
└── video_outputs/           # Output directory
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup
```bash
git checkout -b feature/your-feature
pip install -r requirements.txt
python -m pytest tests/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Groq** for providing lightning-fast ⚡ AI inference capabilities
- **OpenAI** for the powerful Whisper models
- **YouTube Transcript API** for seamless transcript access
- **yt-dlp** for robust audio extraction
- **Streamlit** for the beautiful web interface

## 📞 Support

- 🐛 [Report Issues](https://github.com/lliWcWill/ytFetch/issues)
- 💡 [Feature Requests](https://github.com/lliWcWill/ytFetch/discussions)
- 📖 [Documentation](https://github.com/lliWcWill/ytFetch/wiki)

---

**Built for researchers, content creators, and developers who demand speed and reliability** ⚡