# Cognigy MCP Uplift Plan — Design Spec

**Date:** 2026-06-12
**Source:** docs/exploratory-testing-report.md
**Version:** 1.1

## Overview

Three-phase uplift addressing the 12 critical/high/medium issues identified in exploratory testing. Phase 1 unblocks implementation and onboarding. Phase 2 eliminates 60-80% token waste. Phase 3 cleans up naming, error messages, and remaining rough edges.

---

## Phase 1: Usability & Unblocking

### 1A. PreToolUse Onboarding Gate

**Problem:** Fresh sessions have no architectural mental model, causing 10-15 minutes of confusion before understanding the system.

**Solution:** A plugin-installed PreToolUse hook that catches the first Cognigy MCP tool call in any fresh session and denies it with an injected primer.

**Files to create/modify:**
- **NEW** `hooks/hooks.json` — hook configuration
- **NEW** `hooks/onboarding-gate.sh` — hook script

**Hook configuration** in `hooks/hooks.json`:

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

**Script (`hooks/onboarding-gate.sh`):**
1. Read stdin — extract `tool_name`, `session_id`
2. If `tool_name` contains `explain` → exit 0 (user self-educating, let it pass)
3. Check flag file `/tmp/.cognigy-primer-${session_id}` — if exists → exit 0 (already shown this session)
4. Create flag file: `touch /tmp/.cognigy-primer-${session_id}`
5. Emit via stdout:
   ```json
   {
     "hookSpecificOutput": {
       "permissionDecision": "deny",
       "permissionDecisionReason": "First Cognigy session — loading architectural primer. Re-attempt your tool call.",
       "additionalContext": "COGNIGY ARCHITECTURAL PRIMER: This is a visual flow builder exposed as code. The hierarchy is Projects > Flows > Nodes > AI Agents > Tools. Flows are canvases with connected nodes (Say, Code, Once, HTTP Request, AI Agent Job). AI Agent Job nodes reference AI Agents which may have Tools attached. Key concepts: use cognigy_get/cognigy_create/cognigy_update by resource ID; use resolve_resource to look up IDs by friendly name; use get_flow_chart to see the full node tree; use explain(\"topic\") for detailed guidance on specific patterns. Call explain() with no arguments to see all available topics."
     }
   }
   ```
6. Exit 0 (permissionDecision: "deny" blocks the call; on retry, the primer is already in context so Claude will proceed informed)

---

### 1B. Child Branch Population Documentation

**Problem:** Once nodes auto-create `OnFirstTime` and `Afterwards` children but there is no documented API pattern for populating them. This is a complete implementation blocker for turn structure.

**Files to modify:**
- `cognigy-mcp/cognigy_mcp/tools/explain.py` — update two existing topics and index

**`explain("turn-structure")`** content to add:
- Once nodes auto-create two child branches: `OnFirstTime` (referenceId: the first-time branch) and `Afterwards` (referenceId: the subsequent-visits branch)
- Each branch appears as a child node in the chart with its own `_id` and `referenceId`
- To add a node into a branch: create the node with `mode: "appendChild"` and `target` set to the **branch node's `_id`** (not the parent Once node)
- Important: the branch node is the container — target that, not the parent Once node
- Full example of adding a Code node to `OnFirstTime`:
  1. `get_flow_chart(flow_id)` to find the Once node and its `OnFirstTime` child branch node
  2. Get the branch node's `_id`
  3. `cognigy_create(resource_type="node", body={"type": "code", "mode": "appendChild", "target": "<branch-node-id>", "flowId": "<flow-id>", "config": {"code": "..."}, "label": "Load Guest Profile"})`
- Attempting to manually create child branches returns HTTP 400 — they are auto-created, not user-created

