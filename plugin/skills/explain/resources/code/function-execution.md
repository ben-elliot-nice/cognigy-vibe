---
topic: function-execution
description: async pattern, inject-back via sessions API
group: code
---

## function-execution — Cognigy Functions (Async Pattern)

### What Cognigy Functions are
Serverless JS/TS functions that run outside the flow on Cognigy infrastructure.
Used for long-running async operations (>30s timeout for flows).

### Execute a function
  cognigy_invoke(resource_type="functions", resource_id=<functionId>,
    operation="execute", body={"parameters": {...}})
Path: POST /v2.0/functions/{functionId}/instances

### Check instance status
  cognigy_get(resource_type="functioninstances", resource_id=<instanceId>)
Returns: {status: "pending"|"running"|"done"|"error", result: {...}}

### Inject result back into conversation
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="inject-context", body={"context": {"functionResult": result}})

### In-flow pattern
Use Function Execution node (not raw API) when available.
The node handles invoke + polling + inject natively.

### Session ID for inject
The sessionId is the same value used in talk_to_agent.
In production: comes from input.sessionId within the flow.
