# aiAgentJob Creation Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two production bugs that prevent `aiAgentJob` nodes from being created or updated on Cognigy AU1 (NiCE CXone).

**Architecture:** Bug 1 is a wrong extension name in the auto-inject map — AU1 registers AI Agent node types under `@cognigy/basic-nodes`, not the separate `cognigy-ai-agent` extension that doesn't exist on this environment. Bug 2 is the `patch()` method in the API client calling `resp.json()` unconditionally — Cognigy's node PATCH returns 204 No Content, causing a `json.loads` ValueError even when the write succeeds.

**Tech Stack:** Python 3.11+, pytest, httpx + respx for API client tests, `uv run pytest` for test execution

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `cognigy-mcp/cognigy_mcp/tools/flow_ops.py:162-164` | Change AI Agent types from `cognigy-ai-agent` → `@cognigy/basic-nodes` in `_NODE_EXTENSION_MAP` |
| Modify | `cognigy-mcp/cognigy_mcp/tools/explain.py` | Replace 10 occurrences of `cognigy-ai-agent` with `@cognigy/basic-nodes` |
| Modify | `cognigy-mcp/tests/tools/test_flow_ops.py` | Update existing `test_extension_auto_injected` and add new test for aiAgentJob extension |
| Modify | `cognigy-mcp/cognigy_mcp/api.py:51-54` | Handle 204 No Content in `patch()` |
| Modify | `cognigy-mcp/tests/test_api.py` | Add test for PATCH 204 response |
| Modify | `cognigy-mcp/pyproject.toml` | Bump `1.2.3` → `1.2.4` |
| Modify | `.claude-plugin/plugin.json` | Bump `1.2.3` → `1.2.4` |

---

## Task 1: Fix AI Agent node extension — `@cognigy/basic-nodes` on AU1

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py:162-164`
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py`
- Test: `cognigy-mcp/tests/tools/test_flow_ops.py`

**Context:** `_cognigy_create` calls `_inject_extension(body)` which looks up the node type in `_NODE_EXTENSION_MAP`. The current map has:
```python
"aiAgentJob": "cognigy-ai-agent",
"aiAgentJobTool": "cognigy-ai-agent",
"aiAgentToolAnswer": "cognigy-ai-agent",
```
On AU1 (NiCE CXone), the `cognigy-ai-agent` extension is not installed. These node types are registered under `@cognigy/basic-nodes`. The Cognigy API returns HTTP 404 "The desired node descriptor was not found in the db." when the extension is wrong.

The existing `test_extension_auto_injected` test checks `setSessionConfig` (which tests the voicegateway2 path, not AI agent nodes). We need a test that explicitly checks `aiAgentJob → @cognigy/basic-nodes`.

- [ ] **Step 1: Write the failing test**

Add to `cognigy-mcp/tests/tools/test_flow_ops.py`:

```python
def test_aiagentjob_extension_is_basic_nodes(mock_client, state, cache):
    """aiAgentJob must map to @cognigy/basic-nodes, not cognigy-ai-agent."""
    mock_client.post.return_value = {"_id": "job-1", "type": "aiAgentJob"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentJob", "mode": "append", "target": "start-id",
                 "label": "My Agent", "config": {}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["extension"] == "@cognigy/basic-nodes"


def test_aiagentjobtool_extension_is_basic_nodes(mock_client, state, cache):
    """aiAgentJobTool must map to @cognigy/basic-nodes."""
    mock_client.post.return_value = {"_id": "tool-1", "type": "aiAgentJobTool"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentJobTool", "mode": "appendChild", "target": "job-1",
                 "label": "My Tool", "config": {}},
    })
    call_body = mock_client.post.call_args[0][1]
    assert call_body["extension"] == "@cognigy/basic-nodes"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_flow_ops.py::test_aiagentjob_extension_is_basic_nodes tests/tools/test_flow_ops.py::test_aiagentjobtool_extension_is_basic_nodes -v
```

Expected: FAIL — extension will be `"cognigy-ai-agent"` not `"@cognigy/basic-nodes"`

- [ ] **Step 3: Fix `_NODE_EXTENSION_MAP` in `flow_ops.py`**

In `cognigy-mcp/cognigy_mcp/tools/flow_ops.py`, change lines 162-164:

```python
# Before
    "aiAgentJob": "cognigy-ai-agent",
    "aiAgentJobTool": "cognigy-ai-agent",
    "aiAgentToolAnswer": "cognigy-ai-agent",
```

```python
# After
    "aiAgentJob": "@cognigy/basic-nodes",
    "aiAgentJobTool": "@cognigy/basic-nodes",
    "aiAgentToolAnswer": "@cognigy/basic-nodes",
```

- [ ] **Step 4: Update `explain.py` — replace all `cognigy-ai-agent` occurrences**

There are 10 occurrences of `"cognigy-ai-agent"` in `explain.py` (lines 102, 103, 104, 120, 146, 209, 715, 762, 763, 764). Replace all with `"@cognigy/basic-nodes"`.

The occurrences are in three explain topics:

