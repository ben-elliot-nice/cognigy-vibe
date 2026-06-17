---
topic: agent-tool-branch
description: aiAgentJobTool + code + toolAnswer assembly, tool args access
group: aiagent
---

## agent-tool-branch — Building the AI Agent Tool Branch

### Three-node structure
Every AI Agent tool is a branch under an aiAgentJob:
  aiAgentJob
  └── aiAgentJobTool       (the tool definition — appendChild of aiAgentJob)
       └── Code Node       (implementation — append after tool node)
            └── aiAgentToolAnswer  (surfaces result — append after code node)

### Step 1: Create the tool definition (push_agent_tool)
Write a .tool.json file first — see explain("agent-tool-json") for the convention.

  push_agent_tool(
    tool_file="/path/to/my_tool.tool.json",
    flow_id=<flowId>,
    job_node_id=<aiAgentJobNodeId>
  )

Returns node_id of the new aiAgentJobTool node.

### Step 2: Create the code node (push_code_node)
  push_code_node(
    script_file="/path/to/my_tool.js",
    flow_id=<flowId>,
    mode="append",
    target=<toolNodeId>,
    label="[TOOL] my_tool"
  )

Returns node_id of the new code node.

### Step 3: Append aiAgentToolAnswer
  cognigy_create(resource_type="node", flow_id=<flowId>, body={
    "type": "aiAgentToolAnswer",
    "mode": "append",
    "target": <codeNodeId>,
    "config": {}
  })

### Reading tool arguments in the code node
Parameters the LLM collected are available as:
  const amount = input.aiAgent.toolArgs.amount;
  const reason = input.aiAgent.toolArgs.reason;
These are NOT in input.data — they come via input.aiAgent.toolArgs.<paramName>.

### Updating an existing tool definition
  push_agent_tool(
    tool_file="/path/to/my_tool.tool.json",
    flow_id=<flowId>,
    node_id=<toolNodeId>
  )

Edit the .tool.json file locally first, then push. PATCH is additive on config —
fields not in the file are preserved. No conflict detection (tool config is the file).

### Updating an existing code node
  push_code_node(
    script_file="/path/to/my_tool.js",
    flow_id=<flowId>,
    node_id=<codeNodeId>
  )

### context.toolResponse
  Code node writes: context.toolResponse = {summary: "...", data: {...}}
  aiAgentToolAnswer reads context.toolResponse and surfaces it to the LLM.
  toolResponse.summary = what the LLM reads back to the customer naturally.

### Tool conditions (hide tool from LLM when false)
Set condition in the .tool.json file before pushing. See explain("tool-conditions").
