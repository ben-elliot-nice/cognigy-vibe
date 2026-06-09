# get_flow_chart AU1 Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs that make `get_flow_chart` crash and `sync_remote_state` silently fail on Cognigy AU1 environments with newly created flows.

**Architecture:** Bug 1 is a `KeyError` in `_build_hierarchy` — the dict comprehension uses `r["nodeId"]` but newly created flows on AU1 return relation objects without that field. Bug 2 is `sync_remote_state` using project-scoped list endpoints (`/v2.0/projects/{id}/flows`) that 404 on AU1; the fix adds a fallback to direct (non-project-scoped) endpoints.

**Tech Stack:** Python 3.11+, pytest, `uv run pytest` for test execution, MCP server in `cognigy-mcp/`

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `cognigy-mcp/cognigy_mcp/tools/flow_ops.py:242` | Safe `.get("nodeId")` fallback in `_build_hierarchy` |
| Modify | `cognigy-mcp/cognigy_mcp/tools/state_tools.py:123-169` | AU1 fallback in `_sync_remote_state` |
| Modify | `cognigy-mcp/tests/tools/test_flow_ops.py` | New tests for missing `nodeId` in relations |
| Modify | `cognigy-mcp/tests/tools/test_state_tools.py` | New test for AU1 project-scoped 404 fallback |
| Modify | `cognigy-mcp/pyproject.toml` | Bump `1.2.2` → `1.2.3` |
| Modify | `.claude-plugin/plugin.json` | Bump `1.2.2` → `1.2.3` |

---