**`explain("node-positioning")`** content to add:
- `appendChild` is used to add nodes inside a parent container (Once branch, Tool branch, etc.)
- The `target` for `appendChild` must be the container node's `_id`, not the logical parent
- For Once nodes specifically: find the `OnFirstTime` or `Afterwards` child in the chart, use its `_id` as target
- Common pitfall: using the Once node's `_id` as target for `appendChild` — this targets the Once node itself, not its child branch

---

### 1C. Tool Selection Documentation + Code Node Block

**Problem:** Agents are confused about when to use `push_code_node` vs `cognigy_create`. The now-removed `push_tool_from_file` added further confusion.

**Files to modify:**
- `cognigy-mcp/cognigy_mcp/tools/explain.py` — new topic entry
- `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — block logic in `_cognigy_create` handler

**New `explain("tool-selection")`** topic (add to `TOPICS` list, `_TOPIC_INDEX`, and `_CONTENT`):
Decision tree:
- "Creating a Code node from a local .js/.ts file?" → `push_code_node` (provides conflict detection against Cognigy UI edits)
- "Creating any other node (Say, Once, HTTP Request, AI Agent Job, etc.)?" → `cognigy_create`
- "Creating an HTML/xApp node from a local .html file?" → `push_html_node` (sets mode='full' automatically)
- "Updating an existing node's config?" → `cognigy_update` with `merge_config=true`
- "Reading a node or resource?" → `cognigy_get`

Additional clarifications:
- `push_code_node` and `push_html_node` are the ONLY tools for file-backed content; they provide conflict detection
- `cognigy_create` is for non-file-backed node creation
- Code nodes MUST go through `push_code_node` — `cognigy_create` will reject `type: "code"`

**Dual protection in `_cognigy_create` handler** (`flow_ops.py`):
- When `resource_type` is `"node"` and `body.type` is `"code"`, return an error:
  ```
  Code nodes must be created via push_code_node (provides file-backed conflict detection).
  Use push_code_node for .js/.ts files or inline code pushed from a file.
  See explain("tool-selection") for guidance.
  ```
- This block prevents agents from using the wrong tool and getting no conflict detection
- All other node types proceed normally

---

### 1D. Mode Values Documentation

**Problem:** `cognigy_create` requires a `mode` field but valid values are undocumented — agents get multiple 400 errors through trial and error.

**Files to modify:**
- `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — update `cognigy_create` Tool description

**Updated `cognigy_create` tool description** — add to existing description:
```
For nodes, body must include flowId, type, mode, and target.
- type: node type string ("say", "code", "once", "httpRequest", "aiAgentJob", etc.)
- mode: one of:
  - "appendChild" — add as child of the target container node (e.g. inside a Once node's OnFirstTime branch, or a tool container)
  - "append" — add as last sibling after the target node at the same level
  - "insertAfter" — insert after a specific sibling node (BROKEN on AU1, returns HTTP 500)
  - "insertBefore" — insert before a specific sibling node (BROKEN on AU1, returns HTTP 500)
- target: the _id of the reference node (container for appendChild, sibling for append/insertAfter/insertBefore)
- flowId: always set to the flow _id
```

---

## Phase 2: Token Efficiency

All Phase 2 changes follow the same pattern:
1. Change default response to minimal/simplified
2. Add an explicit opt-in parameter for the full response (preserving backward compatibility)
3. Update tool description with examples showing token savings

All code changes are in `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` unless noted.

### 2A. List Response Optimization

**Problem:** `cognigy_list` returns complete objects (~2000 tokens for 30 flows) when only names and IDs are needed (~50 tokens). 40x overhead.

**Changes:**
- Default response format: `{"items": [{"id": "flow-1", "name": "Main Flow"}, ...], "count": 30}`
- New parameter in Tool schema: `full_objects` (boolean, default false)
- When `full_objects=true`: return full current response
- Handler (`flow_ops.py`): after fetching from API, if not `full_objects`, strip each item to `{"id": item["_id"], "name": item["name"]}` plus keep any additional common fields (`description`, `type`) if present
- Update tool description: `Default returns simplified {id, name} pairs (~95% token savings). Use full_objects=true for complete objects.`

