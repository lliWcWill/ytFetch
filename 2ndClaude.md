## Project Plan: Implementing a Multi-Tiered Transcript Fetching System

**Objective:** Evolve the current YouTube transcript fetcher into a resilient, multi-tiered system. The application will intelligently attempt to fetch transcripts using a cascading series of methods, from the most reliable and highest quality to the most resource-intensive, ensuring the highest possible success rate.

**Lead Developer:** CLAUDE
  **Date:** June 7, 2025

```Mermaid
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

```Mermaid
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

## Main Files: appStreamlit.py, fetchTscript.py, transcribe.py

### 1. High-Level Architecture: The Fallback Strategy

The core of this task is to implement a three-tiered fallback system. The orchestrator will execute these tiers sequentially until a transcript is successfully retrieved.

*   **Tier 1: Official YouTube Data API v3**
    *   **Method:** Use the official, authenticated Google API.
    *   **Target:** Fetches high-quality, manually uploaded caption tracks by the video owner.
    *   **Pros:** Highest reliability, guaranteed accuracy (as provided by owner), official support.
    *   **Cons:** Does **not** work for auto-generated transcripts.

*   **Tier 2: Unofficial `youtube-transcript-api` Library**
    *   **Method:** The existing implementation.
    *   **Target:** Fetches the automatically generated (ASR) transcripts that YouTube creates for most videos.
    *   **Pros:** Works for a vast majority of videos that lack manual captions.
    *   **Cons:** Relies on an unofficial endpoint, subject to intermittent failures (the XML error) that require robust retry logic.

*   **Tier 3: AI-Powered Audio Transcription**
    *   **Method:** Download the video's audio stream and process it via an external speech-to-text API (Groq/OpenAI).
    *   **Target:** A last resort for videos where both manual and auto-generated transcripts are disabled or unavailable.
    *   **Pros:** Catches edge cases that other methods miss.
    *   **Cons:** Most resource-intensive (network bandwidth, processing time, API costs), and introduces a dependency on the `transcribeVid.py` module's logic. A duration limit (e.g., 10 minutes) is a sensible guardrail.

### 2. Implementation Roadmap

This project is broken down into four distinct phases.

---

#### **Phase 0: Project Setup & Configuration**

*   **Goal:** Prepare the environment and configuration for the new API integration.
*   **Tasks:**
    1.  **Install Dependencies:** Add the Google API client library to the project environment.
        ```bash
        # Within the 'venv' environment
        pip install --upgrade google-api-python-client
        ```
    2.  **Update `config.yaml`:** Add a new section for the YouTube Data API v3 key. The existing key used for scraping comments is perfect for this.
        ```yaml
        # In config.yaml
        
        # ... existing groq and openai sections ...
        
        youtube:
          api_key: "YOUR_YOUTUBE_DATA_API_V3_KEY_HERE" 
        ```
    3.  **Update Config Loading:** Ensure the application loads this new key upon startup. This logic likely resides in `appStreamlit.py` or can be added to the `initialize_clients` function in `transcribeVid.py` if it becomes a shared utility.

---

#### **Phase 1: Refactor `transcribeVid.py` for Reusability**

*   **Goal:** Decouple the core audio transcription logic from its Streamlit UI to allow it to be called as a library function from `appStreamlit.py`.
*   **Tasks:**
    1.  **Create a "Headless" Module:** Create a new file, e.g., `audio_transcriber.py`.
    2.  **Migrate Core Logic:** Move the non-UI functions from `transcribeVid.py` into `audio_transcriber.py`. This includes:
        *   `initialize_clients`
        *   `preprocess_audio`
        *   `split_audio_with_overlap`
        *   `transcribe_with_groq`
        *   `transcribe_with_openai`
        *   `select_transcription_provider`
    3.  **Create a Headless Orchestrator:** In `audio_transcriber.py`, create a new primary function, `transcribe_audio_from_file(file_path, language)`.
        *   This function will be a refactored version of `process_audio_file` from `transcribeVid.py`.
        *   **Crucially, remove all `st.*` calls** (e.g., `st.write`, `st.progress`, `st.spinner`). Replace them with `logging` for progress/error reporting.
        *   The function should accept a file path and language, and `return` the final transcript string or `None` on failure.
    4.  **Update `transcribeVid.py`:** Modify the original `transcribeVid.py` to simply `import transcribe_audio_from_file from audio_transcriber` and wrap it with the existing Streamlit UI elements. This preserves its ability to run as a standalone app while making its core logic reusable.

