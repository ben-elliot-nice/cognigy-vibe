# Say Node Schema Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `say-node` explain topic documenting the correct say node config schema — `text` is a plain string array, not an array of objects — with regression tests to prevent re-introduction.

**Architecture:** Add a new `say-node` topic to `cognigy-mcp/cognigy_mcp/tools/explain.py` (TOPICS list, `_TOPIC_INDEX`, and `_CONTENT`). Add a cross-reference note in the existing `node-types` topic. Write regression tests in `cognigy-mcp/tests/tools/test_explain.py`.

**Tech Stack:** Python, pytest, cognigy-mcp explain tool.

---

### Task 1: Write failing regression tests

**Files:**
- Modify: `cognigy-mcp/tests/tools/test_explain.py`

- [ ] **Step 1: Add the failing tests to test_explain.py**

Append the following to `cognigy-mcp/tests/tools/test_explain.py`:

```python
# ── Issue #34: say node config schema ───────────────────────────────────────

def test_say_node_topic_exists(mock_client, state, cache):
    """say-node must be a recognised explain topic."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "say-node"})
    text = result[0].text
    assert "Unknown topic" not in text, "say-node must be a known topic"
    assert len(text) > 100


def test_say_node_text_is_string_array(mock_client, state, cache):
    """say-node must document text as a plain string array, not array of objects."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "say-node"})
    text = result[0].text
    # Correct form — plain string in array
    assert '"text": ["' in text, \
        'say-node must show text as a plain string array, e.g. "text": ["Hello"]'
    # Must not show the wrong object-in-array form
    assert '"text": [{"type"' not in text, \
        'say-node must not document text as array of objects'
    assert '"text": [{"content"' not in text, \
        'say-node must not document text as array of objects with content key'


def test_say_node_required_fields_documented(mock_client, state, cache):
    """say-node must document the required _cognigy and _data fields."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "say-node"})
    text = result[0].text
    assert '"_cognigy": {}' in text, "say-node must document _cognigy: {}"
    assert '"_data"' in text, "say-node must document _data field"
    assert '"_cognigy": {}' in text, "say-node must document _data._cognigy: {}"


def test_say_node_generative_ai_custom_inputs_is_array(mock_client, state, cache):
    """say-node must document generativeAI_customInputs as empty array, not empty string."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "say-node"})
    text = result[0].text
    assert 'generativeAI_customInputs' in text, \
        "say-node must mention generativeAI_customInputs"
    assert '"generativeAI_customInputs": []' in text, \
        "say-node must document generativeAI_customInputs as empty array []"
    assert '"generativeAI_customInputs": ""' not in text, \
        "say-node must not document generativeAI_customInputs as empty string"


def test_node_types_references_say_node_topic(mock_client, state, cache):
    """node-types must cross-reference say-node topic for config schema."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-types"})
    text = result[0].text
    assert "say-node" in text, \
        'node-types must reference explain("say-node") for say node config schema'
```

- [ ] **Step 2: Run failing tests to confirm RED state**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py::test_say_node_topic_exists tests/tools/test_explain.py::test_say_node_text_is_string_array tests/tools/test_explain.py::test_say_node_required_fields_documented tests/tools/test_explain.py::test_say_node_generative_ai_custom_inputs_is_array tests/tools/test_explain.py::test_node_types_references_say_node_topic -v
```

Expected: all 5 tests FAIL.

---

### Task 2: Add say-node topic to explain.py

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py`

- [ ] **Step 1: Add "say-node" to the TOPICS list**

In `explain.py`, find the `TOPICS` list (line 10). Add `"say-node"` after `"node-types"`:

```python
TOPICS = [
    "node-positioning", "node-wiring", "agent-tool-branch", "node-config-update",
    "flow-chart-reading", "tool-conditions", "two-pass-confirm", "turn-structure",
    "xapp-delivery", "xapp-event-handling", "cognigyScript", "code-node-patterns", "voice-gateway",
    "outbound-trigger", "knowledge-store", "endpoint-config", "function-execution",
    "session-injection", "extension-map", "node-types", "say-node", "mcp-comparison", "tool-selection",
    "project-snapshots",
]
```

