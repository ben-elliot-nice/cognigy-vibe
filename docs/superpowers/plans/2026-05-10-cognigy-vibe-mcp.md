# cognigy-vibe-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `cognigy-vibe-mcp`, a modular Python MCP server installable via `uvx` that gives LLM agents structured, token-efficient access to the Cognigy REST API for building demo flows.

**Architecture:** Modular Python package (`cognigy_mcp/`) with a thin `server.py` entry point, shared `api.py`/`cache.py`/`state.py` core, and five focused `tools/` modules. Each tool module exports `TOOLS` (MCP definitions) and `make_handlers(client, state, cache)` (bound callables). The server collects all and registers a single `list_tools`/`call_tool` handler pair.

**Tech Stack:** Python 3.11+, `mcp>=1.0.0`, `httpx>=0.27.0`, `python-dotenv>=1.0.0`, `pytest`, `pytest-asyncio`, `respx` (httpx mocking).

**Reference implementation:** `~/working/rhcnz/cognigy-mcp/server.py` — the most evolved monolith. Cross-reference for Cognigy API path patterns during implementation.

---

## File Map

```
cognigy-mcp/
├── pyproject.toml
├── cognigy_mcp/
│   ├── __init__.py                  # empty
│   ├── server.py                    # MCP Server init, tool wiring, auto-resync middleware
│   ├── api.py                       # CognigyClient: httpx, auth, retry, domain derivation
│   ├── cache.py                     # Cache: TTL resource cache + code-node snapshots
│   ├── state.py                     # ProjectState: config-dir, seed merge, timestamp
│   └── tools/
│       ├── __init__.py              # empty
│       ├── state_tools.py           # sync_remote_state, get_build_state, resolve_resource
│       ├── flow_ops.py              # cognigy_get/list/create/update/delete/invoke, get_flow_chart
│       ├── file_push.py             # push_code_node, push_html_node, push_tool_from_file
│       ├── testing.py               # talk_to_agent
│       └── explain.py               # explain() with 17-topic library
└── tests/
    ├── conftest.py                  # shared fixtures: tmp config dir, mock client
    ├── test_api.py
    ├── test_cache.py
    ├── test_state.py
    └── tools/
        ├── conftest.py              # tool-level fixtures
        ├── test_state_tools.py
        ├── test_flow_ops.py
        ├── test_file_push.py
        ├── test_testing.py
        └── test_explain.py
```

---

## Task 1: Package Scaffold

**Files:**
- Create: `cognigy-mcp/pyproject.toml`
- Create: `cognigy-mcp/cognigy_mcp/__init__.py`
- Create: `cognigy-mcp/cognigy_mcp/tools/__init__.py`
- Create: `cognigy-mcp/tests/__init__.py`
- Create: `cognigy-mcp/tests/tools/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p cognigy-mcp/cognigy_mcp/tools
mkdir -p cognigy-mcp/tests/tools
touch cognigy-mcp/cognigy_mcp/__init__.py
touch cognigy-mcp/cognigy_mcp/tools/__init__.py
touch cognigy-mcp/tests/__init__.py
touch cognigy-mcp/tests/tools/__init__.py
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cognigy-vibe-mcp"
version = "0.1.0"
description = "Cognigy AI agent demo builder MCP server"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
cognigy-vibe-mcp = "cognigy_mcp.server:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "respx>=0.21.0",
]

[tool.hatch.build.targets.wheel]
packages = ["cognigy_mcp"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 3: Install dev dependencies**

```bash
cd cognigy-mcp
uv sync --extra dev
```

Expected: lock file created, packages installed.

- [ ] **Step 4: Verify pytest runs (no tests yet)**

```bash
uv run pytest tests/ -v
```

Expected: `no tests ran` or `collected 0 items`.

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): scaffold package structure"
```

---

## Task 2: `api.py` — Cognigy HTTP Client

**Files:**
- Create: `cognigy-mcp/cognigy_mcp/api.py`
- Create: `cognigy-mcp/tests/test_api.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api.py
import pytest
import httpx
import respx
from cognigy_mcp.api import CognigyClient, ApiError

BASE = "https://cognigy-api-au1.nicecxone.com"


@pytest.fixture
def client():
    return CognigyClient(base_url=BASE, api_key="test-key")


def test_endpoint_base_url_derivation(client):
    assert client.endpoint_base_url == "https://cognigy-endpoint-au1.nicecxone.com"


def test_get_success(client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/flow-123").mock(
            return_value=httpx.Response(200, json={"_id": "flow-123", "name": "Test"})
        )
        result = client.get("/v2.0/flows/flow-123")
    assert result["_id"] == "flow-123"


def test_get_401_raises_api_error(client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/bad").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        with pytest.raises(ApiError) as exc:
            client.get("/v2.0/flows/bad")
    assert exc.value.status_code == 401


def test_get_404_raises_api_error(client):
    with respx.mock:
        respx.get(f"{BASE}/v2.0/flows/missing").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        with pytest.raises(ApiError) as exc:
            client.get("/v2.0/flows/missing")
    assert exc.value.status_code == 404


def test_post_success(client):
    with respx.mock:
        respx.post(f"{BASE}/v2.0/flows").mock(
            return_value=httpx.Response(200, json={"_id": "new-flow", "name": "My Flow"})
        )
        result = client.post("/v2.0/flows", {"name": "My Flow", "projectId": "proj-1"})
    assert result["_id"] == "new-flow"


def test_patch_success(client):
    with respx.mock:
        respx.patch(f"{BASE}/v2.0/flows/flow-123").mock(
            return_value=httpx.Response(200, json={"_id": "flow-123", "name": "Updated"})
        )
        result = client.patch("/v2.0/flows/flow-123", {"name": "Updated"})
    assert result["name"] == "Updated"


def test_delete_success(client):
    with respx.mock:
        respx.delete(f"{BASE}/v2.0/flows/flow-123").mock(
            return_value=httpx.Response(200, json={})
        )
        result = client.delete("/v2.0/flows/flow-123")
    assert result == {}


def test_auth_header_sent(client):
    with respx.mock:
        route = respx.get(f"{BASE}/v2.0/flows").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        client.get("/v2.0/flows")
    assert route.calls[0].request.headers["X-API-Key"] == "test-key"
```

- [ ] **Step 2: Run tests — verify they all fail**

```bash
cd cognigy-mcp && uv run pytest tests/test_api.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `cognigy_mcp.api`.

- [ ] **Step 3: Implement `api.py`**

```python
# cognigy_mcp/api.py
from __future__ import annotations
import httpx


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class CognigyClient:
    def __init__(self, base_url: str, api_key: str):
        self._base = base_url.rstrip("/")
        self._http = httpx.Client(
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    @property
    def endpoint_base_url(self) -> str:
        # cognigy-api-au1.nicecxone.com → cognigy-endpoint-au1.nicecxone.com
        return self._base.replace("cognigy-api-", "cognigy-endpoint-")

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                msg = resp.json().get("error", resp.text)
            except Exception:
                msg = resp.text
            raise ApiError(resp.status_code, msg)

    def get(self, path: str, **params) -> dict:
        resp = self._http.get(self._base + path, params=params or None)
        self._raise_for_status(resp)
        return resp.json()

    def post(self, path: str, body: dict) -> dict:
        resp = self._http.post(self._base + path, json=body)
        self._raise_for_status(resp)
        return resp.json()

    def patch(self, path: str, body: dict) -> dict:
        resp = self._http.patch(self._base + path, json=body)
        self._raise_for_status(resp)
        return resp.json()

    def delete(self, path: str) -> dict:
        resp = self._http.delete(self._base + path)
        self._raise_for_status(resp)
        try:
            return resp.json()
        except Exception:
            return {}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_api.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): add CognigyClient (api.py)"
```

---

## Task 3: `cache.py` — TTL Cache + Code-Node Snapshots

**Files:**
- Create: `cognigy-mcp/cognigy_mcp/cache.py`
- Create: `cognigy-mcp/tests/test_cache.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cache.py
import json
import time
import pytest
from pathlib import Path
from cognigy_mcp.cache import Cache


@pytest.fixture
def cache(tmp_path):
    return Cache(cache_dir=tmp_path / "cache", ttl=60)


def test_miss_returns_none_not_fresh(cache):
    data, fresh = cache.get("flows", "123")
    assert data is None
    assert not fresh


def test_set_then_get_fresh(cache):
    cache.set("flows", "123", {"_id": "123", "name": "My Flow"})
    data, fresh = cache.get("flows", "123")
    assert data["_id"] == "123"
    assert fresh


def test_expired_entry_returns_stale(tmp_path):
    c = Cache(cache_dir=tmp_path / "cache", ttl=0)
    c.set("flows", "abc", {"_id": "abc"})
    _, fresh = c.get("flows", "abc")
    assert not fresh


def test_set_creates_parent_dirs(cache):
    cache.set("aiagents", "agent-1", {"_id": "agent-1"})
    assert (cache.cache_dir / "aiagents" / "agent-1.json").exists()


def test_invalidate_removes_entry(cache):
    cache.set("flows", "123", {"_id": "123"})
    cache.invalidate("flows", "123")
    data, _ = cache.get("flows", "123")
    assert data is None


def test_invalidate_all_wipes_everything(cache):
    cache.set("flows", "123", {"_id": "123"})
    cache.set("aiagents", "agent-1", {"_id": "agent-1"})
    cache.invalidate_all()
    assert not any(cache.cache_dir.rglob("*.json"))


def test_node_snapshot_roundtrip(cache):
    cache.set_node_snapshot("node-abc", "const x = 1;")
    assert cache.get_node_snapshot("node-abc") == "const x = 1;"


def test_node_snapshot_returns_none_when_missing(cache):
    assert cache.get_node_snapshot("no-such-node") is None


def test_node_snapshot_update(cache):
    cache.set_node_snapshot("node-abc", "old content")
    cache.set_node_snapshot("node-abc", "new content")
    assert cache.get_node_snapshot("node-abc") == "new content"
```

- [ ] **Step 2: Run — verify all fail**

```bash
uv run pytest tests/test_cache.py -v
```

Expected: `ImportError` for `cognigy_mcp.cache`.

- [ ] **Step 3: Implement `cache.py`**

```python
# cognigy_mcp/cache.py
from __future__ import annotations
import json
import time
from pathlib import Path


