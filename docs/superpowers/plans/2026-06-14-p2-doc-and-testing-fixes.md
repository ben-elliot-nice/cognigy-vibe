# P2 Doc and Testing Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three confirmed bugs — wrong IF node docs (#14), wrong xApp extension strings (#21), and missing `data` parameter in `talk_to_agent` (#15) — plus two associated explain.py doc corrections (Variant B inject path, relation field names).

**Architecture:** Two files change. `explain.py` gets string-level corrections to five topics (flow-chart-reading, extension-map, node-types, node-wiring, xapp-event-handling, xapp-delivery). `testing.py` gets a new optional `data` parameter wired to the existing `"data"` field in the REST payload body. All changes are regression-tested before touch.

**Tech Stack:** Python 3.11+, pytest, uv, respx (HTTP mocking for testing.py tests)

---

## File Map

| File | Change |
|---|---|
| `cognigy-mcp/cognigy_mcp/tools/explain.py` | Fix 8 incorrect strings across 6 topics |
| `cognigy-mcp/cognigy_mcp/tools/testing.py` | Add `data` param, make `message` optional |
| `cognigy-mcp/tests/tools/test_explain.py` | Add regression assertions for each fix |
| `cognigy-mcp/tests/tools/test_testing.py` | Add tests for data param and optional message |
| `cognigy-mcp/pyproject.toml` | Bump version 1.3.3 → 1.3.4 |
| `.claude-plugin/plugin.json` | Bump version 1.3.3 → 1.3.4 |

---

## Task 1: Regression tests for explain.py doc fixes (#14, #21, and associated)

Write failing tests for every string that will be corrected. Run them — they must all fail before you touch explain.py.

**Files:**
- Modify: `cognigy-mcp/tests/tools/test_explain.py`

- [ ] **Step 1: Add failing regression tests**

Append to `cognigy-mcp/tests/tools/test_explain.py`:

