# Cognigy MCP Uplift Plan — Design Spec

**Date:** 2026-06-12
**Source:** docs/exploratory-testing-report.md
**Version:** 1.0

## Overview

Three-phase uplift addressing the 12 critical/high/medium issues identified in exploratory testing. Phase 1 unblocks implementation and onboarding. Phase 2 eliminates 60-80% token waste. Phase 3 cleans up naming, error messages, and remaining rough edges.

---

## Phase 1: Usability & Unblocking

### 1A. PreToolUse Onboarding Gate

**Problem:** Fresh sessions have no architectural mental model, causing 10-15 minutes of confusion before understanding the system.

**Solution:** A plugin-installed PreToolUse hook that catches the first Cognigy MCP tool call in any fresh session and injects a primer.

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
2. If `tool_name` contains `explain` → exit 0 (user self-educating)
3. Check flag file `/tmp/.cognigy-primer-${session_id}` — if exists → exit 0 (already shown)
4. Create flag file
5. Emit via stdout:
   ```json
   {
     "hookSpecificOutput": {
       "permissionDecision": "deny",
       "permissionDecisionReason": "First Cognigy session — loading architectural primer...",
       "additionalContext": "This is a visual flow builder exposed as code. The hierarchy is: Projects → Flows → Nodes → AI Agents → Tools. Flows are canvases with connected nodes (Say, Code, Once, HTTP Request). AI Agent Job nodes reference AI Agents that use Tools. Use cognigy_get/cognigy_create/cognigy_update by resource ID. resolve_resource looks up IDs by name. get_flow_chart shows the node tree. explain(\"topic\") provides detailed guidance."
     }
   }
   ```
6. Exit 0 (tool is denied via permissionDecision, so the call is blocked)

**Files to create:**
- `hooks/hooks.json` — hook config
- `hooks/onboarding-gate.sh` — hook script

---

### 1B. Child Branch Population Documentation

**Problem:** Once nodes auto-create `OnFirstTime` and `Afterwards` children but there is no documented API pattern for populating them. This is a complete implementation blocker for turn structure.

**Solution:** Document in existing explain topics.

**`explain("turn-structure")`** — add:
- Once nodes auto-create two child branches: `OnFirstTime` and `Afterwards`
- Each branch is a child node with a specific `referenceId`
- Use `mode: "appendChild"` when creating nodes under a branch
- The `target` parameter must be the parent node's `_id`
- Example: creating a Code node under `OnFirstTime`:
  ```json
  {
    "type": "code",
    "mode": "appendChild",
    "target": "<parent-once-node-id>",
    "config": {"code": "..."},
    "label": "Load Guest Profile"
  }
  ```

**`explain("node-positioning")`** — add:
- Child branch population patterns
- `appendChild` vs `append` vs `insertAfter` vs `insertBefore`
- How to reference child branches by `referenceId`

---

### 1C. Tool Selection Documentation + Dual Protection

**Problem:** Agents are confused about when to use `push_code_node` vs `cognigy_create` vs `push_tool_from_file`.

**Solution:** New explain topic + blocking protection in `cognigy_create`.

**New `explain("tool-selection")`** decision tree:
- "Creating a Code node from a local .js/.ts file?" → `push_code_node` (provides conflict detection)
- "Creating a Code node with inline code?" → `cognigy_create` with type `code`
- "Creating a Say node or other standard node?" → `cognigy_create`
- "Creating an HTML/xApp node?" → `push_html_node` (sets mode='full' automatically)
- "Adding a tool to an AI Agent?" → this is done through the AI Agent Job node, not a separate tool

**Dual protection in `cognigy_create` handler:**
- If `body.type` matches a Code node type (e.g. `"code"`), block with:
  ```
  Use push_code_node for Code nodes backed by local files (provides conflict detection).
  Use cognigy_create with type="code" for inline code without conflict detection.
  See explain("tool-selection").
  ```
- All other node types proceed normally.

---

### 1D. Mode Values Documentation

**Problem:** `cognigy_create` requires a `mode` field but valid values are undocumented — agents get multiple 400 errors through trial and error.

**Solution:** Update `cognigy_create` tool description.

**Updated description** (add to existing):
```
Required fields for node creation:
- type: the node type (e.g. "say", "code", "once", "httpRequest", "aiAgentJob")
- mode: one of the following:
  - "appendChild" — add as child of the target parent node (e.g. inside a Once node's branch)
  - "append" — add as last sibling in the parent flow/container
  - "insertAfter" — insert after a specific target node at the same level
  - "insertBefore" — insert before a specific target node at the same level
- target: the _id of the reference node (parent for appendChild, sibling for insertAfter/Before)
- flowId: always set to the flow _id
```

---

## Phase 2: Token Efficiency

All Phase 2 changes follow the same pattern:
1. Change default response to minimal/simplified
2. Add an explicit opt-in parameter for the full response
3. Update tool description with examples showing token savings

### 2A. List Response Optimization

**Problem:** `cognigy_list` returns complete objects (~2000 tokens for 30 flows) when only names and IDs are needed (~50 tokens). 40x overhead.

