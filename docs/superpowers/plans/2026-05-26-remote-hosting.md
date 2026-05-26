# cognigy-vibe Remote Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add StreamableHTTP transport to cognigy-vibe-mcp so it can be deployed on Railway as a shared multi-tenant server.

**Architecture:** A custom `PerSessionMCPManager` creates one `Server` instance per HTTP session (instead of the mcp library's shared-server `StreamableHTTPSessionManager`). Each session-scoped `Server` closes over a `session_ref` list that `configure` populates — no context vars needed. Non-MCP routes (`/health`, `/workspace/…`, `/state/…`) are mounted alongside the MCP endpoint in a single Starlette app.

**Tech Stack:** Python 3.11+, mcp>=1.0.0 (already installed), starlette, uvicorn, anyio (all already present as mcp transitive deps), uv, Railway Persistent Volume at `/data`.

**Spec:** `docs/superpowers/specs/2026-05-26-remote-hosting-design.md`

---

## File Map

| File | Change |
|---|---|
| `cognigy_mcp/state.py` | Add optional `config_base: Path \| None` param to `ProjectState.__init__` |
| `cognigy_mcp/tools/file_push.py` | Add `workspace_dir: Path \| None = None` to `make_handlers`; add `workspace_file` param to all three push tools |
| `cognigy_mcp/session.py` | **New** — `SessionContext` dataclass |
| `cognigy_mcp/server_http.py` | **New** — `PerSessionMCPManager`, `configure` tool, Starlette app, upload + health + state routes |
| `pyproject.toml` | New `cognigy-vibe-mcp-server` script entry; add `starlette`, `uvicorn[standard]`, `anyio` deps |
| `Dockerfile` | **New** — Railway image using uv |
| `railway.toml` | **New** — start command + volume mount |
| `tests/test_state_config_base.py` | **New** — `config_base` param test |
| `tests/tools/test_file_push.py` | Extend — workspace_file tests |
| `tests/test_session.py` | **New** — `SessionContext` creation |
| `tests/test_server_http.py` | **New** — upload endpoint, health, state, configure + tool dispatch |

---

## Task 1: Configurable state base path

**Files:**
- Modify: `cognigy_mcp/state.py`
- Create: `tests/test_state_config_base.py`

- [ ] **Step 1.1: Write failing test**

```python
# tests/test_state_config_base.py
from pathlib import Path
from cognigy_mcp.state import ProjectState


def test_config_base_override(tmp_path):
    custom_base = tmp_path / "custom"
    state = ProjectState(project_id="proj-1", config_base=custom_base)
    assert state.config_dir == custom_base / "proj-1"
    assert state.config_dir.exists()


def test_config_base_default(tmp_path, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "default")
    state = ProjectState(project_id="proj-2")
    assert state.config_dir == tmp_path / "default" / "proj-2"
```

- [ ] **Step 1.2: Run test to verify failure**

```bash
cd cognigy-mcp && uv run pytest tests/test_state_config_base.py -v
```

Expected: `TypeError: ProjectState.__init__() got an unexpected keyword argument 'config_base'`

- [ ] **Step 1.3: Add `config_base` param to `ProjectState.__init__`**

In `cognigy_mcp/state.py`, change:

```python
class ProjectState:
    def __init__(self, project_id: str, resync_hours: float = 4.0):
        self.project_id = project_id
        self.config_dir = CONFIG_BASE / project_id
```

to:

```python
class ProjectState:
    def __init__(self, project_id: str, resync_hours: float = 4.0, config_base: Path | None = None):
        self.project_id = project_id
        self.config_dir = (config_base if config_base is not None else CONFIG_BASE) / project_id
```

- [ ] **Step 1.4: Run tests**

```bash
cd cognigy-mcp && uv run pytest tests/test_state_config_base.py tests/test_state.py -v
```

Expected: all pass

- [ ] **Step 1.5: Commit**

```bash
git add cognigy_mcp/state.py tests/test_state_config_base.py
git commit -m "feat: add config_base param to ProjectState for remote hosting"
```

---

## Task 2: workspace_file support in file_push

**Files:**
- Modify: `cognigy_mcp/tools/file_push.py`
- Modify: `tests/tools/test_file_push.py`

- [ ] **Step 2.1: Write failing tests for workspace_file**

Add to `tests/tools/test_file_push.py`:

```python
def test_push_code_node_workspace_file(mock_client, state, cache, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "payment.js").write_text("api.say('hello');")
    mock_client.get.return_value = {"_id": "node-1", "config": {"code": ""}}
    mock_client.patch.return_value = {"_id": "node-1", "config": {"code": "api.say('hello');"}}
    handlers = make_handlers(mock_client, state, cache, workspace_dir=workspace_dir)
    result = handlers["push_code_node"]({
        "workspace_file": "payment.js",
        "node_id": "node-1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True


def test_push_code_node_workspace_file_not_found(mock_client, state, cache, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    handlers = make_handlers(mock_client, state, cache, workspace_dir=workspace_dir)
    result = handlers["push_code_node"]({
        "workspace_file": "missing.js",
        "node_id": "node-1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_code_node_no_path_arg_returns_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({"node_id": "node-1", "flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_html_node_workspace_file(mock_client, state, cache, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "page.html").write_text("<h1>Hi</h1>")
    mock_client.patch.return_value = {"_id": "node-2"}
    handlers = make_handlers(mock_client, state, cache, workspace_dir=workspace_dir)
    result = handlers["push_html_node"]({
        "workspace_file": "page.html",
        "node_id": "node-2",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True


def test_push_tool_from_file_workspace_file(mock_client, state, cache, tmp_path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    tool_def = {"name": "my_tool", "description": "desc", "parameters": []}
    (workspace_dir / "tool.json").write_text(json.dumps(tool_def))
    mock_client.post.return_value = {"_id": "tool-1", **tool_def}
    handlers = make_handlers(mock_client, state, cache, workspace_dir=workspace_dir)
    result = handlers["push_tool_from_file"]({
        "workspace_file": "tool.json",
        "project_id": "proj-1",
    })
    data = json.loads(result[0].text)
    assert data["_id"] == "tool-1"
```

- [ ] **Step 2.2: Run tests to verify failure**

```bash
cd cognigy-mcp && uv run pytest tests/tools/test_file_push.py::test_push_code_node_workspace_file -v
```

Expected: `TypeError: make_handlers() got an unexpected keyword argument 'workspace_dir'`

- [ ] **Step 2.3: Update `file_push.py` — add `workspace_dir` to `make_handlers` and update tool schemas**

Replace `cognigy_mcp/tools/file_push.py` with:

```python
from __future__ import annotations
import difflib
import json
from pathlib import Path
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="push_code_node",
        description="Push a .js/.ts file to a Cognigy Code node. "
                    "Local mode: provide script_file (absolute path). "
                    "Remote mode: provide workspace_file (relative path within session workspace). "
                    "Performs conflict detection against the last-pushed snapshot.",
        inputSchema={
            "type": "object",
            "properties": {
                "script_file": {"type": "string", "description": "Absolute path to .js or .ts file (local mode)"},
                "workspace_file": {"type": "string", "description": "Relative path within session workspace (remote mode)"},
                "node_id": {"type": "string"},
                "flow_id": {"type": "string"},
            },
            "required": ["node_id", "flow_id"],
        },
    ),
    Tool(
        name="push_html_node",
        description="Push a .html file to a Cognigy setHTMLAppState node. "
                    "Local mode: provide html_file (absolute path). "
                    "Remote mode: provide workspace_file (relative path). "
                    "Automatically sets mode='full'.",
        inputSchema={
            "type": "object",
            "properties": {
                "html_file": {"type": "string", "description": "Absolute path to .html file (local mode)"},
                "workspace_file": {"type": "string", "description": "Relative path within session workspace (remote mode)"},
                "node_id": {"type": "string"},
                "flow_id": {"type": "string"},
            },
            "required": ["node_id", "flow_id"],
        },
    ),
    Tool(
        name="push_tool_from_file",
        description="Read a local JSON tool definition and create or update it in Cognigy. "
                    "Local mode: provide file (absolute path). "
                    "Remote mode: provide workspace_file (relative path).",
        inputSchema={
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Absolute path to JSON tool definition (local mode)"},
                "workspace_file": {"type": "string", "description": "Relative path within session workspace (remote mode)"},
                "project_id": {"type": "string"},
                "tool_id": {"type": "string", "description": "If provided, updates existing tool instead of creating"},
            },
            "required": ["project_id"],
        },
    ),
]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def _diff_summary(old: str, new: str) -> str:
    lines = list(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile="last-pushed",
        tofile="remote-current",
        n=3,
    ))
    if len(lines) > 50:
        truncated = lines[:50]
        truncated.append(f"\n... ({len(lines) - 50} more lines not shown)\n")
        return "".join(truncated)
    return "".join(lines)


def _resolve_path(args: dict, local_key: str, workspace_dir: Path | None) -> tuple[Path | None, list[TextContent] | None]:
    """Resolve script_file/html_file/file or workspace_file to an absolute Path.

    Returns (path, None) on success, or (None, error_response) on failure.
    """
    workspace_file = args.get("workspace_file")
    local_file = args.get(local_key)

    if workspace_file and local_file:
        return None, _ok({"error": f"Provide either {local_key} or workspace_file, not both"})

    if workspace_file:
        if workspace_dir is None:
            return None, _ok({"error": "workspace_file is only supported in remote (HTTP) server mode"})
        return workspace_dir / workspace_file, None

    if local_file:
        return Path(local_file), None

    return None, _ok({"error": f"Either {local_key} or workspace_file is required"})


def make_handlers(
    client: CognigyClient,
    state: ProjectState,
    cache: Cache,
    workspace_dir: Path | None = None,
) -> dict:

    def _push_code_node(args: dict) -> list[TextContent]:
        path, err = _resolve_path(args, "script_file", workspace_dir)
        if err:
            return err

        node_id = args["node_id"]
        flow_id = args["flow_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        local_content = path.read_text()

        try:
            remote = client.get(f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}")
        except Exception as e:
            return _ok({"error": f"Failed to fetch remote node: {e}"})

        remote_code = remote.get("config", {}).get("code", "")
        snapshot = cache.get_node_snapshot(node_id)

        if snapshot is not None and remote_code != snapshot:
            return _ok({
                "conflict": True,
                "message": "Remote node was edited in the Cognigy UI since the last push. "
                           "Review the diff and decide whether to overwrite or incorporate the changes.",
                "diff": _diff_summary(snapshot, remote_code),
            })

        try:
            result = client.patch(
                f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}",
                {"config": {"code": local_content}},
            )
        except Exception as e:
            return _ok({"error": f"Failed to push code to node: {e}"})
        cache.set("nodes", node_id, result)
        cache.set_node_snapshot(node_id, local_content)
        return _ok({"success": True, "node_id": node_id, "bytes": len(local_content)})

    def _push_html_node(args: dict) -> list[TextContent]:
        path, err = _resolve_path(args, "html_file", workspace_dir)
        if err:
            return err

        node_id = args["node_id"]
        flow_id = args["flow_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        html = path.read_text()
        try:
            result = client.patch(
                f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}",
                {"config": {"html": html, "mode": "full"}},
            )
        except Exception as e:
            return _ok({"error": f"Failed to patch node: {e}"})
        cache.set("nodes", node_id, result)
        return _ok({"success": True, "node_id": node_id, "bytes": len(html)})

    def _push_tool_from_file(args: dict) -> list[TextContent]:
        path, err = _resolve_path(args, "file", workspace_dir)
        if err:
            return err

        project_id = args["project_id"]
        tool_id = args.get("tool_id")

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        try:
            body = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            return _ok({"error": f"Invalid JSON in {path}: {e}"})

        try:
            if tool_id:
                result = client.patch(f"/v2.0/projects/{project_id}/tools/{tool_id}", body)
            else:
                result = client.post(f"/v2.0/projects/{project_id}/tools", body)
        except Exception as e:
            return _ok({"error": f"Failed to push tool: {e}"})

        name = result.get("name")
        rid = result.get("_id")
        if name and rid:
            state.set("tools", name, value={"id": rid})
        return _ok(result)

    return {
        "push_code_node": _push_code_node,
        "push_html_node": _push_html_node,
        "push_tool_from_file": _push_tool_from_file,
    }
```

- [ ] **Step 2.4: Run all file_push tests**

```bash
cd cognigy-mcp && uv run pytest tests/tools/test_file_push.py -v
```

Expected: all pass

- [ ] **Step 2.5: Commit**

```bash
git add cognigy_mcp/tools/file_push.py tests/tools/test_file_push.py
git commit -m "feat: add workspace_file param to file_push tools for remote server mode"
```

---

## Task 3: SessionContext dataclass

**Files:**
- Create: `cognigy_mcp/session.py`
- Create: `tests/test_session.py`

- [ ] **Step 3.1: Write failing test**

```python
# tests/test_session.py
from pathlib import Path
from unittest.mock import MagicMock
from cognigy_mcp.session import SessionContext


def test_session_context_creation(tmp_path):
    client = MagicMock()
    state = MagicMock()
    cache = MagicMock()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    handlers = {"some_tool": lambda args: []}

    ctx = SessionContext(
        client=client,
        state=state,
        cache=cache,
        workspace_dir=workspace,
        handlers=handlers,
    )

    assert ctx.client is client
    assert ctx.state is state
    assert ctx.cache is cache
    assert ctx.workspace_dir == workspace
    assert ctx.handlers is handlers
```

- [ ] **Step 3.2: Run test to verify failure**

```bash
cd cognigy-mcp && uv run pytest tests/test_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'cognigy_mcp.session'`

- [ ] **Step 3.3: Create `cognigy_mcp/session.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState


@dataclass
class SessionContext:
    client: CognigyClient
    state: ProjectState
    cache: Cache
    workspace_dir: Path
    handlers: dict[str, Any]
```

- [ ] **Step 3.4: Run test**

```bash
cd cognigy-mcp && uv run pytest tests/test_session.py -v
```

Expected: PASS

- [ ] **Step 3.5: Commit**

```bash
git add cognigy_mcp/session.py tests/test_session.py
git commit -m "feat: add SessionContext dataclass for per-session HTTP server state"
```

---

## Task 4: HTTP server

**Files:**
- Create: `cognigy_mcp/server_http.py`
- Create: `tests/test_server_http.py`

- [ ] **Step 4.1: Write failing tests for the HTTP endpoints**

```python
# tests/test_server_http.py
import json
import os
import pytest
from pathlib import Path
from starlette.testclient import TestClient


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("COGNIGY_VIBE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("COGNIGY_VIBE_TOKEN", "test-token")
    return tmp_path / "data"


@pytest.fixture
def app(data_dir):
    from cognigy_mcp.server_http import create_app
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_requires_auth(client, data_dir):
    resp = client.put(
        "/workspace/proj-1/code.js",
        content=b"api.say('hello');",
    )
    assert resp.status_code == 401


def test_upload_creates_file(client, data_dir):
    resp = client.put(
        "/workspace/proj-1/subdir/code.js",
        content=b"api.say('hello');",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    dest = data_dir / "workspaces" / "proj-1" / "subdir" / "code.js"
    assert dest.exists()
    assert dest.read_bytes() == b"api.say('hello');"


def test_upload_nested_path(client, data_dir):
    resp = client.put(
        "/workspace/proj-2/a/b/c/script.js",
        content=b"// deep",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    dest = data_dir / "workspaces" / "proj-2" / "a" / "b" / "c" / "script.js"
    assert dest.exists()


def test_state_endpoint_missing_project(client):
    resp = client.get(
        "/state/nonexistent-proj",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 404


def test_state_endpoint_requires_auth(client):
    resp = client.get("/state/proj-1")
    assert resp.status_code == 401


def test_state_endpoint_returns_state_json(client, data_dir):
    state_dir = data_dir / "proj-1"
    state_dir.mkdir(parents=True)
    (state_dir / ".state.json").write_text('{"flows": {}}')
    resp = client.get(
        "/state/proj-1",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"flows": {}}
```

- [ ] **Step 4.2: Run tests to verify failure**

```bash
cd cognigy-mcp && uv run pytest tests/test_server_http.py -v
```

Expected: `ModuleNotFoundError: No module named 'cognigy_mcp.server_http'`

- [ ] **Step 4.3: Create `cognigy_mcp/server_http.py`**

```python
from __future__ import annotations
import contextlib
import json
import os
from http import HTTPStatus
from pathlib import Path
from uuid import uuid4

import anyio
from anyio.abc import TaskStatus
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.types import INVALID_REQUEST, ErrorData, JSONRPCError

from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.session import SessionContext
from cognigy_mcp.state import ProjectState
from cognigy_mcp.tools import explain, file_push, flow_ops, state_tools, testing

_CONFIGURE_TOOL = types.Tool(
    name="configure",
    description=(
        "Initialize this MCP session with Cognigy credentials. "
        "Must be called before any other tool. "
        "base_url example: https://cognigy-api-au1.nicecxone.com"
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "base_url": {"type": "string"},
            "api_key": {"type": "string"},
            "project_id": {"type": "string"},
        },
        "required": ["base_url", "api_key", "project_id"],
    },
)

_ALL_TOOLS = (
    [_CONFIGURE_TOOL]
    + state_tools.TOOLS
    + flow_ops.TOOLS
    + file_push.TOOLS
    + testing.TOOLS
    + explain.TOOLS
)


def _ok(data: dict) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


def _data_base() -> Path:
    return Path(os.getenv("COGNIGY_VIBE_DATA_DIR", str(Path.home() / ".config" / "cognigy-mcp")))


def _make_session_server(session_ref: list[SessionContext | None]) -> Server:
    """Create one MCPServer for one HTTP session. session_ref is filled by configure."""
    server = Server("cognigy-vibe")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return _ALL_TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name == "configure":
            base_url = (arguments.get("base_url") or "").strip()
            api_key = (arguments.get("api_key") or "").strip()
            project_id = (arguments.get("project_id") or "").strip()

            if not all([base_url, api_key, project_id]):
                return _ok({"error": "base_url, api_key, and project_id are all required"})

            data_base = _data_base()
            workspace_dir = data_base / "workspaces" / project_id
            workspace_dir.mkdir(parents=True, exist_ok=True)

            client = CognigyClient(base_url=base_url, api_key=api_key)
            state = ProjectState(
                project_id=project_id,
                resync_hours=float(os.getenv("COGNIGY_VIBE_RESYNC_HOURS", "4")),
                config_base=data_base,
            )
            cache = Cache(
                cache_dir=state.config_dir / "cache",
                ttl=int(os.getenv("COGNIGY_VIBE_CACHE_TTL", "300")),
            )
            handlers = {
                **state_tools.make_handlers(client, state, cache),
                **flow_ops.make_handlers(client, state, cache),
                **file_push.make_handlers(client, state, cache, workspace_dir=workspace_dir),
                **testing.make_handlers(client, state, cache),
                **explain.make_handlers(client, state, cache),
            }
            session_ref[0] = SessionContext(
                client=client,
                state=state,
                cache=cache,
                workspace_dir=workspace_dir,
                handlers=handlers,
            )
            return _ok({"configured": True, "project_id": project_id})

        ctx = session_ref[0]
        if ctx is None:
            return _ok({"error": "session not configured", "hint": "Call configure first"})

        if name != "sync_remote_state" and ctx.state.needs_resync():
            try:
                ctx.handlers["sync_remote_state"]({"project_id": ctx.state.project_id})
            except Exception:
                pass

        handler = ctx.handlers.get(name)
        if not handler:
            return _ok({"error": f"Unknown tool: {name}"})

        ctx.state.touch_interaction()
        return handler(arguments or {})

    return server


class PerSessionMCPManager:
    """Manages one MCPServer per HTTP session for isolated Cognigy credentials."""

    def __init__(self) -> None:
        self._transports: dict[str, StreamableHTTPServerTransport] = {}
        self._task_group: anyio.abc.TaskGroup | None = None

    @contextlib.asynccontextmanager
    async def run(self):
        async with anyio.create_task_group() as tg:
            self._task_group = tg
            try:
                yield
            finally:
                tg.cancel_scope.cancel()
                self._task_group = None
                self._transports.clear()

    async def handle_request(self, scope: Scope, receive: Receive, send: Send) -> None:
        from starlette.requests import Request as StarletteRequest
        request = StarletteRequest(scope, receive)
        mcp_sid = request.headers.get("mcp-session-id")

        if mcp_sid is not None:
            transport = self._transports.get(mcp_sid)
            if transport is None:
                err = JSONRPCError(
                    jsonrpc="2.0",
                    id="server-error",
                    error=ErrorData(code=INVALID_REQUEST, message="Session not found"),
                )
                resp = Response(
                    content=err.model_dump_json(by_alias=True, exclude_none=True),
                    status_code=HTTPStatus.NOT_FOUND,
                    media_type="application/json",
                )
                await resp(scope, receive, send)
                return
            await transport.handle_request(scope, receive, send)
            return

        # New session
        assert self._task_group is not None, "Call handle_request inside the run() context"
        new_sid = uuid4().hex
        session_ref: list[SessionContext | None] = [None]
        server = _make_session_server(session_ref)
        transport = StreamableHTTPServerTransport(mcp_session_id=new_sid)
        self._transports[new_sid] = transport

        async def run_server(*, task_status: TaskStatus[None] = anyio.TASK_STATUS_IGNORED) -> None:
            async with transport.connect() as (read, write):
                task_status.started()
                try:
                    await server.run(read, write, server.create_initialization_options())
                except Exception:
                    pass
                finally:
                    self._transports.pop(new_sid, None)

        await self._task_group.start(run_server)
        await transport.handle_request(scope, receive, send)


def _check_bearer(request: Request) -> bool:
    token = os.getenv("COGNIGY_VIBE_TOKEN", "")
    if not token:
        return True
    return request.headers.get("authorization", "") == f"Bearer {token}"


def create_app() -> Starlette:
    manager = PerSessionMCPManager()

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with manager.run():
            yield

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def upload_file(request: Request) -> Response:
        if not _check_bearer(request):
            return Response("Unauthorized", status_code=401)
        project_id = request.path_params["project_id"]
        file_path = request.path_params["path"]
        dest = _data_base() / "workspaces" / project_id / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(await request.body())
        return JSONResponse({"stored": str(dest)})

    async def get_state(request: Request) -> Response:
        if not _check_bearer(request):
            return Response("Unauthorized", status_code=401)
        project_id = request.path_params["project_id"]
        state_path = _data_base() / project_id / ".state.json"
        if not state_path.exists():
            return Response("Not Found", status_code=404)
        return Response(state_path.read_text(), media_type="application/json")

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await manager.handle_request(scope, receive, send)

    return Starlette(
        lifespan=lifespan,
        routes=[
            Route("/health", health),
            Route("/workspace/{project_id}/{path:path}", upload_file, methods=["PUT"]),
            Route("/state/{project_id}", get_state, methods=["GET"]),
            Mount("/mcp", handle_mcp),
        ],
    )


def main() -> None:
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4.4: Run tests**

```bash
cd cognigy-mcp && uv run pytest tests/test_server_http.py -v
```

Expected: all 7 tests pass

- [ ] **Step 4.5: Write and run configure unit test**

Add to `tests/test_server_http.py`:

```python
def test_configure_tool_creates_session(tmp_path, monkeypatch):
    monkeypatch.setenv("COGNIGY_VIBE_DATA_DIR", str(tmp_path / "data"))
    from cognigy_mcp.session import SessionContext
    from cognigy_mcp.server_http import _make_session_server
    import asyncio

    session_ref: list[SessionContext | None] = [None]
    server = _make_session_server(session_ref)

    # We need to invoke the call_tool handler directly.
    # The Server stores its handler in _tool_handler.
    # Easiest: call the registered async handler.
    handler = server._tool_handler

    result = asyncio.run(handler("configure", {
        "base_url": "https://cognigy-api-au1.example.com",
        "api_key": "test-key",
        "project_id": "proj-99",
    }))
    data = json.loads(result[0].text)
    assert data["configured"] is True
    assert session_ref[0] is not None
    assert session_ref[0].state.project_id == "proj-99"
    assert (tmp_path / "data" / "workspaces" / "proj-99").exists()


def test_tool_call_before_configure_returns_error(tmp_path, monkeypatch):
    monkeypatch.setenv("COGNIGY_VIBE_DATA_DIR", str(tmp_path / "data"))
    from cognigy_mcp.server_http import _make_session_server
    import asyncio

    session_ref: list[None] = [None]
    server = _make_session_server(session_ref)
    handler = server._tool_handler

    result = asyncio.run(handler("cognigy_get", {"resource_type": "flows", "resource_id": "abc"}))
    data = json.loads(result[0].text)
    assert "error" in data
    assert "configure" in data.get("hint", "")
```

Run:

```bash
cd cognigy-mcp && uv run pytest tests/test_server_http.py -v
```

Expected: all 9 tests pass

Note: if `server._tool_handler` is not the right attribute name, check `Server` source at `.venv/lib/.../mcp/server/lowlevel/server.py` for the registered call_tool handler attribute and adjust the test accordingly.

- [ ] **Step 4.6: Run full test suite to check for regressions**

```bash
cd cognigy-mcp && uv run pytest -v
```

Expected: all pass

- [ ] **Step 4.7: Commit**

```bash
git add cognigy_mcp/server_http.py cognigy_mcp/session.py tests/test_server_http.py
git commit -m "feat: add HTTP server with per-session MCP instances for Railway deployment"
```

---

## Task 5: Packaging and deployment config

**Files:**
- Modify: `pyproject.toml`
- Create: `cognigy-mcp/Dockerfile`
- Create: `cognigy-mcp/railway.toml`

- [ ] **Step 5.1: Update `pyproject.toml` — new entrypoint + deps**

In `cognigy-mcp/pyproject.toml`, update `[project.scripts]`:

```toml
[project.scripts]
cognigy-vibe-mcp = "cognigy_mcp.server:main"
cognigy-vibe-mcp-server = "cognigy_mcp.server_http:main"
```

Update `[project]` dependencies:

```toml
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "starlette>=0.41.0",
    "uvicorn[standard]>=0.32.0",
    "anyio>=4.0.0",
]
```

- [ ] **Step 5.2: Verify the new entrypoint installs and runs**

```bash
cd cognigy-mcp && uv pip install -e . && cognigy-vibe-mcp-server --help
```

Expected: uvicorn starts (or at minimum the command is found). `Ctrl+C` to stop.

- [ ] **Step 5.3: Create `Dockerfile`**

Create `cognigy-mcp/Dockerfile`:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml .
COPY cognigy_mcp/ cognigy_mcp/

RUN uv pip install --system .

ENV PORT=8080
EXPOSE 8080

CMD ["cognigy-vibe-mcp-server"]
```

