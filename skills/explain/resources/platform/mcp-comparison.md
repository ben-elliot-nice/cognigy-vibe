---
topic: mcp-comparison
description: when to use cognigy-vibe vs NiCE official MCP
group: platform
---

## mcp-comparison — cognigy-vibe vs Official NiCE MCP

Two MCPs operate on the same Cognigy API with different purposes.

### Official NiCE MCP (@cognigy/mcp-server)
Strengths:
- create_ai_agent: creates project + agent + flow + endpoint in ONE call
- create_tool: creates aiAgentJobTool + Resolve Tool Action pair, auto-wired
- manage_flow_nodes: inline node creation with flat config shapes (text: "..." works)
- list_resources, delete_resource: fast discovery and cleanup

Limitations:
- Does NOT support: once, onFirstExecution, afterwards, setSessionConfig, hangup, wait
- Does NOT propagate persona/LLM/temperature/toolChoice to the AI Agent Job Node after creation
- Returned endpointUrl uses cognigy-api-au1 (returns 401) — must substitute cognigy-endpoint-au1
- create_tool returns a field called toolId that is actually the mongo _id of the node (misleading)

### cognigy-vibe (this server)
Strengths:
- cognigy_create: any node type, with extension auto-injection
- cognigy_update: always-fresh-GET + merge_config deep-merge (safe partial updates)
- push_code_node: file-first conflict detection
- get_flow_chart: hierarchy string + raw relations
- sync_remote_state: full project state snapshot
- 17-topic explain library

Limitations:
- No convenience methods — no single call to create a full agent

### Recommended split (two-MCP pattern)
Use NiCE for:         create_ai_agent, create_tool, manage_flow_nodes (say/code/question inside tool branches)
Use cognigy-vibe for: once/setSessionConfig/hangup node creation, patching aiAgentJob config after creation,
                      push_code_node, get_flow_chart, cognigy_update with merge_config

### Critical gotcha — NiCE does NOT patch the AI Agent Job Node
After create_ai_agent, the AI Agent Job Node has generic defaults (name: "Customer Support Specialist",
default LLM, toolChoice: "auto", generic memoryContextInjection).
ALWAYS follow create_ai_agent with cognigy_update on the aiAgentJob node to set your persona config.
