---
topic: env-config-discovery
description: how .env credentials and default-demo-config.json are discovered and merged across project and user-global scope
---

## env-config-discovery — .env and config.json discovery/merge precedence

cognigy-vibe-mcp resolves both credentials (`.env`) and demo build config
(`default-demo-config.json`) from two layers, merged together — not a single
file picked exclusively.

### .env layers

1. **Project layer** — nearest ancestor directory containing a `.env`, walking
   up from the working directory toward `$HOME` (stops at `$HOME` or, if
   `$HOME` isn't an ancestor of the start directory, at the start directory
   itself — this prevents escaping onto unrelated ancestors in CI/`/tmp`
   checkouts).
2. **User-global layer** — `~/.config/cognigy-vibe/.env`.

Both files are read and merged key-by-key: **the project layer wins per-key**
over user-global. If the project `.env` only sets `COGNIGY_PROJECT_ID`, the
user-global `.env`'s `COGNIGY_BASE_URL`/`COGNIGY_API_KEY` still apply — the
server does not fall into degraded mode just because credentials live in a
different file than the project id.

This merge is re-evaluated on every `reload_mcp` respawn, so editing either
file and reloading picks up the change without a full session restart.

### default-demo-config.json layers

Same two-layer model (project-nearest-ancestor + user-global
`~/.config/cognigy-vibe/config.json`), but the merge is **shallow** — only
top-level keys are merged; if both files set `connection`, the project file's
whole `connection` object wins, not a field-by-field merge of nested keys.

### Degraded-mode guidance

When required credentials (`COGNIGY_BASE_URL`, `COGNIGY_API_KEY`) are still
missing after the merge, tool calls return guidance listing exactly which
key(s) are missing and both resolved file paths (found or not), so it's clear
which file to edit and that the project file takes precedence if both set the
same key.
