# Project: Multi-Tier YouTube Transcript Fetcher

This project is a resilient, multi-tiered system for fetching YouTube video transcripts.

## Core Instructions & Context
@docs/memory/architecture.md
@docs/memory/coding_standards.md
@~/.claude/CLAUDE.md

## Required Workflows

**IMPORTANT:** For any complex task (e.g., adding a new feature, a major refactor), you **MUST** follow the **Checklist-Driven Development** workflow:
1.  **Think:** Use the "think hard" directive to analyze the request.
2.  **Plan:** Create a detailed plan as a checklist in a temporary markdown file (e.g., `TASK-feature-name.md`).
3.  **Implement:** Execute the plan, checking off items as you complete them.
4.  **Verify:** Run tests to confirm the implementation is correct.

For adding new functionality, you **MUST** follow the **Test-Driven Development (TDD)** workflow:
1.  Ask me for the requirements and expected input/output.
2.  Write failing tests in the `tests/` directory that cover these requirements.
3.  Commit the failing tests.
4.  Write the minimum implementation code required to make the tests pass.
5.  Commit the implementation code.


### The Core Concept: Authentication is a Separate, User-Driven Action

To answer your excellent question directly: **No, the authentication is *not* initiated when you press 'Fetch Transcript'.**

Think of it this way:
1.  **Authentication is like logging into a website.** You do it *once* at the beginning of your session to prove who you are.
2.  **Fetching a transcript is like clicking a button on that website *after* you've logged in.**

The application doesn't try to authenticate on its own. It simply **checks your status** on every run: "Is this user logged in? Yes or No?"
*   If **No**, it shows you the "Authenticate with Google" button, waiting for *you* to take action.
*   If **Yes**, it shows "Authenticated" and unlocks the Tier 1 feature.

The "Awaiting authentication..." message you see is the correct initial state. The problem is that the button that lets you *change* that state isn't appearing correctly.

### The Bug: Why the "Authenticate" Button Isn't Showing

The provided "fix" was very close but contained a logical flaw that created an infinite loop of "not authenticated."

Look at this part of the proposed fix:

```python
# This is the buggy logic from the "fix"
if isinstance(auth_result, str):  # Correctly identifies you're not logged in
    st.sidebar.link_button("Authenticate with Google", auth_result, ...)
    st.session_state.credentials = None # <-- THE BUG
# ...
else:
    st.sidebar.warning("Awaiting authentication...")
    st.session_state.credentials = None # <-- AND HERE
```

Every time the script runs (which is every time you interact with a Streamlit app), it does this:
1.  `get_credentials()` correctly says, "No credentials found, here is the login URL."
2.  The `if` statement correctly decides to show the login button.
3.  But then the very next line, `st.session_state.credentials = None`, immediately wipes out any possibility of the state changing.

The fundamental principle is: **The UI code should only *read* the session state, not *write* to it.** The `auth_utils.py` module should be the single source of truth for managing credentials.

### The Final Fix: The Correct Code and Workflow

Let's implement the logic correctly. This will make the button appear and the entire flow work as intended.

**Replace the entire Authentication Sidebar section in `appStreamlit.py` with this clean and correct code:**

```python
# In appStreamlit.py

# ... other code ...

# --- Streamlit App UI ---

st.set_page_config(page_title="YouTube Transcript Fetcher", layout="wide")
st.title("🎬 YouTube Transcript Fetcher")

# --- CORRECTED Authentication Sidebar ---
st.sidebar.title("Authentication")

# Initialize credentials in the session state if they don't exist.
# This happens only ONCE per session.
if 'credentials' not in st.session_state:
    st.session_state.credentials = None

# Let get_credentials() manage the flow. It will return an auth_url
# if the user needs to log in, and it will handle the redirect itself.
auth_url = get_credentials()

# The UI now simply READS the state to decide what to show.
# It does NOT change the state itself.
if st.session_state.get('credentials'):
    # STATE 1: User is successfully authenticated.
    st.sidebar.success("✅ Authenticated with Google")
else:
    # STATE 2: User is NOT authenticated.
    if auth_url:
        # Show the login button if we have a URL for it.
        st.sidebar.link_button("Authenticate with Google", auth_url, use_container_width=True)
        st.sidebar.info("Authenticate to enable fetching of official, manually-uploaded transcripts (Tier 1).")
    else:
        # This state occurs during the redirect or if there's an error.
        st.sidebar.warning("Awaiting authentication...")

# ... (The rest of your UI and orchestrator code can remain the same) ...
```

### Your New Workflow (How it's Supposed to Work)

1.  **Save the Fix:** Update `appStreamlit.py` with the corrected sidebar code above.
2.  **Run the App:** `streamlit run appStreamlit.py`
3.  **See the Button:** The sidebar will now correctly show the blue **"Authenticate with Google"** button.
4.  **Click the Button:** Click it. A new browser tab will open to the Google consent screen.
5.  **Approve Access:** Log in with your test user account and click "Allow".
6.  **Get Redirected:** Google will send you back to your Streamlit app. The page will reload, and for a brief moment, you'll see "Awaiting authentication..." as the app processes the redirect.
7.  **See the Success Message:** The sidebar will now update to show **"✅ Authenticated with Google"**.

Now, your session is authenticated. When you paste a URL and click "Fetch Transcript," the `get_transcript_with_fallback` function will receive the valid credentials from `st.session_state.get('credentials')` and Tier 1 will execute successfully for the right videos.