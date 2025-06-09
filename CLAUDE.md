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
