---
name: scaffold-aiagent
description: Add an AI Agent Job node (and optional tool nodes) to an existing Cognigy flow — resolves the AI Agent and insertion point, then creates all nodes via atomic skills. Use when a flow already exists and you need to add an AI Agent Job with its tools.
---

# Scaffold AI Agent Job

Add an AI Agent Job node to an existing Cognigy flow and attach tool nodes to it.

## Assumptions

- The flow already exists. Do not create it — if not found, stop and tell the user.
- The AI Agent already exists. If not found, stop and tell the user.

---

## Step 1: Resolve the Flow

Ask: "Which flow should the AI Agent Job node be added to? You can give a name or ID."

If the user gives a name (not a 24-char hex ID), invoke `cognigy:list` for `flow` to find it.
- If exactly one match → use it.
- If multiple matches → show them and ask the user to choose.
- If no match → stop. Tell the user the flow was not found.

Capture: `flowId`

---

## Step 2: Resolve the AI Agent

Ask: "Which AI Agent should back this job? You can give a name or ID."

If the user gives a name, invoke `cognigy:list` for `ai-agent` to find it. (Project scoping comes from `.env` — there is no `--projectId` flag for list.)
- If exactly one match → use it.
- If multiple matches → show them and ask the user to choose.
- If no match → stop. Tell the user the agent was not found.

Capture the agent's **`referenceId`** field (UUID format, e.g. `d484bc76-6d77-487f-b97e-6d18f728c232`).
Do NOT use `_id` — the `aiAgent` config field requires the `referenceId`.

Capture: `agentReferenceId`, `agentName`

---

## Step 3: Gather Job Details

Ask in a single prompt:

1. **Job label** — display name for the node (e.g. "Renewals Specialist")
2. **Job description** — what this specialist handles (1-2 sentences; leave blank if not needed)
3. **Job instructions** — standing guidance for this job (leave blank if not needed)
4. **Tools** — list of tools to add as child nodes. For each tool collect:
   - `toolId` — snake_case identifier (e.g. `return_to_concierge`)
   - `label` — display name (e.g. "Return to Concierge")
   - `description` — use format: `"Use this tool when {condition}. Expects {params}. Returns {outcome}."`
   - `useParameters` — yes or no. If yes, ask for the JSON Schema for parameters.

If the user doesn't provide description, instructions, or tools, use empty strings and skip tool creation.

---

## Step 4: Resolve Insertion Point

Ask: "Where in the flow should the job node be inserted? (default: after the Start node)"

Invoke `cognigy:select-node` with:
- `flowId` from Step 1
- If the user provided a node identifier (ID, label, or type), pass it as the node hint. If none was given, pass `start` as the hint — `cognigy:select-node` will match the Start node by type.

Capture: `targetNodeId` (the `nodeId` returned by `cognigy:select-node`)

---

## Step 5: Create the AI Agent Job Node

Invoke `cognigy:create` for `node` with these arguments:
- `--flowId <flowId>`
- `--type aiAgentJob`
- `--extension @cognigy/basic-nodes`
- `--label "<job label>"`
- `--target <targetNodeId>`
- `--mode append`
- `--config` with the following JSON object:

```json
{
  "aiAgent": "<agentReferenceId>",
  "name": "<job label>",
  "description": "<job description>",
  "instructions": "<job instructions>",
  "toolChoice": "auto",
  "memoryType": "inherit",
  "temperature": 0.7,
  "maxTokens": 4000,
  "knowledgeSearchBehavior": "onDemand"
}
```

Capture: `jobNodeId` (the `_id` from the response)

---

## Step 6: Create Tool Nodes

For each tool gathered in Step 3, invoke `cognigy:create` for `node` with:
- `--flowId <flowId>`
- `--type aiAgentJobTool`
- `--extension @cognigy/basic-nodes`
- `--label "<tool label>"`
- `--target <jobNodeId>`
- `--mode appendChild`

For tools with `useParameters: false`, use this `--config`:
```json
{
  "toolId": "<toolId>",
  "description": "<tool description>",
  "useParameters": false
}
```

For tools with `useParameters: true`, use this `--config`:
```json
{
  "toolId": "<toolId>",
  "description": "<tool description>",
  "useParameters": true,
  "parameters": {
    "type": "object",
    "properties": {
      "<paramName>": {
        "type": "<string|number|boolean>",
        "description": "<param description>"
      }
    },
    "required": ["<paramName>"],
    "additionalProperties": false
  }
}
```

If any tool creation fails, stop immediately and report which tools were successfully created and which failed — do not continue to the next tool.

---

## Step 7: Report

Present a summary table of all created resources:

| Resource | Name | ID |
|---|---|---|
| Flow (existing) | `<flow name>` | `<flowId>` |
| AI Agent (existing) | `<agentName>` | `<agentReferenceId>` |
| Job Node | `<job label>` | `<jobNodeId>` |
| Tool: `<toolId>` | `<tool label>` | `<tool _id>` |

---

## Notes

- `mode: append` MUST be used for the job node. `insertAfter` returns a 500 from the Cognigy API.
- `mode: appendChild` MUST be used for tool nodes — they are children of the job node.
- The `aiAgent` config field takes the agent's `referenceId` (UUID), not `_id`.
- All node operations require `--flowId`.
- Never hardcode `npx tsx` CLI calls — always invoke atomic skills by name.