**`node-types` topic (lines ~99-104):**
```
# Before
  {"type": "aiAgentJob", "extension": "cognigy-ai-agent"}
  {"type": "aiAgentJobTool", "extension": "cognigy-ai-agent"}
  {"type": "aiAgentToolAnswer", "extension": "cognigy-ai-agent"}

# After
  {"type": "aiAgentJob", "extension": "@cognigy/basic-nodes"}
  {"type": "aiAgentJobTool", "extension": "@cognigy/basic-nodes"}
  {"type": "aiAgentToolAnswer", "extension": "@cognigy/basic-nodes"}
```

Also on line ~209:
```
# Before
AI Agent types (extension: "cognigy-ai-agent"):

# After
AI Agent types (extension: "@cognigy/basic-nodes"):
```

**`agent-tool-branch` topic (lines ~117-150):**
```
# Before (line ~120)
    "extension": "cognigy-ai-agent",

# After
    "extension": "@cognigy/basic-nodes",
```

```
# Before (line ~146)
    "type": "aiAgentToolAnswer", "extension": "cognigy-ai-agent",

# After
    "type": "aiAgentToolAnswer", "extension": "@cognigy/basic-nodes",
```

**`extension-map` topic (lines ~715+):**
```
# Before
### AI Agent nodes (extension: "cognigy-ai-agent")

# After
### AI Agent nodes (extension: "@cognigy/basic-nodes")
```

```
# Before
  aiAgentJob        AI Agent job (extension: cognigy-ai-agent)
  aiAgentJobTool    AI Agent tool branch (extension: cognigy-ai-agent)
  aiAgentToolAnswer Tool result surface (extension: cognigy-ai-agent)

# After
  aiAgentJob        AI Agent job (extension: @cognigy/basic-nodes)
  aiAgentJobTool    AI Agent tool branch (extension: @cognigy/basic-nodes)
  aiAgentToolAnswer Tool result surface (extension: @cognigy/basic-nodes)
```

Use `replace_all=True` in the Edit tool or verify each occurrence is changed. After editing, grep to confirm zero remaining occurrences:

```bash
grep -n "cognigy-ai-agent" /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp/cognigy_mcp/tools/explain.py
```

Expected: no output

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_flow_ops.py -v
```

Expected: all PASS including the two new tests

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git add cognigy-mcp/cognigy_mcp/tools/explain.py
git add cognigy-mcp/tests/tools/test_flow_ops.py
git commit -m "fix: map aiAgentJob types to @cognigy/basic-nodes on AU1"
```

---

## Task 2: Fix `patch()` to handle 204 No Content

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/api.py:51-54`
- Test: `cognigy-mcp/tests/test_api.py`

**Context:** The Cognigy PATCH endpoint for nodes returns 204 No Content on success. The current `patch()` method calls `resp.json()` unconditionally, raising `json.JSONDecodeError` (shown as `ValueError: Expecting value: line 1 column 1 (char 0)`). The update actually succeeds but the caller sees an exception. Compare to `delete()` in the same file — it already handles empty responses with a `try/except` around `resp.json()`. We follow the same pattern for `patch()`, but with an explicit 204 check for clarity.

Current `patch()` (lines 51-54 of `api.py`):
```python
def patch(self, path: str, body: dict) -> dict:
    resp = self._http.patch(self._base + path, json=body)
    self._raise_for_status(resp)
    return resp.json()
```

- [ ] **Step 1: Write the failing test**

Add to `cognigy-mcp/tests/test_api.py`:

```python
def test_patch_204_no_content_returns_empty_dict(client):
    """PATCH returning 204 No Content must not raise and must return {}."""
    with respx.mock:
        respx.patch(f"{BASE}/v2.0/flows/flow-123/chart/nodes/node-1").mock(
            return_value=httpx.Response(204)
        )
        result = client.patch("/v2.0/flows/flow-123/chart/nodes/node-1", {"label": "Updated"})
    assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/test_api.py::test_patch_204_no_content_returns_empty_dict -v
```

Expected: FAIL — `json.JSONDecodeError`

- [ ] **Step 3: Fix `patch()` in `api.py`**

In `cognigy-mcp/cognigy_mcp/api.py`, replace lines 51-54:

```python
def patch(self, path: str, body: dict) -> dict:
    resp = self._http.patch(self._base + path, json=body)
    self._raise_for_status(resp)
    if resp.status_code == 204:
        return {}
    return resp.json()
```

- [ ] **Step 4: Run all API tests to verify they pass**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/test_api.py -v
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
git add cognigy-mcp/cognigy_mcp/api.py
git add cognigy-mcp/tests/test_api.py
git commit -m "fix: handle 204 No Content in patch() to prevent JSON parse error"
```

---

## Task 3: Bump versions and push

**Files:**
- Modify: `cognigy-mcp/pyproject.toml`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump `pyproject.toml`**

In `cognigy-mcp/pyproject.toml`, change:
```toml
version = "1.2.3"
```
to:
```toml
version = "1.2.4"
```

- [ ] **Step 2: Bump `plugin.json`**

In `.claude-plugin/plugin.json`, change:
```json
"version": "1.2.3"
```
to:
```json
"version": "1.2.4"
```

- [ ] **Step 3: Commit and push**

```bash
git add cognigy-mcp/pyproject.toml
git add .claude-plugin/plugin.json
git commit -m "chore: bump to 1.2.4"
git push
```

- [ ] **Step 4: Update marketplace submodule**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```