### 2B. Chart Response Format Options

**Problem:** `get_flow_chart` returns both raw relations AND hierarchy string (~3000 tokens) when only one format is usually needed (~100 tokens). 30x overhead.

**Changes:**
- New `format` parameter in Tool schema: enum `["hierarchy", "raw", "both"]`, default `"hierarchy"`
- `"hierarchy"` — just the human-readable tree string (default, ~95% token savings)
- `"raw"` — just the `nodes` and `relations` arrays as structured JSON
- `"both"` — current behavior (explicit opt-in)
- Handler (`flow_ops.py`): in `_get_flow_chart`, wrap response based on `format` parameter
- Update tool description with format options and token savings

### 2C. Create Response Slimming

**Problem:** `cognigy_create` returns the complete created object (~200 tokens) when only the ID is needed for chaining (~20 tokens). 10x overhead.

**Changes:**
- New parameter in Tool schema: `return_full_object` (boolean, default false)
- Default response: `{"_id": "node-123", "referenceId": "...", "type": "code", "label": "My Node"}`
- When `return_full_object=true`: return complete API response (current behavior)
- Handler (`flow_ops.py`): after successful create, extract minimal fields from the response unless `return_full_object` is set
- Also apply to `cognigy_update` handler for consistency (same parameter, same behavior)
- Update tool descriptions with examples

### 2D. Field Projection

**Problem:** All get operations return complete objects when only specific fields are needed (5-13x overhead).

**Changes:**
- New `fields` parameter in `cognigy_get` Tool schema: array of strings, optional
- `cognigy_get(resource_type="node", resource_id="x", fields=["_id", "type", "label"])` returns only specified keys
- When `fields` is omitted: return full object (current behavior — no breaking change)
- Handler (`flow_ops.py`): after cache read or API fetch, filter response to `fields` keys if provided
- Also add `fields` parameter to `cognigy_list` Tool schema (same semantics, applied after full_objects filter if both are set)
- Update tool descriptions:
  ```
  Use fields=['_id','name'] to reduce response size by ~80%.
  Example: cognigy_get(resource_type="flow", resource_id="flow-1", fields=["_id", "name"])
  ```

---

## Phase 3: Cleanup

### 3A. Remove `push_tool_from_file`

**Problem:** The tool definition targets a hallucinated API endpoint (`POST /v2.0/projects/{project_id}/tools`) that does not exist. It is non-functional.

**Files to modify:**
- `cognigy-mcp/cognigy_mcp/tools/file_push.py` — remove `push_tool_from_file` from TOOLS list; remove `_push_tool_from_file` handler function; remove handler from `make_handlers()` return dict
- `cognigy-mcp/tests/tools/test_file_push.py` — remove `test_push_tool_from_file_create`, `test_push_tool_from_file_invalid_json` tests; update `test_all_tools_exported` to remove assertion for `push_tool_from_file`
- `cognigy-mcp/README.md` — remove from tool list
- `docs/architecture.md` — remove File push entry for push_tool_from_file

Note: `push_code_node` and `push_html_node` remain fully functional and unchanged.

### 3B. State Query Description

**Problem:** `get_build_state` supports `resource_type` filtering but the parameter is underutilized because it passes without friction.

**Files to modify:**
- `cognigy-mcp/cognigy_mcp/tools/state_tools.py` — update `get_build_state` Tool description only

**Change:** Update tool description to lead with filtered use:
```
Return the current .state.json — all known name to ID mappings.
Pass resource_type to scope the response and avoid context overflow on large projects.
Example: get_build_state(resource_type="flows") returns ~50 tokens vs ~500 for full state.
Filter values: flows, agents, endpoints, tools, nodes, jobs.
```
No handler code changes needed — filtering already works.

### 3C. Testing Response Filter

