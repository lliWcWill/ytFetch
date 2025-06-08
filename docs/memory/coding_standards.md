# Project Coding Standards & Best Practices

## Python Style Guide

*   **Formatting:** **IMPORTANT: You MUST strictly adhere to PEP 8**, with a maximum line length of 88 characters to align with the `black` code formatter.
*   **Type Hinting:** All function signatures **MUST** include type hints for parameters and return values.
*   **Docstrings:** All public modules, classes, and functions **MUST** have Google-style docstrings.
*   **Imports:** Sort imports into three groups: standard library, third-party packages, and local application modules, separated by a blank line.
*   **Error Handling:** **IMPORTANT: You MUST use specific exception handling** (`try...except SpecificError`), not generic `except Exception`. Log errors with context using the `logging` module.
*   **Dependencies:** All dependencies **MUST** be tracked in `requirements.txt`.

## Git & Version Control

*   **Commit Messages:** **You MUST follow the Conventional Commits specification.**
    *   Examples: `feat: Add OAuth2 authentication flow`, `fix: Correctly handle API rate limit errors`, `docs: Update architecture diagram`.
*   **Branching:** **You MUST use feature branches** for all new work (e.g., `feat/add-caching`). Pull Requests are required for merging into `main`.

## Streamlit Best Practices

*   **Secrets:** **CRITICAL: You MUST NEVER hardcode API keys or secrets.** Pull all secrets from `st.secrets` when deployed or a local `config.yaml` (which is in `.gitignore`) during development.
*   **Modularity:** Keep complex logic out of `appStreamlit.py`. **ALWAYS** refactor logic into helper modules (e.g., `auth_utils.py`, `audio_transcriber.py`).