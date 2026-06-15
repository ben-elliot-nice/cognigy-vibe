---
topic: tool-selection
description: when to use push_code_node vs cognigy_create vs cognigy_update
group: aiagent
---

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
