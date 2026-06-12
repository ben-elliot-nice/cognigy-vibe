# Cognigy MCP Uplift — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 12 usability, token efficiency, and cleanup issues identified in exploratory testing across three sequential phases.

**Architecture:** Five source files in `cognigy-mcp/cognigy_mcp/tools/` handle all MCP tool behavior. A new `hooks/` directory adds plugin-level onboarding. Changes are focused: explain.py for documentation, flow_ops.py for data operations, state_tools.py/testing.py/file_push.py for specific behaviors.

**Tech Stack:** Python 3.11+, MCP SDK, bash (hook script)

---

## File Map

| File | Phase | What's changing |
|------|-------|-----------------|
| `hooks/hooks.json` (NEW) | 1A | PreToolUse hook config |
| `hooks/onboarding-gate.sh` (NEW) | 1A | Hook script — gate + inject primer |
| `cognigy-mcp/cognigy_mcp/tools/explain.py` | 1B, 1C | New/changed explain topics |
| `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` | 1C, 1D, 2A-2D, 3D | Tool descriptions, handlers, validation |
| `cognigy-mcp/cognigy_mcp/tools/file_push.py` | 3A | Remove push_tool_from_file |
| `cognigy-mcp/tests/tools/test_file_push.py` | 3A | Remove related tests |
| `cognigy-mcp/README.md` | 3A | Remove tool from list |
| `docs/architecture.md` | 3A | Remove tool reference |
| `cognigy-mcp/cognigy_mcp/tools/state_tools.py` | 3B | Description update |
| `cognigy-mcp/cognigy_mcp/tools/testing.py` | 3C | Add minimal parameter |
| `cognigy-mcp/pyproject.toml` | Each phase | Version bump |
| `.claude-plugin/plugin.json` | Each phase | Version bump |

---

## Phase 1: Usability & Unblocking

### Task 1A: PreToolUse Onboarding Gate

**Files:**
- Create: `hooks/hooks.json`
- Create: `hooks/onboarding-gate.sh`

- [ ] **Step 1: Create hooks/hooks.json**

Write:
```json
{
  "PreToolUse": [
    {
      "matcher": "mcp__cognigy-vibe__.*",
      "hooks": [
        {
          "type": "command",
          "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/onboarding-gate.sh",
          "timeout": 5
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Create hooks/onboarding-gate.sh**

Write:
```bash
#!/bin/bash
set -euo pipefail

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')
session_id=$(echo "$input" | jq -r '.session_id')

# Let explain calls pass through — user is self-educating
if echo "$tool_name" | grep -qi "explain"; then
  exit 0
fi

# Check if primer already shown this session
flag_file="/tmp/.cognigy-primer-${session_id}"
if [ -f "$flag_file" ]; then
  exit 0
fi

# First Cognigy call this session — inject primer and deny
touch "$flag_file"

cat <<'PRIMER'
{
  "hookSpecificOutput": {
    "permissionDecision": "deny",
    "permissionDecisionReason": "First Cognigy session — loading architectural primer. Re-attempt your tool call.",
    "additionalContext": "COGNIGY ARCHITECTURAL PRIMER: This is a visual flow builder exposed as code. The hierarchy is Projects > Flows > Nodes > AI Agents > Tools. Flows are canvases with connected nodes (Say, Code, Once, HTTP Request, AI Agent Job). AI Agent Job nodes reference AI Agents which may have Tools attached. Key concepts: use cognigy_get/cognigy_create/cognigy_update by resource ID; use resolve_resource to look up IDs by friendly name; use get_flow_chart to see the full node tree; use explain(\"topic\") for detailed guidance on specific patterns. Call explain() with no arguments to see all available topics."
  }
}
PRIMER
```

- [ ] **Step 3: Make hook script executable**

Run: `chmod +x hooks/onboarding-gate.sh`

- [ ] **Step 4: Verify script produces valid JSON**

Run: `echo '{"tool_name":"mcp__cognigy-vibe__cognigy_get","session_id":"test-123"}' | bash hooks/onboarding-gate.sh | jq .`
Expected: Valid JSON with hookSpecificOutput.permissionDecision = "deny"

- [ ] **Step 5: Verify explain bypass**

Run: `echo '{"tool_name":"mcp__cognigy-vibe__explain","session_id":"test-123"}' | bash hooks/onboarding-gate.sh; echo "EXIT:$?"`
Expected: EXIT:0, no output

- [ ] **Step 6: Verify flag file prevents repeat**

Run: `echo '{"tool_name":"mcp__cognigy-vibe__cognigy_get","session_id":"test-456"}' | bash hooks/onboarding-gate.sh; echo "EXIT:$?"`
Expected: EXIT:0 (first call sets flag)
Run again same command
Expected: EXIT:0 (second call sees flag and exits)

- [ ] **Step 7: Commit**

```bash
git add hooks/hooks.json hooks/onboarding-gate.sh
git commit -m "feat: add PreToolUse onboarding gate with architectural primer injection"
```

---

### Task 1B: Child Branch Population Documentation

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py` — update turn-structure topic, node-positioning topic, and index

