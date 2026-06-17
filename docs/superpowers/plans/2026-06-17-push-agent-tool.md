# push_agent_tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `push_agent_tool` — a file-backed MCP tool that creates/updates `aiAgentJobTool` nodes from a local `.tool.json` file, matching `push_code_node`'s create/update pattern.

**Architecture:** New handler added to `file_push.py` alongside existing file-push tools. `cognigy_create` gains a blocker for `aiAgentJobTool` type. Four explain topics updated (tool-conditions corrected, tool-selection and agent-tool-branch updated, new agent-tool-json topic added). Explain topics are rebuilt via `scripts/build_explain_topics.py` — never edit `_explain_topics_generated.py` or `skills/explain/SKILL.md` directly.

**Tech Stack:** Python, httpx (via `CognigyClient`), pytest, `uv run scripts/build_explain_topics.py`

---

## File Map

| Action | File |
|---|---|
| Modify | `cognigy-mcp/cognigy_mcp/tools/file_push.py` |
| Modify | `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` |
| Modify | `cognigy-mcp/tests/tools/test_file_push.py` |
| Modify | `cognigy-mcp/tests/tools/test_flow_ops.py` |
| Modify | `skills/explain/resources/aiagent/tool-conditions.md` |
| Modify | `skills/explain/resources/aiagent/tool-selection.md` |
| Modify | `skills/explain/resources/aiagent/agent-tool-branch.md` |
| Create | `skills/explain/resources/aiagent/agent-tool-json.md` |
| Rebuild | `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py` (via script) |
| Rebuild | `skills/explain/SKILL.md` (via script) |
| Modify | `skills/add-aiagent-job/SKILL.md` |
| Modify | `cognigy-mcp/pyproject.toml` |
| Modify | `.claude-plugin/plugin.json` |

---

## Task 1: Fix tool-conditions.md

**Context:** Live API tests confirmed `condition` lives inside `config`, not at the top-level node body. Top-level `condition` returns HTTP 400. The current topic is wrong.

**Files:**
- Modify: `skills/explain/resources/aiagent/tool-conditions.md`

- [ ] **Step 1: Replace the topic content**

Replace the entire content of `skills/explain/resources/aiagent/tool-conditions.md` with:

```markdown
---
topic: tool-conditions
description: CognigyScript condition field, hiding tools from LLM
group: aiagent
---

## tool-conditions — Controlling Tool Visibility

### What conditions do
The condition field on an aiAgentJobTool is a CognigyScript expression stored in `config.condition`.
When falsy → tool is hidden from the LLM. LLM cannot call what it cannot see.
This is more reliable than code guards (LLM can ignore code; can't call hidden tool).

### Setting a condition
Use push_agent_tool with condition set in the .tool.json file (see explain("agent-tool-json")).
Or update directly:
  cognigy_update(resource_type="node", resource_id=<toolNodeId>, flow_id=<flowId>,
    merge_config=False,
    body={"config": {"condition": "!context.authVerified"}}
  )

**Important:** condition is inside `config`, NOT a top-level field. Sending it top-level
returns HTTP 400: "Field 'condition' is not allowed."

### Condition examples
  "!context.authVerified"                    // show authenticate_caller only before auth
  "context.contracts.booking.stage === 0"    // show only at correct workflow stage
  "context.shortTermMemory.policyLoaded"     // show after policy is loaded

### Removing a condition (always show)
  body={"config": {"condition": ""}}  or  body={"config": {"condition": null}}

### CognigyScript in conditions
- Use context.* variables (set by code nodes or Set Context nodes)
- Use input.data.* for per-turn data
- Operators: ===, !==, &&, ||, !, >, <
- No function calls, no complex expressions

### Context namespace visibility
- context.shortTermMemory.*  → VISIBLE to LLM (included in agent context)
- context.contracts.*        → NOT visible to LLM (use for enforcement state)
- context.ami.*              → NOT visible to LLM (use for config/flags)
```