- [ ] **Step 5.4: Create `railway.toml`**

Create `cognigy-mcp/railway.toml`:

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "cognigy-vibe-mcp-server"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

[[volumes]]
mountPath = "/data"
```

- [ ] **Step 5.5: Verify Docker build (if Docker is available)**

```bash
cd cognigy-mcp && docker build -t cognigy-vibe-mcp-server .
```

Expected: image builds successfully

- [ ] **Step 5.6: Run full test suite one last time**

```bash
cd cognigy-mcp && uv run pytest -v
```

Expected: all pass

- [ ] **Step 5.7: Commit**

```bash
git add cognigy-mcp/pyproject.toml cognigy-mcp/Dockerfile cognigy-mcp/railway.toml
git commit -m "feat: add Railway deployment config and HTTP server entrypoint to pyproject"
```

---

## Self-Review Against Spec

| Spec requirement | Covered by |
|---|---|
| StreamableHTTP transport | Task 4 — `PerSessionMCPManager` + `StreamableHTTPServerTransport` |
| Per-session `configure` tool | Task 4 — `_CONFIGURE_TOOL` + handler in `_make_session_server` |
| `session_ref` isolation | Task 4 — one `list[SessionContext | None]` per session |
| `COGNIGY_VIBE_DATA_DIR` env var | Task 1 — `config_base` param; Task 4 — `_data_base()` |
| `workspace_file` param | Task 2 — `_resolve_path()` in `file_push.py` |
| `PUT /workspace/{project_id}/{path}` | Task 4 — `upload_file` route |
| Bearer token auth | Task 4 — `_check_bearer()` |
| `GET /health` | Task 4 — `health` route |
| `GET /state/{project_id}` | Task 4 — `get_state` route |
| `cognigy-vibe-mcp-server` entrypoint | Task 5 — `pyproject.toml` + `main()` |
| Railway Dockerfile + railway.toml | Task 5 |
| Local stdio mode unchanged | No task — `server.py` untouched throughout |
| Auto-resync logic | Task 4 — mirrored from `server.py` in `call_tool` handler |

**Note on Task 4, Step 4.5:** The `server._tool_handler` attribute name is an implementation detail of the mcp library. If it's not accessible that way, the configure unit test should instead test `_make_session_server` by calling configure through an in-process MCP channel (look at `tests/test_server.py` for existing patterns). Adjust accordingly — the test logic is what matters, not the exact invocation path.