- [ ] **Step 1: Update `_TOPIC_INDEX` for node-positioning**

In `cognigy-mcp/cognigy_mcp/tools/explain.py`, change line 20 from:
```
  node-positioning     append vs appendChild modes, insertAfter 500 bug on AU1
```
to:
```
  node-positioning     append vs appendChild modes, child branch population, insertAfter 500 bug on AU1
```

- [ ] **Step 2: Update `_TOPIC_INDEX` for turn-structure**

In `explain.py`, change line 27 from:
```
  turn-structure       Once/OnFirstTime/Afterwards, input.execution, context reset prevention
```
to:
```
  turn-structure       Once/OnFirstTime/Afterwards, input.execution, context reset prevention, child branch API patterns
```

- [ ] **Step 3: Add child branch population section to `node-positioning` topic**

In `explain.py`, inside the `_CONTENT["node-positioning"]` string, append after the existing content and before the closing `"""`:

```python

### Child branch population (Once node example)
Once nodes auto-create two child branch nodes: OnFirstTime and Afterwards.
Each branch appears as a separate node in the chart with its own _id.

To add a node into a branch:
1. Find the branch node in the chart (e.g. OnFirstTime child of the Once node)
2. Use mode: "appendChild" with target set to the BRANCH NODE's _id

Common pitfall: targeting the parent Once node's _id instead of the branch node.
The branch node's _id is what you need — it's the container for child nodes.

Example: chart shows Once node "a1b2" with childIds ["c3d4", "e5f6"]
  - "c3d4" is the OnFirstTime branch node
  - "e5f6" is the Afterwards branch node
  - To add a Code node to OnFirstTime, target "c3d4", NOT "a1b2"
```

- [ ] **Step 4: Add child branch API patterns to `turn-structure` topic**

In `explain.py`, inside the `_CONTENT["turn-structure"]` string, append after the "Context reset prevention" section:

```python

### Programmatic child branch population
Once nodes auto-create OnFirstTime and Afterwards branches — do NOT attempt to create
them manually (returns HTTP 400 "operation conflicts with constraints").

To add a node to a child branch via the API:
1. GET the flow chart to find the Once node and its childIds
2. The childIds array contains the branch node _ids
3. Create your node with mode="appendChild", target="<branch-node-id>"

Full example — adding a Code node to OnFirstTime:
  // Step 1: get_flow_chart to find the Once node
  // Chart shows Once node "once-abc" with childIds ["onfirst-xyz", "after-xyz"]

  // Step 2: create the Code node as child of OnFirstTime branch
  cognigy_create(resource_type="node", body={
    "flowId": "<flow-id>",
    "type": "code",
    "label": "Load Guest Profile",
    "mode": "appendChild",
    "target": "onfirst-xyz",
    "config": {"code": "const profile = await api.httpRequest({...});"}
  })

Unlike aiAgentJobTool branches (which use append after the tool node),
Once branches use appendChild with the branch node as target.
```

- [ ] **Step 5: Verify explain topics load correctly**

Run: `python3 -c "from cognigy_mcp.tools.explain import _CONTENT; print('node-positioning' in _CONTENT); print('turn-structure' in _CONTENT); print('appendChild' in _CONTENT['node-positioning']); print('Programmatic child branch' in _CONTENT['turn-structure'])"`
Expected: four `True` outputs

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/explain.py
git commit -m "docs: add child branch population patterns to explain topics"
```

---

### Task 1C: Tool Selection Documentation + Code Node Block

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py` — new tool-selection topic
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — block in _cognigy_create handler

- [ ] **Step 1: Add `tool-selection` to TOPICS list**