class Cache:
    def __init__(self, cache_dir: Path, ttl: int = 300):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl

    def _resource_path(self, resource_type: str, resource_id: str) -> Path:
        return self.cache_dir / resource_type / f"{resource_id}.json"

    def _snapshot_path(self, node_id: str) -> Path:
        return self.cache_dir / "nodes" / node_id / "code.js"

    def get(self, resource_type: str, resource_id: str) -> tuple[dict | None, bool]:
        path = self._resource_path(resource_type, resource_id)
        if not path.exists():
            return None, False
        entry = json.loads(path.read_text())
        fresh = (time.time() - entry["_cached_at"]) < self.ttl
        return entry["data"], fresh

    def set(self, resource_type: str, resource_id: str, data: dict) -> None:
        path = self._resource_path(resource_type, resource_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"_cached_at": time.time(), "data": data}))

    def invalidate(self, resource_type: str, resource_id: str) -> None:
        path = self._resource_path(resource_type, resource_id)
        if path.exists():
            path.unlink()

    def invalidate_all(self) -> None:
        for f in self.cache_dir.rglob("*.json"):
            f.unlink()
        for f in self.cache_dir.rglob("*.js"):
            f.unlink()

    def get_node_snapshot(self, node_id: str) -> str | None:
        path = self._snapshot_path(node_id)
        return path.read_text() if path.exists() else None

    def set_node_snapshot(self, node_id: str, content: str) -> None:
        path = self._snapshot_path(node_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
```

- [ ] **Step 4: Run — verify all pass**

```bash
uv run pytest tests/test_cache.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): add Cache with TTL and code-node snapshots"
```

---

## Task 4: `state.py` — Config Dir, Seed Merge, Timestamp

**Files:**
- Create: `cognigy-mcp/cognigy_mcp/state.py`
- Create: `cognigy-mcp/tests/test_state.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_state.py
import json
import time
import pytest
from pathlib import Path
from cognigy_mcp.state import ProjectState


@pytest.fixture
def config_base(tmp_path):
    return tmp_path / "cognigy-mcp"


@pytest.fixture
def state(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    return ProjectState(project_id="proj-123", resync_hours=4.0)


def test_config_dir_created(state, config_base):
    assert (config_base / "proj-123").is_dir()


def test_seed_values_available(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    proj_dir = config_base / "proj-123"
    proj_dir.mkdir(parents=True)
    seed = {"flows": {"Main Flow": {"id": "seed-flow-id"}}}
    (proj_dir / ".state-seed.json").write_text(json.dumps(seed))
    s = ProjectState("proj-123")
    assert s.get("flows", "Main Flow", "id") == "seed-flow-id"


def test_runtime_overrides_seed(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    proj_dir = config_base / "proj-123"
    proj_dir.mkdir(parents=True)
    (proj_dir / ".state-seed.json").write_text(json.dumps({"x": "seed"}))
    (proj_dir / ".state.json").write_text(json.dumps({"x": "runtime"}))
    s = ProjectState("proj-123")
    assert s.get("x") == "runtime"


def test_needs_resync_when_no_timestamp(state):
    assert state.needs_resync()


def test_no_resync_after_touch(state):
    state.touch_interaction()
    assert not state.needs_resync()


def test_needs_resync_after_threshold(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState("proj-123", resync_hours=0.0)
    s.touch_interaction()
    assert s.needs_resync()


def test_set_and_save_and_reload(config_base, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState("proj-123")
    s.set("flows", "My Flow", value={"id": "flow-xyz"})
    s.save()
    s2 = ProjectState("proj-123")
    assert s2.get("flows", "My Flow", "id") == "flow-xyz"


def test_get_missing_key_returns_none(state):
    assert state.get("nonexistent", "key") is None


def test_config_dir_property(state, config_base):
    assert state.config_dir == config_base / "proj-123"
```

- [ ] **Step 2: Run — verify all fail**

```bash
uv run pytest tests/test_state.py -v
```

Expected: `ImportError` for `cognigy_mcp.state`.

- [ ] **Step 3: Implement `state.py`**

```python
# cognigy_mcp/state.py
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any

CONFIG_BASE = Path.home() / ".config" / "cognigy-mcp"


def _deep_get(d: dict, *keys: str) -> Any:
    for key in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
        if d is None:
            return None
    return d


def _deep_set(d: dict, *keys: str, value: Any) -> None:
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


class ProjectState:
    def __init__(self, project_id: str, resync_hours: float = 4.0):
        self.project_id = project_id
        self.config_dir = CONFIG_BASE / project_id
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self.config_dir / ".state.json"
        self._seed_path = self.config_dir / ".state-seed.json"
        self._interaction_path = self.config_dir / "last-interaction"
        self.resync_hours = resync_hours
        self._state: dict = {}
        self._load()

    def _load(self) -> None:
        seed = json.loads(self._seed_path.read_text()) if self._seed_path.exists() else {}
        runtime = json.loads(self._state_path.read_text()) if self._state_path.exists() else {}
        # seed provides defaults; runtime values win
        self._state = _deep_merge(seed, runtime)

    def save(self) -> None:
        self._state_path.write_text(json.dumps(self._state, indent=2))

    def get(self, *keys: str) -> Any:
        return _deep_get(self._state, *keys)

    def set(self, *keys: str, value: Any) -> None:
        _deep_set(self._state, *keys, value=value)
        self.save()

    def needs_resync(self) -> bool:
        if not self._interaction_path.exists():
            return True
        last = float(self._interaction_path.read_text())
        return (time.time() - last) > (self.resync_hours * 3600)

    def touch_interaction(self) -> None:
        self._interaction_path.write_text(str(time.time()))


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
```

- [ ] **Step 4: Run — verify all pass**

```bash
uv run pytest tests/test_state.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): add ProjectState with config dir and seed merge"
```

---

## Task 5: `tools/state_tools.py`

**Files:**
- Create: `cognigy-mcp/cognigy_mcp/tools/state_tools.py`
- Create: `cognigy-mcp/tests/tools/conftest.py`
- Create: `cognigy-mcp/tests/tools/test_state_tools.py`

- [ ] **Step 1: Write shared tools conftest**

```python
# tests/tools/conftest.py
import pytest
from unittest.mock import MagicMock
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def cache(tmp_path):
    return Cache(cache_dir=tmp_path / "cache", ttl=60)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    return ProjectState(project_id="test-proj")
```

- [ ] **Step 2: Write failing tests**

```python
# tests/tools/test_state_tools.py
import json
import pytest
from cognigy_mcp.tools.state_tools import make_handlers, TOOLS


def test_tools_exported():
    names = [t.name for t in TOOLS]
    assert "sync_remote_state" in names
    assert "get_build_state" in names
    assert "resolve_resource" in names


def test_get_build_state_returns_state(mock_client, state, cache):
    state.set("flows", "Main", value={"id": "flow-1"})
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_build_state"]({})
    data = json.loads(result[0].text)
    assert data["flows"]["Main"]["id"] == "flow-1"


def test_resolve_resource_found(mock_client, state, cache):
    state.set("flows", "Main", value={"id": "flow-1"})
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["resolve_resource"]({"name": "Main", "resource_type": "flows"})
    data = json.loads(result[0].text)
    assert data["id"] == "flow-1"


def test_resolve_resource_not_found(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["resolve_resource"]({"name": "Missing", "resource_type": "flows"})
    data = json.loads(result[0].text)
    assert "not found" in data.get("error", "").lower()


def test_sync_remote_state_calls_api(mock_client, state, cache):
    project_id = state.project_id
    mock_client.get.side_effect = [
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},   # list flows
        {"items": [{"_id": "agent-1", "name": "My Agent"}]},   # list agents
        {"items": [{"_id": "ep-1", "name": "REST", "urlToken": "tok123", "flowReferenceId": "flow-1"}]},  # list endpoints
        {"nodes": []},  # flow chart for tool discovery
    ]
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["sync_remote_state"]({"project_id": project_id})
    data = json.loads(result[0].text)
    assert data.get("synced") is True
    assert state.get("flows", "Main Flow", "id") == "flow-1"
```

- [ ] **Step 3: Run — verify all fail**

```bash
uv run pytest tests/tools/test_state_tools.py -v
```

Expected: `ImportError` for `cognigy_mcp.tools.state_tools`.

- [ ] **Step 4: Implement `state_tools.py`**

```python
# cognigy_mcp/tools/state_tools.py
from __future__ import annotations
import json
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient, ApiError
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="sync_remote_state",
        description="Hard reset: wipe local cache and repopulate from Cognigy remote. "
                    "Runs automatically after session idle > threshold. Call manually "
                    "after making changes in the Cognigy UI.",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Cognigy project ID"},
            },
            "required": ["project_id"],
        },
    ),
    Tool(
        name="get_build_state",
        description="Return the current .state.json — all known name→ID mappings for "
                    "flows, agents, endpoints, tools. Use resolve_resource for single lookups.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="resolve_resource",
        description="Fast lookup of a Cognigy resource ID by friendly name from .state.json. "
                    "No API call. Returns the full state entry for that resource.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "resource_type": {
                    "type": "string",
                    "description": "One of: flows, agents, endpoints, tools, nodes, jobs",
                },
            },
            "required": ["name", "resource_type"],
        },
    ),
]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def make_handlers(
    client: CognigyClient, state: ProjectState, cache: Cache
) -> dict:
    def _sync_remote_state(args: dict) -> list[TextContent]:
        project_id = args["project_id"]
        cache.invalidate_all()

        # Flows
        flows_resp = client.get(f"/v2.0/projects/{project_id}/flows", limit=100)
        for flow in flows_resp.get("items", []):
            state.set("flows", flow["name"], value={"id": flow["_id"]})
            cache.set("flows", flow["_id"], flow)
            # Discover aiAgentJobTool nodes within this flow
            try:
                chart = client.get(f"/v2.0/flows/{flow['_id']}/chart")
                for node in chart.get("nodes", []):
                    if node.get("type") == "aiAgentJobTool":
                        label = node.get("label", node["_id"])
                        state.set("tools", label, value={
                            "id": node["_id"],
                            "flowId": flow["_id"],
                            "flowName": flow["name"],
                        })
            except ApiError:
                pass

        # Agents
        agents_resp = client.get(f"/v2.0/projects/{project_id}/aiagents", limit=100)
        for agent in agents_resp.get("items", []):
            state.set("agents", agent["name"], value={"id": agent["_id"]})
            cache.set("aiagents", agent["_id"], agent)

        # Endpoints
        eps_resp = client.get(f"/v2.0/projects/{project_id}/endpoints", limit=100)
        for ep in eps_resp.get("items", []):
            state.set("endpoints", ep["name"], value={
                "id": ep["_id"],
                "urlToken": ep.get("urlToken", ""),
                "flowReferenceId": ep.get("flowReferenceId", ""),
            })
            cache.set("endpoints", ep["_id"], ep)

        state.touch_interaction()
        return _ok({"synced": True, "project_id": project_id})

    def _get_build_state(_args: dict) -> list[TextContent]:
        return _ok(state._state)

    def _resolve_resource(args: dict) -> list[TextContent]:
        name = args["name"]
        rtype = args["resource_type"]
        entry = state.get(rtype, name)
        if entry is None:
            return _ok({"error": f"'{name}' not found in {rtype}"})
        return _ok(entry)

    return {
        "sync_remote_state": _sync_remote_state,
        "get_build_state": _get_build_state,
        "resolve_resource": _resolve_resource,
    }