---

#### **Phase 2: Implement the Tiered Orchestrator in `appStreamlit.py`**

*   **Goal:** Create the central function that implements the cascading fallback logic.
*   **Tasks:**
    1.  **Create the Orchestrator Function:** In `appStreamlit.py`, define a new function: `get_transcript_with_fallback(video_id, api_key)`. This function will return a tuple: `(transcript_text, method_used)`.
    2.  **Implement Tier 1 Logic:**
        *   Inside the orchestrator, first attempt to fetch the transcript using the official API.
        *   Use `googleapiclient` to call `captions.list()`.
        *   If manual English captions are found, `captions.download()` them.
        *   On success, `return (transcript_text, "Official YouTube API")`.
        *   Gracefully handle `googleapiclient.errors.HttpError` and other exceptions, logging them and proceeding to Tier 2.
    3.  **Implement Tier 2 Logic:**
        *   If Tier 1 fails, call the existing `fetch_transcript_segments(video_id)`.
        *   If segments are returned, format them into a plain text string using `format_segments`.
        *   On success, `return (formatted_text, "Unofficial Transcript Library")`.
        *   If it fails, log the error and proceed to Tier 3.
    4.  **Implement Tier 3 Logic:**
        *   If Tier 2 fails, get the video's duration using `yt-dlp` (the `get_video_info` function can be adapted for this).
        *   **Apply the guardrail:** If duration > 10 minutes, log this and abort Tier 3.
        *   If within the limit, use `yt-dlp` to download the audio to a temporary file in the `video_outputs` directory. The logic for this is already in `fetchTscript.py` (`download_audio_as_mp3`). This function should be moved or imported into `appStreamlit.py`.
        *   Call the newly refactored `transcribe_audio_from_file()` from the `audio_transcriber` module, passing the path to the downloaded audio file.
        *   On success, `return (transcript_text, "AI Audio Transcription")`.
        *   **Crucially, ensure the temporary audio file is deleted after transcription.**
    5.  **Final Failure:** If all three tiers fail, `return (None, "All methods failed")`.

---

#### **Phase 3: Update the Streamlit UI (`appStreamlit.py`)**

*   **Goal:** Integrate the new orchestrator into the user interface and provide clear feedback.
*   **Tasks:**
    1.  **Modify the Submit Logic:** In the `if submit_button:` block, replace the direct call to `fetch_transcript_segments` with a call to the new `get_transcript_with_fallback`.
    2.  **Display Results and Method:**
        *   When a transcript is successfully returned, display it in the text area as before.
        *   Add a new UI element, like `st.success()` or `st.info()`, to explicitly state *how* the transcript was obtained. Example: `st.success("✅ Transcript fetched successfully using the Official YouTube API.")`.
    3.  **Handle Final Failure:** If the orchestrator returns `None`, display a comprehensive error message to the user, e.g., `st.error("❌ Could not retrieve a transcript for this video. Manual, auto-generated, and AI transcription methods all failed.")`.


# Code Example Implmentation

