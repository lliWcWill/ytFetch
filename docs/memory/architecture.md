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

The system uses a three-tiered fallback strategy to ensure the highest possible success rate for transcript retrieval.

## Tiered Fallback Logic

1.  **Tier 1: Official YouTube API (OAuth2)**
    *   **Method:** Authenticated calls using `google-api-python-client`.
    *   **Target:** High-quality, manually uploaded captions.
    *   **Trigger:** This tier is only attempted if the user has authenticated via the OAuth2 flow.

2.  **Tier 2: Unofficial Transcript Library**
    *   **Method:** The `youtube-transcript-api` library.
    *   **Target:** Auto-generated ASR transcripts.
    *   **Trigger:** This is the default for unauthenticated users or when Tier 1 fails (e.g., no manual captions found).

3.  **Tier 3: AI Audio Transcription**
    *   **Method:** Download audio via `yt-dlp` and process via `audio_transcriber.py` (using Groq/OpenAI).
    *   **Target:** Videos with all captions disabled.
    *   **Guardrail:** This tier is only attempted if the video duration is less than or equal to 10 minutes.

## Architectural Flowcharts

### High-Level Flow
```mermaid
graph TD
    A[Start: Get Video URL] --> B{Try Official YouTube API};
    B -- Success --> C{Manual Captions Found?};
    B -- Error/Fail --> D{Try Unofficial Library};
    C -- Yes --> E[Download Transcript];
    C -- No --> D;
    D -- Success --> F{Auto-Transcript Found?};
    D -- Error/Fail --> H{Video < 10 mins?};
    F -- Yes --> G[Fetch & Format Transcript];
    F -- No --> H;
    H -- Yes --> I[Download Audio];
    H -- No --> Y[End: Fail];
    I --> J[Transcribe with AI];
    J -- Success --> K[Return AI Transcript];
    J -- Error/Fail --> Y;
    E --> Z[End: Success];
    G --> Z;
    K --> Z;
```

### Sequence Diagram
```mermaid
sequenceDiagram
    participant User
    participant App as appStreamlit.py
    participant OfficialAPI as Official YouTube API
    participant UnofficialAPI as youtube-transcript-api
    participant Transcriber as audio_transcriber.py
    participant AI as AI Provider (Groq/OpenAI)
    User->>App: Enters URL & Clicks Fetch
    App->>OfficialAPI: captions.list(video_id)
    alt Manual Captions Exist
        OfficialAPI-->>App: Caption List
        App->>OfficialAPI: captions.download(id)
        OfficialAPI-->>App: Transcript Text
    else No Manual Captions / Error
        OfficialAPI-->>App: Empty List / Error
        App->>UnofficialAPI: list_transcripts(video_id)
        alt Auto-Transcript Exists
            UnofficialAPI-->>App: Transcript Segments
        else No Auto-Transcript / Error
            UnofficialAPI-->>App: Failure / Error
            App->>App: Check video duration
            alt Duration < 10 mins
                App->>App: Download audio via yt-dlp
                App->>Transcriber: transcribe_audio_from_file(path)
                Transcriber->>AI: Transcribe chunk
                AI-->>Transcriber: Text
                Transcriber-->>App: Full Transcript
            else Duration > 10 mins
                App-->>App: Abort
            end
        end
    end
    App->>User: Display Transcript & Method
```