**Change in `flow_ops.py`:**
- Default response format:
  ```json
  {"items": [{"id": "flow-1", "name": "Main Flow"}, ...], "count": 30}
  ```
- New parameter: `cognigy_list(..., full_objects=True)` returns current full-object behavior
- Tool description updated with example:
  ```
  Use fields=['id','name'] (via future field projection) or full_objects=True for complete objects.
  Default simplified response saves ~95% tokens on discovery operations.
  ```

### 2B. Chart Response Format Options

**Problem:** `get_flow_chart` returns both raw relations AND hierarchy string (~3000 tokens) when only one format is usually needed (~100 tokens). 30x overhead.

**Change in `flow_ops.py`:**
- New `format` parameter:
  - `format="hierarchy"` (default) — just the human-readable tree string
  - `format="raw"` — just the raw relations + nodes arrays
  - `format="both"` — current behavior (both)
- Tool description updated with examples

### 2C. Create Response Slimming

**Problem:** `cognigy_create` returns the complete created object (~200 tokens) when only the ID is needed for chaining (~20 tokens). 10x overhead.

**Change in `flow_ops.py`:**
- Default response:
  ```json
  {"_id": "node-123", "referenceId": "...", "type": "code", "label": "My Node"}
  ```
- New parameter: `cognigy_create(..., return_full_object=True)` returns complete object
- Tool description updated with example

### 2D. Field Projection

**Problem:** All get operations return complete objects when only specific fields are needed (5-13x overhead).

**Change in `flow_ops.py` `cognigy_get` handler:**
- New `fields` parameter: `cognigy_get(resource_type="node", resource_id="x", fields=["_id", "type", "label"])`
- When `fields` is provided, filter the response to only those keys
- When omitted, return full object (current behavior — no breaking change)
- Tool description updated:
  ```
  Use fields=['_id','name'] to reduce response size by ~80%.
  Example: cognigy_get(resource_type="flow", resource_id="flow-1", fields=["_id", "name"])
  ```

---

## Phase 3: Cleanup

### 3A. Remove `push_tool_from_file`

**Problem:** The tool definition was built around a hallucinated API endpoint (`POST /v2.0/projects/{project_id}/tools`) that does not exist. It is non-functional.

**Changes:**
- Remove tool definition and `_push_tool_from_file` handler from `file_push.py`
- Remove `test_file_push.py` entirely (the only test was for this tool)
- Remove reference from `README.md` and `architecture.md`
- Bump version

### 3B. State Query Description

**Problem:** `get_build_state` supports `resource_type` filtering but the parameter is underutilized because it's not well-documented.

**Change:**
- Update `get_build_state` tool description to lead with the filtered use case:
  ```
  Returns name→ID mappings. Pass resource_type to scope the response and avoid context overflow on large projects.
  Example: get_build_state(resource_type="flows") — returns just flows mapping (~50 tokens vs ~500 for full state).
  ```
- No code changes needed — parameter already exists.

### 3C. Testing Response Filter

**Problem:** `talk_to_agent` returns complete response when only output text is needed (10x overhead).

**Change in `testing.py`:**
- New parameter: `talk_to_agent(..., minimal=True)`
- When `minimal=True`, returns:
  ```json
  {"outputText": "...", "sessionId": "..."}
  ```
- When `minimal=False` (default), returns current full response (no breaking change)
- Tool description updated with example

### 3D. Error Message Improvements

**Problem:** Invalid mode values result in "Invalid value for field 'mode'" with no guidance on valid values.

**Change in `cognigy_mcp/api.py` (error handling):**
- In the PATCH/POST error handler, check if the response body contains `"mode"` in the error message text
- If detected, rewrite error message:
  ```
  "Invalid value for field 'mode'. Valid values: append, appendChild, insertAfter, insertBefore. appendChild adds a child node to a parent branch. append adds as last sibling. insertAfter/insertBefore insert relative to a target node."
  ```
- Catch 400 errors related to other common fields with similar keyword-based detection
- Add the Code node block (see 1C): any POST/PATCH on a `node` resource where `body.type` is `"code"` is blocked with the redirect message

**Code node type detection rule:**
- `body.type === "code"` triggers the block
- Only applies when `resource_type` is `"node"` (not other resource types that happen to have `type: "code"`)

---

## Implementation Order

```
Phase 1                         Phase 2                    Phase 3
├── 1A PreToolUse hook          ├── 2A List optimization   ├── 3A Remove push_tool_from_file
├── 1B Child branch docs        ├── 2B Chart format        ├── 3B State query description
├── 1C Tool selection + block   ├── 2C Create slimming     ├── 3C Testing response filter
├── 1D Mode values docs         ├── 2D Field projection    └── 3D Error messages
└── ──                          └── ──                    └── ──
  4 independent items            4 items (quick wins 1st)   4 independent items
```

Within each phase, items are independent unless noted. Phase 1 as a whole should ship first, then Phase 2, then Phase 3 — but items within a phase can be parallelized.

## Version Strategy

Three releases:
- **Phase 1**: 1.3.0 (new feature: onboarding hook + docs)
- **Phase 2**: 1.4.0 (breaking-ish: list default changes)
- **Phase 3**: 1.5.0 (breaking-ish: tool removal)

All versions incremented in `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json`.