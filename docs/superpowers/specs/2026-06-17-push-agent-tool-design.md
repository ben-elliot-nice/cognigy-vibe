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
       "parameters": "<json.dumps(parameters) or omitted>",
       "debugMessage": true,
       "condition": "<condition or empty string>"
     }
   }
   ```
   **Validated:** `parameters` must be serialized to a JSON string before sending — API stores and expects a string, not an object.
   **Validated:** `condition` lives inside `config`, not top-level. API returns HTTP 400 if sent as a top-level field.
   **Validated:** `debugMessage: true` should always be sent explicitly.
4. Save `{id, flowId}` to state keyed by `toolId`
5. Return `{success: true, node_id: <_id>, created: true}`

### Update Mode

1. Read and parse `tool_file`
2. Derive `useParameters`, serialize `parameters` to JSON string
3. `PATCH /v2.0/flows/{flow_id}/chart/nodes/{node_id}` with full config from file

   **Validated:** PATCH on `aiAgentJobTool` is additive on `config` — omitted fields are preserved. Sending full file config is safe and authoritative. `merge_config` is not needed.

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

### `tool-conditions.md`

**Correction required.** Current topic incorrectly states `condition` is a top-level node field. Validated via live API: `condition` must be inside `config`. Top-level `condition` returns HTTP 400. Update all examples to use `config.condition`.

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

## 4. Live API Tests — Results

All tests run against "Tool Selection Test" flow and "Sammy — Guest Services" flow (AU1). UI-verified by user.

**Test 1 — Bare minimum create: ✅ PASSED**
`toolId` + `description` + `useParameters: false` is sufficient. API auto-sets `debugMessage: true` and `condition: ""`. `parameters` field appears even when not sent (API fills with a default string) but is inert when `useParameters: false`.

**Test 2 — Full create with parameters: ✅ PASSED**
All fields accepted. `parameters` as a JSON string round-tripped correctly. `condition` stored inside `config` and visible in UI as expected. Both `account_id` and `amount` parameters appeared correctly in the UI.

**Test 3 — PATCH is additive on config: ✅ PASSED**
Sending only `{"config": {"description": "..."}}` left all other config fields intact. PATCH on `aiAgentJobTool` merges config — it is NOT full-replace. `merge_config` flag is irrelevant for this node type.

**Test 4 — `condition` is inside `config`, not top-level: ✅ PASSED**
`{"condition": "..."}` at the top-level body returns HTTP 400: "Field 'condition' is not allowed." `{"config": {"condition": "..."}}` accepted and visible in UI. `tool-conditions.md` is incorrect and must be fixed.

**Test 5 — `add-aiagent-job` skill alignment:**
Skill creates `aiAgentJobTool` inline in POST body — confirmed equivalent to the tested create path. Skill does not pass `debugMessage: true` explicitly (API sets it anyway). Skill should be updated to use `push_agent_tool` once available.
