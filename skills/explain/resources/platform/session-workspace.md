---
topic: session-workspace
description: session workspace directory model — cwd vs Demo Builds/, .env scope, sync_remote_state project binding
group: platform
---

# session-workspace

## Directory model

The session workspace is the directory Claude Code is open in (cwd). It is **shared** across all demo builds in a session.

```
<session-workspace>/          ← cwd — workspace root
  .env                        ← workspace-level credentials (COGNIGY_BASE_URL + COGNIGY_API_KEY only)
  default-demo-config.json    ← optional workspace-level config override
  Demo Builds/
    <brand>-demo/             ← per-build artifact directory
      brand-research.md
      tools/
      code-nodes/
      xapp/
      knowledge/
      <Customer>-agent-persona.md
      <Customer>-agent-architecture.md
      ...
```

Claude's cwd does **not** change when a build starts. The `Demo Builds/<brand>-demo/` path is a subdirectory — file paths written by sub-skills are relative to the workspace root, not cwd-relative to the demo dir.

## `.env` scope

`.env` lives at the workspace root (cwd) and is workspace-level — it is shared across all builds in the session.

**What goes in `.env`:**
- `COGNIGY_BASE_URL` — the Cognigy API base URL for this tenant
- `COGNIGY_API_KEY` — the API key for this tenant

**What does NOT go in `.env`:**
- `COGNIGY_PROJECT_ID` — this is NOT set at session start. Projects are bound mid-session via `sync_remote_state`.

## Project binding: `sync_remote_state`

Each build targets a different Cognigy project. The project is bound mid-session — no restart, no per-build `.env`, no per-build `.claude/mcp.json`.

```
sync_remote_state({ project_id: "<projectId>" })
```

Call this once after creating or locating the target project (build-orchestrator §1.1.5). All subsequent MCP calls in the same session operate against the newly bound project.

On session resume: call `sync_remote_state` again before any MCP call to refresh state.

## Config cascade

`default-demo-config.json` (non-secret build defaults: LLM, TTS, STT, voice, locale) is discovered by the MCP server at startup:

1. `<cwd>/default-demo-config.json` — workspace-level override
2. Walk up from cwd toward `$HOME`, first match wins
3. `~/.config/cognigy-vibe/config.json` — global default (written by `cognigy:init-cognigy-vibe`)
4. Nothing found → `config_loaded: false`

The winning file applies to **all** builds in this session. There is no per-build config file — the workspace root config is shared. See `cognigy:build-config` for the full field schema.

## Legacy model (superseded)

The flat-structure model — where cwd was the demo directory, `COGNIGY_PROJECT_ID` was pinned in `.env`, and `cognigy:init-mcp` was run per project — is superseded by the session-workspace model. In the current model:

- No `COGNIGY_PROJECT_ID` in `.env`
- No per-build `.claude/mcp.json`
- No `cognigy:init-mcp` per project
- No session restart between builds

`cognigy:init-mcp` remains available for edge cases (non-plugin users who want a single-project flat directory with `COGNIGY_PROJECT_ID` pinned at session start), but is not part of the standard demo-build workflow.