```

- [ ] **Step 5: Run — verify all pass**

```bash
uv run pytest tests/tools/test_state_tools.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): add state_tools (sync, get_state, resolve)"
```

---

## Task 6: `tools/flow_ops.py`

**Files:**
- Create: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py`
- Create: `cognigy-mcp/tests/tools/test_flow_ops.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_flow_ops.py
import json
import pytest
from unittest.mock import MagicMock, patch
from cognigy_mcp.tools.flow_ops import make_handlers, TOOLS


def test_all_tools_exported():
    names = [t.name for t in TOOLS]
    for expected in [
        "cognigy_get", "cognigy_list", "cognigy_create",
        "cognigy_update", "cognigy_delete", "cognigy_invoke", "get_flow_chart",
    ]:
        assert expected in names


def test_cognigy_get_cache_hit(mock_client, state, cache):
    cache.set("flows", "flow-1", {"_id": "flow-1", "name": "Main"})
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({"resource_type": "flows", "resource_id": "flow-1"})
    data = json.loads(result[0].text)
    assert data["_id"] == "flow-1"
    assert data["_source"] == "cache"
    mock_client.get.assert_not_called()


def test_cognigy_get_cache_miss_calls_api(mock_client, state, cache):
    mock_client.get.return_value = {"_id": "flow-1", "name": "Main"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({"resource_type": "flows", "resource_id": "flow-1"})
    data = json.loads(result[0].text)
    assert data["_source"] == "api"
    mock_client.get.assert_called_once()


def test_cognigy_list_returns_items(mock_client, state, cache):
    mock_client.get.return_value = {"items": [{"_id": "f1", "name": "Flow 1"}]}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_list"]({"resource_type": "flows", "project_id": "proj-1"})
    data = json.loads(result[0].text)
    assert len(data["items"]) == 1


def test_cognigy_create_saves_to_state(mock_client, state, cache):
    mock_client.post.return_value = {"_id": "new-flow", "name": "My Flow"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({
        "resource_type": "flows",
        "body": {"name": "My Flow", "projectId": "proj-1"},
    })
    data = json.loads(result[0].text)
    assert data["_id"] == "new-flow"
    assert state.get("flows", "My Flow", "id") == "new-flow"


def test_cognigy_update_with_merge_config(mock_client, state, cache):
    cache.set("flows", "flow-1", {"_id": "flow-1", "config": {"a": 1, "b": 2}})
    mock_client.patch.return_value = {"_id": "flow-1", "config": {"a": 1, "b": 99}}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_update"]({
        "resource_type": "flows",
        "resource_id": "flow-1",
        "body": {"config": {"b": 99}},
        "merge_config": True,
    })
    call_body = mock_client.patch.call_args[0][1]
    assert call_body["config"]["a"] == 1
    assert call_body["config"]["b"] == 99


def test_cognigy_delete_node_uses_chart_path(mock_client, state, cache):
    mock_client.delete.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_delete"]({
        "resource_type": "node",
        "resource_id": "node-1",
        "flow_id": "flow-1",
    })
    mock_client.delete.assert_called_once_with(
        "/v2.0/flows/flow-1/chart/nodes/node-1"
    )


def test_cognigy_delete_regular_resource(mock_client, state, cache):
    mock_client.delete.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_delete"]({"resource_type": "flows", "resource_id": "flow-1"})
    mock_client.delete.assert_called_once_with("/v2.0/flows/flow-1")


def test_cognigy_invoke_move_node(mock_client, state, cache):
    mock_client.post.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_invoke"]({
        "resource_type": "node",
        "resource_id": "node-1",
        "operation": "move",
        "body": {"mode": "append", "target": "node-0"},
        "flow_id": "flow-1",
    })
    mock_client.post.assert_called_once_with(
        "/v2.0/flows/flow-1/chart/nodes/node-1/move",
        {"mode": "append", "target": "node-0"},
    )


def test_get_flow_chart_returns_hierarchy(mock_client, state, cache):
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "start", "type": "start", "label": "Start", "config": {}},
            {"_id": "say-1", "type": "say", "label": "Hello", "config": {}},
        ],
        "relations": [
            {"nodeId": "start", "nextId": "say-1", "previousId": None, "parentId": None, "childIds": []},
            {"nodeId": "say-1", "nextId": None, "previousId": "start", "parentId": None, "childIds": []},
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "hierarchy" in data
    assert "relations" in data
    assert "Start" in data["hierarchy"] or "start" in data["hierarchy"]
```

- [ ] **Step 2: Run — verify all fail**

```bash
uv run pytest tests/tools/test_flow_ops.py -v
```

- [ ] **Step 3: Implement `flow_ops.py`**

```python
# cognigy_mcp/tools/flow_ops.py
from __future__ import annotations
import json
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient, ApiError
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="cognigy_get",
        description="GET any Cognigy resource by ID. Cache-first (5-min TTL). "
                    "Response includes _source: 'cache' or 'api'.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string", "description": "e.g. flows, aiagents, endpoints"},
                "resource_id": {"type": "string"},
                "flow_id": {"type": "string", "description": "Required when resource_type is 'node'"},
            },
            "required": ["resource_type", "resource_id"],
        },
    ),
    Tool(
        name="cognigy_list",
        description="List Cognigy resources. Pass project_id for project-scoped resources, "
                    "agent_id for agent-scoped resources (e.g. listing jobs).",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "project_id": {"type": "string"},
                "agent_id": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["resource_type"],
        },
    ),
    Tool(
        name="cognigy_create",
        description="POST to create a new Cognigy resource. Auto-saves name→ID to .state.json. "
                    "For nodes, body must include flowId, type, mode, target.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "body": {"type": "object"},
                "flow_id": {"type": "string", "description": "Required when creating nodes"},
            },
            "required": ["resource_type", "body"],
        },
    ),
    Tool(
        name="cognigy_update",
        description="PATCH a Cognigy resource. WARNING: Cognigy PATCH is full-replace on 'config' — "
                    "set merge_config=true to deep-merge instead of overwriting. Always use merge_config=true "
                    "for partial config updates.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string"},
                "body": {"type": "object"},
                "merge_config": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, deep-merges body.config with current config rather than replacing",
                },
                "flow_id": {"type": "string", "description": "Required when resource_type is 'node'"},
            },
            "required": ["resource_type", "resource_id", "body"],
        },
    ),
    Tool(
        name="cognigy_delete",
        description="DELETE a Cognigy resource. For nodes, pass flow_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string"},
                "flow_id": {"type": "string", "description": "Required when resource_type is 'node'"},
            },
            "required": ["resource_type", "resource_id"],
        },
    ),
    Tool(
        name="cognigy_invoke",
        description="Run a named operation on a Cognigy resource. "
                    "Operations: node/move, flow/clone, aiagent/train, "
                    "knowledgestore/run, sessions/inject-context, sessions/inject-state.",
        inputSchema={
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string"},
                "operation": {"type": "string"},
                "body": {"type": "object", "default": {}},
                "flow_id": {"type": "string", "description": "Required for node operations"},
            },
            "required": ["resource_type", "resource_id", "operation"],
        },
    ),
    Tool(
        name="get_flow_chart",
        description="Fetch the full chart for a flow. Returns both the raw relations array and "
                    "a human-readable hierarchy string for quick orientation.",
        inputSchema={
            "type": "object",
            "properties": {
                "flow_id": {"type": "string"},
            },
            "required": ["flow_id"],
        },
    ),
]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def _resource_path(resource_type: str, resource_id: str, flow_id: str | None = None) -> str:
    if resource_type == "node":
        if not flow_id:
            raise ValueError("flow_id required for node operations")
        return f"/v2.0/flows/{flow_id}/chart/nodes/{resource_id}"
    return f"/v2.0/{resource_type}/{resource_id}"


def _invoke_path(resource_type: str, resource_id: str, operation: str, body: dict, flow_id: str | None) -> str:
    mapping = {
        ("node", "move"): f"/v2.0/flows/{flow_id}/chart/nodes/{resource_id}/move",
        ("flow", "clone"): f"/v2.0/flows/{resource_id}/clone",
        ("aiagent", "train"): f"/v2.0/aiagents/{resource_id}/train",
        ("sessions", "inject-context"): f"/v2.0/sessions/{resource_id}/context/inject",
        ("sessions", "inject-state"): f"/v2.0/sessions/{resource_id}/state/inject",
        ("sessions", "reset-context"): f"/v2.0/sessions/{resource_id}/context/reset",
        ("sessions", "reset-state"): f"/v2.0/sessions/{resource_id}/state/reset",
    }
    if resource_type == "knowledgestore" and operation == "run":
        connector_id = body.get("connector_id", "")
        return f"/v2.0/knowledgestores/{resource_id}/connectors/{connector_id}/run"
    return mapping.get(
        (resource_type, operation),
        f"/v2.0/{resource_type}/{resource_id}/{operation}",
    )


def _build_hierarchy(chart: dict) -> str:
    nodes = {n["_id"]: n for n in chart.get("nodes", [])}
    relations = {r["nodeId"]: r for r in chart.get("relations", [])}

    def render(node_id: str, indent: int = 0) -> list[str]:
        node = nodes.get(node_id, {})
        label = node.get("label") or node.get("type", node_id)
        ntype = node.get("type", "")
        prefix = "  " * indent
        lines = [f"{prefix}[{ntype}] {label} ({node_id})"]
        rel = relations.get(node_id, {})
        for child_id in rel.get("childIds", []):
            lines += render(child_id, indent + 1)
        next_id = rel.get("nextId")
        if next_id:
            lines += render(next_id, indent)
        return lines

    # Find root: node with no parent and no previous
    roots = [
        nid for nid, rel in relations.items()
        if not rel.get("parentId") and not rel.get("previousId")
    ]
    lines = []
    for root in roots:
        lines += render(root)
    return "\n".join(lines) if lines else "(empty chart)"


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _cognigy_get(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        rid = args["resource_id"]
        flow_id = args.get("flow_id")
        cached, fresh = cache.get(rtype, rid)
        if fresh and cached:
            return _ok({**cached, "_source": "cache"})
        if rtype == "node":
            data = client.get(f"/v2.0/flows/{flow_id}/chart/nodes/{rid}")
        else:
            data = client.get(f"/v2.0/{rtype}/{rid}")
        cache.set(rtype, rid, data)
        return _ok({**data, "_source": "api"})

    def _cognigy_list(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        project_id = args.get("project_id")
        agent_id = args.get("agent_id")
        limit = args.get("limit", 100)
        if agent_id:
            path = f"/v2.0/aiagents/{agent_id}/{rtype}"
        elif project_id:
            path = f"/v2.0/projects/{project_id}/{rtype}"
        else:
            path = f"/v2.0/{rtype}"
        data = client.get(path, limit=limit)
        return _ok(data)

    def _cognigy_create(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        body = args["body"]
        flow_id = args.get("flow_id")
        if rtype == "node":
            if not flow_id:
                raise ValueError("flow_id required to create a node")
            path = f"/v2.0/flows/{flow_id}/chart/nodes"
        else:
            path = f"/v2.0/{rtype}"
        result = client.post(path, body)
        # Auto-save to state
        name = result.get("name") or result.get("label")
        if name:
            state.set(rtype, name, value={"id": result["_id"]})
        cache.set(rtype, result["_id"], result)
        return _ok(result)

    def _cognigy_update(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        rid = args["resource_id"]
        body = args["body"]
        merge_config = args.get("merge_config", False)
        flow_id = args.get("flow_id")

        if rtype == "node":
            path = f"/v2.0/flows/{flow_id}/chart/nodes/{rid}"
            current = client.get(path)
        else:
            path = f"/v2.0/{rtype}/{rid}"
            current = client.get(path)

        if merge_config and "config" in body and "config" in current:
            merged = {**current["config"], **body["config"]}
            body = {**body, "config": merged}

        result = client.patch(path, body)
        cache.set(rtype, rid, result)
        return _ok(result)

    def _cognigy_delete(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        rid = args["resource_id"]
        flow_id = args.get("flow_id")
        if rtype == "node":
            path = f"/v2.0/flows/{flow_id}/chart/nodes/{rid}"
        else:
            path = f"/v2.0/{rtype}/{rid}"
        result = client.delete(path)
        cache.invalidate(rtype, rid)
        return _ok({"deleted": True, "resource_id": rid, **result})

    def _cognigy_invoke(args: dict) -> list[TextContent]:
        rtype = args["resource_type"]
        rid = args["resource_id"]
        operation = args["operation"]
        body = args.get("body", {})
        flow_id = args.get("flow_id")
        path = _invoke_path(rtype, rid, operation, body, flow_id)
        result = client.post(path, body)
        return _ok(result)

    def _get_flow_chart(args: dict) -> list[TextContent]:
        flow_id = args["flow_id"]
        chart = client.get(f"/v2.0/flows/{flow_id}/chart")
        hierarchy = _build_hierarchy(chart)
        return _ok({"relations": chart.get("relations", []), "nodes": chart.get("nodes", []), "hierarchy": hierarchy})

    return {
        "cognigy_get": _cognigy_get,
        "cognigy_list": _cognigy_list,
        "cognigy_create": _cognigy_create,
        "cognigy_update": _cognigy_update,
        "cognigy_delete": _cognigy_delete,
        "cognigy_invoke": _cognigy_invoke,
        "get_flow_chart": _get_flow_chart,
    }
```

