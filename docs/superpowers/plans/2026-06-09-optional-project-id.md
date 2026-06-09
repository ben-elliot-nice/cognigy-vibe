# Optional COGNIGY_PROJECT_ID Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MCP server bootable without `COGNIGY_PROJECT_ID` — if it's set in `mcp.json` everything works as before; if it's absent the server starts, tools work, and Claude gets clear actionable errors directing it to call `sync_remote_state(project_id=...)` which sets the project scope mid-session with no restart needed.

**Architecture:** Three-layer change. (1) `ProjectState` gains an `Optional[str]` project_id and a `bind_project()` method that re-scopes state to a real project dir mid-session. (2) `server.py` changes one `os.environ[...]` to `os.getenv(...)` and skips auto-resync when no project is bound. (3) `sync_remote_state` calls `state.bind_project()` after resolving a project_id, wiring up the in-session scoping without a server restart.

**Tech Stack:** Python 3.11+, pytest, `uv run pytest`, `python-dotenv`, filesystem-backed state in `~/.config/cognigy-mcp/`

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `cognigy-mcp/cognigy_mcp/state.py:37-48` | `__init__` accepts `project_id: str \| None`; uses `.unscoped` sentinel dir when None |
| Modify | `cognigy-mcp/cognigy_mcp/state.py` | Add `bind_project(project_id: str)` method |
| Modify | `cognigy-mcp/tests/test_state.py` | Tests for None project_id and bind_project |
| Modify | `cognigy-mcp/cognigy_mcp/server.py:21-29` | `os.getenv` for project_id; auto-resync skips when project_id is None |
| Modify | `cognigy-mcp/tests/test_server.py` | Test server boots without COGNIGY_PROJECT_ID |
| Modify | `cognigy-mcp/cognigy_mcp/tools/state_tools.py:117` | Call `state.bind_project()` after resolving project_id |
| Modify | `cognigy-mcp/tests/tools/test_state_tools.py` | Test that sync_remote_state binds the project in-session |
| Modify | `cognigy-mcp/pyproject.toml` | Bump `1.2.4` → `1.2.5` |
| Modify | `.claude-plugin/plugin.json` | Bump `1.2.4` → `1.2.5` |

---

## Task 1: `ProjectState` supports optional project_id and `bind_project()`

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/state.py:37-48`
- Test: `cognigy-mcp/tests/test_state.py`

**Context:** `ProjectState.__init__` currently does `CONFIG_BASE / project_id` on line 40 — if `project_id` is `None` this raises `TypeError`. We need it to fall back to a sentinel dir (`CONFIG_BASE / ".unscoped"`) so the server can boot, hold in-memory + filesystem state for pre-project operations, and then re-scope to a real project dir when `bind_project()` is called.

`bind_project()` migrates the instance in-place: updates `project_id`, `config_dir`, and all derived paths, then reloads state from the new dir. In-session writes to `.unscoped` (e.g. resource IDs from `cognigy_create` calls before the project was known) are discarded — `sync_remote_state` (which calls `bind_project`) immediately repopulates state from the API anyway.

- [ ] **Step 1: Write the failing tests**

Add to `cognigy-mcp/tests/test_state.py`:

```python
def test_none_project_id_uses_unscoped_dir(config_base, monkeypatch):
    """ProjectState with project_id=None must not raise and must use .unscoped dir."""
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState(project_id=None)
    assert s.config_dir == config_base / ".unscoped"
    assert s.project_id is None


def test_bind_project_rescopes_state(config_base, monkeypatch):
    """bind_project() must update project_id, config_dir, and reload state from new dir."""
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState(project_id=None)
    s.set("flows", "Old", value={"id": "old-id"})  # written to .unscoped

    s.bind_project("proj-456")

    assert s.project_id == "proj-456"
    assert s.config_dir == config_base / "proj-456"
    # .unscoped data must NOT bleed into the project-scoped state
    assert s.get("flows", "Old") is None


def test_bind_project_loads_existing_state(config_base, monkeypatch):
    """bind_project() must load persisted state if the project dir already has one."""
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    # Pre-create a project dir with existing state
    proj_dir = config_base / "proj-789"
    proj_dir.mkdir(parents=True)
    (proj_dir / ".state.json").write_text('{"flows": {"Main": {"id": "existing-id"}}}')

    s = ProjectState(project_id=None)
    s.bind_project("proj-789")

    assert s.get("flows", "Main", "id") == "existing-id"