**Problem:** `talk_to_agent` returns complete response when only output text is needed (10x overhead).

**Files to modify:**
- `cognigy-mcp/cognigy_mcp/tools/testing.py` — add parameter to Tool schema; update handler

**Changes:**
- New parameter in Tool schema: `minimal` (boolean, default false)
- When `minimal=true`: return `{"outputText": "...", "sessionId": "..."}`
  - Extract output text from `resp.json()` — path depends on Cognigy response shape; extract `data.output` or equivalent
- When `minimal=false`: return current full response (no breaking change)
- Update tool description:
  ```
  Use minimal=true for token-efficient testing (~90% savings).
  Example: talk_to_agent(message="hello", minimal=true, ...)
  ```

### 3D. Error Message Improvements

**Problem:** Invalid mode values result in "Invalid value for field 'mode'" with no guidance on valid values.

**Files to modify:**
- `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` — add validation in create/update handlers

**Changes:**
- In `_cognigy_create` handler: if `resource_type` is `"node"` and `body.mode` is present but not in `["appendChild", "append", "insertAfter", "insertBefore"]`, return:
  ```
  Invalid value for field 'mode': "<received value>".
  Valid values: appendChild (add as child of container node), append (add as last sibling),
  insertAfter (insert after target sibling — BROKEN on AU1), insertBefore (insert before target sibling — BROKEN on AU1).
  ```
- Denied mode values still produce a clear error instead of a generic 400
- Also handle the Code node block from 1C as a separate check before the mode validation (order: first check for code type, then validate mode)
- Apply same mode validation in `_cognigy_update` handler when updating node configs that include a mode field

---

## Implementation Order

```
Phase 1                         Phase 2                    Phase 3
├── 1A PreToolUse hook          ├── 2A List optimization   ├── 3A Remove push_tool_from_file
├── 1B Child branch docs        ├── 2B Chart format        ├── 3B State query description
├── 1C Tool selection + block   ├── 2C Create/update slim  ├── 3C Testing response filter
├── 1D Mode values docs          ├── 2D Field projection    └── 3D Error messages
└── ──                          └── ──                    └── ──
  4 independent items            4 items (quick wins 1st)   4 independent items
```

Within each phase, items are independent unless noted. Phase 1 ships first, then Phase 2, then Phase 3. Items within a phase can be parallelized.

## Files Changed Summary

| Phase | File | Items |
|-------|------|-------|
| 1A | `hooks/hooks.json` (NEW) | Onboarding hook config |
| 1A | `hooks/onboarding-gate.sh` (NEW) | Onboarding hook script |
| 1B | `cognigy-mcp/cognigy_mcp/tools/explain.py` | turn-structure + node-positioning updates |
| 1C | `cognigy-mcp/cognigy_mcp/tools/explain.py` | New tool-selection topic |
| 1C | `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` | Code node block in `_cognigy_create` |
| 1D | `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` | cognigy_create description update |
| 2A-2D | `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` | All token efficiency changes |
| 3A | `cognigy-mcp/cognigy_mcp/tools/file_push.py` | Remove push_tool_from_file |
| 3A | `cognigy-mcp/tests/tools/test_file_push.py` | Remove related tests |
| 3A | `cognigy-mcp/README.md`, `docs/architecture.md` | Remove references |
| 3B | `cognigy-mcp/cognigy_mcp/tools/state_tools.py` | Description update only |
| 3C | `cognigy-mcp/cognigy_mcp/tools/testing.py` | minimal parameter |
| 3D | `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` | Mode validation + error messages |

## Version Strategy

Three releases:
- **Phase 1**: 1.3.0 (new feature: onboarding hook + explain topics)
- **Phase 2**: 1.4.0 (breaking-ish: list/chart/create defaults change)
- **Phase 3**: 1.5.0 (removal: push_tool_from_file deleted)

All versions incremented in `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json`.