In `explain.py`, add `"tool-selection"` to the `TOPICS` list (around line 13, after `"mcp-comparison",`):

```python
    "mcp-comparison", "tool-selection",
```

- [ ] **Step 2: Add `tool-selection` to `_TOPIC_INDEX`**

In `explain.py`, append to the `_TOPIC_INDEX` string before the closing `"""`:

```
  tool-selection       when to use push_code_node vs cognigy_create vs cognigy_update
```

- [ ] **Step 3: Add `tool-selection` content to `_CONTENT` dict**

In `explain.py`, add a new entry to the `_CONTENT` dict (after `"mcp-comparison"`):

```python
    "tool-selection": """
## tool-selection — Choosing the Right Tool

### Decision tree
- "Creating a Code node from a local .js/.ts file?" → push_code_node (provides conflict detection against Cognigy UI edits)
- "Creating any other node (Say, Once, HTTP Request, AI Agent Job, etc.)?" → cognigy_create
- "Creating an HTML/xApp node from a local .html file?" → push_html_node (sets mode='full' automatically)
- "Updating an existing node's config?" → cognigy_update with merge_config=true
- "Reading a node or resource?" → cognigy_get

### Why push_code_node for Code nodes?
push_code_node provides conflict detection: if someone edited the node in the Cognigy UI
since your last push, the push is blocked with a diff. cognigy_create has no such protection.

### File-backed vs direct
- push_code_node / push_html_node: local file → remote node, with conflict detection
- cognigy_create: create node from scratch, no local file backing

### What about AI Agent Tools?
The now-removed push_tool_from_file was targeting a hallucinated API endpoint.
AI Agent tool configuration is done through the aiAgentJobTool node config in a flow.
See explain("agent-tool-branch") for the three-node pattern.
""",
```

- [ ] **Step 4: Add Code node block to `_cognigy_create` in flow_ops.py**

In `flow_ops.py`, in the `_cognigy_create` handler (around line 313), add the block after the `flow_id` check and before the Say node normalization:

```python
def _cognigy_create(args: dict) -> list[TextContent]:
    rtype = _normalise_rtype(args["resource_type"])
    body = args["body"]
    flow_id = args.get("flow_id")
    if rtype == "node":
        if not flow_id:
            return _ok({"error": "flow_id required to create a node"})
        if body.get("type") == "code":
            return _ok({"error": (
                "Code nodes must be created via push_code_node "
                "(provides file-backed conflict detection). "
                "Use push_code_node for .js/.ts files. "
                'See explain("tool-selection") for guidance.'
            )})
        if body.get("type") == "say" and "config" in body:
            body = {**body, "config": _normalise_say_config(body["config"])}
        body = _inject_extension(body)
        path = f"/v2.0/flows/{flow_id}/chart/nodes"
    else:
        path = f"/v2.0/{rtype}"
    result = client.post(path, body)
    name = result.get("name") or result.get("label")
    if name:
        state.set(rtype, name, value={"id": result["_id"]})
    cache.set(rtype, result["_id"], result)
    return _ok(result)
```

- [ ] **Step 5: Add the same block to `_cognigy_update` in flow_ops.py**

In the `_cognigy_update` handler, add after the flow_id check:

```python
    if rtype == "node" and current.get("type") == "code":
        return _ok({"error": (
            "Code nodes must be updated via push_code_node "
            "(provides file-backed conflict detection). "
            'See explain("tool-selection") for guidance.'
        )})
```

Insert this right after `current = client.get(path)` and before the Say node normalisation check (`if current.get("type") == "say"`).

- [ ] **Step 6: Verify the block logic**

Run: `python3 -c "
from cognigy_mcp.tools.flow_ops import _normalise_rtype
print(_normalise_rtype('node'))
print(_normalise_rtype('flow'))
"`
Expected: `node` and `flows`

- [ ] **Step 7: Run existing tests to ensure nothing breaks**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_flow_ops.py -v`
Expected: All existing tests pass

- [ ] **Step 8: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/explain.py cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git commit -m "feat: add tool-selection explain topic and block code node creation via cognigy_create"
```

---

### Task 1D: Mode Values Documentation

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — update cognigy_create Tool description

- [ ] **Step 1: Update `cognigy_create` tool description**

In `flow_ops.py`, replace the `cognigy_create` Tool description (current: `"POST to create a new Cognigy resource. Auto-saves name to ID to .state.json. For nodes, body must include flowId, type, mode, target."`):