## Task 1: Fix `_build_hierarchy` KeyError on missing `nodeId`

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py:241-242`
- Test: `cognigy-mcp/tests/tools/test_flow_ops.py`

**Context:** `_build_hierarchy` builds a `relations` dict keyed by `nodeId`. On AU1, newly created flows return relation objects where `nodeId` is absent — only `_id` is present. `r["nodeId"]` raises `KeyError`.

The existing test `test_get_flow_chart_returns_hierarchy` passes nodes with `nodeId` populated — it won't catch this. We need a test with relations that omit `nodeId`.

- [ ] **Step 1: Write the failing test**

Add to `cognigy-mcp/tests/tools/test_flow_ops.py`:

```python
def test_get_flow_chart_bare_nodes_no_nodeId(mock_client, state, cache):
    """AU1 bare Start/End nodes: relations have _id but not nodeId — must not raise KeyError."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "start-id", "type": "start", "label": "Start"},
            {"_id": "end-id", "type": "end", "label": "End"},
        ],
        "relations": [
            {"_id": "start-id", "nextId": "end-id", "previousId": None, "parentId": None, "childIds": []},
            {"_id": "end-id", "nextId": None, "previousId": "start-id", "parentId": None, "childIds": []},
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-new"})
    data = json.loads(result[0].text)
    assert "hierarchy" in data
    assert "error" not in data


def test_get_flow_chart_mixed_nodeId_and_id(mock_client, state, cache):
    """Some relations have nodeId, others only _id — both must be indexed correctly."""
    mock_client.get.return_value = {
        "nodes": [
            {"_id": "n1", "type": "say", "label": "Hello"},
            {"_id": "n2", "type": "say", "label": "Bye"},
        ],
        "relations": [
            {"nodeId": "n1", "_id": "n1", "nextId": "n2", "previousId": None, "parentId": None, "childIds": []},
            {"_id": "n2", "nextId": None, "previousId": "n1", "parentId": None, "childIds": []},
        ],
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["get_flow_chart"]({"flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "Hello" in data["hierarchy"] or "n1" in data["hierarchy"]
    assert "Bye" in data["hierarchy"] or "n2" in data["hierarchy"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_flow_ops.py::test_get_flow_chart_bare_nodes_no_nodeId tests/tools/test_flow_ops.py::test_get_flow_chart_mixed_nodeId_and_id -v
```

Expected: FAIL — `KeyError: 'nodeId'` on `test_get_flow_chart_bare_nodes_no_nodeId`

- [ ] **Step 3: Fix `_build_hierarchy` in `flow_ops.py`**

In `cognigy-mcp/cognigy_mcp/tools/flow_ops.py`, replace line 242:

```python
# Before
relations = {r["nodeId"]: r for r in chart.get("relations", [])}
```

```python
# After
relations = {
    (r.get("nodeId") or r.get("_id")): r
    for r in chart.get("relations", [])
    if r.get("nodeId") or r.get("_id")
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_flow_ops.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git add cognigy-mcp/tests/tools/test_flow_ops.py
git commit -m "fix: safe nodeId fallback in _build_hierarchy for AU1 bare nodes"
```

---

## Task 2: Fix `sync_remote_state` AU1 404 on project-scoped endpoints

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/state_tools.py:123-169`
- Test: `cognigy-mcp/tests/tools/test_state_tools.py`

**Context:** `_sync_remote_state` fetches flows, agents, and endpoints using project-scoped paths:
- `GET /v2.0/projects/{project_id}/flows`
- `GET /v2.0/projects/{project_id}/aiagents`
- `GET /v2.0/projects/{project_id}/endpoints`

AU1 returns 404 for all three. The fix: when the project-scoped request raises an exception, fall back to the direct path (`/v2.0/flows`, `/v2.0/aiagents`, `/v2.0/endpoints`). The errors list should note when a fallback was used, but the sync should succeed.

- [ ] **Step 1: Write the failing test**

Add to `cognigy-mcp/tests/tools/test_state_tools.py`:

```python
def test_sync_falls_back_to_direct_endpoints_on_404(mock_client, state, cache):
    """When project-scoped endpoints 404 (AU1), fall back to direct /v2.0/flows etc."""
    project_id = state.project_id
    mock_client.get.side_effect = [
        Exception("404 Not Found"),                                                          # /projects/{id}/flows → 404
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},                                # /flows fallback
        {"nodes": []},                                                                       # chart for Main Flow
        Exception("404 Not Found"),                                                          # /projects/{id}/aiagents → 404
        {"items": [{"_id": "agent-1", "name": "My Agent"}]},                                # /aiagents fallback
        Exception("404 Not Found"),                                                          # /projects/{id}/endpoints → 404
        {"items": [{"_id": "ep-1", "name": "REST", "urlToken": "tok", "flowReferenceId": "flow-1"}]},  # /endpoints fallback
    ]
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["sync_remote_state"]({"project_id": project_id})
    data = json.loads(result[0].text)
    assert data["synced"] is True
    assert state.get("flows", "Main Flow", "id") == "flow-1"
    assert state.get("agents", "My Agent", "id") == "agent-1"
    assert state.get("endpoints", "REST", "id") == "ep-1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_state_tools.py::test_sync_falls_back_to_direct_endpoints_on_404 -v
```

Expected: FAIL — flows/agents/endpoints all go into the `errors` list and state is empty

- [ ] **Step 3: Implement fallback in `state_tools.py`**

Replace the flows, agents, and endpoints blocks in `_sync_remote_state` (lines 122-168 of `state_tools.py`) with versions that fall back to non-project-scoped paths on any exception:

```python
        # Flows
        flows: list = []
        try:
            flows_resp = client.get(f"/v2.0/projects/{project_id}/flows", limit=100)
            flows = flows_resp.get("items", [])
        except Exception:
            try:
                flows_resp = client.get("/v2.0/flows", limit=100)
                flows = flows_resp.get("items", [])
            except Exception as exc:
                errors.append(f"flows: {exc}")

        for flow in flows:
            state.set("flows", flow["name"], value={"id": flow["_id"]})
            cache.set("flows", flow["_id"], flow)

        # Chart-based tool discovery (non-fatal per flow)
        for flow in flows:
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
            except Exception:
                pass

        # Agents
        try:
            agents_resp = client.get(f"/v2.0/projects/{project_id}/aiagents", limit=100)
            for agent in agents_resp.get("items", []):
                state.set("agents", agent["name"], value={"id": agent["_id"]})
                cache.set("aiagents", agent["_id"], agent)
        except Exception:
            try:
                agents_resp = client.get("/v2.0/aiagents", limit=100)
                for agent in agents_resp.get("items", []):
                    state.set("agents", agent["name"], value={"id": agent["_id"]})
                    cache.set("aiagents", agent["_id"], agent)
            except Exception as exc:
                errors.append(f"agents: {exc}")

        # Endpoints
        try:
            eps_resp = client.get(f"/v2.0/projects/{project_id}/endpoints", limit=100)
            for ep in eps_resp.get("items", []):
                state.set("endpoints", ep["name"], value={
                    "id": ep["_id"],
                    "urlToken": ep.get("urlToken", ""),
                    "flowReferenceId": ep.get("flowReferenceId", ""),
                })
                cache.set("endpoints", ep["_id"], ep)
        except Exception:
            try:
                eps_resp = client.get("/v2.0/endpoints", limit=100)
                for ep in eps_resp.get("items", []):
                    state.set("endpoints", ep["name"], value={
                        "id": ep["_id"],
                        "urlToken": ep.get("urlToken", ""),
                        "flowReferenceId": ep.get("flowReferenceId", ""),
                    })
                    cache.set("endpoints", ep["_id"], ep)
            except Exception as exc:
                errors.append(f"endpoints: {exc}")
```

Also update the existing test `test_sync_handles_list_failure_gracefully` in `test_state_tools.py` — it currently expects 4 side_effects; after this change, each failed project-scoped call triggers a fallback call, so the side_effect sequence changes. Replace that test with:

```python
def test_sync_handles_list_failure_gracefully(mock_client, state, cache):
    """sync_remote_state should return synced=True even if both project-scoped and direct agents/endpoints fail."""
    project_id = state.project_id
    mock_client.get.side_effect = [
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},  # /projects/{id}/flows OK
        {"nodes": []},                                          # chart OK
        Exception("API unavailable"),                          # /projects/{id}/aiagents FAIL
        Exception("API unavailable"),                          # /aiagents direct FAIL
        Exception("API unavailable"),                          # /projects/{id}/endpoints FAIL
        Exception("API unavailable"),                          # /endpoints direct FAIL
    ]
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["sync_remote_state"]({"project_id": project_id})
    data = json.loads(result[0].text)
    assert data["synced"] is True
    assert "errors" in data
    assert any("agents" in e for e in data["errors"])
    assert state.get("flows", "Main Flow", "id") == "flow-1"
```

- [ ] **Step 4: Run all state_tools tests to verify they pass**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_state_tools.py -v
```

Expected: all PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/state_tools.py
git add cognigy-mcp/tests/tools/test_state_tools.py
git commit -m "fix: AU1 fallback to direct endpoints in sync_remote_state"
```

---

## Task 3: Bump versions and push

**Files:**
- Modify: `cognigy-mcp/pyproject.toml`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump `pyproject.toml`**

In `cognigy-mcp/pyproject.toml`, change:
```toml
version = "1.2.2"
```
to:
```toml
version = "1.2.3"
```

- [ ] **Step 2: Bump `plugin.json`**

In `.claude-plugin/plugin.json`, change:
```json
"version": "1.2.2"
```
to:
```json
"version": "1.2.3"
```

- [ ] **Step 3: Commit and push**

```bash
git add cognigy-mcp/pyproject.toml
git add .claude-plugin/plugin.json
git commit -m "chore: bump to 1.2.3"
git push
```

- [ ] **Step 4: Update marketplace submodule**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace
git submodule update --remote
git add plugins
git commit -m "Further cognigy plugins revisions"
git push
```