```python
# You'll need to install the google api client
# pip install --upgrade google-api-python-client

import googleapiclient.discovery
import googleapiclient.errors
import io
from googleapiclient.http import MediaIoBaseDownload

# --- Helper function to get video metadata (including duration) ---
def get_video_details(video_id, api_key):
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
        request = youtube.videos().list(
            part="snippet,contentDetails",
            id=video_id
        )
        response = request.execute()
        if not response.get("items"):
            return None
        
        # Parse duration from ISO 8601 format (e.g., "PT1H2M3S")
        duration_iso = response["items"][0]["contentDetails"]["duration"]
        # A simple regex can parse this, or use a library like `isodate`
        # For simplicity, we'll just return the ISO string here.
        # A real implementation would convert "PT10M5S" to 605 seconds.
        
        return {
            "title": response["items"][0]["snippet"]["title"],
            "duration_iso": duration_iso 
            # You would add duration parsing logic here
        }
    except Exception as e:
        print(f"Could not get video details via official API: {e}")
        # Fallback to yt-dlp if needed
        return get_video_info(video_id) # Your existing function

# --- The Main Orchestrator Function ---
def fetch_transcript_with_fallback(video_id, api_key):
    """
    Tries to fetch a transcript using a cascading fallback strategy.
    Returns a tuple: (transcript_text, method_used)
    """
    
    # --- TIER 1: Try Official YouTube Data API v3 ---
    print("✅ TIER 1: Attempting to fetch with Official YouTube API...")
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
        captions_request = youtube.captions().list(part="snippet", videoId=video_id)
        captions_response = captions_request.execute()

        if captions_response.get("items"):
            print("  -> Success: Found manually uploaded caption track(s).")
            caption_id = captions_response["items"][0]["id"] # Using the first one
            
            download_request = youtube.captions().download(id=caption_id, tfmt="srt")
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, download_request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            fh.seek(0)
            transcript = fh.read().decode('utf-8')
            return (transcript, "Official API")
        else:
            print("  -> Info: No manual captions found. Falling back.")

    except googleapiclient.errors.HttpError as e:
        print(f"  -> Error: Official API failed with HTTP Error: {e}. Falling back.")
    except Exception as e:
        print(f"  -> Error: An unexpected error occurred with the official API: {e}. Falling back.")

    # --- TIER 2: Try Unofficial youtube-transcript-api Library ---
    print("\n✅ TIER 2: Attempting to fetch with unofficial library...")
    segments, info, error = fetch_transcript_segments(video_id) # Your existing robust function
    if segments:
        print("  -> Success: Found auto-generated transcript.")
        # format_segments returns a string, which is what we want.
        transcript = format_segments(segments, "txt") 
        return (transcript, "Unofficial Library")
    else:
        print(f"  -> Info: Unofficial library failed. Error: {error}. Falling back.")

    # --- TIER 3: Try Audio Transcription via OpenAI Whisper ---
    print("\n✅ TIER 3: Attempting audio transcription as a last resort...")
    # NOTE: You need a function to get duration in seconds.
    # For now, let's assume a placeholder function `get_duration_in_seconds(video_id)`
    # video_duration = get_duration_in_seconds(video_id) 
    video_duration = 300 # Placeholder
    
    if video_duration <= 600: # 10 minutes
        print(f"  -> Info: Video duration ({video_duration}s) is within the limit. Proceeding.")
        try:
            # Placeholder for your existing logic
            # 1. download_audio_as_mp3(video_id, ...)
            # 2. transcript = transcribe_with_openai("path/to/audio.mp3")
            transcript = "This is a placeholder for the Whisper-generated transcript." # Placeholder
            return (transcript, "OpenAI Whisper")
        except Exception as e:
            print(f"  -> Error: Audio transcription failed: {e}")
    else:
        print(f"  -> Info: Video is longer than 10 minutes ({video_duration}s). Skipping audio transcription.")

    # If all methods fail
    return (None, "All methods failed")

# In your Streamlit app's submit block:
# if submit_button:
#     ...
#     transcript, method = fetch_transcript_with_fallback(video_id, YOUR_API_KEY)
#     if transcript:
#         st.success(f"Transcript fetched successfully using: {method}!")
#         st.text_area("Transcript", transcript, height=300)
#     else:
#         st.error("Could not retrieve transcript for this video using any available method.")
```


# **Phase 4: Validation, Testing, and Refinement**.

Regarding your question about Mojo, it's a fantastic and forward-thinking question. Let's tackle the testing plan first and then do a deep dive into Mojo's potential role.

---

### Phase 4: A Structured Testing & Validation Plan

Instead of ad-hoc tests, we'll define specific test cases to verify that every tier of the fallback logic works as expected.

#### **Step 1: Create a Test Harness**

Before you even touch the Streamlit UI, create a simple command-line script (`test_runner.py`) to test your core orchestrator function directly. This isolates the backend logic from the UI, making testing faster and more repeatable.