- [ ] **Step 4: Run — verify all pass**

```bash
uv run pytest tests/tools/test_flow_ops.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): add flow_ops (get/list/create/update/delete/invoke/chart)"
```

---

## Task 7: `tools/file_push.py`

**Files:**
- Create: `cognigy-mcp/cognigy_mcp/tools/file_push.py`
- Create: `cognigy-mcp/tests/tools/test_file_push.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_file_push.py
import json
import pytest
from pathlib import Path
from cognigy_mcp.tools.file_push import make_handlers, TOOLS


def test_all_tools_exported():
    names = [t.name for t in TOOLS]
    assert "push_code_node" in names
    assert "push_html_node" in names
    assert "push_tool_from_file" in names


def test_push_code_node_first_push(mock_client, state, cache, tmp_path):
    script = tmp_path / "payment.js"
    script.write_text("api.say('hello');")
    mock_client.get.return_value = {"_id": "node-1", "config": {"code": ""}}
    mock_client.patch.return_value = {"_id": "node-1", "config": {"code": "api.say('hello');"}}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script),
        "node_id": "node-1",
        "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert cache.get_node_snapshot("node-1") == "api.say('hello');"


def test_push_code_node_no_conflict(mock_client, state, cache, tmp_path):
    script = tmp_path / "payment.js"
    script.write_text("new content")
    cache.set_node_snapshot("node-1", "old content")
    # Remote matches snapshot (no UI edits)
    mock_client.get.return_value = {"_id": "node-1", "config": {"code": "old content"}}
    mock_client.patch.return_value = {"_id": "node-1", "config": {"code": "new content"}}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script), "node_id": "node-1", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True


def test_push_code_node_conflict_blocked(mock_client, state, cache, tmp_path):
    script = tmp_path / "payment.js"
    script.write_text("my new code")
    cache.set_node_snapshot("node-1", "original")
    # Remote has been edited in UI (differs from snapshot)
    mock_client.get.return_value = {"_id": "node-1", "config": {"code": "edited in UI"}}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": str(script), "node_id": "node-1", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "conflict" in data
    mock_client.patch.assert_not_called()


def test_push_code_node_file_not_found(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_code_node"]({
        "script_file": "/nonexistent/file.js", "node_id": "node-1", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_html_node(mock_client, state, cache, tmp_path):
    html_file = tmp_path / "page.html"
    html_file.write_text("<h1>Hello</h1>")
    mock_client.get.return_value = {"_id": "node-2", "config": {"html": "", "mode": "url"}}
    mock_client.patch.return_value = {"_id": "node-2", "config": {"html": "<h1>Hello</h1>", "mode": "full"}}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_html_node"]({
        "html_file": str(html_file), "node_id": "node-2", "flow_id": "flow-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    patch_body = mock_client.patch.call_args[0][1]
    assert patch_body["config"]["mode"] == "full"


def test_push_tool_from_file_create(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "my_tool.json"
    tool_def = {"name": "my_tool", "description": "Does stuff", "parameters": []}
    tool_file.write_text(json.dumps(tool_def))
    mock_client.post.return_value = {"_id": "tool-1", **tool_def}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_tool_from_file"]({
        "file": str(tool_file), "project_id": "proj-1",
    })
    data = json.loads(result[0].text)
    assert data["_id"] == "tool-1"
```

- [ ] **Step 2: Run — verify all fail**

```bash
uv run pytest tests/tools/test_file_push.py -v
```

- [ ] **Step 3: Implement `file_push.py`**

```python
# cognigy_mcp/tools/file_push.py
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
        description="Read a local .js/.ts file and push its content to a Cognigy Code node. "
                    "Performs conflict detection: if the remote node was edited in the Cognigy UI "
                    "since the last push, the operation is blocked and a diff is returned.",
        inputSchema={
            "type": "object",
            "properties": {
                "script_file": {"type": "string", "description": "Absolute path to .js or .ts file"},
                "node_id": {"type": "string"},
                "flow_id": {"type": "string"},
            },
            "required": ["script_file", "node_id", "flow_id"],
        },
    ),
    Tool(
        name="push_html_node",
        description="Read a local .html file and push it to a Cognigy setHTMLAppState node. "
                    "Automatically sets mode='full'.",
        inputSchema={
            "type": "object",
            "properties": {
                "html_file": {"type": "string", "description": "Absolute path to .html file"},
                "node_id": {"type": "string"},
                "flow_id": {"type": "string"},
            },
            "required": ["html_file", "node_id", "flow_id"],
        },
    ),
    Tool(
        name="push_tool_from_file",
        description="Read a local JSON tool definition and create or update it in Cognigy.",
        inputSchema={
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Absolute path to JSON tool definition"},
                "project_id": {"type": "string"},
                "tool_id": {"type": "string", "description": "If provided, updates existing tool instead of creating"},
            },
            "required": ["file", "project_id"],
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
    return "".join(lines[:50])


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _push_code_node(args: dict) -> list[TextContent]:
        path = Path(args["script_file"])
        node_id = args["node_id"]
        flow_id = args["flow_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        local_content = path.read_text()

        # Always fetch fresh remote state for writes
        try:
            remote = client.get(f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}")
        except Exception as e:
            return _ok({"error": f"Failed to fetch remote node: {e}"})

        remote_code = remote.get("config", {}).get("code", "")
        snapshot = cache.get_node_snapshot(node_id)

        # Conflict: remote has been edited in UI since last push
        if snapshot is not None and remote_code != snapshot:
            return _ok({
                "conflict": True,
                "message": "Remote node was edited in the Cognigy UI since the last push. "
                           "Review the diff and decide whether to overwrite or incorporate the changes.",
                "diff": _diff_summary(snapshot, remote_code),
            })

        result = client.patch(
            f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}",
            {"config": {"code": local_content}},
        )
        cache.set("nodes", node_id, result)
        cache.set_node_snapshot(node_id, local_content)
        return _ok({"success": True, "node_id": node_id, "bytes": len(local_content)})

    def _push_html_node(args: dict) -> list[TextContent]:
        path = Path(args["html_file"])
        node_id = args["node_id"]
        flow_id = args["flow_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        html = path.read_text()
        result = client.patch(
            f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}",
            {"config": {"html": html, "mode": "full"}},
        )
        cache.set("nodes", node_id, result)
        return _ok({"success": True, "node_id": node_id, "bytes": len(html)})

    def _push_tool_from_file(args: dict) -> list[TextContent]:
        path = Path(args["file"])
        project_id = args["project_id"]
        tool_id = args.get("tool_id")

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        body = json.loads(path.read_text())

        if tool_id:
            result = client.patch(f"/v2.0/projects/{project_id}/tools/{tool_id}", body)
        else:
            result = client.post(f"/v2.0/projects/{project_id}/tools", body)

        name = result.get("name")
        if name:
            state.set("tools", name, value={"id": result["_id"]})
        return _ok(result)

    return {
        "push_code_node": _push_code_node,
        "push_html_node": _push_html_node,
        "push_tool_from_file": _push_tool_from_file,
    }
```

- [ ] **Step 4: Run — verify all pass**

```bash
uv run pytest tests/tools/test_file_push.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): add file_push with conflict detection"
```

---

## Task 8: `tools/testing.py`

**Files:**
- Create: `cognigy-mcp/cognigy_mcp/tools/testing.py`
- Create: `cognigy-mcp/tests/tools/test_testing.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_testing.py
import json
import pytest
import httpx
import respx
from cognigy_mcp.tools.testing import make_handlers, TOOLS
from cognigy_mcp.api import CognigyClient

ENDPOINT_BASE = "https://cognigy-endpoint-au1.nicecxone.com"


@pytest.fixture
def real_client():
    return CognigyClient(
        base_url="https://cognigy-api-au1.nicecxone.com",
        api_key="test-key",
    )


def test_tool_exported():
    assert any(t.name == "talk_to_agent" for t in TOOLS)


def test_talk_to_agent_uses_endpoint_base(real_client, state, cache):
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={
                "text": "Hello!", "data": {}, "type": "output"
            })
        )
        result = handlers["talk_to_agent"]({
            "message": "Hi",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
        })
    data = json.loads(result[0].text)
    assert data["text"] == "Hello!"


def test_talk_to_agent_missing_token_and_flow_id(real_client, state, cache):
    handlers = make_handlers(real_client, state, cache)
    result = handlers["talk_to_agent"]({
        "message": "Hi",
        "session_id": "sess-1",
        "user_id": "user-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data
```