- [ ] **Step 2: Commit**

```bash
git add skills/explain/resources/aiagent/tool-conditions.md
git commit -m "fix: tool-conditions — condition lives in config not top-level (API-validated)"
```

---

## Task 2: Add agent-tool-json.md

**Context:** New explain topic documenting the `.tool.json` file convention. LLMs read this before writing or editing a tool definition file.

**Files:**
- Create: `skills/explain/resources/aiagent/agent-tool-json.md`

- [ ] **Step 1: Create the file**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add skills/explain/resources/aiagent/agent-tool-json.md
git commit -m "docs: add agent-tool-json explain topic — .tool.json convention"
```

---

## Task 3: Update tool-selection.md and agent-tool-branch.md

**Files:**
- Modify: `skills/explain/resources/aiagent/tool-selection.md`
- Modify: `skills/explain/resources/aiagent/agent-tool-branch.md`

- [ ] **Step 1: Update tool-selection.md**

Replace the entire content of `skills/explain/resources/aiagent/tool-selection.md` with:

```markdown
---
topic: tool-selection
description: when to use push_agent_tool vs push_code_node vs cognigy_create vs cognigy_update
group: aiagent
---

## tool-selection — Choosing the Right Tool

### Decision tree
- "Creating or updating an AI Agent tool definition?" → push_agent_tool (file-backed, maps .tool.json to Cognigy config)
- "Creating a Code node from a local .js/.ts file?" → push_code_node (provides conflict detection against Cognigy UI edits)
- "Creating any other node (Say, Once, HTTP Request, AI Agent Job, etc.)?" → cognigy_create
- "Creating an HTML/xApp node from a local .html file?" → push_html_node (sets mode='full' automatically)
- "Updating an existing node's config?" → cognigy_update with merge_config=true
- "Reading a node or resource?" → cognigy_get

### Why push_agent_tool for aiAgentJobTool nodes?
push_agent_tool handles the JSON serialization Cognigy requires (parameters must be a JSON string,
not an object), auto-derives useParameters, and sets debugMessage:true. cognigy_create is blocked
for aiAgentJobTool — attempting it returns an error redirecting here.

### Why push_code_node for Code nodes?
push_code_node provides conflict detection: if someone edited the node in the Cognigy UI
since your last push, the push is blocked with a diff. cognigy_create is also blocked for code nodes.

### File-backed vs direct
- push_agent_tool / push_code_node / push_html_node: local file → remote node
- cognigy_create: create node from scratch inline — blocked for code and aiAgentJobTool types

### AI Agent tool branch
See explain("agent-tool-branch") for the full three-node assembly sequence.
See explain("agent-tool-json") for the .tool.json file convention.
```

- [ ] **Step 2: Update agent-tool-branch.md**

Replace the entire content of `skills/explain/resources/aiagent/agent-tool-branch.md` with:

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add skills/explain/resources/aiagent/tool-selection.md skills/explain/resources/aiagent/agent-tool-branch.md
git commit -m "docs: update tool-selection and agent-tool-branch for push_agent_tool"
```

---

## Task 4: Rebuild explain topics

**Context:** The explain pipeline generates `_explain_topics_generated.py` and `SKILL.md` from the markdown source files. Never edit those files directly — always run the build script after changing source topics.

**Files:**
- Rebuild: `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py`
- Rebuild: `skills/explain/SKILL.md`

- [ ] **Step 1: Run the build script**

```bash
uv run scripts/build_explain_topics.py
```

Expected output:
```
Generated: cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
Generated: skills/explain/SKILL.md
Done. <N> topic(s) processed.
```

If it exits with an error, check the frontmatter in the newly added/modified files (required fields: `topic`, `description`).

- [ ] **Step 2: Verify agent-tool-json topic appears in generated file**

```bash
grep "agent-tool-json" cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
```

Expected: a line containing `'agent-tool-json': '...'`