```python
# ── Issue #14: IF node type string and creation docs ────────────────────────

def test_flow_chart_reading_if_node_type_is_if_not_ifthenelse(mock_client, state, cache):
    """flow-chart-reading must document type string as 'if', not 'ifThenElse'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "flow-chart-reading"})
    text = result[0].text
    assert 'ifThenElse (note: NOT "if")' not in text, \
        "Must not document inverted type string"
    assert 'if (note: NOT "ifThenElse")' in text, \
        "Must document correct type string: if (note: NOT \"ifThenElse\")"


def test_flow_chart_reading_if_node_is_createable_via_api(mock_client, state, cache):
    """flow-chart-reading must document that IF nodes CAN be created via cognigy_create."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "flow-chart-reading"})
    text = result[0].text
    assert "Cannot be created via cognigy_create" not in text, \
        "Must not claim IF nodes are UI-only"
    assert 'cognigy_create' in text and '"type": "if"' in text, \
        "Must document cognigy_create with type 'if'"


def test_flow_chart_reading_if_node_config_schema(mock_client, state, cache):
    """flow-chart-reading must document the correct condition config schema."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "flow-chart-reading"})
    text = result[0].text
    assert '"condition"' in text, "Must document top-level 'condition' key"
    assert "conditions[0]" not in text, "Must not document wrong schema 'conditions[0]'"


def test_node_types_if_type_string(mock_client, state, cache):
    """node-types must document type string 'if', not 'ifThenElse'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-types"})
    text = result[0].text
    assert "ifThenElse        Conditional (NOT" not in text, \
        "node-types must not have inverted ifThenElse entry"
    assert "if                Conditional (NOT" in text, \
        "node-types must have correct 'if' entry"
    assert "create in UI only" not in text, \
        "node-types must not say 'create in UI only' for if nodes"


def test_extension_map_if_type_string(mock_client, state, cache):
    """extension-map must list 'if' not 'ifThenElse' for the conditional node type."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "extension-map"})
    text = result[0].text
    assert "ifThenElse          Conditional branch (create in UI" not in text, \
        "extension-map must not have UI-only ifThenElse entry"
    assert "if                  Conditional branch" in text, \
        "extension-map must have 'if' conditional branch entry"


# ── Issue #21: xApp extension strings ───────────────────────────────────────

def test_extension_map_xapp_extension_is_basic_nodes(mock_client, state, cache):
    """extension-map must document xApp nodes as @cognigy/basic-nodes, not cxone-utils."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "extension-map"})
    text = result[0].text
    assert '### xApp nodes (extension: "cxone-utils")' not in text, \
        "extension-map must not document xApp extension as cxone-utils"
    assert '### xApp nodes (extension: "@cognigy/basic-nodes")' in text, \
        "extension-map must document xApp extension as @cognigy/basic-nodes"


def test_node_wiring_xapp_extension_is_basic_nodes(mock_client, state, cache):
    """node-wiring inline examples must use @cognigy/basic-nodes for xApp nodes."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-wiring"})
    text = result[0].text
    assert '"extension": "cxone-utils"' not in text, \
        "node-wiring must not document cxone-utils extension"
    assert '"initAppSession"' in text and '"@cognigy/basic-nodes"' in text, \
        "node-wiring must document initAppSession with @cognigy/basic-nodes"


def test_xapp_delivery_extension_is_basic_nodes(mock_client, state, cache):
    """xapp-delivery must document setHTMLAppState with @cognigy/basic-nodes."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "xapp-delivery"})
    text = result[0].text
    assert 'extension: "cxone-utils"' not in text, \
        "xapp-delivery must not reference cxone-utils extension"
    assert 'extension: "@cognigy/basic-nodes"' in text, \
        "xapp-delivery must document @cognigy/basic-nodes for setHTMLAppState"


def test_node_types_xapp_extension_is_basic_nodes(mock_client, state, cache):
    """node-types must document xApp nodes as @cognigy/basic-nodes."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-types"})
    text = result[0].text
    assert "cxone-utils" not in text, \
        "node-types must not reference cxone-utils"
    assert "initAppSession" in text and "@cognigy/basic-nodes" in text, \
        "node-types must reference @cognigy/basic-nodes for xApp nodes"


# ── Issue #15 (doc): xapp-event-handling Variant B inject path ──────────────

def test_xapp_event_handling_variant_b_inject_path(mock_client, state, cache):
    """xapp-event-handling must not document the non-existent management API inject path."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "xapp-event-handling"})
    text = result[0].text
    assert "POST /v2.0/projects/{projectId}/sessions/{sessionId}" not in text, \
        "Must not document the non-existent management API path (returns 404 on AU1)"
    assert "cognigy-endpoint-" in text or "urlToken" in text, \
        "Must document the correct REST endpoint injection path"


# ── Associated: node-wiring relation field names ─────────────────────────────

def test_node_wiring_relation_field_names_are_correct(mock_client, state, cache):
    """node-wiring must document actual API field names: 'node', 'next', 'children'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-wiring"})
    text = result[0].text
    assert '"nodeId"' not in text, \
        "node-wiring must not document 'nodeId' — actual field is 'node'"
    assert '"nextId"' not in text, \
        "node-wiring must not document 'nextId' — actual field is 'next'"
    assert '"childIds"' not in text, \
        "node-wiring must not document 'childIds' — actual field is 'children'"
    assert '"node"' in text, "node-wiring must document 'node' field"
    assert '"next"' in text, "node-wiring must document 'next' field"
    assert '"children"' in text, "node-wiring must document 'children' field"
```

- [ ] **Step 2: Run tests — confirm all new tests fail**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py -v -k "if_node or xapp_extension or variant_b or relation_field" 2>&1 | tail -40
```

Expected: 11 FAILED, 0 passed

---

## Task 2: Fix explain.py — all doc correctness issues (#14, #21, #15-doc, relations)

Apply all string corrections to `explain.py`. No logic changes — only content strings.

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py`

- [ ] **Step 1: Fix flow-chart-reading topic — IF node type string and creation**

In `_CONTENT["flow-chart-reading"]`, replace:
```python
  ifThenElse (note: NOT "if")
```
with:
```python
  if (note: NOT "ifThenElse")
```

Replace the xApp extension line in the same topic:
```python
xApp/Voice types (extension: "cxone-utils"):
```
with:
```python
xApp/Voice types (extension: "@cognigy/basic-nodes"):
```

Replace the entire `### ifThenElse nodes` section:
```python
### ifThenElse nodes
Cannot be created via cognigy_create — only via Cognigy UI.
Condition is in config.conditions[0].rule — it is an OBJECT, not a string:
  config.conditions[0].rule = {
    "left": "{{context.someVar}}",
    "operand": "equals",   // equals, notEquals, contains, greaterThan, lessThan, etc.
    "right": "expectedValue"
  }
Branches are in childIds[]: index 0 = true branch, index 1 = false/else branch.
```
with:
```python
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
To add nodes inside a branch: use mode="appendChild", target="<branch-container-_id>".
Branches are in childIds[]: index 0 = Then (true), index 1 = Else (false).
```

