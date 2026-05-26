# cognigy-vibe MCP — Remote Hosting Design

**Date:** 2026-05-26  
**Status:** Approved  
**Covers tasks:** (02) Railway hosting, (03) Per-session config, (04) Auth abstraction

---

## 1. Problem

The current server uses stdio transport and process-level singletons. Three env vars baked in at startup (`COGNIGY_BASE_URL`, `COGNIGY_API_KEY`, `COGNIGY_PROJECT_ID`) make it single-tenant and local-only. Running it on Railway requires:

1. HTTP transport (Railway doesn't support stdio processes as services)
2. Per-session credential routing (shared server, multiple Cognigy environments)
3. Persistent state that survives redeploys
4. A file-push mechanism that doesn't route file content through the LLM

---

## 2. Core constraint: file content must not enter LLM context

The existing `push_code_node` pattern works because Claude passes a *path pointer* and the *server* reads the bytes. If file content were passed as a tool argument, Claude would see it and tend to regenerate it on subsequent calls.

For a remote server the bytes must travel from the developer's machine to the Railway container **without** going through the LLM. The mechanism is a Bash `curl` call (run by the skill, not by the LLM as content generation):

```
Developer's machine                 Railway container
  /local/code-node.js   ──PUT──>   /data/workspaces/{session_id}/code-node.js
       ↑                                      ↑
  Bash: curl (no LLM context)       push_code_node reads from here
```

Claude only ever sees the path string and the curl response code.

---

## 3. Architecture

### 3.1 Transport

A new entrypoint `cognigy-vibe-mcp-server` uses StreamableHTTP transport via the `mcp` library's ASGI support. The existing `cognigy-vibe-mcp` stdio entrypoint is **unchanged**.

The two modes are separate entrypoints, not a runtime flag. Local stdio mode requires no changes to any existing code path.

### 3.2 Session model

Each HTTP connection receives a `SessionContext` — a scoped replacement for the current process-level singletons:

```python
@dataclass
class SessionContext:
    client: CognigyClient
    state: ProjectState
    cache: Cache
    workspace_dir: Path       # /data/workspaces/{session_id}/
    last_interaction: float   # for expiry
    configured: bool = False
```

Sessions are stored in a server-level dict keyed by MCP session ID. A background task (or lazy check on each tool call) expires sessions idle for more than `COGNIGY_VIBE_SESSION_TTL` hours (default: 4). On expiry the workspace dir is deleted; project state is retained (it's per-project, not per-session).

### 3.3 `configure` tool

```
configure(base_url, api_key, project_id) → {"configured": True, "session_id": "..."}
```

- Creates a `CognigyClient` from the supplied credentials
- Creates or loads `ProjectState` from `/data/cognigy-mcp/{project_id}/`
- Creates `Cache` at `/data/cognigy-mcp/{project_id}/cache/`
- Creates workspace dir `/data/workspaces/{session_id}/`
- Must be called before any other tool; all other tools return `{"error": "session not configured", "hint": "Call configure first"}` if invoked before this

Calling `configure` on an already-configured session replaces the client/credentials but preserves the workspace.

### 3.4 State persistence

Railway Persistent Volume mounted at `/data`. `ProjectState` and `Cache` use the same filesystem approach — only the base path changes.

`STATE_BASE` is derived from `COGNIGY_VIBE_DATA_DIR` env var:
- Local mode default: `~/.config/cognigy-mcp` (unchanged behaviour)
- Railway: `/data/cognigy-mcp`

Per-project dirs (`{STATE_BASE}/{project_id}/`) persist across redeploys. Workspace dirs (`/data/workspaces/{session_id}/`) are ephemeral and cleaned up on session expiry.

### 3.5 File upload endpoint

```
PUT /workspace/{session_id}/{path}
Authorization: Bearer {COGNIGY_VIBE_TOKEN}
Content-Type: application/octet-stream
```

- Stores raw bytes at `/data/workspaces/{session_id}/{path}` (creates parent dirs)
- Returns `{"stored": "/data/workspaces/{session_id}/{path}"}` on success
- Returns 401 if Bearer token missing/wrong
- Returns 404 if session_id not found

The skill calls this endpoint via a Bash `curl` command. File bytes go directly from the developer's filesystem to the Railway volume — the LLM is not involved in content handling.

### 3.6 Modified file-push tools

`push_code_node` and `push_html_node` each gain a new optional parameter:

| Parameter | Type | Mode |
|---|---|---|
| `script_file` | absolute local path | local stdio only |
| `workspace_file` | relative path within session workspace | remote HTTP |

Exactly one must be provided. When `workspace_file` is given, the handler resolves it relative to the session's `workspace_dir` (`SessionContext.workspace_dir / workspace_file`). Conflict detection and snapshot logic are unchanged.

`push_tool_from_file` gains `workspace_file` in the same way.

### 3.7 Companion HTTP endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | none | Railway liveness probe |
| `GET /state/{session_id}` | Bearer token | Returns session's `.state.json` for debugging |

### 3.8 Auth

- `COGNIGY_VIBE_TOKEN`: static Bearer token set as a Railway env var. Protects `PUT /workspace/…` and `GET /state/…`. Not required on MCP tool calls (the MCP session controls tool access).
- Cognigy credentials (`base_url`, `api_key`, `project_id`) are **never set on Railway** — always supplied per-session via `configure`.

---

## 4. Project structure

```
cognigy_mcp/
  __init__.py
  api.py              unchanged
  cache.py            unchanged
  state.py            modified — STATE_BASE reads COGNIGY_VIBE_DATA_DIR
  server.py           unchanged — stdio entrypoint
  session.py          new — SessionContext dataclass + session registry + expiry
  server_http.py      new — ASGI app: MCP streamable-HTTP + upload + health routes
  tools/
    __init__.py       unchanged
    explain.py        unchanged
    file_push.py      modified — workspace_file param on all three push tools
    flow_ops.py       unchanged
    state_tools.py    unchanged
    testing.py        unchanged

pyproject.toml        modified — new entrypoint + starlette + uvicorn deps
Dockerfile            new — Railway image build
railway.toml          new — start command, volume mount config
```

**New files:** `session.py`, `server_http.py`, `Dockerfile`, `railway.toml`  
**Modified files:** `state.py`, `tools/file_push.py`, `pyproject.toml`  
**Unchanged:** everything else

---

## 5. Skill changes

The `cognigy:init-mcp` skill will need a remote-mode branch: instead of writing `stdio` config to `.claude/mcp.json`, it writes the Railway URL + Bearer token. A new `cognigy:upload-file` atomic skill handles the `curl` upload step and is called by `cognigy:push-code` before invoking the MCP tool.

Skill changes are **out of scope for this implementation plan** — they follow once the server is deployed and the endpoint URL is known.

---

## 6. What doesn't change

- All 15 existing tools behave identically once a session is configured — `make_handlers(client, state, cache)` signatures are unchanged; the HTTP server extracts these three objects from the `SessionContext` before calling `make_handlers`, so tool logic is unaware of sessions
- `endpoint_base_url` derivation (`cognigy-api-*` → `cognigy-endpoint-*`) is kept as-is; parameterising it directly is a separate future concern
- Local stdio mode requires zero changes to any existing file

---

## 7. Out of scope

- Horizontal scaling / multiple Railway replicas (sessions are in-process memory; single replica assumed)
- Redis or external state store (filesystem + persistent volume is sufficient for demo workloads)
- Per-user access control beyond the single static Bearer token
- Skill updates (follow-on work, depends on deployed URL)
