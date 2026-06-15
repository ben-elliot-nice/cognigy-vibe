---
topic: agent-tool-branch
description: aiAgentJobTool + code + toolAnswer assembly, tool args access
group: aiagent
---

## agent-tool-branch — Building the AI Agent Tool Chain

### Three-node pattern
Every AI Agent tool is a branch of three nodes under an aiAgentJob:
  aiAgentJob
  └── aiAgentJobTool       (the tool node — appendChild of aiAgentJob)
       └── Code Node       (implementation — append after tool node)
            └── aiAgentToolAnswer  (surfaces result — append after code node)

### Step 1: Create aiAgentJobTool
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "aiAgentJobTool",
    "extension": "@cognigy/basic-nodes",
    "label": "my_tool",
    "mode": "appendChild",
    "target": "<aiAgentJobNodeId>",
    "config": {}
  })

### Step 2: Update aiAgentJobTool config
  cognigy_update(resource_type="node", resource_id=<toolNodeId>, merge_config=True, body={
    "config": {
      "toolId": "<toolId from Cognigy tools library>",
      "description": "What this tool does",
      "useParameters": True,
      "parameters": [{"name": "amount", "type": "number", "description": "Amount to charge"}]
    }
  })

### Step 3: Append Code node
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "code", "label": "[TOOL] my_tool",
    "mode": "append", "target": "<toolNodeId>",
    "config": {"code": "context.toolResponse = {summary: 'Done'}; api.resolve();"}
  })

### Step 4: Append aiAgentToolAnswer
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "aiAgentToolAnswer", "extension": "@cognigy/basic-nodes",
    "mode": "append", "target": "<codeNodeId>",
    "config": {}
  })

### Reading tool arguments in the code node
Parameters the LLM collected are available as:
  const amount = input.aiAgent.toolArgs.amount;
  const reason = input.aiAgent.toolArgs.reason;
These are NOT in input.data — they come via input.aiAgent.toolArgs.<paramName>.

### Tool conditions (hide tool from LLM when false)
  cognigy_update(..., body={"condition": "!context.authVerified"})
  Note: condition is a TOP-LEVEL field, NOT inside config.

### context.toolResponse
  Code node writes: context.toolResponse = {summary: "...", data: {...}}
  aiAgentToolAnswer reads context.toolResponse and surfaces it to the LLM.
  toolResponse.summary = what the LLM reads back to the customer naturally.