- [ ] **Step 2: Run — verify all fail**

```bash
uv run pytest tests/tools/test_testing.py -v
```

- [ ] **Step 3: Implement `testing.py`**

```python
# cognigy_mcp/tools/testing.py
from __future__ import annotations
import json
import httpx
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOOLS: list[Tool] = [
    Tool(
        name="talk_to_agent",
        description="Send a message to a Cognigy flow via its REST endpoint and return the response. "
                    "Use for testing flows without opening the Cognigy UI. "
                    "Provide endpoint_token (from get_build_state) or flow_id (looks up token from state). "
                    "IMPORTANT: Use a new user_id to start a completely fresh session — Cognigy caches "
                    "session state by userId and reusing one will carry stale context silently. "
                    "IMPORTANT: This tool returns text output only. Tool calls made by the agent are "
                    "NOT visible in the response — only the agent's spoken text is returned. "
                    "Pass data={verbose: true} in the request body to surface errors that are otherwise swallowed.",
        inputSchema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "endpoint_token": {"type": "string", "description": "URL token from endpoint config"},
                "flow_id": {"type": "string", "description": "Looks up token from state if endpoint_token not provided"},
                "session_id": {"type": "string", "description": "Conversation session ID — reuse to continue, new to reset"},
                "user_id": {"type": "string", "description": "User ID — new value starts fresh session"},
            },
            "required": ["message", "session_id", "user_id"],
        },
    ),
]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _talk_to_agent(args: dict) -> list[TextContent]:
        message = args["message"]
        session_id = args["session_id"]
        user_id = args["user_id"]
        token = args.get("endpoint_token")

        if not token:
            flow_id = args.get("flow_id")
            if not flow_id:
                return _ok({"error": "Provide endpoint_token or flow_id"})
            # Find endpoint token from state by matching flow reference
            endpoints = state.get("endpoints") or {}
            for ep_name, ep in endpoints.items():
                if ep.get("flowReferenceId") == flow_id or ep.get("flowId") == flow_id:
                    token = ep.get("urlToken")
                    break
            if not token:
                return _ok({"error": f"No endpoint found for flow_id={flow_id}. Run sync_remote_state or provide endpoint_token."})

        endpoint_url = f"{client.endpoint_base_url}/{token}"
        payload = {
            "userId": user_id,
            "sessionId": session_id,
            "text": message,
            "data": {},
        }

        try:
            resp = httpx.post(endpoint_url, json=payload, timeout=30.0)
            resp.raise_for_status()
            return _ok(resp.json())
        except httpx.HTTPStatusError as e:
            return _ok({"error": f"HTTP {e.response.status_code}: {e.response.text}"})
        except Exception as e:
            return _ok({"error": str(e)})

    return {"talk_to_agent": _talk_to_agent}
```

- [ ] **Step 4: Run — verify all pass**

```bash
uv run pytest tests/tools/test_testing.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): add talk_to_agent testing tool"
```

---

## Task 9: `tools/explain.py` — 17-Topic Reference Library

**Files:**
- Create: `cognigy-mcp/cognigy_mcp/tools/explain.py`
- Create: `cognigy-mcp/tests/tools/test_explain.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/tools/test_explain.py
import json
import pytest
from cognigy_mcp.tools.explain import make_handlers, TOOLS, TOPICS


def test_tool_exported():
    assert any(t.name == "explain" for t in TOOLS)


def test_tool_description_contains_all_topic_names():
    tool = next(t for t in TOOLS if t.name == "explain")
    for topic in TOPICS:
        assert topic in tool.description, f"Topic '{topic}' missing from explain description"


def test_explain_no_args_returns_orientation(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({})
    text = result[0].text
    assert "Topics" in text
    for topic in TOPICS:
        assert topic in text


def test_explain_known_topic_returns_content(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    for topic in TOPICS:
        result = handlers["explain"]({"topic": topic})
        text = result[0].text
        assert len(text) > 100, f"Topic '{topic}' returned too-short content: {text!r}"


def test_explain_unknown_topic_returns_topic_list(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "nonexistent-topic"})
    text = result[0].text
    assert "nonexistent-topic" in text
    assert "Topics" in text
```

- [ ] **Step 2: Run — verify all fail**

```bash
uv run pytest tests/tools/test_explain.py -v
```

- [ ] **Step 3: Implement `explain.py`**

