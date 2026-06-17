---
topic: agent-tool-json
description: .tool.json convention for defining AI agent tools locally
group: aiagent
---

## agent-tool-json — Local Tool Definition File

### Purpose
A `.tool.json` file defines a single AI Agent tool locally. push_agent_tool reads this
file and maps it to the Cognigy API — no inline JSON required in the MCP call.

### Complete example
```json
{
  "toolId": "check_balance",
  "label": "Check Balance",
  "description": "Use this tool when the customer asks about their account balance. Returns balance and currency.",
  "parameters": {
    "type": "object",
    "properties": {
      "account_type": {
        "type": "string",
        "description": "Savings or current"
      }
    },
    "required": ["account_type"],
    "additionalProperties": false
  },
  "condition": "context.authVerified"
}
```

### Field reference

| Field | Required | Notes |
|---|---|---|
| `toolId` | yes | Snake_case identifier used by the LLM to call the tool |
| `description` | yes | LLM-facing. Format: "Use this tool when {condition}. Expects {params}. Returns {outcome}." |
| `label` | no | Display name in Cognigy UI. Defaults to `toolId` if omitted |
| `parameters` | no | Full JSON Schema object. Omit entirely for parameter-free tools |
| `condition` | no | CognigyScript expression. Omit to always show tool to LLM |

### Parameters shape
Use standard JSON Schema (same format as MCP tool definitions and OpenAPI specs).
`useParameters` is auto-derived from whether `parameters` is present — do not include it.
`additionalProperties: false` is recommended to prevent hallucinated parameters.

### Minimal example (no parameters)
```json
{
  "toolId": "end_call",
  "description": "Use this tool when the conversation is complete and the call should be ended."
}
```

### Tool description format
Follow the contract format from the agent prompting guide:
  "Use this tool when {condition}. [Compliance rule at point-of-use.] Expects {params}. Returns {outcome}."

Always say what it returns — the LLM uses this to interpret toolResponse.
