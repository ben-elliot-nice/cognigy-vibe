# Issue #22 — cognigy_get aiagents returns node config instead of resource

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `cognigy_get(resource_type="aiagents")` returning `aiAgentJob` chart-node data instead of the canonical AI Agent resource.

**Architecture:** `sync_remote_state` discovers AI Agent IDs via `/v2.0/flows/{flow_id}/chart/nodes/aiagents` (a chart-scoped endpoint), then caches the raw chart-node objects. Those objects have chart-node fields (`nodeId`, `config.name`, `config.instructions`, `type: "aiAgentJob"`) rather than canonical resource fields (`description`, `speakingStyle`, `knowledgeReferenceId`). Fix: after discovering the agent's `_id` from the chart endpoint, fetch the canonical resource from `/v2.0/aiagents/{id}` before caching. If that fetch fails, skip caching (cognigy_get will fetch on first access).

**Tech Stack:** Python 3.12, pytest, cognigy_mcp (state_tools.py, flow_ops.py)

---

## File Map

| Action | File | What changes |
|--------|------|-------------|
| Modify | `cognigy-mcp/cognigy_mcp/tools/state_tools.py:173-181` | Replace `cache.set(agent_chart_data)` with fetch-then-cache using canonical endpoint |
| Modify | `cognigy-mcp/tests/tools/test_state_tools.py` | Fix existing `test_sync_remote_state_calls_api` mock call count; add test asserting canonical resource is cached |
| Modify | `cognigy-mcp/tests/tools/test_flow_ops.py` | Add test: cognigy_get aiagents with stale cache fetches `/v2.0/aiagents/{id}` (not chart endpoint) |
| Modify | `cognigy-mcp/pyproject.toml` | Version 1.3.7 → 1.3.8 |
| Modify | `.claude-plugin/plugin.json` | Version 1.3.7 → 1.3.8 |

---

### Task 1: Add a failing test — sync_remote_state must not cache chart-node data for aiagents

**Files:**
- Modify: `cognigy-mcp/tests/tools/test_state_tools.py`

The new test sets up sync so that the chart/nodes/aiagents endpoint returns a chart-node-shaped object (with `nodeId`, `config`, `type: "aiAgentJob"`), then asserts that the aiagents cache entry has the canonical resource fields rather than the chart-node fields. The test should also account for the extra GET call (for the canonical resource fetch) in the mock side_effect.

- [ ] **Step 1: Add the failing test**

Open `cognigy-mcp/tests/tools/test_state_tools.py` and add the following test after `test_sync_remote_state_calls_api`:

```python
def test_sync_remote_state_caches_canonical_aiagent_resource(mock_client, state, cache):
    """sync_remote_state must cache the canonical AI Agent resource, not chart-node data.

    The chart/nodes/aiagents endpoint returns hybrid objects with chart-node fields
    (nodeId, config.name, type: "aiAgentJob"). Caching these directly causes
    cognigy_get to return node config instead of the agent resource (issue #22).
    After the fix, sync must fetch /v2.0/aiagents/{id} and cache that instead.
    """
    project_id = state.project_id
    chart_node_data = {
        "_id": "agent-1",
        "type": "aiAgentJob",
        "nodeId": "node-abc",
        "config": {"name": "My Agent", "instructions": "be helpful"},
    }
    canonical_resource = {
        "_id": "agent-1",
        "name": "My Agent",
        "description": "A helpful agent",
        "speakingStyle": "formal",
        "knowledgeReferenceId": "ks-xyz",
    }
    mock_client.get.side_effect = [
        {"items": [{"_id": "flow-1", "name": "Main Flow"}]},  # flows
        {"_embedded": {"extensions": []}},                      # extensions
        {"nodes": []},                                          # chart (tool discovery)
        {"items": [chart_node_data]},                           # chart/nodes/aiagents
        canonical_resource,                                     # /v2.0/aiagents/agent-1
        {"items": []},                                          # endpoints
    ]
    handlers = make_handlers(mock_client, state, cache)
    handlers["sync_remote_state"]({"project_id": project_id})

    cached, fresh = cache.get("aiagents", "agent-1")
    assert fresh, "Cache entry should be fresh after sync"
    assert cached is not None, "Cache entry should exist for agent-1"
    assert "speakingStyle" in cached, (
        "Cached data must be canonical AI Agent resource, not chart-node data. "
        f"Got: {cached}"
    )
    assert "nodeId" not in cached, (
        "Cache must not contain chart-node fields (nodeId). "
        f"Got: {cached}"
    )
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_state_tools.py::test_sync_remote_state_caches_canonical_aiagent_resource -v
```

