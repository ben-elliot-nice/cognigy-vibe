# push_agent_tool — Design Spec

**Date:** 2026-06-17
**Status:** Approved

## Problem

Creating an AI Agent tool branch today requires 4 manual MCP calls: create `aiAgentJobTool` node, update its config, append a code node, append `aiAgentToolAnswer`. The tool definition config (toolId, description, parameters) is produced generatively inline each time — no local file, no surgical edits, no version history.

## Scope

This spec covers:
1. New MCP tool: `push_agent_tool`
2. Blocker in `cognigy_create` for `aiAgentJobTool` type
3. Explain topic updates to align guidance to the new path
4. Live API tests to verify the exact config shape before implementation

Out of scope: `aiAgentToolAnswer` creation (handled by existing patterns), code node creation (handled by `push_code_node`).

---

## 1. `push_agent_tool` MCP Tool

### Pattern

Single tool, two modes — matching `push_code_node`:
- **Create** (`node_id` absent): reads local JSON file → `POST` new `aiAgentJobTool` node as child of a given `aiAgentJob` node
- **Update** (`node_id` present): reads local JSON file → `PATCH` existing `aiAgentJobTool` node config

### Local JSON Convention

File path is caller-supplied (absolute path, any name). Convention: `.tool.json` suffix.

```json
{
  "toolId": "check_balance",
  "label": "Check Balance",
  "description": "Use this tool when the customer asks about their account balance. Expects account_type. Returns current balance and currency.",
  "parameters": {
    "type": "object",
    "properties": {
      "account_type": {
        "type": "string",
        "description": "The account type to check (savings or current)"
      }
    },
    "required": ["account_type"],
    "additionalProperties": false
  },
  "condition": "context.authVerified"
}
```

**Field reference:**

| Field | Required | Notes |
|---|---|---|
| `toolId` | yes | Snake_case identifier used by the LLM |
| `description` | yes | LLM-facing description — use "Use this tool when..." format |
| `label` | no | Display name in Cognigy UI. Defaults to `toolId` if omitted |
| `parameters` | no | Full JSON Schema object. Omit for parameter-free tools |
| `condition` | no | CognigyScript expression. Omit to always show tool to LLM |

`useParameters` is **auto-derived**: `true` when `parameters` is present and non-empty, `false` otherwise. Never written explicitly in the JSON file.

`parameters` uses standard JSON Schema — LLMs produce this natively (same format as MCP tool definitions and OpenAPI specs). No translation layer; passed verbatim to the Cognigy API.

### MCP Tool Inputs

| Field | Required | Notes |
|---|---|---|
| `tool_file` | always | Absolute path to `.tool.json` |
| `flow_id` | always | Flow containing the node |
| `job_node_id` | create only | `_id` of the parent `aiAgentJob` node |
| `node_id` | update only | `_id` of the existing `aiAgentJobTool` node |

### Create Mode

1. Read and parse `tool_file`
2. Derive `useParameters` from presence of `parameters`
3. `POST /v2.0/flows/{flow_id}/chart/nodes`:
   ```json
   {
     "type": "aiAgentJobTool",
     "extension": "@cognigy/basic-nodes",
     "label": "<label or toolId>",
     "mode": "appendChild",
     "target": "<job_node_id>",
     "config": {
       "toolId": "<toolId>",
       "description": "<description>",
       "useParameters": <bool>,
       "parameters": <parameters or omitted>
     }
   }
   ```
4. Save `{id, flowId}` to state keyed by `toolId`
5. Return `{success: true, node_id: <_id>, created: true}`

If `condition` is present, include it as a top-level field in the POST body alongside `config`. If the API rejects top-level fields on POST, fall back to a follow-up PATCH. API Test 4 resolves which path is correct.

### Update Mode

1. Read and parse `tool_file`
2. Derive `useParameters`
3. `PATCH /v2.0/flows/{flow_id}/chart/nodes/{node_id}` with updated config
4. If `condition` present in file, patch it as a top-level field in the same call

No conflict detection on update — tool config is the file of record. (Code body conflict detection remains `push_code_node`'s responsibility.)

### Error cases

- File not found → error with path
- Missing required fields (`toolId`, `description`) → error listing missing fields
- `job_node_id` absent in create mode → error
- `flow_id` absent → error
- API error → surface status + message

---

## 2. Blocker in `cognigy_create`

Add a guard for `aiAgentJobTool` type matching the existing code node guard:

```
"AI Agent tool nodes must be created via push_agent_tool
(file-backed, maps .tool.json spec to Cognigy config).
To create a new tool: push_agent_tool(tool_file=..., flow_id=..., job_node_id=...)
See explain('tool-selection') for guidance."
```

---

## 3. Explain Topic Updates

### `tool-selection.md`

Add to decision tree:
- "Creating or updating an AI Agent tool definition?" → `push_agent_tool`

Remove stale `push_tool_from_file` note; replace with pointer to `push_agent_tool`.

### `agent-tool-branch.md`

Rewrite Steps 1–2 to use `push_agent_tool` instead of the raw `cognigy_create` + `cognigy_update` pair. The topic becomes the canonical end-to-end sequence:

```
push_agent_tool   → creates aiAgentJobTool node
push_code_node    → creates/updates code node (append after tool node)
cognigy_create    → creates aiAgentToolAnswer (append after code node)
```

Steps 3–4 (code node + toolAnswer) remain unchanged.

### New topic: `agent-tool-json.md`

Documents the `.tool.json` convention: all fields, required vs optional, the JSON Schema shape for `parameters`, `condition` semantics, and a complete example. This is the reference an LLM reads before writing or editing a `.tool.json` file.

### Ensure full tool branch sequence is covered end-to-end

The explain topics must collectively document the complete sequence from `push_agent_tool` through to `aiAgentToolAnswer` so agents can resolve the full creation path without gaps. Audit all aiagent-group topics after implementation and fill any missing links.

---

## 4. Live API Tests

Run before implementation to verify exact config shape. Results feed into: the `.tool.json` schema definition, `push_agent_tool` mapping logic, and any corrections to `agent-tool-branch.md`.

**Test 1 — Bare minimum create:** `aiAgentJobTool` with only `toolId` and `description`, no `parameters`, no `condition`. Confirms truly required fields.

**Test 2 — Full create with parameters:** `aiAgentJobTool` with all fields including full JSON Schema `parameters` and a `condition`. Confirms accepted shape and storage format.

**Test 3 — PATCH behaviour:** patch an existing `aiAgentJobTool` — change description, add/remove a parameter. Confirms whether PATCH is full-replace on `config` (requiring careful handling) or additive.

**Test 4 — `condition` as top-level field:** confirm `condition` is patched at the node root, not inside `config`. Verify it is correctly excluded from the LLM when falsy.

**Test 5 — `add-aiagent-job` skill alignment:** the skill currently creates `aiAgentJobTool` with config inline in the create body. Confirm this is equivalent to create-then-patch, and flag whether the skill should be updated to use `push_agent_tool` once available.