```python
        description="POST to create a new Cognigy resource. Auto-saves name to ID to .state.json. "
                    "For nodes, body must include: "
                    "type (e.g. 'say', 'code', 'once', 'httpRequest', 'aiAgentJob'), "
                    "mode — one of: 'appendChild' (add as child of target container), "
                    "'append' (add as last sibling after target), "
                    "'insertAfter' or 'insertBefore' (relative to sibling, BROKEN on AU1), "
                    "target (the _id of the reference node), "
                    "and flowId (the flow _id).",
```

- [ ] **Step 2: Verify tool description is parseable**

Run: `python3 -c "from cognigy_mcp.tools.flow_ops import TOOLS; t = [x for x in TOOLS if x.name == 'cognigy_create'][0]; print(t.description)"`
Expected: Updated description with mode values

- [ ] **Step 3: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git commit -m "docs: document valid mode values in cognigy_create tool description"
```

- [ ] **Step 4: Bump Phase 1 version**

Edit `cognigy-mcp/pyproject.toml`: change `version = "1.2.9"` to `version = "1.3.0"`
Edit `.claude-plugin/plugin.json`: change `"version": "1.2.9"` to `"version": "1.3.0"`

```bash
git add cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "chore: bump to 1.3.0 — Phase 1 usability uplift"
```

---

## Phase 2: Token Efficiency

All Phase 2 changes are in `cognigy-mcp/cognigy_mcp/tools/flow_ops.py`. Tasks 2A-2D each touch different handlers in the same file so they are ordered by complexity.

### Task 2A: List Response Optimization

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — _cognigy_list handler + Tool definition

- [ ] **Step 1: Add `full_objects` parameter to `cognigy_list` Tool schema**

In `flow_ops.py`, in the `cognigy_list` Tool `inputSchema.properties`, add after `"limit"`:

```python
                "full_objects": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, returns complete objects. Default false returns simplified {id, name} pairs (~95% token savings).",
                },
```

- [ ] **Step 2: Update `cognigy_list` tool description**

Replace the current `cognigy_list` description with:

```python
        description="List Cognigy resources. Pass project_id for project-scoped resources, "
                    "agent_id for agent-scoped resources (e.g. listing jobs). "
                    "resource_type accepts both singular ('flow') and plural ('flows'). "
                    "Default: returns simplified {id, name} pairs. Use full_objects=true for complete objects.",
```

- [ ] **Step 3: Update `_cognigy_list` handler to strip responses**

Replace the `_cognigy_list` handler:

```python
def _cognigy_list(args: dict) -> list[TextContent]:
    rtype = _normalise_rtype(args["resource_type"])
    project_id = args.get("project_id")
    agent_id = args.get("agent_id")
    limit = args.get("limit", 100)
    full_objects = args.get("full_objects", False)
    if agent_id:
        data = client.get(f"/v2.0/aiagents/{agent_id}/{rtype}", limit=limit)
    elif project_id:
        data = client.get(f"/v2.0/{rtype}", projectId=project_id, limit=limit)
    else:
        data = client.get(f"/v2.0/{rtype}", limit=limit)
    if not full_objects:
        items = data.get("items", [])
        simplified = []
        for item in items:
            entry = {"id": item.get("_id"), "name": item.get("name")}
            if "description" in item:
                entry["description"] = item["description"]
            if "type" in item:
                entry["type"] = item["type"]
            simplified.append(entry)
        return _ok({"items": simplified, "count": len(simplified)})
    return _ok(data)
```

- [ ] **Step 4: Run existing tests**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_flow_ops.py -v`
Expected: All tests pass (simplified format may require test updates)

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git commit -m "feat: optimize cognigy_list to return simplified {id, name} pairs by default"
```

---

### Task 2B: Chart Response Format Options

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — get_flow_chart Tool + _get_flow_chart handler

- [ ] **Step 1: Add `format` parameter to `get_flow_chart` Tool schema**

In `flow_ops.py`, in the `get_flow_chart` Tool `inputSchema.properties`, add after `"flow_id"`:

```python
                "format": {
                    "type": "string",
                    "enum": ["hierarchy", "raw", "both"],
                    "default": "hierarchy",
                    "description": "'hierarchy': tree string only (~95% savings, default). 'raw': nodes + relations arrays. 'both': current behavior (explicit opt-in).",
                },