Expected: FAIL — either `AssertionError: Cache entry should exist` (current code uses wrong call count) or `AssertionError: Cached data must be canonical AI Agent resource` (if mock happens to align).

---

### Task 2: Add a failing test — cognigy_get aiagents calls the correct endpoint on cache miss

**Files:**
- Modify: `cognigy-mcp/tests/tools/test_flow_ops.py`

This test verifies that `cognigy_get` for aiagents routes to `/v2.0/aiagents/{id}`, not a chart-node endpoint. This already works correctly in the live code path (the routing is correct), but the test documents the contract explicitly so regressions are caught.

- [ ] **Step 1: Add the test**

Add to `cognigy-mcp/tests/tools/test_flow_ops.py`:

```python
def test_cognigy_get_aiagents_calls_canonical_endpoint(mock_client, state, cache):
    """cognigy_get for aiagents must call /v2.0/aiagents/{id}, not a chart/node endpoint.

    Regression guard for issue #22: cache pollution caused cognigy_get to return
    chart-node data. If the cache is empty, the live API call must go to the correct path.
    """
    canonical_resource = {
        "_id": "agent-1",
        "name": "My Agent",
        "speakingStyle": "formal",
        "knowledgeReferenceId": "ks-xyz",
    }
    mock_client.get.return_value = canonical_resource
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_get"]({"resource_type": "aiagents", "resource_id": "agent-1"})
    data = json.loads(result[0].text)

    called_path = mock_client.get.call_args[0][0]
    assert called_path == "/v2.0/aiagents/agent-1", (
        f"Expected /v2.0/aiagents/agent-1, got {called_path}"
    )
    assert data.get("speakingStyle") == "formal"
    assert "_source" in data
```

- [ ] **Step 2: Run the test to confirm it passes already**

```bash
uv run pytest tests/tools/test_flow_ops.py::test_cognigy_get_aiagents_calls_canonical_endpoint -v
```

Expected: PASS — the routing is already correct; this is a regression guard. If it fails, the routing is broken and must be fixed in `_resource_path`.

---

### Task 3: Fix sync_remote_state — fetch canonical resource before caching

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/state_tools.py:173-181`

- [ ] **Step 1: Apply the fix**

Find this block in `state_tools.py` (around lines 173–181):

```python
            try:
                agents_resp = client.get(f"/v2.0/flows/{flow['_id']}/chart/nodes/aiagents")
                for agent in agents_resp.get("items", []):
                    if agent["_id"] not in seen_agents:
                        seen_agents.add(agent["_id"])
                        state.set("agents", agent["name"], value={"id": agent["_id"]})
                        cache.set("aiagents", agent["_id"], agent)
            except Exception:
                pass
```

Replace with:

```python
            try:
                agents_resp = client.get(f"/v2.0/flows/{flow['_id']}/chart/nodes/aiagents")
                for agent in agents_resp.get("items", []):
                    if agent["_id"] not in seen_agents:
                        seen_agents.add(agent["_id"])
                        state.set("agents", agent["name"], value={"id": agent["_id"]})
                        try:
                            agent_resource = client.get(f"/v2.0/aiagents/{agent['_id']}")
                            cache.set("aiagents", agent["_id"], agent_resource)
                        except Exception:
                            pass  # cache miss on first cognigy_get is acceptable
            except Exception:
                pass