- [ ] **Step 2: Fix node-wiring topic — xApp extensions and relation field names**

In `_CONTENT["node-wiring"]`, replace both xApp extension lines:
```python
  {"type": "initAppSession", "extension": "cxone-utils"}
  {"type": "setHTMLAppState", "extension": "cxone-utils"}
```
with:
```python
  {"type": "initAppSession", "extension": "@cognigy/basic-nodes"}
  {"type": "setHTMLAppState", "extension": "@cognigy/basic-nodes"}
```

Replace the Relations entry shape block:
```python
### Relations entry shape
  {
    "nodeId": "abc",
    "previousId": "xyz",   // node before in sequential chain (null for first)
    "nextId": "def",       // node after in sequential chain (null for last)
    "parentId": null,      // set if this is a child node (e.g. tool branch)
    "childIds": ["..."]    // children hanging off this node (e.g. tool nodes)
  }
```
with:
```python
### Relations entry shape
  {
    "node": "abc",         // the node ID this relation describes
    "_id": "rel-id",       // the relation's own MongoDB ID (different from node _id)
    "next": "def",         // next node in sequential chain (null if last)
    "children": ["..."]    // child node IDs (e.g. tool branches, if-node branches)
  }
```

Also remove the now-wrong sequential/children explanation that references "nextId":
Replace:
```python
- Sequential: follow nextId links from start node
- Children: follow childIds from parent (aiAgentJob, ifThenElse branches)
- Tool branches are children of aiAgentJob, NOT in sequential chain
```
with:
```python
- Sequential: follow "next" links from start node
- Children: follow "children" array from parent (aiAgentJob, if node branches)
- Tool branches are children of aiAgentJob, NOT in sequential chain
```

- [ ] **Step 3: Fix extension-map topic — xApp extension and if node entry**

In `_CONTENT["extension-map"]`, replace:
```python
### xApp nodes (extension: "cxone-utils")
  initAppSession      Generate xApp session URL (stored in input.apps.url)
  setHTMLAppState     Push HTML content to an active xApp session
```
with:
```python
### xApp nodes (extension: "@cognigy/basic-nodes")
  initAppSession      Generate xApp session URL (stored in input.apps.url)
  setHTMLAppState     Push HTML content to an active xApp session
```

Replace:
```python
  ifThenElse          Conditional branch (create in UI, not via API)
```
with:
```python
  if                  Conditional branch (NOT "ifThenElse") — create via cognigy_create
```

- [ ] **Step 4: Fix node-types topic — if type string and xApp extensions**

In `_CONTENT["node-types"]`, replace:
```python
  ifThenElse        Conditional (NOT "if") — create in UI only
```
with:
```python
  if                Conditional (NOT "ifThenElse") — create via cognigy_create
```

Replace:
```python
  initAppSession    xApp session init (extension: cxone-utils)
  setHTMLAppState   xApp HTML push (extension: cxone-utils)
```
with:
```python
  initAppSession    xApp session init (extension: @cognigy/basic-nodes)
  setHTMLAppState   xApp HTML push (extension: @cognigy/basic-nodes)
```

- [ ] **Step 5: Fix xapp-delivery topic — setHTMLAppState extension**

In `_CONTENT["xapp-delivery"]`, replace:
```python
Use the setHTMLAppState node instead (type: "setHTMLAppState", extension: "cxone-utils").
```
with:
```python
Use the setHTMLAppState node instead (type: "setHTMLAppState", extension: "@cognigy/basic-nodes").
```

- [ ] **Step 6: Fix xapp-event-handling topic — Variant B inject path**