```

- [ ] **Step 2: Update `get_flow_chart` tool description**

Replace the current description with:

```python
        description="Fetch the full chart for a flow. Default: returns human-readable hierarchy string. "
                    "Use format='raw' for structured arrays or format='both' for the legacy combined response.",
```

- [ ] **Step 3: Update `_get_flow_chart` handler**

Replace the handler:

```python
def _get_flow_chart(args: dict) -> list[TextContent]:
    flow_id = args["flow_id"]
    fmt = args.get("format", "hierarchy")
    chart = client.get(f"/v2.0/flows/{flow_id}/chart")
    if fmt == "hierarchy":
        hierarchy = _build_hierarchy(chart)
        return _ok({"hierarchy": hierarchy})
    elif fmt == "raw":
        return _ok({"nodes": chart.get("nodes", []), "relations": chart.get("relations", [])})
    else:
        hierarchy = _build_hierarchy(chart)
        return _ok({"relations": chart.get("relations", []), "nodes": chart.get("nodes", []), "hierarchy": hierarchy})
```

- [ ] **Step 4: Run existing tests**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_flow_ops.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git commit -m "feat: add format parameter to get_flow_chart with hierarchy default"
```

---

### Task 2C: Create/Update Response Slimming

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — _cognigy_create + _cognigy_update handlers + Tool definitions

- [ ] **Step 1: Add `return_full_object` parameter to `cognigy_create` Tool schema**

In `flow_ops.py`, in the `cognigy_create` Tool `inputSchema.properties`, add:

```python
                "return_full_object": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, returns the complete created object. Default false returns minimal {_id, referenceId, type, label} (~90% token savings).",
                },
```

- [ ] **Step 2: Add `return_full_object` parameter to `cognigy_update` Tool schema**

In the `cognigy_update` Tool `inputSchema.properties`, add after `"flow_id"`:

```python
                "return_full_object": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, returns the complete updated object. Default false returns minimal {_id, type, label} (~90% token savings).",
                },
```

- [ ] **Step 3: Update `_cognigy_create` handler to return minimal by default**

At the end of `_cognigy_create`, replace:
```python
        cache.set(rtype, result["_id"], result)
        return _ok(result)
```
with:
```python
        cache.set(rtype, result["_id"], result)
        if args.get("return_full_object"):
            return _ok(result)
        minimal = {
            "_id": result.get("_id"),
            "referenceId": result.get("referenceId"),
            "type": result.get("type"),
            "label": result.get("label"),
        }
        return _ok({k: v for k, v in minimal.items() if v is not None})
```

- [ ] **Step 4: Update `_cognigy_update` handler to return minimal by default**

At the end of `_cognigy_update`, replace:
```python
        cache.set(rtype, rid, result)
        return _ok(result)
```
with:
```python
        cache.set(rtype, rid, result)
        if args.get("return_full_object"):
            return _ok(result)
        minimal = {
            "_id": result.get("_id"),
            "type": result.get("type"),
            "label": result.get("label"),
        }
        return _ok({k: v for k, v in minimal.items() if v is not None})
```

- [ ] **Step 5: Run existing tests**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_flow_ops.py -v`
Expected: Tests may need updating if they assert on full objects — update them to use `return_full_object=True` where needed

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git commit -m "feat: slim cognigy_create/update responses to minimal {_id, type, label} by default"
```

---

### Task 2D: Field Projection

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — cognigy_get + cognigy_list Tool definitions + handlers

- [ ] **Step 1: Add `fields` parameter to `cognigy_get` Tool schema**

In `flow_ops.py`, in the `cognigy_get` Tool `inputSchema.properties`, add after `"flow_id"`:

```python
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: return only these keys. Example: fields=['_id','name'] reduces size by ~80%.",
                },
```

- [ ] **Step 2: Add `fields` parameter to `cognigy_list` Tool schema**

In the `cognigy_list` Tool `inputSchema.properties`, add after the new `"full_objects"` entry:

```python
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: return only these keys from each item. Applied after full_objects filter. Example: fields=['_id','name','description'].",
                },
```

- [ ] **Step 3: Update `_cognigy_get` handler for field projection**

After the cache/API fetch in `_cognigy_get`, add field filtering. Replace the last part:

