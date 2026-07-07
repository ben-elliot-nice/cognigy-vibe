---
topic: session-workspace
description: session workspace directory model — cwd vs Demo Builds/, .env scope, sync_remote_state project binding
group: platform
---

## session-workspace — Session Workspace Directory Model

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

**What does NOT go in `.env` at setup time:**
- `COGNIGY_PROJECT_ID` — not written at session start. It is written dynamically by `sync_remote_state` each time a project is bound mid-session. If you inspect `.env` after a build has started you will see it there — that is normal. The distinction is *when* it is written, not *whether* it appears in `.env`.

## Project binding: `sync_remote_state`

Each build targets a different Cognigy project. The project is bound mid-session — no restart, no per-build `.env`, no per-build `.claude/mcp.json`.

```
sync_remote_state({ project_id: "<projectId>" })
```

Call this once after creating or locating the target project (build-orchestrator S1.1.5). All subsequent MCP calls in the same session operate against the newly bound project.

On session resume: call `sync_remote_state` again before any MCP call to refresh state.

## Config cascade

`default-demo-config.json` (non-secret build defaults: LLM, TTS, STT, voice, locale) is discovered by the MCP server at startup:

1. `<cwd>/default-demo-config.json` — workspace-level override
2. Walk up from cwd toward `$HOME`, first match wins
3. `~/.config/cognigy-vibe/config.json` — global default (written by `cognigy:init-cognigy-vibe`)
4. Nothing found → `config_loaded: false`

The winning file applies to **all** builds in this session. There is no per-build config file — the workspace root config is shared. See `cognigy:build-config` for the full field schema.

## Cross-workspace and different-tenant sessions

`.env` is workspace-scoped — it holds credentials for **one tenant**. If you need to work against a different tenant (different base URL or different API key), open a separate workspace directory and write a new `.env` there. Do not overwrite the existing `.env` mid-session.

Common scenarios that require a separate workspace:
- Switching from a production tenant to a staging/trial tenant
- Running builds for two customers who are on different Cognigy environments
- A second developer on the same machine who has a different API key

Each workspace directory has its own `.env` (and optionally its own `default-demo-config.json`). The `cognigy:init-cognigy-vibe` wizard writes `.env` to cwd — run it once per workspace, not once globally.

`~/.config/cognigy-vibe/config.json` (the non-secret build defaults) is global and shared across all workspaces on the same machine. Per-workspace build defaults go in `<workspace>/default-demo-config.json`.

## Legacy model (superseded)

The flat-structure model — where cwd was the demo directory, `COGNIGY_PROJECT_ID` was pinned in `.env`, and `cognigy:init-mcp` was run per project — is superseded by the session-workspace model. In the current model:

- No `COGNIGY_PROJECT_ID` pinned in `.env` at session start (it is written dynamically by `sync_remote_state` — see `.env` scope above)
- No per-build `.claude/mcp.json`
- No `cognigy:init-mcp` per project
- No session restart between builds

`cognigy:init-mcp` remains available for edge cases (non-plugin users who want a single-project flat directory with `COGNIGY_PROJECT_ID` pinned at session start), but is not part of the standard demo-build workflow.