def test_bind_project_noop_when_already_bound(config_base, monkeypatch):
    """bind_project() with the same project_id must not reload state."""
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", config_base)
    s = ProjectState(project_id="proj-123")
    s.set("flows", "Canary", value={"id": "canary"})

    s.bind_project("proj-123")  # same id — must be no-op

    assert s.get("flows", "Canary", "id") == "canary"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/test_state.py::test_none_project_id_uses_unscoped_dir tests/test_state.py::test_bind_project_rescopes_state tests/test_state.py::test_bind_project_loads_existing_state tests/test_state.py::test_bind_project_noop_when_already_bound -v
```

Expected: FAIL — `TypeError` on `CONFIG_BASE / None`, `AttributeError` on `bind_project`

- [ ] **Step 3: Update `ProjectState.__init__` and add `bind_project()`**

Replace `cognigy-mcp/cognigy_mcp/state.py` `ProjectState` class (lines 37-88) with:

```python
class ProjectState:
    def __init__(self, project_id: str | None, resync_hours: float = 4.0):
        self.resync_hours = resync_hours
        self._state: dict = {}
        self._bind(project_id)

    def _bind(self, project_id: str | None) -> None:
        self.project_id = project_id
        self.config_dir = CONFIG_BASE / (project_id or ".unscoped")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self.config_dir / ".state.json"
        self._seed_path = self.config_dir / ".state-seed.json"
        self._interaction_path = self.config_dir / "last-interaction"
        self._state = {}
        self._load()

    def bind_project(self, project_id: str) -> None:
        """Re-scope this state instance to a specific project. Safe to call mid-session."""
        if self.project_id == project_id:
            return
        self._bind(project_id)

    def _load(self) -> None:
        try:
            seed = json.loads(self._seed_path.read_text()) if self._seed_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            seed = {}
        try:
            runtime = json.loads(self._state_path.read_text()) if self._state_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            runtime = {}
        self._state = _deep_merge(seed, runtime)

    def save(self) -> None:
        payload = json.dumps(self._state, indent=2)
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(payload)
        tmp.replace(self._state_path)

    def get(self, *keys: str) -> Any:
        return _deep_get(self._state, *keys)

    def set(self, *keys: str, value: Any) -> None:
        _deep_set(self._state, *keys, value=value)
        self.save()

    def needs_resync(self) -> bool:
        if not self._interaction_path.exists():
            return True
        try:
            last = float(self._interaction_path.read_text())
            return (time.time() - last) > (self.resync_hours * 3600)
        except (ValueError, OSError):
            return True

    def touch_interaction(self) -> None:
        tmp = self._interaction_path.with_suffix(".tmp")
        tmp.write_text(str(time.time()))
        tmp.replace(self._interaction_path)

    def as_dict(self) -> dict:
        return copy.deepcopy(self._state)
```

- [ ] **Step 4: Run all state tests**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/test_state.py -v
```

Expected: all PASS (existing 11 + 4 new = 15)

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/state.py
git add cognigy-mcp/tests/test_state.py
git commit -m "feat: ProjectState accepts optional project_id, adds bind_project()"
```

---

## Task 2: Server boots without `COGNIGY_PROJECT_ID`

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/server.py:21-29,56-62`
- Test: `cognigy-mcp/tests/test_server.py`

**Context:** Two changes to `server.py`:

1. Line 21: `os.environ["COGNIGY_PROJECT_ID"]` → `os.getenv("COGNIGY_PROJECT_ID")` — removes the KeyError crash at boot.

2. Lines 56-62: The auto-resync block reads `project_id` from the closure variable (set at boot). When `project_id` is None, calling `sync_handler({"project_id": None})` hits the "project_id required" error path in `_sync_remote_state` which returns an error dict — not a crash, but noisy. Change to read from `state.project_id` (updated by `bind_project`) and skip auto-resync entirely when it's None.

The existing `test_server_creates_without_error` sets `COGNIGY_PROJECT_ID` via monkeypatch — it keeps passing unchanged. We add a new test that omits it.

- [ ] **Step 1: Write the failing test**

Add to `cognigy-mcp/tests/test_server.py`:

```python
def test_server_boots_without_project_id(monkeypatch, tmp_path):
    """Server must start successfully when COGNIGY_PROJECT_ID is not set."""
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://cognigy-api-au1.nicecxone.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "test-key")
    monkeypatch.delenv("COGNIGY_PROJECT_ID", raising=False)
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    server, all_tools = create_server()
    assert len(all_tools) == 15
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/test_server.py::test_server_boots_without_project_id -v
```

Expected: FAIL — `KeyError: 'COGNIGY_PROJECT_ID'`

- [ ] **Step 3: Update `server.py`**

In `cognigy-mcp/cognigy_mcp/server.py`, make these two changes:

**Change 1 — line 21:** Remove hard read of project_id:
```python
# Before
    project_id = os.environ["COGNIGY_PROJECT_ID"]
    state = ProjectState(
        project_id=project_id,

# After
    state = ProjectState(
        project_id=os.getenv("COGNIGY_PROJECT_ID"),
```