```

- [ ] **Step 2: Update test_sync_remote_state_calls_api mock to include the canonical resource call**

The existing test at line 37 of `test_state_tools.py` has this mock side_effect:

```python
mock_client.get.side_effect = [
    {"items": [{"_id": "flow-1", "name": "Main Flow"}]},                                    # GET /v2.0/flows?projectId=...
    {"_embedded": {"extensions": []}},                                                       # GET /v2.0/extensions?projectId=...
    {"nodes": []},                                                                           # chart (tool discovery)
    {"items": [{"_id": "agent-1", "name": "My Agent"}]},                                    # chart/nodes/aiagents
    {"items": [{"_id": "ep-1", "name": "REST", "URLToken": "tok123", "flowId": "flow-1"}]},  # GET /v2.0/endpoints?projectId=...
]
```

After the fix, `sync_remote_state` will make an additional GET call for the canonical agent resource. Update the mock:

```python
mock_client.get.side_effect = [
    {"items": [{"_id": "flow-1", "name": "Main Flow"}]},                                     # GET /v2.0/flows?projectId=...
    {"_embedded": {"extensions": []}},                                                        # GET /v2.0/extensions?projectId=...
    {"nodes": []},                                                                            # chart (tool discovery)
    {"items": [{"_id": "agent-1", "name": "My Agent"}]},                                     # chart/nodes/aiagents
    {"_id": "agent-1", "name": "My Agent", "speakingStyle": "formal"},                       # GET /v2.0/aiagents/agent-1
    {"items": [{"_id": "ep-1", "name": "REST", "URLToken": "tok123", "flowId": "flow-1"}]},  # GET /v2.0/endpoints?projectId=...
]
```

- [ ] **Step 3: Update test_sync_remote_state_binds_project_in_session mock (line 110)**

The mock at line 110 of `test_state_tools.py` also simulates the sync flow. After the fix it has no agents to discover (agents response is `{"items": []}`), so no additional call is needed. Verify the mock still works:

```python
mock_client.get.side_effect = [
    {"items": [{"_id": "flow-1", "name": "Main Flow"}]},  # flows
    {"_embedded": {"extensions": []}},                      # extensions (empty)
    {"nodes": []},                                          # chart (tool discovery)
    {"items": []},                                          # chart/nodes/aiagents — no agents, no extra call
    {"items": []},                                          # endpoints
]
```

This mock is unchanged — no update needed. Just confirm the test passes.

---

### Task 4: Run all affected tests

- [ ] **Step 1: Run the full test suite**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/ -v
```

Expected: all tests PASS. Pay attention to:
- `test_sync_remote_state_calls_api` — must pass with the updated mock
- `test_sync_remote_state_caches_canonical_aiagent_resource` — must now PASS (Task 1 test)
- `test_cognigy_get_aiagents_calls_canonical_endpoint` — must PASS (regression guard)
- `test_sync_remote_state_binds_project_in_session` — must still pass (unchanged mock)

If any test fails due to mock call count or StopIteration (too few side_effects), check whether the fix introduced more GET calls than the mock expects. Add another entry for `/v2.0/aiagents/{id}` for each agent in the side_effect list.

---

### Task 5: Version bump and commit

**Files:**
- Modify: `cognigy-mcp/pyproject.toml` — `version = "1.3.7"` → `version = "1.3.8"`
- Modify: `.claude-plugin/plugin.json` — `"version": "1.3.7"` → `"version": "1.3.8"`

- [ ] **Step 1: Bump versions**

In `cognigy-mcp/pyproject.toml`, change:
```toml
version = "1.3.7"
```
to:
```toml
version = "1.3.8"
```

In `.claude-plugin/plugin.json`, change:
```json
"version": "1.3.7"
```
to:
```json
"version": "1.3.8"
```

- [ ] **Step 2: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/state_tools.py cognigy-mcp/tests/tools/test_state_tools.py cognigy-mcp/tests/tools/test_flow_ops.py cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "fix: fetch canonical AI Agent resource in sync_remote_state before caching (fixes #22)"
```

- [ ] **Step 3: Push**

```bash
git push
```

Then run the post-push command from CLAUDE.md:

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```