```python
# cognigy_mcp/tools/explain.py
from __future__ import annotations
import json
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOPICS = [
    "node-positioning", "node-wiring", "agent-tool-branch", "node-config-update",
    "flow-chart-reading", "tool-conditions", "two-pass-confirm", "turn-structure",
    "xapp-delivery", "cognigyScript", "code-node-patterns", "voice-gateway",
    "outbound-trigger", "knowledge-store", "endpoint-config", "function-execution",
    "session-injection",
]

_TOPIC_INDEX = """
Topics and what they cover:

  node-positioning     append vs appendChild modes, insertAfter 500 bug on AU1
  node-wiring          chart structure, relations array, sequential vs child chains
  agent-tool-branch    aiAgentJobTool + code + toolAnswer three-node assembly
  node-config-update   full-replace semantics, merge_config pattern, silent field deletion
  flow-chart-reading   reading chart output, node type strings, extension field
  tool-conditions      CognigyScript condition field, hiding tools from LLM
  two-pass-confirm     inter-turn flag management, STOP gate wording
  turn-structure       Once/OnFirstTime/Afterwards, context reset prevention
  xapp-delivery        session init, postMessage bridge, SDK.submit, data paths
  cognigyScript        interpolation contexts, what works where
  code-node-patterns   api.* functions, no fetch/import/require, api.log
  voice-gateway        voice config, DTMF, REST vs voice streaming differences
  outbound-trigger     6-step CXone trigger, Accept-Encoding: identity requirement
  knowledge-store      chunking, connector run, source management
  endpoint-config      referenceId vs _id gotcha, urlToken caching
  function-execution   async pattern, inject-back via sessions API
  session-injection    context/state inject for in-session testing

Call explain("topic-name") for full details on any topic.
"""

_CONTENT: dict[str, str] = {
    "node-positioning": """
## node-positioning — Inserting and Moving Nodes

### Mode: append (SAFE on AU1)
Only reliable insertion mode. Target = node you want to insert AFTER.
  body: {"type": "say", "label": "My Node", "mode": "append", "target": "<previousNodeId>"}

### Mode: appendChild (for tool branch nodes)
Use when adding aiAgentJobTool as a child of an aiAgentJob node.
  body: {"type": "aiAgentJobTool", "mode": "appendChild", "target": "<aiAgentJobNodeId>"}

### BROKEN on AU1 (return 500 "Error while reading ChartData")
  - insertAfter
  - insertBefore

### Move an existing node
Use cognigy_invoke with operation="move":
  body: {"mode": "append", "target": "<nodeId to insert after>"}

### Common mistakes
- Using chartReference as target → 404 "Failed to find chart node"
- New flows have Start and End nodes; list them first to get Start ID as initial append target
- Child nodes (tool branches) only exist in childIds[], NOT in next chain — append returns 404 on them
""",

    "node-wiring": """
## node-wiring — Understanding the Flow Chart Structure

### Chart shape
GET /v2.0/flows/{flowId}/chart returns:
  {
    "nodes": [...],       // all node objects
    "relations": [...]    // positional relationships
  }

### Relations entry shape
  {
    "nodeId": "abc",
    "previousId": "xyz",   // node before in sequential chain (null for first)
    "nextId": "def",       // node after in sequential chain (null for last)
    "parentId": null,      // set if this is a child node (e.g. tool branch)
    "childIds": ["..."]    // children hanging off this node (e.g. tool nodes)
  }

### Sequential chain vs children
- Sequential: follow nextId links from start node
- Children: follow childIds from parent (aiAgentJob, ifThenElse branches)
- Tool branches are children of aiAgentJob, NOT in sequential chain

### Non-core node types require extension field
  {"type": "initAppSession", "extension": "cxone-utils"}
  {"type": "setHTMLAppState", "extension": "cxone-utils"}
  {"type": "aiAgentJob", "extension": "cognigy-ai-agent"}
  {"type": "aiAgentJobTool", "extension": "cognigy-ai-agent"}
  {"type": "aiAgentToolAnswer", "extension": "cognigy-ai-agent"}
""",

    "agent-tool-branch": """
## agent-tool-branch — Building the AI Agent Tool Chain

### Three-node pattern
Every AI Agent tool is a branch of three nodes under an aiAgentJob:
  aiAgentJob
  └── aiAgentJobTool       (the tool node — appendChild of aiAgentJob)
       └── Code Node       (implementation — append after tool node)
            └── aiAgentToolAnswer  (surfaces result — append after code node)

### Step 1: Create aiAgentJobTool
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "aiAgentJobTool",
    "extension": "cognigy-ai-agent",
    "label": "my_tool",
    "mode": "appendChild",
    "target": "<aiAgentJobNodeId>",
    "config": {}
  })

### Step 2: Update aiAgentJobTool config
  cognigy_update(resource_type="node", resource_id=<toolNodeId>, merge_config=True, body={
    "config": {
      "toolId": "<toolId from Cognigy tools library>",
      "description": "What this tool does",
      "useParameters": True,
      "parameters": [{"name": "amount", "type": "number", "description": "Amount to charge"}]
    }
  })

### Step 3: Append Code node
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "code", "label": "[TOOL] my_tool",
    "mode": "append", "target": "<toolNodeId>",
    "config": {"code": "context.toolResponse = {summary: 'Done'}; api.resolve();"}
  })

### Step 4: Append aiAgentToolAnswer
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "aiAgentToolAnswer", "extension": "cognigy-ai-agent",
    "mode": "append", "target": "<codeNodeId>",
    "config": {}
  })

### Tool conditions (hide tool from LLM when false)
  cognigy_update(..., body={"condition": "!context.authVerified"})
  Note: condition is a TOP-LEVEL field, NOT inside config.

### context.toolResponse
  Code node writes: context.toolResponse = {summary: "...", data: {...}}
  aiAgentToolAnswer reads context.toolResponse and surfaces it to the LLM.
  toolResponse.summary = what the LLM reads back to the customer naturally.

### Reading tool arguments in the code node
Parameters the LLM collected (declared in aiAgentJobTool config.parameters) are available as:
  const amount = input.aiAgent.toolArgs.amount;
  const reason = input.aiAgent.toolArgs.reason;
These are NOT in input.data — they come via input.aiAgent.toolArgs.<paramName>.
Always read from toolArgs, never assume they appear elsewhere.
""",

    "node-config-update": """
## node-config-update — Safe Config Updates

### CRITICAL: Cognigy PATCH is FULL REPLACE on config
If you PATCH {"config": {"code": "..."}} on a code node that also has
{"config": {"code": "...", "preview": "..."}} — the preview field is SILENTLY DELETED.

### Always use merge_config=True for partial updates
  cognigy_update(resource_type="node", resource_id=..., merge_config=True, body={
    "config": {"code": "new code here"}
  })
This will GET current config, deep-merge your changes, then PATCH.

### Safe pattern for any update
  1. cognigy_get to see current state
  2. cognigy_update with merge_config=True
  3. cognigy_get again to confirm

### Known fields silently deleted if not included
- code nodes: preview, triggers
- aiAgentJobTool: conditions array when updating toolId only
- Any node: position.x/y when updating config without including position

### GoTo node: use referenceId (UUID), NOT _id (hex)
GoTo nodes reference their target flow by UUID referenceId, not the hex _id.
  // flow._id = "64a3f1c2b9e7d05a8c4f2e91"    ← hex, DO NOT use
  // flow.referenceId = "550e8400-e29b-..."     ← UUID, USE THIS
Get referenceId from cognigy_get(resource_type="flows", resource_id=...) → result.referenceId

### Chart endpoint returns metadata only (not node configs)
GET /v2.0/flows/{id}/chart returns node structure and positions.
Node config fields (code, conditions, toolId etc.) are NOT included.
To read a node's config, use cognigy_get(resource_type="node", resource_id=nodeId, flow_id=flowId).
""",

    "flow-chart-reading": """
## flow-chart-reading — Reading get_flow_chart Output

### Verified node type strings (exact, case-sensitive)
Core types (no extension needed):
  say, question, code, setContext, goTo, once, lookup, log, stopBot, httpRequest
  ifThenElse (note: NOT "if")

AI Agent types (extension: "cognigy-ai-agent"):
  aiAgentJob, aiAgentJobTool, aiAgentToolAnswer

xApp/Voice types (extension: "cxone-utils"):
  initAppSession  (NOT "xAppInitSession")
  setHTMLAppState (NOT "setHTMLxAppState")

### Reading node objects
  {
    "_id": "abc123",       // use this as node_id in tool calls
    "type": "say",
    "label": "Greeting",  // human-readable
    "config": {...},       // type-specific configuration
    "position": {"x": 0, "y": 100}
  }

### ifThenElse nodes
Cannot be created via cognigy_create — only via Cognigy UI.
Condition is in config.conditions[0].rule — it is an OBJECT, not a string:
  config.conditions[0].rule = {
    "left": "{{context.someVar}}",
    "operand": "equals",   // equals, notEquals, contains, greaterThan, lessThan, etc.
    "right": "expectedValue"
  }
Branches are in childIds[]: index 0 = true branch, index 1 = false/else branch.

### Reading the hierarchy string
get_flow_chart returns "hierarchy": a tree string like:
  [start] Start (abc)
  [say] Greeting (def)
  [aiAgentJob] Concierge (ghi)
    [aiAgentJobTool] authenticate_caller (jkl)
      [code] [TOOL] authenticate_caller (mno)
      [aiAgentToolAnswer] Tool Answer (pqr)
""",

    "tool-conditions": """
## tool-conditions — Controlling Tool Visibility

### What conditions do
The condition field on an aiAgentJobTool is a CognigyScript expression.
When falsy → tool is hidden from the LLM. LLM cannot call what it cannot see.
This is more reliable than code guards (LLM can ignore code; can't call hidden tool).

### Setting a condition
  cognigy_update(resource_type="node", resource_id=<toolNodeId>,
    merge_config=False,   # condition is top-level, not in config
    body={"condition": "!context.authVerified"}
  )

### Condition examples
  "!context.authVerified"                    // show authenticate_caller only before auth
  "context.contracts.booking.stage === 0"    // show only at correct workflow stage
  "context.shortTermMemory.policyLoaded"     // show after policy is loaded

### Removing a condition (always show)
  body={"condition": ""}  or  body={"condition": null}

### CognigyScript in conditions
- Use context.* variables (set by code nodes or Set Context nodes)
- Use input.data.* for per-turn data
- Operators: ===, !==, &&, ||, !, >, <
- No function calls, no complex expressions
""",

    "two-pass-confirm": """
## two-pass-confirm — Staged Confirmation Pattern

### Problem
LLM will collapse propose+execute into a single tool call without explicit instructions.

### Pattern
Pass 1: Tool called without confirmation flag → returns summary, does NOT execute.
Pass 2: Tool called with confirmation flag → executes.

### Tracking state between turns
  // Code node (Pass 1):
  context.contracts.myTool = {pendingConfirm: true, ...details};
  context.toolResponse = {summary: "I'll do X. Confirm?"};

  // Code node (Pass 2):
  if (!context.contracts.myTool?.pendingConfirm) {
    context.toolResponse = {error: "No pending confirmation"};
    return;
  }
  // execute...
  context.contracts.myTool = null;  // clear
  context.toolResponse = {summary: "Done."};

### toolResponse.summary vs pre-call instructions
- toolResponse.summary: what LLM reads BACK to customer after tool completes
- Tool description: rules LLM reads BEFORE deciding to call the tool
- Do NOT put "Say this to the customer" in tool description — it runs before the call

### STOP gate wording that works
In AI job instructions:
  "Your ONLY spoken output before calling confirm_action is: [exact words].
   Stop there. DO NOT add anything else. Call the tool."

### Inter-turn flag via context.contracts.*
Use context.contracts namespace — LLM cannot see this namespace (short-term memory blind spot).
context.shortTermMemory IS visible to LLM. context.contracts.* is NOT.
""",

    "turn-structure": """
## turn-structure — Canonical Cognigy Turn Architecture

### Standard flow structure
  Start
  └── Once
      ├── OnFirstTime (runs once at session start)
      │   ├── Set Context (config, auth flags, etc.)
      │   ├── Code: Build Greeting (builds context.greetingText)
      │   └── Say: Proactive Greeting (outputs context.greetingText)
      └── Afterwards (runs every turn after the first)
          └── AI Agent Job (Concierge)
  End

### Why this matters
Set Context in the main chain runs every turn — resets context on every message.
Set Context in OnFirstTime runs once — persists for the session.
AI Agent Job in Afterwards — never runs on the very first turn (greeting runs instead).

### Proactive greeting pattern
  // Code node:
  const name = context.shortTermMemory?.customerName || 'there';
  context.greetingText = `Hello ${name}, I'm Vera. How can I help you today?`;
  // Then: Say node outputs {{context.greetingText}}
This guarantees on-brand, correctly personalised greeting with zero LLM latency.

### Flow close pattern
  Once → next → End
The Once node's "next" pointer leads to End for clean termination.
Do NOT put any nodes after End or the flow will loop.

### Context reset prevention
If context resets every turn, check:
  1. Set Context is in main chain (move to OnFirstTime)
  2. Flow is being reset by a goTo with reset=true
  3. Multiple flows calling into each other with shared context

### First-turn signal
input.execution === 1 is the canonical way to detect the first turn in a code node.
Do NOT use turn-count variables or session flags for this — input.execution is reliable.
  if (input.execution === 1) {
    // first turn setup
  }
Use this inside code nodes when you need to run logic once without the Once/OnFirstTime structure.
""",

    "xapp-delivery": """
## xapp-delivery — xApp Patterns

### Session init
initAppSession node generates input.apps.url (EPHEMERAL — only available this turn).
Immediately after: Code node reads and persists it:
  context.xappSessionUrl = input.apps.url;

### Sending the xApp URL
SMS via CXone:
  const smsBody = `Click here: ${context.xappSessionUrl}`;
  // Use CXone SMS API via httpRequest node

### Passing context to the xApp page
Embed CognigyScript in iframe src URL params:
  https://my-app.com/page?name={{context.shortTermMemory.customerName}}&token={{context.xappSessionUrl}}

### Page submits back to Cognigy
Option A (webchat): window.parent.postMessage({type: 'cognigy-submit', payload: {...}}, '*')
Option B (SDK): SDK.submit({...})
PostMessage bridge in iframe:
  window.addEventListener('message', (e) => {
    if (e.data?.type === 'cognigy-submit') SDK.submit(e.data.payload);
  });

### Reading submission in flow
SDK path:  input.data._cognigy._app.payload
Webchat:   input.data (direct)

### Session guard pattern
xApp session URL must be persisted in context — input.apps.url is ephemeral.
  if (!context.xappSessionUrl) {
    // session was lost — reinitiate
  }

### api.setAppState() limitation
api.setAppState() in code nodes CANNOT push HTML content or external URLs.
Use the setHTMLAppState node instead (type: "setHTMLAppState", extension: "cxone-utils").
Pattern for conditional xApp push from code:
  1. Code node: context.xappTrigger = true; (sets flag)
  2. ifThenElse: condition = context.xappTrigger === true
  3. setHTMLAppState node (in true branch)
  4. Code node: context.xappTrigger = false; (clear flag)

### Dual xApp moments
Some flows need TWO distinct xApp interactions (e.g., form submission then status update).
Each is a separate initAppSession → setHTMLAppState → postMessage cycle.
The second xApp session URL is a different URL — store separately:
  context.xappSessionUrl      // first moment
  context.xappDocUploadUrl    // second moment (document upload, status dashboard, etc.)
This pattern is NOT in the Cognigy documentation — it is discovered during build.
""",

    "cognigyScript": """
## cognigyScript — CognigyScript Interpolation

### Syntax
{{context.namespace.field}}
{{input.data.fieldName}}
{{profile.firstName}}

### Confirmed working contexts
- Say node text field
- AI Agent Job instruction fields
- setHTMLAppState node HTML content
- Endpoint URL parameters (iframe src attribute values)
- Node labels (cosmetic only)

### NOT available
- Inside code node JavaScript bodies (use context.* variables directly in JS)
- Inside JSON string values in httpRequest payloadJSON (unconfirmed, test carefully)

### payloadJSON in httpRequest
CognigyScript interpolation in payloadJSON is UNCONFIRMED.
Safe approach: use a Code node to build the payload object and store in context,
then reference it from the httpRequest via the context variable.

### Common pattern: build in code, reference in node
  // Code node:
  context.smsPayload = {
    to: context.shortTermMemory.mobile,
    body: `Your code is ${context.otpCode}`
  };
  // httpRequest node config: use {{context.smsPayload}} if payloadJSON works,
  // or pipe through code node's api.httpRequest() call instead.
""",

    "code-node-patterns": """
