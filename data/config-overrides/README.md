# Runtime Config Overrides

This directory is the stage 5 writable overlay.

Tracked files in this directory are only placeholders and documentation. Runtime files such as `active.yaml`, `history/`, and `audit.jsonl` are intentionally ignored by Git.

The API accepts only non-sensitive configuration fields. API keys, tokens, passwords, DSNs, arbitrary SQL, scripts, and executable code must stay out of this directory.