- [ ] **Step 3: Verify tool-conditions fix appears**

```bash
grep "condition is inside" cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
```

Expected: match found.

- [ ] **Step 4: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py skills/explain/SKILL.md
git commit -m "chore: rebuild explain topics — add agent-tool-json, fix tool-conditions, update tool-selection and agent-tool-branch"
```

---

## Task 5: Write failing tests for push_agent_tool

**Context:** Tests go in the existing `test_file_push.py`. Use `mock_client`, `state`, and `cache` fixtures from `tests/tools/conftest.py`. `mock_client` is a `MagicMock` — `.post.return_value` and `.patch.return_value` control API responses.

**Files:**
- Modify: `cognigy-mcp/tests/tools/test_file_push.py`

- [ ] **Step 1: Add all push_agent_tool tests**

Append to `cognigy-mcp/tests/tools/test_file_push.py`:

```python
# ---------------------------------------------------------------------------
# push_agent_tool tests
# ---------------------------------------------------------------------------

def test_push_agent_tool_exported():
    names = [t.name for t in TOOLS]
    assert "push_agent_tool" in names


def test_push_agent_tool_create_bare_minimum(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "end_call.tool.json"
    tool_file.write_text('{"toolId": "end_call", "description": "End the call."}')
    mock_client.post.return_value = {"_id": "tool-node-1", "type": "aiAgentJobTool", "label": "end_call"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({
        "tool_file": str(tool_file),
        "flow_id": "flow-1",
        "job_node_id": "job-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["created"] is True
    assert data["node_id"] == "tool-node-1"
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["type"] == "aiAgentJobTool"
    assert posted_body["extension"] == "@cognigy/basic-nodes"
    assert posted_body["mode"] == "appendChild"
    assert posted_body["target"] == "job-1"
    assert posted_body["config"]["toolId"] == "end_call"
    assert posted_body["config"]["description"] == "End the call."
    assert posted_body["config"]["useParameters"] is False
    assert posted_body["config"]["debugMessage"] is True
    assert posted_body["config"]["condition"] == ""


def test_push_agent_tool_create_label_defaults_to_tool_id(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "check_balance", "description": "Check balance."}')
    mock_client.post.return_value = {"_id": "tool-node-2", "type": "aiAgentJobTool", "label": "check_balance"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["label"] == "check_balance"


def test_push_agent_tool_create_label_from_file(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "check_balance", "label": "Check Balance", "description": "Check balance."}')
    mock_client.post.return_value = {"_id": "tool-node-3", "type": "aiAgentJobTool", "label": "Check Balance"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["label"] == "Check Balance"


def test_push_agent_tool_create_with_parameters(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "check.tool.json"
    tool_file.write_text(json.dumps({
        "toolId": "check_balance",
        "description": "Check balance.",
        "parameters": {
            "type": "object",
            "properties": {"account_type": {"type": "string", "description": "Savings or current"}},
            "required": ["account_type"],
            "additionalProperties": False,
        }
    }))
    mock_client.post.return_value = {"_id": "tool-node-4", "type": "aiAgentJobTool", "label": "check_balance"}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({
        "tool_file": str(tool_file),
        "flow_id": "flow-1",
        "job_node_id": "job-1",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["config"]["useParameters"] is True
    # parameters must be a JSON string, not an object
    params_value = posted_body["config"]["parameters"]
    assert isinstance(params_value, str)
    params_parsed = json.loads(params_value)
    assert params_parsed["properties"]["account_type"]["type"] == "string"


def test_push_agent_tool_create_with_condition(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text(json.dumps({
        "toolId": "sensitive_action",
        "description": "Sensitive action.",
        "condition": "context.authVerified",
    }))
    mock_client.post.return_value = {"_id": "tool-node-5", "type": "aiAgentJobTool", "label": "sensitive_action"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["config"]["condition"] == "context.authVerified"


def test_push_agent_tool_create_saves_to_state(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Does things."}')
    mock_client.post.return_value = {"_id": "tool-node-6", "type": "aiAgentJobTool", "label": "my_tool"}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    entry = state.get("nodes", "my_tool")
    assert entry is not None
    assert entry["id"] == "tool-node-6"
    assert entry["flowId"] == "flow-1"


def test_push_agent_tool_create_missing_job_node_id(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Does things."}')
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1"})
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.post.assert_not_called()


def test_push_agent_tool_update(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Updated description."}')
    mock_client.patch.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({
        "tool_file": str(tool_file),
        "flow_id": "flow-1",
        "node_id": "tool-node-existing",
    })
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data.get("updated") is True
    mock_client.post.assert_not_called()
    patch_path = mock_client.patch.call_args[0][0]
    assert "tool-node-existing" in patch_path
    patch_body = mock_client.patch.call_args[0][1]
    assert patch_body["config"]["description"] == "Updated description."
    assert patch_body["config"]["debugMessage"] is True


def test_push_agent_tool_update_parameters_serialized(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text(json.dumps({
        "toolId": "my_tool",
        "description": "Does things.",
        "parameters": {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"], "additionalProperties": False},
    }))
    mock_client.patch.return_value = {}
    handlers = make_handlers(mock_client, state, cache)
    handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "node_id": "tool-node-existing"})
    patch_body = mock_client.patch.call_args[0][1]
    assert isinstance(patch_body["config"]["parameters"], str)
    assert patch_body["config"]["useParameters"] is True


def test_push_agent_tool_file_not_found(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({
        "tool_file": "/nonexistent/tool.tool.json",
        "flow_id": "flow-1",
        "job_node_id": "job-1",
    })
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.post.assert_not_called()


def test_push_agent_tool_missing_required_fields(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool"}')  # missing description
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    data = json.loads(result[0].text)
    assert "error" in data
    mock_client.post.assert_not_called()


def test_push_agent_tool_create_api_failure(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Does things."}')
    mock_client.post.side_effect = Exception("network error")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "job_node_id": "job-1"})
    data = json.loads(result[0].text)
    assert "error" in data


def test_push_agent_tool_update_api_failure(mock_client, state, cache, tmp_path):
    tool_file = tmp_path / "tool.tool.json"
    tool_file.write_text('{"toolId": "my_tool", "description": "Does things."}')
    mock_client.patch.side_effect = Exception("api error")
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["push_agent_tool"]({"tool_file": str(tool_file), "flow_id": "flow-1", "node_id": "tool-node-existing"})
    data = json.loads(result[0].text)
    assert "error" in data
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
cd cognigy-mcp && uv run pytest tests/tools/test_file_push.py -k "push_agent_tool" -v 2>&1 | tail -20
```

Expected: all new tests FAIL with `KeyError: 'push_agent_tool'` (handler not yet registered).

- [ ] **Step 3: Commit failing tests**

```bash
git add cognigy-mcp/tests/tools/test_file_push.py
git commit -m "test: add failing tests for push_agent_tool"
```

---

## Task 6: Implement push_agent_tool

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/file_push.py`

- [ ] **Step 1: Add Tool definition to TOOLS list**

In `file_push.py`, append to the `TOOLS` list (after `push_html_node`):

```python
    Tool(
        name="push_agent_tool",
        description=(
            "Read a local .tool.json file and push its definition to a Cognigy aiAgentJobTool node. "
            "Two modes: "
            "(1) UPDATE — provide node_id to update an existing aiAgentJobTool node. "
            "(2) CREATE — omit node_id and provide job_node_id to create a new tool node as a child of an aiAgentJob node. "
            "The .tool.json file must contain toolId and description. "
            "parameters (JSON Schema object) and condition (CognigyScript) are optional. "
            "See explain('agent-tool-json') for the .tool.json file convention."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tool_file": {"type": "string", "description": "Absolute path to .tool.json file"},
                "flow_id": {"type": "string"},
                "node_id": {"type": "string", "description": "ID of an existing aiAgentJobTool node to update. Omit to create."},
                "job_node_id": {"type": "string", "description": "Required when creating: ID of the parent aiAgentJob node"},
            },
            "required": ["tool_file", "flow_id"],
        },
    ),
```

- [ ] **Step 2: Add handler in make_handlers**

In `file_push.py`, add this function inside `make_handlers` (after `_push_html_node`):

```python
    def _push_agent_tool(args: dict) -> list[TextContent]:
        path = Path(args["tool_file"])
        node_id = args.get("node_id")
        flow_id = args["flow_id"]

        if not path.exists():
            return _ok({"error": f"File not found: {path}"})

        try:
            tool_spec = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            return _ok({"error": f"Invalid JSON in {path}: {e}"})

        missing = [f for f in ("toolId", "description") if not tool_spec.get(f)]
        if missing:
            return _ok({"error": f"Missing required fields in tool file: {', '.join(missing)}"})

        parameters = tool_spec.get("parameters")
        use_parameters = parameters is not None

        config: dict = {
            "toolId": tool_spec["toolId"],
            "description": tool_spec["description"],
            "useParameters": use_parameters,
            "debugMessage": True,
            "condition": tool_spec.get("condition", ""),
        }
        if use_parameters:
            config["parameters"] = json.dumps(parameters, separators=(",", ":"))

        if not node_id:
            job_node_id = args.get("job_node_id")
            if not job_node_id:
                return _ok({"error": "Provide node_id to update an existing tool node, or job_node_id to create a new one"})
            body = {
                "type": "aiAgentJobTool",
                "extension": "@cognigy/basic-nodes",
                "label": tool_spec.get("label", tool_spec["toolId"]),
                "mode": "appendChild",
                "target": job_node_id,
                "config": config,
            }
            try:
                result = client.post(f"/v2.0/flows/{flow_id}/chart/nodes", body)
            except Exception as e:
                return _ok({"error": f"Failed to create tool node: {e}"})
            new_node_id = result["_id"]
            state.set("nodes", tool_spec["toolId"], value={"id": new_node_id, "flowId": flow_id})
            return _ok({"success": True, "node_id": new_node_id, "created": True})

        try:
            client.patch(f"/v2.0/flows/{flow_id}/chart/nodes/{node_id}", {"config": config})
        except Exception as e:
            return _ok({"error": f"Failed to update tool node: {e}"})
        return _ok({"success": True, "node_id": node_id, "updated": True})
```

- [ ] **Step 3: Register handler in the return dict**

In `make_handlers`, add to the return dict:

```python
        "push_agent_tool": _push_agent_tool,
```

- [ ] **Step 4: Run tests**

```bash
cd cognigy-mcp && uv run pytest tests/tools/test_file_push.py -k "push_agent_tool" -v 2>&1 | tail -25
```

Expected: all push_agent_tool tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd cognigy-mcp && uv run pytest tests/ -v 2>&1 | tail -15
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/file_push.py
git commit -m "feat: add push_agent_tool — file-backed aiAgentJobTool create/update"
```

---

## Task 7: Add aiAgentJobTool blocker in cognigy_create

**Context:** `cognigy_create` already blocks `code` node creation and redirects to `push_code_node`. Add the same pattern for `aiAgentJobTool`.

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py`
- Modify: `cognigy-mcp/tests/tools/test_flow_ops.py`

- [ ] **Step 1: Write failing test**

Append to `cognigy-mcp/tests/tools/test_flow_ops.py`:

```python
def test_cognigy_create_aiagentjobtool_blocked(mock_client, state, cache):
    """cognigy_create must redirect aiAgentJobTool to push_agent_tool."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({
        "resource_type": "node",
        "flow_id": "flow-1",
        "body": {"type": "aiAgentJobTool", "mode": "appendChild", "target": "job-1", "config": {}},
    })
    data = json.loads(result[0].text)
    assert "error" in data
    assert "push_agent_tool" in data["error"]
    mock_client.post.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd cognigy-mcp && uv run pytest tests/tools/test_flow_ops.py::test_cognigy_create_aiagentjobtool_blocked -v
```

Expected: FAIL — the node is currently created, not blocked.

- [ ] **Step 3: Add blocker in flow_ops.py**

In `_cognigy_create` in `flow_ops.py`, after the existing code node guard (which reads `if body.get("type") == "code":`), add:

```python
            if body.get("type") == "aiAgentJobTool":
                return _ok({"error": (
                    "AI Agent tool nodes must be created via push_agent_tool "
                    "(file-backed, maps .tool.json spec to Cognigy config). "
                    "To create a new tool: push_agent_tool(tool_file=..., flow_id=..., job_node_id=...). "
                    'See explain("tool-selection") for guidance.'
                )})
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd cognigy-mcp && uv run pytest tests/tools/test_flow_ops.py::test_cognigy_create_aiagentjobtool_blocked -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
cd cognigy-mcp && uv run pytest tests/ -v 2>&1 | tail -15
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py cognigy-mcp/tests/tools/test_flow_ops.py
git commit -m "feat: block cognigy_create for aiAgentJobTool — redirect to push_agent_tool"
```

---

## Task 8: Update add-aiagent-job skill

**Context:** The skill currently creates `aiAgentJobTool` nodes via `cognigy_create` inline in Step 6. With the blocker in place, this will now fail. Update Step 6 to use `push_agent_tool` instead.

**Files:**
- Modify: `skills/add-aiagent-job/SKILL.md`

- [ ] **Step 1: Replace Step 6 in the skill**

In `skills/add-aiagent-job/SKILL.md`, replace the entire **Step 6: Create Tool Nodes** section with:

```markdown
## Step 6: Create Tool Nodes

For each tool gathered in Step 3, first write a `.tool.json` file for it (see explain("agent-tool-json")), then call `push_agent_tool`.

Write the file to the user's current working directory (not the plugin root):

```json
{
  "toolId": "<toolId>",
  "label": "<tool label>",
  "description": "<tool description>",
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

Omit `parameters` entirely for tools where `useParameters` is false.

Then call `push_agent_tool` with:
- `tool_file`: absolute path to the written `.tool.json` file
- `flow_id`: `<flowId>`
- `job_node_id`: `<jobNodeId>`

Capture: tool `_id` from the response as `<toolNodeId>`.

If any tool creation fails, stop immediately and report which tools were successfully created and which failed — do not continue to the next tool.
```

- [ ] **Step 2: Update the Notes section**

In the Notes section of `skills/add-aiagent-job/SKILL.md`, replace:

```
- `mode: appendChild` MUST be used for tool nodes — they are children of the job node.
```

with:

```
- Tool nodes are created via push_agent_tool (not cognigy_create directly) — cognigy_create is blocked for aiAgentJobTool type.
- push_agent_tool always uses mode: appendChild — no need to specify it.
```

- [ ] **Step 3: Commit**

```bash
git add skills/add-aiagent-job/SKILL.md
git commit -m "fix: update add-aiagent-job to use push_agent_tool for tool nodes"
```

---

## Task 9: Version bump

**Context:** CLAUDE.md requires patch version increment in both `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json` after any change to `cognigy-mcp/` or `skills/`. CI enforces this on PRs to main.

Current version: `1.4.1` → bump to `1.4.2`.

**Files:**
- Modify: `cognigy-mcp/pyproject.toml`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump version in pyproject.toml**

Change line `version = "1.4.1"` to `version = "1.4.2"`.

- [ ] **Step 2: Bump version in plugin.json**

Change `"version": "1.4.1"` to `"version": "1.4.2"`.

- [ ] **Step 3: Commit**

```bash
git add cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "chore: bump to 1.4.2 — push_agent_tool, explain topic fixes"
```