- [ ] **Step 2: Add say-node entry to _TOPIC_INDEX**

In `_TOPIC_INDEX`, add the `say-node` line after the `node-types` line:

```
  node-types           quick reference for all node type strings
  say-node             say node config schema: correct text field, required _cognigy/_data fields, generativeAI_customInputs
```

- [ ] **Step 3: Add say-node content to _CONTENT**

Add the following entry to `_CONTENT` after the `"node-types"` entry:

```python
    "say-node": """
## say-node — Say Node Config Schema

### CRITICAL: text must be a plain string array

The say node's config.say.text field is a plain string array — NOT an array of objects.

WRONG (causes [object Object] in output):
  "config": {
    "say": {
      "text": [{"type": "text", "content": "Hello, how can I help?"}]
    }
  }

CORRECT:
  "config": {
    "say": {
      "text": ["Hello, how can I help?"]
    }
  }

### Full minimal config with all required fields

  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "say",
    "label": "Greeting",
    "mode": "append",
    "target": "<previousNodeId>",
    "config": {
      "say": {
        "text": ["Hello, how can I help you today?"],
        "type": "text",
        "data": "",
        "linear": false,
        "loop": false,
        "_cognigy": {},
        "_data": {"_cognigy": {}}
      },
      "generativeAI_customInputs": []
    }
  })

### Required fields
- "text": ["..."]              — plain string array; one string per output variation
- "type": "text"               — output type; always "text" for standard text output
- "data": ""                   — data payload; empty string is valid
- "linear": false              — whether to cycle through text variants linearly
- "loop": false                — whether to loop back to first variant after last
- "_cognigy": {}               — internal Cognigy metadata; must be present as empty object
- "_data": {"_cognigy": {}}    — internal data wrapper; must be present with _cognigy key
- "generativeAI_customInputs": []  — empty array (NOT empty string "")

### Using CognigyScript in say text
CognigyScript interpolation works in the say node text field:
  "text": ["Hello {{context.shortTermMemory.customerName}}, how can I help?"]

### Multiple output variations (random selection)
  "text": ["Hello! How can I help?", "Hi there! What can I do for you?"]
Cognigy picks one at random each time the node fires.
With "linear": true — cycles through in order instead of random selection.

### Common mistake
Passing a string directly instead of an array:
  WRONG: "text": "Hello"
  CORRECT: "text": ["Hello"]
""",
```

- [ ] **Step 4: Add cross-reference in node-types topic**

In the `"node-types"` content block, find the line:
```
  say               Speak text
```
Replace it with:
```
  say               Speak text (config schema: explain("say-node"))
```

- [ ] **Step 5: Run the failing tests to confirm GREEN state**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py::test_say_node_topic_exists tests/tools/test_explain.py::test_say_node_text_is_string_array tests/tools/test_explain.py::test_say_node_required_fields_documented tests/tools/test_explain.py::test_say_node_generative_ai_custom_inputs_is_array tests/tools/test_explain.py::test_node_types_references_say_node_topic -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/explain.py cognigy-mcp/tests/tools/test_explain.py
git commit -m "fix: document correct say node config schema in explain say-node topic (#34)"
```

---

### Task 3: Bump versions

**Files:**
- Modify: `cognigy-mcp/pyproject.toml` — `version = "1.3.9"` → `version = "1.3.10"`
- Modify: `.claude-plugin/plugin.json` — `"version": "1.3.9"` → `"version": "1.3.10"`

- [ ] **Step 1: Bump cognigy-mcp/pyproject.toml**

Change `version = "1.3.9"` to `version = "1.3.10"`.

- [ ] **Step 2: Bump .claude-plugin/plugin.json**

Change `"version": "1.3.9"` to `"version": "1.3.10"`.

- [ ] **Step 3: Commit version bump**

```bash
git add cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "chore: bump version to 1.3.10"
```

- [ ] **Step 4: Push**

```bash
git push
```