```python
# test_runner.py
import yaml
from appStreamlit import get_transcript_with_fallback # Assuming the orchestrator is in appStreamlit.py

def load_api_key():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
        return config.get("youtube", {}).get("api_key")

def run_test(video_id, expected_method):
    print(f"\n--- TESTING VIDEO ID: {video_id} ---")
    print(f"    EXPECTED METHOD: {expected_method}")
    api_key = load_api_key()
    
    transcript, method_used = get_transcript_with_fallback(video_id, api_key)
    
    if transcript and method_used == expected_method:
        print(f"✅ PASS: Transcript found using the correct method: '{method_used}'")
        print(f"    Transcript snippet: '{transcript[:100]}...'")
    elif method_used != expected_method:
        print(f"❌ FAIL: Used method '{method_used}' but expected '{expected_method}'")
    else:
        print(f"❌ FAIL: No transcript found. Final status: '{method_used}'")

if __name__ == "__main__":
    # Define your test cases here
    test_cases = {
        # Tier 1 Success: Video with known manual captions
        "dQw4w9WgXcQ": "Official YouTube API",
        
        # Tier 2 Success: Video with only auto-captions (your original problem case)
        "aR6CzM0x-g0": "Unofficial Transcript Library",
        
        # Tier 3 Success: Video with captions disabled, < 10 mins
        # You may need to upload a short, unlisted video with captions turned off for this test
        "YOUR_TEST_VIDEO_ID_NO_CAPTIONS": "AI Audio Transcription",
        
        # Tier 3 Skip (Duration): Video with no captions, > 10 mins
        "kL8Bfl_c4dY": "All methods failed", # Example: A long gaming stream with no captions
        
        # Total Failure: A known private or deleted video
        "invalid_or_private_id": "All methods failed",
    }
    
    for video_id, expected in test_cases.items():
        run_test(video_id, expected)
```

#### **Step 2: Execute Systematic Test Cases**

Use the `test_runner.py` script to execute the following scenarios. The key is not just to see *if* you get a transcript, but to **verify it was retrieved using the correct tier**.

1.  **Test Case: Tier 1 Success (Official API)**
    *   **Video:** Use a video with known, high-quality manual captions. Official music videos or TED talks are great for this. (e.g., `dQw4w9WgXcQ` for Rick Astley, which has official lyrics).
    *   **Expected Outcome:** The script should report success using the `"Official YouTube API"`. The transcript should be well-formatted (like an SRT file).

2.  **Test Case: Tier 2 Success (Unofficial Library)**
    *   **Video:** Use your original problem video (`aR6CzM0x-g0`) or any typical lecture/podcast that relies on auto-captions.
    *   **Expected Outcome:** The logs should show Tier 1 failing (no manual captions), and the script should report success using the `"Unofficial Transcript Library"`.

3.  **Test Case: Tier 3 Success (AI Transcription)**
    *   **Video:** This is the hardest to find. The best way is to **create your own test case**: upload a 1-2 minute unlisted video to your YouTube account. In the video settings, explicitly **disable** all captions.
    *   **Expected Outcome:** Logs show Tiers 1 and 2 failing. The script should then download the audio and report success using `"AI Audio Transcription"`.

4.  **Test Case: Tier 3 Skip (Duration Guardrail)**
    *   **Video:** Find a long video (e.g., a 2-hour podcast or livestream) that you know has no manual or auto-captions.
    *   **Expected Outcome:** Logs show Tiers 1 and 2 failing. The orchestrator should then identify the video is >10 minutes and abort, with the script reporting `"All methods failed"`.

5.  **Test Case: Total Failure**
    *   **Video:** Use an invalid video ID or the ID of a video you know has been set to private or deleted.
    *   **Expected Outcome:** All tiers should fail gracefully, and the script should report `"All methods failed"`.

#### **Step 3: Manual End-to-End Testing**

Once the backend logic is confirmed with the test harness, run the `appStreamlit.py` application and manually test a few of the key cases above. Pay close attention to the UI:
*   Do the status messages and spinners update correctly?
*   Is the final success/error message clear and accurate?
*   Is the final transcript displayed correctly?
*   Do the download buttons work?

---


Excellent. This is the correct and professional way to proceed. Adding a major feature like authentication invalidates our previous testing assumptions, and a dedicated, more comprehensive validation phase is not just a good idea—it's a requirement for a high-quality system.

You've completed the initial setup for OAuth2. Let's formalize the next steps into a new, rigorous plan. We will define a new **Phase 5** focused on integration and comprehensive testing, and the original deployment plan will become 