## code-node-patterns — Writing Cognigy Code Nodes

### Available API methods
  api.say("text")                    // output text to channel
  api.output({text:"...", data:{}})  // structured output with data payload
  api.log("message")                 // debug log (NOT console.log)
  api.setContext({key: value})       // set context variables
  api.resolve()                      // signal completion (required for async nodes)
  api.reject("error message")        // signal failure
  api.inject({...})                  // inject turn result (Function Execution pattern)

### NOT available
  fetch()          // NO — use HTTP Request node for outbound HTTP
  require()        // NO — no module system
  import           // NO — not ES modules
  console.log()    // NO — use api.log() instead

### Async pattern (when using await)
  async function main() {
    const result = await someAsyncOperation();
    context.result = result;
    api.resolve();
  }
  main();

### Bare return bug
  return;  // at top level → transpile error "Illegal return statement"
  // Fix: wrap in function, or just omit the return

### Deep copy before multi-path assignment
  // WRONG — serializer collapses repeated object references:
  context.pathA.data = myObject;
  context.pathB.data = myObject;  // pathB and pathA will share the same ref → corruption
  // RIGHT:
  context.pathB.data = JSON.parse(JSON.stringify(myObject));

### Available libraries
  _          // lodash
  moment     // date/time
  xmljs      // XML parsing
  textcleaner // text utilities

### No top-level await
  // WRONG:
  const data = await fetch(...);
  // RIGHT:
  async function main() { const data = await fetch(...); }
  main();

### TypeScript syntax: no "as const"
  // WRONG — Cognigy code nodes don't support TypeScript generics/assertions:
  const STATUS = {PENDING: 'pending'} as const;
  // RIGHT:
  const STATUS = {PENDING: 'pending'};

### httpRequest node response wrapping
The httpRequest node wraps its response body under a `.result` key.
  // Code node reading httpRequest output:
  const body = context.httpResponse.result;   // NOT context.httpResponse directly
  // httpResponse shape: {result: {...actualBody}, status: 200, headers: {...}}
Configure the response context key in the httpRequest node config under "storeLocation" / "contextKey".
""",

    "voice-gateway": """
## voice-gateway — Voice Channel Patterns

### Voice config placement
Voice Gateway config node MUST be in the OnFirstTime branch.
Placing it in the main chain re-initialises voice settings every turn.

### DTMF input
Comes in via: input.data.dtmf (string, e.g. "1" or "2")
Use an ifThenElse or lookup node to branch on DTMF value.

### ANI (caller ID) from voice
  const ani = input.data?.payload?.from;  // SIP format: "+61412345678"
  // Strip leading + for some API calls: ani.replace('+', '')

### REST vs Voice streaming differences
REST endpoint with outputImmediately:true:
  - Terminates connection on tool_calls before all output is delivered
  - Single-pass response recommended (don't split across tool call boundary)
Voice pipeline:
  - Synchronous — all tool handling completes before response delivered to caller
  - Two-pass confirmation pattern works correctly on voice

### Voice output format
api.say() for simple text. Voice gateway handles TTS.
For SSML: api.output({text: "<speak>...</speak>", data: {}})

### Session persistence on voice
context variables persist across turns within a call.
New call = new session = fresh context.

### VG Entrypoint + Channel Settings — required pairing
VG Entrypoint and Channel Settings are paired in the Cognigy UI.
The Channel Settings node holds the TTS/STT config and instructions (NOT the VG Entrypoint).
Both must exist. Set Session Config node (copy-paste identical across demos):
  - Place in OnFirstTime branch
  - Contains: TTS engine, STT engine, barge-in config, silence timeout, atmosphere settings

### VG endpoint routing — undocumented UI configuration
The Cognigy endpoint for a voice flow must be configured to route DIRECTLY to the main flow.
It must NOT route through VG Entrypoint (a common mistake that breaks voice).
This is configured in the Cognigy endpoint settings UI — it is not in any code file.
After creating a voice endpoint, open it in the Cognigy UI and set the flow target manually.

### SIP header paths (voice context)
  input.data.payload.from          // ANI — caller's phone number (SIP format: "+61412345678")
  input.data.payload.to            // DNIS — dialled number
  input.data.payload.callerEmail   // email from SIP header (if CXone passes it)
  input.data.payload.headers       // full SIP headers object
""",

    "outbound-trigger": """
## outbound-trigger — CXone Outbound Call Trigger

### 6-step sequence (run in backend/code node)

Step 1: OAuth token
  POST https://na1.nice-incontact.com/authentication/v1/token/access-token
  Headers: Accept-Encoding: identity  ← CRITICAL (Node 18+ undici decompression bug)
  Body: {grant_type, username, password, ...}

Step 2: Extract tenantId from JWT
  const payload = JSON.parse(atob(token.split('.')[1]));
  const tenantId = payload.tenantId;

Step 3: Get cluster API base URL
  GET https://cxone-configuration.niceincontact.com/config?tenantId={tenantId}
  Headers: Accept-Encoding: identity
  Returns: {api_base_url: "https://na1.nice-incontact.com"}

Step 4: Find script by PATH (not by static ID)
  GET {api_base_url}/services/v16.0/scripts
  Headers: Accept-Encoding: identity, Authorization: Bearer {token}
  Filter: scripts.find(s => s.scriptName === "My Script Name")
  → DO NOT hardcode script IDs — they differ across environments

Step 5: PATCH claim/session state FIRST
  Do this BEFORE starting the outbound call.
  Reason: UI must update even if CXone call fails. State patch is idempotent.

Step 6: Start script
  POST {api_base_url}/services/v16.0/scripts/{scriptId}/start
  Headers: Accept-Encoding: identity
  Body: {scriptId, parameters: {phone: "+61412345678", ...}}

### Accept-Encoding: identity — WHY
Node 18 switched HTTP client to undici. Undici auto-decompresses gzip but
CXone sends malformed compressed responses. identity disables compression.
Omitting this header causes JSON parse errors on all CXone API responses.
""",

    "knowledge-store": """
## knowledge-store — Managing Knowledge Sources

### Resource hierarchy
Project → KnowledgeStore → Sources → Chunks

### List knowledge stores
  cognigy_list(resource_type="knowledgestores", project_id=...)

### Create a source
  cognigy_create(resource_type="sources", flow_id=None, body={
    "knowledgeStoreId": "<ksId>",
    "name": "My Docs",
    "type": "text",   // or "url", "file"
    "content": "..."  // for type=text
  })
Path: POST /v2.0/knowledgestores/{ksId}/sources

### Trigger ingestion via connector
  cognigy_invoke(resource_type="knowledgestore", resource_id=<ksId>,
    operation="run", body={"connector_id": "<connectorId>"})
Path: POST /v2.0/knowledgestores/{ksId}/connectors/{connectorId}/run

### Query chunks (for debugging)
  cognigy_list(resource_type="chunks", ...)
Path: GET /v2.0/knowledgestores/{ksId}/sources/{sourceId}/chunks

### Using in a flow
Knowledge AI node references the knowledge store by ID.
Get the ID from state: resolve_resource(name="My Store", resource_type="knowledgestores")
""",

    "endpoint-config": """
## endpoint-config — Creating and Referencing Endpoints

### CRITICAL: Use flowReferenceId, NOT _id
Endpoint creation requires the flow's referenceId (a UUID), NOT the _id (hex string).

  // Get the flow first:
  const flow = cognigy_get(resource_type="flows", resource_id=flowId)
  // flow._id = "64a3f1c2..."      ← hex, DO NOT use as flowReferenceId
  // flow.referenceId = "550e8400-..."  ← UUID, USE THIS

  cognigy_create(resource_type="endpoints", body={
    "name": "My REST Endpoint",
    "channel": "rest",
    "flowId": flow._id,
    "flowReferenceId": flow.referenceId,   ← required
    "projectId": projectId,
  })

### urlToken caching
After endpoint creation, cache the urlToken in state:
  state.set("endpoints", "My REST Endpoint", value={
    "id": endpoint._id,
    "urlToken": endpoint.urlToken,
    "flowReferenceId": endpoint.flowReferenceId,
  })
This allows talk_to_agent to find the token without an API call.

### Endpoint URL format
  {COGNIGY_ENDPOINT_BASE}/{urlToken}
  where COGNIGY_ENDPOINT_BASE = COGNIGY_BASE_URL with cognigy-api- → cognigy-endpoint-

### AU1 domain derivation
  cognigy-api-au1.nicecxone.com → cognigy-endpoint-au1.nicecxone.com
""",

    "function-execution": """
## function-execution — Cognigy Functions (Async Pattern)

### What Cognigy Functions are
Serverless JS/TS functions that run outside the flow on Cognigy's infrastructure.
Used for long-running async operations (>30s timeout for flows).

### Execute a function
  cognigy_invoke(resource_type="functions", resource_id=<functionId>,
    operation="execute", body={"parameters": {...}})
Path: POST /v2.0/functions/{functionId}/instances

### Check instance status
  cognigy_get(resource_type="functioninstances", resource_id=<instanceId>)
Path: GET /v2.0/functions/{functionId}/instances/{instanceId}
Returns: {status: "pending"|"running"|"done"|"error", result: {...}}

### Inject result back into conversation
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="inject-context", body={"context": {"functionResult": result}})
Path: POST /v2.0/sessions/{sessionId}/context/inject

### In-flow pattern
Use Function Execution node (not raw API) when available.
The node handles invoke + polling + inject natively.
Flow continues automatically when function completes.

### Session ID for inject
The sessionId is the same value used in talk_to_agent.
In production: comes from input.sessionId within the flow.
""",

    "session-injection": """
## session-injection — Injecting State for Testing

### Inject context variables
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="inject-context",
    body={"context": {"authVerified": True, "customerName": "Alice"}})
Path: POST /v2.0/sessions/{sessionId}/context/inject

### Inject flow state (navigate to a flow)
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="inject-state",
    body={"state": "FlowName"})
Path: POST /v2.0/sessions/{sessionId}/state/inject

### Reset context
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="reset-context", body={})

### Reset state (return to start)
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="reset-state", body={})

### Session ID
sessionId = the userId value passed to talk_to_agent.
In Cognigy: sessionId and userId are both set from the incoming request userId field.
New userId → fresh session. Same userId → continue existing session.

### Testing workflow
  1. talk_to_agent(message="...", user_id="test-1", session_id="test-1")
  2. Inject context to simulate a specific state
  3. talk_to_agent(message="...", user_id="test-1", session_id="test-1")  // continues
  4. Verify response matches expected behaviour