```python
        cached, fresh = cache.get(rtype, rid)
        if fresh and cached:
            data = cached
            source = "cache"
        else:
            path = _resource_path(rtype, rid, flow_id)
            if path is None:
                return _ok({"error": "flow_id required when resource_type is 'node'"})
            data = client.get(path)
            cache.set(rtype, rid, data)
            source = "api"
        fields = args.get("fields")
        if fields:
            data = {k: data[k] for k in fields if k in data}
        return _ok({**data, "_source": source})
```

- [ ] **Step 4: Update `_cognigy_list` handler for field projection on full_objects mode**

In the `_cognigy_list` handler, add field projection after the simplified/full split:

```python
    if not full_objects:
        items = data.get("items", [])
        simplified = []
        for item in items:
            entry = {"id": item.get("_id"), "name": item.get("name")}
            if "description" in item:
                entry["description"] = item["description"]
            if "type" in item:
                entry["type"] = item["type"]
            simplified.append(entry)
        result_data = {"items": simplified, "count": len(simplified)}
    else:
        result_data = data
    fields = args.get("fields")
    if fields:
        items = result_data.get("items", [])
        filtered = [{k: item[k] for k in fields if k in item} for item in items]
        result_data = {"items": filtered, "count": len(filtered)}
    return _ok(result_data)
```

- [ ] **Step 5: Run existing tests**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_flow_ops.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git commit -m "feat: add fields parameter to cognigy_get and cognigy_list for token-efficient queries"
```

- [ ] **Step 7: Bump Phase 2 version**

Edit `cognigy-mcp/pyproject.toml`: change `version = "1.3.0"` to `version = "1.4.0"`
Edit `.claude-plugin/plugin.json`: change `"version": "1.3.0"` to `"version": "1.4.0"`

```bash
git add cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "chore: bump to 1.4.0 — Phase 2 token efficiency"
```

---

## Phase 3: Cleanup

### Task 3A: Remove `push_tool_from_file`

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/file_push.py`
- Modify: `cognigy-mcp/tests/tools/test_file_push.py`
- Modify: `cognigy-mcp/README.md`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Remove tool definition from TOOLS list in file_push.py**

Remove lines 39-52 in `file_push.py` — the entire `push_tool_from_file` Tool block (from `Tool(` through the closing `),`).

- [ ] **Step 2: Remove `_push_tool_from_file` handler function from file_push.py**

Remove lines 134-159 in `file_push.py` — the entire `_push_tool_from_file` function.

- [ ] **Step 3: Remove handler from make_handlers return dict**

In `file_push.py`, in the `make_handlers` function return dict (lines 161-165), remove:
```python
        "push_tool_from_file": _push_tool_from_file,
```

- [ ] **Step 4: Update test_all_tools_exported in test_file_push.py**

Remove line 11:
```python
    assert "push_tool_from_file" in names
```

- [ ] **Step 5: Remove push_tool_from_file tests from test_file_push.py**

Remove two test functions entirely:
- `test_push_tool_from_file_create` (lines 84-94)
- `test_push_tool_from_file_invalid_json` (lines 112-118)

- [ ] **Step 6: Run tests to confirm nothing broken**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_file_push.py -v`
Expected: All remaining tests pass

- [ ] **Step 7: Remove from README.md**

In `cognigy-mcp/README.md`, remove any reference to `push_tool_from_file`.

- [ ] **Step 8: Remove from architecture.md**

In `docs/architecture.md`, in the File push row of the Tools table (line 31), change:
```
| File push | `push_code_node`, `push_html_node`, `push_tool_from_file` |
```
to:
```
| File push | `push_code_node`, `push_html_node` |
```

- [ ] **Step 9: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/file_push.py cognigy-mcp/tests/tools/test_file_push.py cognigy-mcp/README.md docs/architecture.md
git commit -m "feat: remove hallucinated push_tool_from_file (API endpoint does not exist)"
```

---

### Task 3B: State Query Description

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/state_tools.py` — get_build_state Tool description only

- [ ] **Step 1: Update `get_build_state` description**

In `state_tools.py`, replace the current `get_build_state` description with:

```python
        description="Return the current .state.json — all known name to ID mappings. "
                    "Pass resource_type to scope the response and avoid context overflow on large projects. "
                    "Example: get_build_state(resource_type='flows') returns ~50 tokens vs ~500 for full state. "
                    "Filter values: flows, agents, endpoints, tools, nodes, jobs.",
