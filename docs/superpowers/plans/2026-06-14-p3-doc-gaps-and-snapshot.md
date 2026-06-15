# P3 Doc Gaps & Snapshot Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four P3 issues from the issues #14–25 triage: helpful error for node listing (#18), document insertBefore workaround (#19), document IF node branch population (#23), and add project snapshot support (#24).

**Architecture:** All changes are isolated to `explain.py` (documentation string edits) except #18 (one guard in `flow_ops.py`) and #24 (verify cognigy_create already works for snapshots + new explain topic). No schema changes, no new tools, no API layer changes.

**Tech Stack:** Python 3.14, pytest + uv, cognigy-mcp MCP server

---

## File Map

| File | Change |
|---|---|
| `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` | Add node-listing guard to `_cognigy_list` (#18) |
| `cognigy-mcp/cognigy_mcp/tools/explain.py` | Update `_TOPIC_INDEX`, `node-positioning`, add `project-snapshots` topic, add to `TOPICS` list (#18, #19, #23, #24) |
| `cognigy-mcp/tests/tools/test_flow_ops.py` | Test node-listing error response (#18) |
| `cognigy-mcp/tests/tools/test_explain.py` | Regression tests for new/updated explain content (#19, #23, #24) |

---

### Task 1: Guard cognigy_list against node resource type (#18)

**Context:** `cognigy_list(resource_type="node")` currently constructs `GET /v2.0/node?projectId=...` which 404s. Nodes have no independent listing endpoint — the flow chart is the only way to enumerate them. A helpful error is better than a confusing 404.

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` (function `_cognigy_list`, after `rtype = _normalise_rtype(...)`)
- Test: `cognigy-mcp/tests/tools/test_flow_ops.py`

- [ ] **Step 1: Write the failing test**

Add to `cognigy-mcp/tests/tools/test_flow_ops.py`:

```python
def test_cognigy_list_node_returns_helpful_error(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    for rtype in ("node", "nodes"):
        result = handlers["cognigy_list"]({"resource_type": rtype})
        data = json.loads(result[0].text)
        assert "error" in data
        assert "get_flow_chart" in data["error"]
        mock_client.get.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd cognigy-mcp && uv run pytest tests/tools/test_flow_ops.py::test_cognigy_list_node_returns_helpful_error -v
```

Expected: FAIL — no error is returned, the client GET is called and raises on the mock.

- [ ] **Step 3: Add the guard to _cognigy_list**

In `cognigy-mcp/cognigy_mcp/tools/flow_ops.py`, find `_cognigy_list`. After the line `rtype = _normalise_rtype(args["resource_type"])`, add:

```python
        if rtype in ("node", "nodes"):
            return _ok({
                "error": (
                    "Nodes cannot be listed independently — they exist only within a flow chart. "
                    "Use get_flow_chart(flow_id=<flowId>) to list all nodes in a flow."
                )
            })
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/tools/test_flow_ops.py::test_cognigy_list_node_returns_helpful_error -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py cognigy-mcp/tests/tools/test_flow_ops.py
git commit -m "fix: cognigy_list(node/nodes) returns helpful error pointing to get_flow_chart (fixes #18)"
```

---

### Task 2: Document insertBefore/insertAfter workaround (#19)

**Context:** Both `insertBefore` and `insertAfter` return HTTP 500 "Error while reading ChartData" on AU1 — confirmed live. This is an API-side bug. The current docs correctly flag them as broken but do not tell the agent what to do instead. An agent trying to insert a node "before" an existing node has no documented path.

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py` (`_TOPIC_INDEX` entry for `node-positioning`, `_CONTENT["node-positioning"]`)
- Test: `cognigy-mcp/tests/tools/test_explain.py`

- [ ] **Step 1: Write the failing test**

Add to `cognigy-mcp/tests/tools/test_explain.py`:

```python
def test_node_positioning_documents_insert_before_workaround(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "insertBefore" in text, "Should mention insertBefore by name"
    assert "predecessor" in text, "Should document the predecessor-node workaround"
    assert "move" in text.lower(), "Should mention the move operation as alternative"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/tools/test_explain.py::test_node_positioning_documents_insert_before_workaround -v
```

Expected: FAIL — "predecessor" not in text.

- [ ] **Step 3: Update explain.py**

In `cognigy-mcp/cognigy_mcp/tools/explain.py`:

**3a. Update `_TOPIC_INDEX`** — find the `node-positioning` line and change it to:

```python
  node-positioning     append vs appendChild modes, child branch population, insertAfter + insertBefore 500 bug on AU1, insert-before workaround
```

**3b. Update `_CONTENT["node-positioning"]`** — replace the `### BROKEN on AU1` section:

Current text (find this block):
```
### BROKEN on AU1 (return 500 "Error while reading ChartData")
  - insertAfter
  - insertBefore
```

Replace with:
```
### BROKEN on AU1 (return 500 "Error while reading ChartData")
  - insertAfter
  - insertBefore

### Workaround: inserting a node BEFORE an existing target
There is no direct "insert before" mode. To place a new node before target node T:

Option A — append after predecessor (preferred):
  1. GET the flow chart
  2. Find T's predecessor: the relation whose "next" == T._id
  3. Create the new node with mode: "append", target: <predecessorNodeId>

Option B — append anywhere, then move:
  1. Create the new node with mode: "append" anywhere convenient
  2. cognigy_invoke(resource_type="flows", resource_id=<flowId>,
       operation="move", body={"nodeId": <newNodeId>, "mode": "append", "target": <predecessorNodeId>})

Use Option A when you know the predecessor. Use Option B when the node already exists
and needs repositioning.
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/tools/test_explain.py::test_node_positioning_documents_insert_before_workaround -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/explain.py cognigy-mcp/tests/tools/test_explain.py
git commit -m "docs: document insertBefore/After workaround in node-positioning explain topic (fixes #19)"
```

---

### Task 3: Document IF node branch population (#23)

**Context:** IF nodes (type: `"if"`) auto-create two branch container nodes when created: Then (childIds[0]) and Else (childIds[1]). To add nodes inside a branch, you must use `mode: "appendChild"` targeting the branch container's `_id` — NOT the IF node's `_id`. This is the same pattern as the Once node, but it is not documented anywhere. Note: the type string fix ("if" not "ifThenElse") is in the P2 plan for #14 — this task only adds the branch population docs.

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py` (`_CONTENT["node-positioning"]`)
- Test: `cognigy-mcp/tests/tools/test_explain.py`

- [ ] **Step 1: Write the failing test**

Add to `cognigy-mcp/tests/tools/test_explain.py`:

```python
def test_node_positioning_documents_if_branch_population(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "IF node" in text or "if node" in text.lower(), "Should document IF node branch pattern"
    assert "Then" in text and "Else" in text, "Should name both branch containers"
    assert "childIds[0]" in text or "children[0]" in text, "Should document how to find branch container IDs"
    assert "appendChild" in text, "Should document appendChild for branch population"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/tools/test_explain.py::test_node_positioning_documents_if_branch_population -v
```

Expected: FAIL — "IF node" not in text.

- [ ] **Step 3: Add IF branch population section to explain.py**

In `cognigy-mcp/cognigy_mcp/tools/explain.py`, in `_CONTENT["node-positioning"]`, append the following section at the end of the topic (after the Once node example):

```python
### IF node branch population
IF nodes (type: "if") auto-create two branch container nodes when created.
Each branch container has its own _id and appears in the IF node's childIds[]:
  - childIds[0] = Then branch container
  - childIds[1] = Else branch container

To add a node into an IF branch:
1. Create the IF node via cognigy_create (see flow-chart-reading for correct config schema)
2. GET the flow chart — find the IF node's childIds array
3. childIds[0] is the Then container _id, childIds[1] is the Else container _id
4. Create child nodes with mode: "appendChild", target: <branch-container-_id>

Example: IF node "if-abc" with childIds ["then-xyz", "else-xyz"]
  - To add a Say node to the Then branch: mode="appendChild", target="then-xyz"
  - To add a Code node to the Else branch: mode="appendChild", target="else-xyz"

Common pitfall: targeting the IF node's own _id ("if-abc") instead of the branch container.
The IF node itself is NOT the container — use its childIds entries.
This is the same pattern as Once → OnFirstTime/Afterwards branches (see above).
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/tools/test_explain.py::test_node_positioning_documents_if_branch_population -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/explain.py cognigy-mcp/tests/tools/test_explain.py
git commit -m "docs: document IF node Then/Else branch population in node-positioning topic (fixes #23)"
```

---

### Task 4: Add project snapshot support and documentation (#24)

**Context:** Flow-level versioning does not exist in the Cognigy API (`/v2.0/flows/{id}/versions` = 404). However, project-level snapshots DO work: `POST /v2.0/snapshots` with `{name, description, projectId}` returns a queued async job. The alias `"snapshot"` → `"snapshots"` already exists in `_RESOURCE_TYPE_ALIASES`, so `cognigy_create(resource_type="snapshot", body={...})` already constructs the correct URL — no code change needed. The only work is: write a test confirming it, add a `project-snapshots` explain topic, and register it in `TOPICS`.

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py` (add to `TOPICS`, `_TOPIC_INDEX`, `_CONTENT`)
- Test: `cognigy-mcp/tests/tools/test_flow_ops.py` (verify cognigy_create routes correctly)
- Test: `cognigy-mcp/tests/tools/test_explain.py` (verify topic content)

- [ ] **Step 1: Write the failing tests**

Add to `cognigy-mcp/tests/tools/test_flow_ops.py`:

```python
def test_cognigy_create_snapshot_posts_to_correct_url(mock_client, state, cache):
    mock_client.post.return_value = {
        "_id": "job-abc123",
        "status": "queued",
        "type": "createSnapshot",
        "parameters": {"properties": {"name": "My Snapshot", "description": "test"}},
        "progress": 0,
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({
        "resource_type": "snapshot",
        "body": {"name": "My Snapshot", "description": "test", "projectId": "proj-1"},
    })
    mock_client.post.assert_called_once_with(
        "/v2.0/snapshots",
        {"name": "My Snapshot", "description": "test", "projectId": "proj-1"},
    )
    data = json.loads(result[0].text)
    assert data.get("status") == "queued" or data.get("type") == "createSnapshot"
```

Add to `cognigy-mcp/tests/tools/test_explain.py`:

```python
def test_project_snapshots_topic_exists_and_documents_api(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "project-snapshots"})
    text = result[0].text
    assert len(text) > 100
    assert "snapshot" in text.lower()
    assert "description" in text, "Should document the required description field"
    assert "queued" in text, "Should explain the async/queued response"
    assert "cognigy_create" in text, "Should show how to create via MCP tool"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_flow_ops.py::test_cognigy_create_snapshot_posts_to_correct_url tests/tools/test_explain.py::test_project_snapshots_topic_exists_and_documents_api -v
```

Expected: Both FAIL — the explain topic doesn't exist yet.

- [ ] **Step 3: Add project-snapshots to TOPICS list and _TOPIC_INDEX**

In `cognigy-mcp/cognigy_mcp/tools/explain.py`:

**3a.** Add `"project-snapshots"` to the `TOPICS` list:

```python
TOPICS = [
    "node-positioning", "node-wiring", "agent-tool-branch", "node-config-update",
    "flow-chart-reading", "tool-conditions", "two-pass-confirm", "turn-structure",
    "xapp-delivery", "xapp-event-handling", "cognigyScript", "code-node-patterns", "voice-gateway",
    "outbound-trigger", "knowledge-store", "endpoint-config", "function-execution",
    "session-injection", "extension-map", "node-types", "mcp-comparison", "tool-selection",
    "project-snapshots",
]
```

**3b.** Add to `_TOPIC_INDEX` (append before the closing `"""`):

```
  project-snapshots    create project snapshots for versioning (flow-level versioning does not exist in the API)
```

- [ ] **Step 4: Add _CONTENT["project-snapshots"]**

In `cognigy-mcp/cognigy_mcp/tools/explain.py`, add to `_CONTENT`:

```python
    "project-snapshots": """
## project-snapshots — Project Versioning via Snapshots

### Flow-level versioning does not exist
POST /v2.0/flows/{flowId}/versions returns 404. The "Save Version" button in the Cognigy UI
creates a project-level snapshot, not a flow-scoped version. There is no API for flow-scoped versioning.

### Create a project snapshot (captures entire project state)
  cognigy_create(resource_type="snapshot", body={
    "name": "Task 0 — Foundation",
    "description": "Baseline before AI Agent job additions",
    "projectId": "<projectId>"
  })

Required fields: name, description, projectId
"description" is required — omitting it returns HTTP 400.

### Response: async job (not the snapshot itself)
Snapshot creation is asynchronous. The response is a queued job:
  {
    "_id": "<jobId>",
    "status": "queued",
    "type": "createSnapshot",
    "progress": 0,
    "parameters": {
      "properties": {"name": "...", "description": "..."}
    }
  }
The jobId is NOT the snapshotId. The snapshot appears in the Cognigy UI once the job completes
(usually within a few seconds). There is no polling endpoint for job completion.

### List existing snapshots
  cognigy_list(resource_type="snapshots", project_id="<projectId>")
Returns: {"items": [...], "count": N}

### When to snapshot
Use at task completion milestones during multi-agent builds:
  - Before starting a major new component (safety checkpoint)
  - After a working demo state is confirmed (named "DEMO READY")
  - Before destructive operations (delete/replace flow nodes)
""",
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/tools/test_flow_ops.py::test_cognigy_create_snapshot_posts_to_correct_url tests/tools/test_explain.py::test_project_snapshots_topic_exists_and_documents_api -v
```

Expected: Both PASS

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass. The `test_tool_description_contains_all_topic_names` test verifies `"project-snapshots"` is in the explain tool description — confirm it passes.

- [ ] **Step 7: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/explain.py cognigy-mcp/tests/tools/test_flow_ops.py cognigy-mcp/tests/tools/test_explain.py
git commit -m "feat: add project-snapshots explain topic and verify cognigy_create routing (fixes #24)"
```

---

## Self-Review

**Spec coverage:**
- #18 — guarded in `_cognigy_list`, tested, committed ✓
- #19 — `node-positioning` updated with insertBefore workaround (predecessor-append + move options) ✓
- #23 — `node-positioning` updated with IF node Then/Else branch population pattern ✓
- #24 — `project-snapshots` topic added, cognigy_create routing confirmed by test ✓

**Placeholder scan:** No TBD/TODO/similar. All code blocks are complete. Test assertions are specific.

**Type consistency:** No type changes across tasks. All references to `_ok`, `make_handlers`, `TOPICS`, `_CONTENT`, `_TOPIC_INDEX` match existing patterns.

**Noted scope boundary:** The type-string fix for `"if"` vs `"ifThenElse"` (#14) and the flow-chart-reading config schema correction are in the P2 plan. Task 3 adds branch population docs referencing the correct type string but does not fix the main type string error — the P2 plan must be applied first or in parallel for #23 docs to be fully consistent with the rest of the explain content.