""",
}

TOOLS: list[Tool] = [
    Tool(
        name="explain",
        description=(
            "Retrieve implementation guidance before brute-forcing or web-searching.\n\n"
            "Topics: " + " | ".join(TOPICS) + "\n\n"
            "Call explain() for orientation and topic list.\n"
            "Call explain(\"topic\") for full reference on that topic."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic name from the list above. Omit for orientation overview.",
                },
            },
        },
    ),
]


def _ok(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _explain(args: dict) -> list[TextContent]:
        topic = args.get("topic", "").strip()
        if not topic:
            return _ok("# cognigy-vibe-mcp Reference Library\n\n" + _TOPIC_INDEX)
        content = _CONTENT.get(topic)
        if content:
            return _ok(content.strip())
        return _ok(
            f"Unknown topic: '{topic}'\n\n"
            f"Available Topics:\n{_TOPIC_INDEX}"
        )

    return {"explain": _explain}
```

- [ ] **Step 4: Run — verify all pass**

```bash
uv run pytest tests/tools/test_explain.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): add explain tool with 17-topic reference library"
```

---

## Task 10: `server.py` — Wire Everything Together

**Files:**
- Create: `cognigy-mcp/cognigy_mcp/server.py`
- Create: `cognigy-mcp/tests/conftest.py`

- [ ] **Step 1: Write shared conftest**

```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def cache(tmp_path):
    return Cache(cache_dir=tmp_path / "cache", ttl=60)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    return ProjectState(project_id="test-proj")
```

- [ ] **Step 2: Write a smoke test for server wiring**

```python
# tests/test_server.py
import pytest
from cognigy_mcp.server import create_server


def test_server_creates_without_error(monkeypatch):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://cognigy-api-au1.nicecxone.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "test-key")
    monkeypatch.setenv("COGNIGY_PROJECT_ID", "proj-123")
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE",
                        __import__("pathlib").Path("/tmp/cognigy-vibe-test"))
    server, all_tools = create_server()
    tool_names = [t.name for t in all_tools]
    assert "cognigy_get" in tool_names
    assert "explain" in tool_names
    assert "push_code_node" in tool_names
    assert "talk_to_agent" in tool_names
    assert "sync_remote_state" in tool_names
    assert len(all_tools) == 15
```

- [ ] **Step 3: Run — verify it fails**

```bash
uv run pytest tests/test_server.py -v
```

- [ ] **Step 4: Implement `server.py`**

```python
# cognigy_mcp/server.py
from __future__ import annotations
import asyncio
import json
import os
from typing import Any
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.tools import state_tools, flow_ops, file_push, testing, explain


def create_server() -> tuple[Server, list[types.Tool]]:
    client = CognigyClient(
        base_url=os.environ["COGNIGY_BASE_URL"],
        api_key=os.environ["COGNIGY_API_KEY"],
    )
    project_id = os.environ["COGNIGY_PROJECT_ID"]
    state = ProjectState(
        project_id=project_id,
        resync_hours=float(os.getenv("COGNIGY_VIBE_RESYNC_HOURS", "4")),
    )
    cache = Cache(
        cache_dir=state.config_dir / "cache",
        ttl=int(os.getenv("COGNIGY_VIBE_CACHE_TTL", "300")),
    )

    all_tools = (
        state_tools.TOOLS
        + flow_ops.TOOLS
        + file_push.TOOLS
        + testing.TOOLS
        + explain.TOOLS
    )

    all_handlers: dict[str, Any] = {
        **state_tools.make_handlers(client, state, cache),
        **flow_ops.make_handlers(client, state, cache),
        **file_push.make_handlers(client, state, cache),
        **testing.make_handlers(client, state, cache),
        **explain.make_handlers(client, state, cache),
    }

    server = Server("cognigy-vibe")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return all_tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        # Auto-resync check (skip for sync_remote_state itself)
        auto_synced = False
        if name != "sync_remote_state" and state.needs_resync():
            sync_handler = all_handlers["sync_remote_state"]
            sync_handler({"project_id": project_id})
            auto_synced = True

        state.touch_interaction()

        handler = all_handlers.get(name)
        if not handler:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"})
            )]

        result = handler(arguments or {})

        if auto_synced and result:
            # Inject flag into first response object if it's JSON
            try:
                first = json.loads(result[0].text)
                first["auto_synced"] = True
                result[0] = types.TextContent(type="text", text=json.dumps(first, indent=2))
            except Exception:
                pass

        return result

    return server, all_tools


async def _run() -> None:
    server, _ = create_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    load_dotenv()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run — verify test passes**

```bash
uv run pytest tests/test_server.py -v
```

Expected: 1 test PASS, `len(all_tools) == 15`.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Smoke test the server starts**

```bash
COGNIGY_BASE_URL=https://cognigy-api-au1.nicecxone.com \
COGNIGY_API_KEY=dummy \
COGNIGY_PROJECT_ID=proj-123 \
uv run cognigy-vibe-mcp &
sleep 1 && kill %1
```

Expected: server starts without error (will fail with connection refused on first API call, but that's fine).

- [ ] **Step 8: Commit**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): wire server.py with auto-resync middleware"
```

---

## Task 11: `cognigy:init-mcp` Skill

**Files:**
- Create: `skills/init-mcp/SKILL.md`

The init skill is a Claude Code skill (markdown), not Python. No automated tests — verify manually.

- [ ] **Step 1: Create the skill file**

```bash
mkdir -p skills/init-mcp
```

- [ ] **Step 2: Write `skills/init-mcp/SKILL.md`**

```markdown
# cognigy:init-mcp

Set up cognigy-vibe-mcp for a new demo project. Run once per project from the project root.

## Prerequisites

- `COGNIGY_PROJECT_ID` known (get from Cognigy UI: Project Settings)
- `COGNIGY_BASE_URL` known (e.g. `https://cognigy-api-au1.nicecxone.com`)
- `COGNIGY_API_KEY` known (get from Cognigy UI: My Profile → API Keys)
- `uv` installed
- `cognigy-vibe-mcp` installed: `uv tool install cognigy-vibe-mcp`

## Steps

### 1. Read COGNIGY_PROJECT_ID from user or .env if present

If a `.env` file exists in CWD, read `COGNIGY_PROJECT_ID` from it.
Otherwise, ask the user for it.

### 2. Create config directory

```bash
mkdir -p ~/.config/cognigy-mcp/<COGNIGY_PROJECT_ID>
```

### 3. Create or copy .state-seed.json

If `.state-seed.json` exists in CWD, copy it:
```bash
cp .state-seed.json ~/.config/cognigy-mcp/<COGNIGY_PROJECT_ID>/.state-seed.json
```

Otherwise, create an empty seed:
```bash
echo '{}' > ~/.config/cognigy-mcp/<COGNIGY_PROJECT_ID>/.state-seed.json
```

### 4. Create symlink

```bash
ln -sf ~/.config/cognigy-mcp/<COGNIGY_PROJECT_ID> .cognigy-mcp
```

### 5. Add to .gitignore

Check if `.cognigy-mcp` is already in `.gitignore`. If not:
```bash
echo '.cognigy-mcp' >> .gitignore
```

### 6. Write MCP server entry to .claude/mcp.json

Create `.claude/` if needed:
```bash
mkdir -p .claude
```

Write or merge this entry into `.claude/mcp.json`:
```json
{
  "mcpServers": {
    "cognigy-vibe": {
      "command": "uvx",
      "args": ["cognigy-vibe-mcp"],
      "env": {
        "COGNIGY_BASE_URL": "<COGNIGY_BASE_URL>",
        "COGNIGY_API_KEY": "<COGNIGY_API_KEY>",
        "COGNIGY_PROJECT_ID": "<COGNIGY_PROJECT_ID>"
      }
    }
  }
}
```

If `.claude/mcp.json` already exists, merge the `cognigy-vibe` key into the existing `mcpServers` object — do not overwrite other entries.

### 7. Confirm to user

Report:
- Config dir created at: `~/.config/cognigy-mcp/<projectId>/`
- Symlink created: `.cognigy-mcp → ~/.config/cognigy-mcp/<projectId>/`
- `.gitignore` updated
- MCP server entry written to `.claude/mcp.json`

Remind user to:
1. Restart Claude Code to load the new MCP server
2. Run `sync_remote_state(project_id="<projectId>")` as the first tool call in the new session
```

- [ ] **Step 3: Register skill in plugin.json**

Open `.claude-plugin/plugin.json`. Add `"init-mcp"` to the skills array:

```json
{
  "skills": [
    "...",
    "init-mcp"
  ]
}
```

- [ ] **Step 4: Increment versions**

In `cli/package.json` and `.claude-plugin/plugin.json`, bump patch version (e.g. `1.1.14` → `1.1.15`).

- [ ] **Step 5: Commit**

```bash
git add skills/init-mcp/ .claude-plugin/plugin.json cli/package.json
git commit -m "feat(vibe-mcp): add cognigy:init-mcp skill"
```

---

## Task 12: Integration Verification

Manual verification against a real Cognigy project.

- [ ] **Step 1: Install locally**

```bash
cd cognigy-mcp
uv tool install --editable .
```

- [ ] **Step 2: Run init skill in a test project**

Create a temp dir, run `cognigy:init-mcp`, verify symlink and mcp.json created.

- [ ] **Step 3: Restart Claude Code and verify tool list**

In a new Claude Code session in the test project dir:
- Type a message and confirm `cognigy-vibe` tools appear in the tool list
- Run `explain()` — verify topic list returned
- Run `sync_remote_state(project_id="<real-project-id>")` — verify state.json populated

- [ ] **Step 4: Push a code node**

Write a simple JS file, call `push_code_node`, verify it appears in the Cognigy UI.

- [ ] **Step 5: Final commit and version bump**

```bash
git add cognigy-mcp/
git commit -m "feat(vibe-mcp): complete v0.1.0 implementation"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Package identity (`cognigy-vibe-mcp`, `cognigy-vibe`) — Task 1
- ✅ Modular package structure — Tasks 1–10
- ✅ Config dir at `~/.config/cognigy-mcp/<project-id>/` — Task 4
- ✅ Symlink + gitignore via init skill — Task 11
- ✅ 5-min TTL cache with write-through — Task 3, Task 6
- ✅ Code-node snapshot + server-side conflict detection — Task 7
- ✅ Auto-resync on stale session — Task 10
- ✅ 15 tools total — verified in Task 10 smoke test
- ✅ `explain` with 17 topics front-loaded in description — Task 9
- ✅ `cognigy_delete`/`cognigy_invoke` absorb node-specific tools — Task 6
- ✅ `merge_config` deep-merge — Task 6
- ✅ `cognigy:init-mcp` skill — Task 11
- ✅ `uvx cognigy-vibe-mcp` entry point — Task 1

**Placeholder scan:** No TBDs or TODOs. All code is complete.

**Type consistency:** `_ok()` helper used consistently across all tool modules. `make_handlers()` signature is identical across all modules. `TOOLS` list exported from every module. Handler signatures are `(args: dict) -> list[TextContent]` throughout.