# **Phase 5 (Revised): Deployment, Documentation, and Strategic Enhancement**

**Objective:** Transition the application from a validated prototype to a production-ready tool. This involves making it accessible to users, creating robust documentation for future development, and strategically addressing the known limitations discovered in Phase 4.

#### **Step 1: Productionalize & Deploy via a Controlled Git Workflow**

The application is validated locally and the project is already under version control. We will now prepare it for deployment to Streamlit Community Cloud using a clean, professional Git process.

*   **Task 1: Create a Deployment Preparation Branch.**
    *   All changes related to deployment (updating requirements, adding secrets logic, etc.) will be done on a dedicated feature branch. This keeps the `main` branch clean and stable.
    *   **Action:** From your terminal in the project root:
        ```bash
        # Ensure you are on the main branch and have the latest changes
        git checkout main
        git pull

        # Create and switch to a new branch for this work
        git checkout -b feat/streamlit-deployment-prep
        ```

*   **Task 2: Prepare the Application for Deployment (on the new branch).**
    1.  **Generate `requirements.txt`:** Freeze the exact package versions from your virtual environment to ensure a reproducible build on the cloud.
        ```bash
        # From your project's root directory, with the venv activated
        pip freeze > requirements.txt
        ```
    2.  **Secure API Keys:** Your `config.yaml` contains secrets and must not be committed.
        *   **Add `config.yaml` to `.gitignore`:** Open your `.gitignore` file and add a new line with `config.yaml` to prevent it from ever being tracked.
        *   **Create `config.yaml.example`:** Duplicate `config.yaml` and rename it to `config.yaml.example`. Replace all secret keys with placeholder text like `"YOUR_KEY_HERE"`. This file *will* be committed to show other developers the required structure.
    3.  **Integrate Streamlit Secrets Management:** Modify the application to use Streamlit's secrets manager when deployed, falling back to the local `config.yaml` for development.
        ```python
        # In appStreamlit.py (or a new config_loader.py module)
        import streamlit as st
        import yaml

        def load_api_keys():
            # Check if running in Streamlit Cloud environment
            if hasattr(st, 'secrets'):
                print("Loading keys from Streamlit secrets...")
                return {
                    "youtube_api_key": st.secrets.get("youtube", {}).get("api_key"),
                    "groq_api_key": st.secrets.get("groq", {}).get("api_key"),
                    "openai_api_key": st.secrets.get("openai", {}).get("api_key")
                }
            else:
                # Running locally, use config.yaml
                print("Loading keys from local config.yaml...")
                with open("config.yaml", "r") as f:
                    config = yaml.safe_load(f)
                    return {
                        "youtube_api_key": config.get("youtube", {}).get("api_key"),
                        "groq_api_key": config.get("groq", {}).get("api_key"),
                        "openai_api_key": config.get("openai", {}).get("api_key")
                    }
        ```

*   **Task 3: Commit, Push, and Create a Pull Request.**
    1.  **Commit the changes:** Stage all your work and commit it with a clear message.
        ```bash
        git add requirements.txt config.yaml.example .gitignore appStreamlit.py
        git commit -m "feat: Prepare application for Streamlit Cloud deployment"
        ```
    2.  **Push the new branch to GitHub:**
        ```bash
        # The 'gh' CLI makes this easy
        gh repo sync
        # Or using pure git
        git push --set-upstream origin feat/streamlit-deployment-prep
        ```
    3.  **Create a Pull Request (PR):** On GitHub, create a new Pull Request from `feat/streamlit-deployment-prep` to `main`. This is a crucial step for code review (even if you're the one reviewing it) and creates a formal record of the changes.
    4.  **Merge the PR:** Once you're satisfied with the changes, merge the Pull Request into the `main` branch. Your `main` branch now contains the production-ready code.

*   **Task 4: Deploy to Streamlit Community Cloud.**
    1.  Sign in to [share.streamlit.io](https://share.streamlit.io).
    2.  Click "New app" and connect your existing GitHub repository.
    3.  Select the **`main` branch** for deployment.
    4.  Point it to the `appStreamlit.py` file.
    5.  In the "Advanced settings," paste the contents of your local `config.yaml` into the Secrets manager.
    6.  Click **"Deploy!"**. The app will now build and launch from your stable `main` branch.

---
