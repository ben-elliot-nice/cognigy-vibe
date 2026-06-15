---
topic: flow-chart-reading
description: reading chart output, node type strings, extension field
group: nodes
---

## flow-chart-reading — Reading get_flow_chart Output

### Verified node type strings (exact, case-sensitive)
Core types (no extension needed):
  say, question, code, setContext, goTo, once, lookup, log, stopBot, httpRequest
  if (note: NOT "ifThenElse")

AI Agent types (extension: "@cognigy/basic-nodes"):
  aiAgentJob, aiAgentJobTool, aiAgentToolAnswer

xApp/Voice types (extension: "@cognigy/basic-nodes"):
  initAppSession  (NOT "xAppInitSession")
  setHTMLAppState (NOT "setHTMLxAppState")

### Reading node objects
  {
    "_id": "abc123",       // use this as node_id in tool calls
    "type": "say",
    "label": "Greeting",  // human-readable
    "config": {...},       // type-specific configuration (ONLY in cognigy_get, not chart)
    "position": {"x": 0, "y": 100}
  }

### if nodes (NOT "ifThenElse")
Can be created via cognigy_create. Type string is "if".
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "if",
    "mode": "append",
    "target": "<previousNodeId>",
    "config": {
      "condition": {
        "type": "rule",
        "rule": {
          "left": "context.someVar",
          "operand": "neq",    // equals, notEquals (neq), contains, greaterThan, lessThan
          "right": "someValue"
        }
      }
    }
  })
Creating an if node auto-creates two branch container nodes: Then (childIds[0]) and Else (childIds[1]).
To add nodes inside a branch: use mode="append", target="<branch-marker-_id>" (same rule as Once nodes — append after the marker, not as a child of it).
Branches are in childIds[]: index 0 = Then (true), index 1 = Else (false).

### Reading the hierarchy string
get_flow_chart returns "hierarchy": a tree string like:
  [start] Start (abc)
  [say] Greeting (def)
  [aiAgentJob] Concierge (ghi)
    [aiAgentJobTool] authenticate_caller (jkl)
      [code] [TOOL] authenticate_caller (mno)
      [aiAgentToolAnswer] Tool Answer (pqr)