In `_CONTENT["xapp-event-handling"]`, replace the entire Variant B inject block:
```python
External API then injects into Cognigy:
  POST /v2.0/projects/{projectId}/sessions/{sessionId}
  { "data": { "paymentResult": { "success": "true", "reference": "PAY-123" } } }

Injected payload arrives as input.data.paymentResult (or whatever field you choose).
```
with:
```python
External API then injects into Cognigy via the REST endpoint (same channel as talk_to_agent):
  POST https://cognigy-endpoint-{env}.nicecxone.com/{urlToken}
  {
    "userId": "<userId from SESSION>",
    "sessionId": "<sessionId from SESSION>",
    "text": "",
    "data": { "paymentResult": { "success": "true", "reference": "PAY-123" } }
  }

IMPORTANT: The management API path POST /v2.0/projects/{projectId}/sessions/{sessionId}
does NOT exist on AU1 (returns 404). The correct injection path is the REST endpoint host,
not the management API. The xApp HTML's SESSION object already contains the urlToken,
userId, and sessionId needed to construct this call.

Injected payload arrives as input.data.paymentResult (or whatever field you choose).
```

- [ ] **Step 7: Run the regression tests — confirm all pass**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py -v 2>&1 | tail -30
```

Expected: All tests pass (including the 11 new ones and all pre-existing tests).

- [ ] **Step 8: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/cognigy_mcp/tools/explain.py
git add cognigy-mcp/tests/tools/test_explain.py
git commit -m "$(cat <<'EOF'
fix: correct IF node type string, xApp extensions, and Variant B inject path in explain docs

Fixes issues #14, #21, and the xapp-event-handling Variant B doc bug:
- flow-chart-reading: type is 'if' not 'ifThenElse'; nodes ARE createable via cognigy_create; correct condition config schema
- extension-map/node-types/node-wiring/xapp-delivery: xApp extension is @cognigy/basic-nodes not cxone-utils (confirmed on 4 live nodes)
- xapp-event-handling: Variant B inject path is REST endpoint host, not management API (which 404s on AU1)
- node-wiring: relation fields are node/next/children, not nodeId/nextId/childIds
EOF
)"
```

---

## Task 3: Add data parameter to talk_to_agent (#15)

`data` is already sent in every REST payload as `{}`. This task exposes it as a caller-controlled parameter and makes `message` optional so data-only turns (xApp submit emulation) work.

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/testing.py`
- Modify: `cognigy-mcp/tests/tools/test_testing.py`

- [ ] **Step 1: Write failing tests**

Append to `cognigy-mcp/tests/tools/test_testing.py`:

```python
def test_talk_to_agent_sends_data_param_in_payload(real_client, state, cache):
    """data param must be forwarded in the REST POST body."""
    handlers = make_handlers(real_client, state, cache)
    captured = {}
    with respx.mock:
        def capture(request):
            import json
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"text": "ok", "data": {}})
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(side_effect=capture)
        handlers["talk_to_agent"]({
            "message": "",
            "endpoint_token": "tok123",
            "session_id": "sess-data",
            "user_id": "user-data",
            "data": {"selectedStore": "Repco Cheltenham", "selectedQuantity": 2},
        })
    assert captured["body"]["data"] == {
        "selectedStore": "Repco Cheltenham",
        "selectedQuantity": 2,
    }, "data param must be forwarded to POST body"
    assert captured["body"]["text"] == "", "message defaults to empty string"


def test_talk_to_agent_data_defaults_to_empty_dict_when_omitted(real_client, state, cache):
    """When data is not provided, POST body must have data: {}."""
    handlers = make_handlers(real_client, state, cache)
    captured = {}
    with respx.mock:
        def capture(request):
            import json
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"text": "Hi!", "data": {}})
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(side_effect=capture)
        handlers["talk_to_agent"]({
            "message": "Hello",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
        })
    assert captured["body"]["data"] == {}, "data must default to {}"


def test_talk_to_agent_message_optional_when_data_provided(real_client, state, cache):
    """talk_to_agent must not raise when message is absent and data is provided."""
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={"text": "Noted.", "data": {}})
        )
        # No "message" key at all — should not raise KeyError
        result = handlers["talk_to_agent"]({
            "endpoint_token": "tok123",
            "session_id": "sess-xapp",
            "user_id": "user-xapp",
            "data": {"xappField": "value"},
        })
    data = json.loads(result[0].text)
    assert "error" not in data, f"Should not error on missing message: {data}"
```

- [ ] **Step 2: Run tests — confirm all three new tests fail**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_testing.py -v -k "data_param or data_defaults or message_optional" 2>&1 | tail -20
```

Expected: 3 FAILED — `KeyError: 'message'` on the third, wrong `data` value on the first.

- [ ] **Step 3: Update testing.py**

In `cognigy-mcp/cognigy_mcp/tools/testing.py`, replace the full `TOOLS` list and handler:

Replace the `Tool(name="talk_to_agent", ...)` block (lines 10–37) with:

```python
    Tool(
        name="talk_to_agent",
        description="Send a message to a Cognigy flow via its REST endpoint and return the response. "
                    "Use for testing flows without opening the Cognigy UI. "
                    "Provide endpoint_token (from get_build_state) or flow_id (looks up token from state). "
                    "IMPORTANT: Use a new user_id to start a completely fresh session — Cognigy caches "
                    "session state by userId and reusing one will carry stale context silently. "
                    "IMPORTANT: This tool returns text output only. Tool calls made by the agent are "
                    "NOT visible in the response — only the agent's spoken text is returned. "
                    "For xApp submit emulation: send message=\"\" and data={...submitted payload...}. "
                    "Pass data={verbose: true} in the request body to surface errors that are otherwise swallowed.",
        inputSchema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "User text. Use empty string for data-only turns (xApp submit emulation)."},
                "endpoint_token": {"type": "string", "description": "URL token from endpoint config"},
                "flow_id": {"type": "string", "description": "Looks up token from state if endpoint_token not provided"},
                "session_id": {"type": "string", "description": "Conversation session ID — reuse to continue, new to reset"},
                "user_id": {"type": "string", "description": "User ID — new value starts fresh session"},
                "data": {
                    "type": "object",
                    "description": "Optional data payload forwarded as input.data in the flow. Use for xApp submit emulation: pass the sdk.submit() payload here with message=\"\".",
                },
                "minimal": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, returns only {outputText, sessionId} (~90% token savings). Default false returns full response.",
                },
            },
            "required": ["session_id", "user_id"],
        },
    ),
```

In the `_talk_to_agent` handler (lines 46–91), replace:
```python
        message = args["message"]
```
with:
```python
        message = args.get("message", "")
```

And replace the hardcoded `"data": {}`:
```python
        payload = {
            "userId": user_id,
            "sessionId": session_id,
            "text": message,
            "data": {},
        }
```
with:
```python
        payload = {
            "userId": user_id,
            "sessionId": session_id,
            "text": message,
            "data": args.get("data") or {},
        }
```

- [ ] **Step 4: Run all testing.py tests — confirm all pass**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_testing.py -v 2>&1 | tail -25
```

Expected: All tests pass. The three new tests should now be GREEN. Existing tests must remain green (message is no longer required, so tests that pass `"message": "Hi"` still work fine).

- [ ] **Step 5: Run full test suite — confirm nothing regressed**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest -v 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/cognigy_mcp/tools/testing.py
git add cognigy-mcp/tests/tools/test_testing.py
git commit -m "$(cat <<'EOF'
fix: expose data param in talk_to_agent for xApp submit emulation (#15)

data was already sent as {} on every call — now caller-controlled.
message is now optional (defaults to "") so data-only turns work without
specifying empty string explicitly. Required for testing xApp sdk.submit()
return events where input.text is empty and input.data holds the payload.
EOF
)"
```

---

## Task 4: Bump versions

**Files:**
- Modify: `cognigy-mcp/pyproject.toml`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump cognigy-mcp version**

In `cognigy-mcp/pyproject.toml`, replace:
```toml
version = "1.3.3"
```
with:
```toml
version = "1.3.4"
```

- [ ] **Step 2: Bump plugin version**

In `.claude-plugin/plugin.json`, replace:
```json
  "version": "1.3.3",
```
with:
```json
  "version": "1.3.4",
```

- [ ] **Step 3: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "chore: bump version to 1.3.4"
```

---

## Self-Review

**Spec coverage:**
- #14 (IF node type, creation, config schema): Task 1 tests + Task 2 Step 1 ✓
- #21 (xApp cxone-utils → @cognigy/basic-nodes): Task 1 tests + Task 2 Steps 2–5 ✓
- #15 code (data param, optional message): Task 3 ✓
- #15 doc (Variant B inject path): Task 1 test + Task 2 Step 6 ✓
- node-wiring relation field names: Task 1 test + Task 2 Step 2 ✓

**Placeholder scan:** No TBDs, no "add appropriate error handling", all test assertions are specific and checkable.

**Type consistency:** No new types introduced. `args.get("data") or {}` returns `dict` matching the existing `"data": {}` type in the payload. `args.get("message", "")` returns `str` matching the existing `message: str` usage downstream.
