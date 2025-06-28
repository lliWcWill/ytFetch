### New Project Memory Structure

```
.
├── CLAUDE.md         # The new, lean project memory hub
├── docs/
│   └── memory/
│       ├── architecture.md
│       └── coding_standards.md
└── ... (your other project files)
```

---

# System Architecture

The system uses a simplified two-tiered fallback strategy to ensure reliable transcript retrieval with production-grade robustness.

## Tiered Fallback Logic

1.  **Tier 1: Unofficial Transcript Library (Primary Method)**
    *   **Method:** The `youtube-transcript-api` library with `tenacity` for robust retry logic.
    *   **Target:** Auto-generated and manually created captions.
    *   **Robustness:** Production-grade retry handling with exponential backoff to handle intermittent XML parsing errors.

2.  **Tier 2: AI Audio Transcription (Last Resort)**
    *   **Method:** Download audio via `yt-dlp` and process via `audio_transcriber.py` (using Groq/OpenAI).
    *   **Target:** Videos with all captions disabled.
    *   **Scope:** No duration limits - handles videos of any length through intelligent chunking.

## Architectural Flowcharts

### High-Level Flow
```mermaid
graph TD
    A[Start: Get Video URL] --> B[Try Unofficial Library with Tenacity];
    B -- Success --> C[Return Transcript Segments];
    B -- All Retries Failed --> D[Try AI Audio Transcription];
    D -- Success --> E[Return AI Transcript];
    D -- Failed --> F[End: All Methods Failed];
    C --> G[End: Success];
    E --> G;
```

### Sequence Diagram
```mermaid
sequenceDiagram
    participant User
    participant App as appStreamlit.py
    participant UnofficialAPI as youtube-transcript-api + tenacity
    participant Transcriber as audio_transcriber.py
    participant AI as AI Provider (Groq/OpenAI)
    User->>App: Enters URL & Clicks Fetch
    App->>UnofficialAPI: fetch_transcript_segments(video_id) with retries
    alt Transcript Found (after retries)
        UnofficialAPI-->>App: Transcript Segments
    else All Retries Failed
        UnofficialAPI-->>App: Failure after exponential backoff
        App->>App: Download audio via yt-dlp
        App->>Transcriber: transcribe_audio_from_file(path)
        Transcriber->>AI: Transcribe chunks
        AI-->>Transcriber: Transcribed text
        Transcriber-->>App: Full Transcript
    end
    App->>User: Display Transcript & Method
```
