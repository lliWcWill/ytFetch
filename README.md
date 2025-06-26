# ⚡ ytFetch
# YouTube Transcript & AI Audio Transcription Toolkit

[![Latest Release](https://img.shields.io/github/v/release/lliWcWill/ytFetch.svg)](https://github.com/lliWcWill/ytFetch/releases)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Ubuntu 20.04+](https://img.shields.io/badge/ubuntu-20.04%2B-orange.svg)](https://ubuntu.com/)
[![macOS 10.15+](https://img.shields.io/badge/macOS-10.15%2B-blue.svg)](https://www.apple.com/macos/)
[![Windows 10+](https://img.shields.io/badge/windows-10%2B-blue.svg)](https://www.microsoft.com/windows/)
[![Test Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](#)
[![Conda Compatible](https://img.shields.io/badge/conda-compatible-green.svg)](https://anaconda.org/)
[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

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
- **Groq Dev Tier integration**: Ultra-fast transcription (up to **271x realtime**)
- **Intelligent chunking**: Parallel processing for maximum speed
- **Progress tracking**: Real-time updates with ETA calculations
- **Automatic optimization**: Adaptive chunk sizing and worker scaling
- **Production-grade reliability**: Robust error handling and retry logic

### 🚀 Advanced Performance Optimizations
- **Circuit breaker patterns**: Prevents infinite retry loops and 503 errors
- **HTTP/2 connection pooling**: Persistent connections with reduced latency
- **Request deduplication**: Eliminates redundant API calls
- **Exponential backoff with jitter**: Prevents thundering herd problems
- **Memory-efficient streaming**: Handles 2+ hour videos without memory issues
- **Adaptive concurrency**: Dynamic worker scaling based on file duration

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

| Audio Length | Processing Time | Speed Factor | Success Rate | Model Used |
|-------------|----------------|--------------|--------------|------------|
| 5 minutes   | 3.2 seconds    | 94x realtime | 100% | distil-whisper-large-v3-en |
| 17 minutes  | 6.1 seconds    | 167x realtime| 100% | distil-whisper-large-v3-en |
| **39 minutes** | **8.6 seconds** | **271x realtime** | **100%** | **distil-whisper-large-v3-en** |
| 60 minutes  | 18.4 seconds   | 195x realtime| 100% | distil-whisper-large-v3-en |

### 🏆 **Latest Achievement: 271x Realtime Speed**
- **38.8 minutes** of audio transcribed in **8.58 seconds**
- **Zero failures** - 100% success rate across 20 chunks
- **5 parallel workers** perfectly balanced for optimal performance
- **Groq Dev Tier** with advanced rate limiting and circuit breakers

*All benchmarks verified with production-grade error handling and retry logic*

## 🔧 Architecture

### Two-Tier Fallback Strategy
1. **Tier 1**: YouTube Transcript API with exponential backoff retry
2. **Tier 2**: AI Audio Transcription with parallel processing

### Enhanced AI Transcription Pipeline
```
Audio Input → Preprocessing → Chunking → Parallel Transcription → Assembly
     ↓             ↓            ↓              ↓                    ↓
  FLAC 16kHz   Optimal Size   Smart Split   Groq API x50        Final Text
                                ↓              ↓
                        Circuit Breakers  HTTP/2 Pooling
                        Rate Limiting     Request Deduplication
```

### 🛡️ Advanced Reliability Features
- **Circuit breaker patterns**: Automatic service recovery with CLOSED → OPEN → HALF_OPEN states
- **Intelligent retry logic**: Exponential backoff with jitter prevents API overload
- **Connection health monitoring**: Persistent HTTP/2 connections with automatic recycling
- **Memory optimization**: Streaming processing for unlimited video length

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

### Groq Dev Tier Optimization Settings
```python
# Rate limiting with circuit breakers
MAX_CONCURRENT_REQUESTS = 50    # Dev tier optimized (400 RPM)
CIRCUIT_BREAKER_THRESHOLD = 3   # Trip after 3 failures
RECOVERY_TIMEOUT = 60           # 60s recovery period

# Audio processing optimization
CHUNK_DURATION_SECONDS = 122    # Dynamic sizing based on file length
OPTIMAL_SAMPLE_RATE = 16000     # Speech optimized
HTTP2_CONNECTION_POOL = True    # Persistent connections
```

### Adaptive Performance Tuning
- **Small files (< 3 min)**: Single request processing for minimal overhead
- **Medium files (3-30 min)**: Moderate chunking with 5-10 workers
- **Large files (30+ min)**: Intelligent batching with circuit breakers
- **Massive files (2+ hours)**: Conservative mode with enhanced error handling

## 📁 Project Structure

```
ytFetch/
├── appStreamlit.py              # Web interface with enhanced UI
├── audio_transcriber.py         # Groq-optimized transcription engine
├── fetchTscript.py             # CLI transcript extraction
├── transcribeVid.py            # Direct transcription interface
├── config.yaml.example        # Configuration template
├── performance_optimizations/   # ⚡ Advanced performance modules
│   ├── __init__.py            # Package initialization
│   ├── advanced_rate_limiter.py   # Circuit breakers & rate limiting
│   ├── connection_pool_manager.py # HTTP/2 connection pooling
│   ├── enhanced_audio_transcriber.py # Performance integration
│   ├── rate_limiting_examples.py  # Usage examples & demos
│   └── README.md              # Performance documentation
├── docs/                       # Documentation and screenshots
│   ├── memory/                # Architecture documentation
│   └── SpeechtoTextGroqDocs.md # Groq API specifications
├── tests/                     # Unit tests with pytest
└── video_outputs/             # Output directory for transcripts
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

- **Groq** for providing lightning-fast ⚡ AI inference capabilities (271x realtime!)
- **OpenAI** for the powerful Whisper models and transcription quality
- **YouTube Transcript API** for seamless transcript access
- **yt-dlp** for robust audio extraction and download capabilities
- **Streamlit** for the beautiful, responsive web interface
- **httpx & aiohttp** for enabling HTTP/2 connection pooling optimizations

## 📞 Support

- 🐛 [Report Issues](https://github.com/lliWcWill/ytFetch/issues)
- 💡 [Feature Requests](https://github.com/lliWcWill/ytFetch/discussions)
- 📖 [Documentation](https://github.com/lliWcWill/ytFetch/wiki)

---

**Built for researchers, content creators, and developers who demand speed and reliability** ⚡