**Change 2 — lines 56-62:** Read project_id from state (not closure), skip when None:
```python
# Before
        if name != "sync_remote_state" and state.needs_resync():
            sync_handler = all_handlers["sync_remote_state"]
            try:
                sync_handler({"project_id": project_id})
                auto_synced = True
            except Exception:
                pass  # auto-resync failed; continue with stale state

# After
        if name != "sync_remote_state" and state.project_id and state.needs_resync():
            sync_handler = all_handlers["sync_remote_state"]
            try:
                sync_handler({"project_id": state.project_id})
                auto_synced = True
            except Exception:
                pass  # auto-resync failed; continue with stale state
```

The cache line also depends on `state.config_dir` — that still works because `state.config_dir` now always resolves (to `.unscoped` if no project_id).

- [ ] **Step 4: Run all server tests**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/test_server.py -v
```

Expected: all PASS (existing 1 + new 1 = 2)

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/server.py
git add cognigy-mcp/tests/test_server.py
git commit -m "fix: server boots without COGNIGY_PROJECT_ID, skips auto-resync when unset"
```

---

## Task 3: `sync_remote_state` binds the project in-session

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/state_tools.py:117`
- Test: `cognigy-mcp/tests/tools/test_state_tools.py`

**Context:** After resolving a `project_id` (from arg, env, or prompt), `_sync_remote_state` currently writes it to `.env` via `_write_to_dotenv` but does not update the live `ProjectState` instance. This means within the same session, `state.project_id` remains None (or the old value), so `auto_resync` still skips and `get_build_state` returns whatever was in `.unscoped`.

Fix: call `state.bind_project(project_id)` immediately after the dotenv write. `bind_project` is a no-op if the project is already bound to the same id.

- [ ] **Step 1: Write the failing test**

Add to `cognigy-mcp/tests/tools/test_state_tools.py`:

```python
def test_sync_remote_state_binds_project_in_session(mock_client, state, cache):
    """sync_remote_state must call bind_project so state.project_id is set for the rest of the session."""
    # state fixture starts with project_id="test-proj" (from conftest)
    # Create a fresh unscoped state to simulate booting without project_id
    import cognigy_mcp.state as state_mod
    from cognigy_mcp.state import ProjectState
    unscoped = ProjectState(project_id=None)

    mock_client.get.side_effect = [
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},  # flows
        {"nodes": []},                                          # chart
        {"items": []},                                          # agents
        {"items": []},                                          # endpoints
    ]
    handlers = make_handlers(mock_client, unscoped, cache)
    result = handlers["sync_remote_state"]({"project_id": "proj-new"})
    data = json.loads(result[0].text)

    assert data["synced"] is True
    assert unscoped.project_id == "proj-new"
    assert unscoped.get("flows", "Main Flow", "id") == "flow-1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_state_tools.py::test_sync_remote_state_binds_project_in_session -v
```

Expected: FAIL — `assert unscoped.project_id == "proj-new"` fails (still None)

- [ ] **Step 3: Add `state.bind_project()` call in `state_tools.py`**

In `cognigy-mcp/cognigy_mcp/tools/state_tools.py`, after line 117 (`_write_to_dotenv("COGNIGY_PROJECT_ID", project_id)`), add:

```python
        # Bind the live state instance to this project so the rest of this session
        # is scoped correctly (no restart required).
        state.bind_project(project_id)
```

The full block after the dotenv write should read:

```python
        # Write to .env if not already there
        _write_to_dotenv("COGNIGY_PROJECT_ID", project_id)

        # Bind the live state instance to this project so the rest of this session
        # is scoped correctly (no restart required).
        state.bind_project(project_id)

        cache.invalidate_all()
        errors: list[str] = []
```

- [ ] **Step 4: Run all state_tools tests**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_state_tools.py -v
```

Expected: all PASS

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/state_tools.py
git add cognigy-mcp/tests/tools/test_state_tools.py
git commit -m "feat: sync_remote_state binds project in-session via bind_project()"
```

---

## Task 4: Bump versions and push

**Files:**
- Modify: `cognigy-mcp/pyproject.toml`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump `pyproject.toml`**

Change `version = "1.2.4"` → `version = "1.2.5"`

- [ ] **Step 2: Bump `plugin.json`**

Change `"version": "1.2.4"` → `"version": "1.2.5"`

- [ ] **Step 3: Commit and push**

```bash
git add cognigy-mcp/pyproject.toml
git add .claude-plugin/plugin.json
git commit -m "chore: bump to 1.2.5"
git push
```

- [ ] **Step 4: Update marketplace submodule**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```