```

- [ ] **Step 2: Verify tool still loads**

Run: `python3 -c "from cognigy_mcp.tools.state_tools import TOOLS; t = [x for x in TOOLS if x.name == 'get_build_state'][0]; print(t.description)"`
Expected: Updated description

- [ ] **Step 3: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/state_tools.py
git commit -m "docs: promote resource_type filtering in get_build_state description"
```

---

### Task 3C: Testing Response Filter

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/testing.py` — talk_to_agent Tool + handler

- [ ] **Step 1: Add `minimal` parameter to `talk_to_agent` Tool schema**

In `testing.py`, in the `talk_to_agent` Tool `inputSchema.properties`, add after `"user_id"`:

```python
                "minimal": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, returns only {outputText, sessionId} (~90% token savings). Default false returns full response.",
                },
```

- [ ] **Step 2: Update `_talk_to_agent` handler for minimal mode**

In `testing.py`, update the handler. Replace the return after `resp.raise_for_status()`:

```python
        try:
            resp = httpx.post(endpoint_url, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            if args.get("minimal"):
                session_info = data.get("data", {})
                return _ok({
                    "outputText": session_info.get("output", data.get("output", data.get("text", ""))),
                    "sessionId": session_id,
                })
            return _ok(data)
```

- [ ] **Step 3: Run existing tests if any**

Run: `cd cognigy-mcp && uv run pytest tests/ -v -k "talk_to_agent" 2>/dev/null || echo "No talk_to_agent tests yet"`
Expected: Nothing broken

- [ ] **Step 4: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/testing.py
git commit -m "feat: add minimal parameter to talk_to_agent for token-efficient responses"
```

---

### Task 3D: Error Message Improvements

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — mode validation in _cognigy_create and _cognigy_update

- [ ] **Step 1: Add mode validation to `_cognigy_create`**

In `flow_ops.py`, in `_cognigy_create`, add mode validation after the code node block (from 1C) and before the extension injection:

```python
            valid_modes = {"appendChild", "append", "insertAfter", "insertBefore"}
            if "mode" in body and body["mode"] not in valid_modes:
                return _ok({
                    "error": (
                        f'Invalid value for field "mode": "{body["mode"]}". '
                        f'Valid values: appendChild (add as child of container node), '
                        f'append (add as last sibling), '
                        f'insertAfter (insert after target sibling — BROKEN on AU1), '
                        f'insertBefore (insert before target sibling — BROKEN on AU1).'
                    )
                })
```

- [ ] **Step 2: Add mode validation to `_cognigy_update`**

In `_cognigy_update`, add the same validation when `"mode"` is in the body:

```python
            if "mode" in body:
                valid_modes = {"appendChild", "append", "insertAfter", "insertBefore"}
                if body["mode"] not in valid_modes:
                    return _ok({
                        "error": (
                            f'Invalid value for field "mode": "{body["mode"]}". '
                            f'Valid values: appendChild, append, insertAfter, insertBefore.'
                        )
                    })
```

Insert this right after the `if path is None: return _ok(...)` check.

- [ ] **Step 3: Run tests**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_flow_ops.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git commit -m "feat: add mode validation with clear error messages in cognigy_create/update"
```

- [ ] **Step 5: Bump Phase 3 version**

Edit `cognigy-mcp/pyproject.toml`: change `version = "1.4.0"` to `version = "1.5.0"`
Edit `.claude-plugin/plugin.json`: change `"version": "1.4.0"` to `"version": "1.5.0"`

```bash
git add cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "chore: bump to 1.5.0 — Phase 3 cleanup"
```

---

## Post-Implementation Verification

- [ ] Run all tests: `cd cognigy-mcp && uv run pytest tests/ -v`
- [ ] Verify hook JSON is valid: `python3 -m json.tool hooks/hooks.json`
- [ ] Verify hook script outputs valid JSON: `echo '{"tool_name":"mcp__cognigy-vibe__cognigy_get","session_id":"test"}' | bash hooks/onboarding-gate.sh | python3 -m json.tool`
- [ ] Verify explain() lists the new topic: `python3 -c "from cognigy_mcp.tools.explain import TOPICS; print('tool-selection' in TOPICS)"`
- [ ] Verify import works end-to-end: `python3 -c "from cognigy_mcp.tools import flow_ops, explain, state_tools, testing, file_push; print('OK')"`