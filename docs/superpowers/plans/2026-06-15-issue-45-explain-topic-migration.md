# Issue #45: Explain Topic Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all 24 legacy explain topics plus the new `voice-silence-timeout` topic into the `skills/explain/resources/` markdown-file framework, apply runtime-reference overlays, apply issue corrections, then promote `explain_dev` to replace `explain` and retire the inline content strings.

**Architecture:** A one-time extraction script reads `explain.py`'s inline `_CONTENT` dict and writes 20 resource files into `skills/explain/resources/`. Layer-2 overlays then rewrite `code-node-patterns` with richer runtime-reference content and add a new `output-formats` topic. Layer-3 corrections apply targeted fixes from issues #40, #41, and #42. After all 25+ topics are in resource files, `explain.py` is refactored to import from the generated module, the inline dicts are deleted, and `explain_dev` is retired.

**Tech Stack:** Python 3.11+ stdlib. Scripts established by POC (issue #44). pytest. uv.

**Prerequisites — verify these exist before starting:**
- `skills/explain/resources/` containing `code-node-patterns.md`, `xapp/index.md`, `xapp/delivery.md`, `xapp/event-handling.md`
- `scripts/build_explain_topics.py`
- `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py`
- `explain_dev` tool registered in `cognigy-mcp/cognigy_mcp/tools/explain.py`

If any are missing, merge issue #44's plan first.

---

## File Map

| Action | Path | Source |
|--------|------|--------|
| Create | `scripts/extract_explain_topics.py` | One-time extraction script |
| Create | `skills/explain/resources/nodes/node-positioning.md` | L1: explain.py |
| Create | `skills/explain/resources/nodes/node-wiring.md` | L1: explain.py |
| Create | `skills/explain/resources/nodes/node-config-update.md` | L1: explain.py |
| Create | `skills/explain/resources/nodes/node-types.md` | L1: explain.py |
| Create | `skills/explain/resources/nodes/flow-chart-reading.md` | L1: explain.py |
| Create | `skills/explain/resources/aiagent/agent-tool-branch.md` | L1: explain.py |
| Create | `skills/explain/resources/aiagent/tool-conditions.md` | L1: explain.py |
| Create | `skills/explain/resources/aiagent/two-pass-confirm.md` | L1: explain.py |
| Create | `skills/explain/resources/aiagent/turn-structure.md` | L1: explain.py |
| Create | `skills/explain/resources/aiagent/tool-selection.md` | L1: explain.py |
| Create | `skills/explain/resources/code/cognigyScript.md` | L1: explain.py |
| Create | `skills/explain/resources/code/function-execution.md` | L1: explain.py |
| Create | `skills/explain/resources/code/session-injection.md` | L1: explain.py |
| Create | `skills/explain/resources/voice/voice-gateway.md` | L1: explain.py |
| Create | `skills/explain/resources/platform/say-node.md` | L1: explain.py |
| Create | `skills/explain/resources/platform/outbound-trigger.md` | L1: explain.py |
| Create | `skills/explain/resources/platform/knowledge-store.md` | L1: explain.py |
| Create | `skills/explain/resources/platform/endpoint-config.md` | L1: explain.py |
| Create | `skills/explain/resources/platform/extension-map.md` | L1: explain.py |
| Create | `skills/explain/resources/platform/mcp-comparison.md` | L1: explain.py |
| Create | `skills/explain/resources/platform/project-snapshots.md` | L1: explain.py |
| Rewrite | `skills/explain/resources/code-node-patterns.md` | L2: merged with runtime-reference |
| Create | `skills/explain/resources/code/output-formats.md` | L2: from cognigy-output-formats.md |
| Modify | `skills/explain/resources/xapp/event-handling.md` | L3: issue #40 payload path fix |
| Create | `skills/explain/resources/voice/voice-silence-timeout.md` | L3: issue #41 new topic |
| Modify | `skills/explain/resources/code-node-patterns.md` | L3: issue #42 api.addToInput removal |
| Modify | `runtime-reference/cognigy-api-reference.md` | L3: issue #42 api.addToInput removal |
| Rewrite | `cognigy-mcp/cognigy_mcp/tools/explain.py` | Promotion: import from generated module |
| Delete | `cognigy-mcp/tests/tools/test_explain_dev.py` | Retire migration scaffold tests |
| Modify | `cognigy-mcp/tests/tools/test_explain.py` | Add regression tests for corrections |

---

## Task 1: Extract 20 legacy topics via one-time script

**Files:**
- Create: `scripts/extract_explain_topics.py`
- Creates: `skills/explain/resources/nodes/` (5 files)
- Creates: `skills/explain/resources/aiagent/` (5 files)
- Creates: `skills/explain/resources/code/` (3 files)
- Creates: `skills/explain/resources/voice/` (1 file)
- Creates: `skills/explain/resources/platform/` (7 files)

- [ ] **Step 1: Create extraction script**

Create `scripts/extract_explain_topics.py`:

```python
#!/usr/bin/env python3
"""One-time script: extract legacy explain.py inline topics into resource markdown files.

Run once from repo root with: uv run scripts/extract_explain_topics.py
"""
from __future__ import annotations
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EXPLAIN_PY = REPO_ROOT / "cognigy-mcp" / "cognigy_mcp" / "tools" / "explain.py"
RESOURCES = REPO_ROOT / "skills" / "explain" / "resources"

# (relative_output_path, description, group)
TOPIC_MAP: dict[str, tuple[str, str, str]] = {
    "node-positioning":  ("nodes/node-positioning.md",  "append vs appendChild modes, child branch population, insertAfter + insertBefore 500 bug on AU1, insert-before workaround", "nodes"),
    "node-wiring":       ("nodes/node-wiring.md",        "chart structure, relations array, sequential vs child chains", "nodes"),
    "node-config-update":("nodes/node-config-update.md", "full-replace semantics, merge_config pattern, silent field deletion", "nodes"),
    "node-types":        ("nodes/node-types.md",         "quick reference for all node type strings", "nodes"),
    "flow-chart-reading":("nodes/flow-chart-reading.md", "reading chart output, node type strings, extension field", "nodes"),
    "agent-tool-branch": ("aiagent/agent-tool-branch.md","aiAgentJobTool + code + toolAnswer assembly, tool args access", "aiagent"),
    "tool-conditions":   ("aiagent/tool-conditions.md",  "CognigyScript condition field, hiding tools from LLM", "aiagent"),
    "two-pass-confirm":  ("aiagent/two-pass-confirm.md", "inter-turn flag management, STOP gate wording", "aiagent"),
    "turn-structure":    ("aiagent/turn-structure.md",   "Once/OnFirstTime/Afterwards, input.execution, context reset prevention, child branch API patterns", "aiagent"),
    "tool-selection":    ("aiagent/tool-selection.md",   "when to use push_code_node vs cognigy_create vs cognigy_update", "aiagent"),
    "cognigyScript":     ("code/cognigyScript.md",       "interpolation contexts, what works where", "code"),
    "function-execution":("code/function-execution.md",  "async pattern, inject-back via sessions API", "code"),
    "session-injection": ("code/session-injection.md",   "context/state inject for in-session testing", "code"),
    "voice-gateway":     ("voice/voice-gateway.md",      "VG endpoint routing, Set Session Config, SIP headers, DTMF", "voice"),
    "say-node":          ("platform/say-node.md",        "say node config schema: correct text field, required _cognigy/_data fields, generativeAI_customInputs", "platform"),
    "outbound-trigger":  ("platform/outbound-trigger.md","6-step CXone trigger, Accept-Encoding: identity requirement", "platform"),
    "knowledge-store":   ("platform/knowledge-store.md", "chunking, connector run, source management", "platform"),
    "endpoint-config":   ("platform/endpoint-config.md", "referenceId vs _id gotcha, urlToken caching", "platform"),
    "extension-map":     ("platform/extension-map.md",   "complete type → extension lookup table", "platform"),
    "mcp-comparison":    ("platform/mcp-comparison.md",  "when to use cognigy-vibe vs NiCE official MCP", "platform"),
    "project-snapshots": ("platform/project-snapshots.md","create project snapshots for versioning (flow-level versioning does not exist in the API)", "platform"),
}

# Topics already handled by the POC — skip them
POC_TOPICS = {"code-node-patterns", "xapp", "xapp-delivery", "xapp-event-handling"}


def extract_topics(source: str) -> dict[str, str]:
    """Extract all triple-quoted topic bodies from _CONTENT dict in explain.py."""
    pattern = re.compile(r'"([a-z][a-z0-9-]+)":\s*"""(.*?)""",', re.DOTALL)
    return {m.group(1): m.group(2) for m in pattern.finditer(source)}


def main() -> None:
    source = EXPLAIN_PY.read_text(encoding="utf-8")
    topics = extract_topics(source)
    print(f"Found {len(topics)} topics in explain.py")

    created = 0
    for topic, (rel_path, description, group) in TOPIC_MAP.items():
        if topic in POC_TOPICS:
            print(f"  SKIP (POC): {topic}")
            continue
        if topic not in topics:
            print(f"  ERROR: topic not found in explain.py: {topic}")
            continue
        out_path = RESOURCES / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        body = topics[topic].strip()
        content = f"---\ntopic: {topic}\ndescription: {description}\ngroup: {group}\n---\n\n{body}\n"
        out_path.write_text(content, encoding="utf-8")
        print(f"  Created: skills/explain/resources/{rel_path}")
        created += 1

    print(f"Done. {created} files created.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run extraction script**

```bash
uv run scripts/extract_explain_topics.py
```

Expected output:
```
Found 24 topics in explain.py
  SKIP (POC): code-node-patterns
  SKIP (POC): xapp
  SKIP (POC): xapp-delivery
  SKIP (POC): xapp-event-handling
  Created: skills/explain/resources/nodes/node-positioning.md
  ... (17 more lines)
Done. 20 files created.
```

- [ ] **Step 3: Verify file count**

```bash
find skills/explain/resources -name "*.md" | sort
```

Expected: 24 files total (4 from POC + 20 new).

- [ ] **Step 4: Run build script**

```bash
uv run scripts/build_explain_topics.py
```

Expected output ends with: `Done. 24 topic(s) processed.`

- [ ] **Step 5: Update the explain_dev test that asserts node-positioning is unknown**

The existing `cognigy-mcp/tests/tools/test_explain_dev.py` has a test `test_explain_dev_does_not_serve_legacy_content` that asserts `explain_dev("node-positioning")` returns "Unknown topic". After this task, node-positioning IS a migrated topic and will return content, causing the test to fail. Update it:

Find this test in `cognigy-mcp/tests/tools/test_explain_dev.py`:
```python
def test_explain_dev_does_not_serve_legacy_content(mock_client, state, cache):
    """explain_dev must return an error for topics that only exist in the legacy explain tool."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "node-positioning"})
    text = result[0].text
    assert "Unknown topic" in text
    # Legacy content for node-positioning starts with this heading
    assert "Inserting and Moving Nodes" not in text
```

Replace with:
```python
def test_explain_dev_unknown_topic_returns_error(mock_client, state, cache):
    """explain_dev must return an error for topics that don't exist at all."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "definitely-not-a-real-topic"})
    text = result[0].text
    assert "Unknown topic" in text
    assert "definitely-not-a-real-topic" in text
```

- [ ] **Step 6: Run full test suite**

```bash
cd cognigy-mcp
uv run pytest -v
```

Expected: all tests pass. If `test_explain_dev_known_topic_returns_content` now iterates 24 topics and all pass, the extraction was successful.

- [ ] **Step 7: Commit**

```bash
git add scripts/extract_explain_topics.py skills/explain/resources/ cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py skills/explain/SKILL.md cognigy-mcp/tests/tools/test_explain_dev.py
git commit -m "feat: extract 20 legacy explain topics into resources framework (layer 1)"
```

---

## Task 2: Layer 2 — Rewrite code-node-patterns with runtime-reference content

**Files:**
- Rewrite: `skills/explain/resources/code-node-patterns.md`
- Reference: `runtime-reference/cognigy-api-reference.md`
- Reference: `runtime-reference/cognigy-code-conventions.md`

This task merges the two runtime-reference files into `code-node-patterns`, producing the authoritative reference for code node authoring. The runtime-reference content takes precedence over the existing POC content where they conflict.

- [ ] **Step 1: Rewrite `skills/explain/resources/code-node-patterns.md`**

Replace the entire file with this content:

```markdown
---
topic: code-node-patterns
description: api.* functions, execution model, utility functions (getVar/setVar/mergeVar), as const bug, httpRequest .result
---

## code-node-patterns — Writing Cognigy Code Nodes

### Execution Model

- Flow waits until the code node finishes
- 1 second maximum execution time (non-configurable)
- No top-level `await` — wrap async logic in `async function main() {}`
- No `import` or `require` — sandboxed scope, no module loading
- No `console.log` — use `api.log()` instead
- Maximum 100 `api.*` calls per node
- Uncaught errors halt flow execution; timeout errors write to `input.codeNodeError.message`

### NOT available

  fetch()          // NO — use HTTP Request node for outbound HTTP
  require()        // NO — no module system
  import           // NO — not ES modules
  console.log()    // NO — use api.log() instead

### API Functions

#### Output
  api.say('Hello!')                  // send reply to user
  api.output('Hello!', data?)        // alias for api.say()

For channel-specific output (quick replies, buttons, gallery) pass a `_cognigy` payload as `data`.
See explain('output-formats') for all supported shapes.

#### Context
  api.setContext('key', value)
  api.getContext('key')
  api.addToContext('key', value, 'simple' | 'array')
  api.removeFromContext('key')
  api.deleteContext('key')
  api.resetContext()
  api.getConversationTranscript()

#### Flow Control
  api.setNextNode('nodeId')          // override next node in execution path
  api.stopExecution()                // halt flow
  api.addConditionalEntrypoint()     // trigger flow on conditional event
  api.resetNextNodes()               // clear navigation overrides

#### Logging & Analytics
  api.log('debug' | 'info' | 'error', message)
  api.completeGoal('goalName')
  api.trackAnalyticsStep('stepName')
  api.getLLMTokenUsageForSession()

#### Input Enrichment
DO NOT use api.addToInput() — it is unreliable and causes transpile errors.
Use the setVar/mergeVar utility functions instead:
  await setVar('input.smsNumber', number)
  await mergeVar('input.requestPayload', { url, method, body })

#### Profile
  api.updateProfile('fieldName', value)
  api.addContactMemory({ label: 'key', value: 'val' })
  api.activateProfile()
  api.deactivateProfile()
  api.deleteProfile()
  api.mergeProfile('targetProfileId')

#### Handover
  api.handover('provider', options?)

#### xApps
  api.setAppState(stateObject)       // non-HTML state only; does NOT push HTML

#### CognigyScript
  api.parseCognigyScript('{{ input.text }}')
  api.parseCognigyScriptCondition('{{ input.slots.city.value == "Sydney" }}')
  api.parseCognigyScriptText('Hello {{ input.text }}!')

### Available Libraries

  _                  // lodash (full docs: lodash.com/docs/4.17.10)
  moment             // date/time (full docs: momentjs.com/docs)
  xmljs              // XML parsing: xmljs.xml2json(str, {compact: true, spaces: 4})
  getTextCleaner     // text utilities: getTextCleaner('en-US', {}).clean(input.text)

### TypeScript Pitfalls

#### No "as const"
  // WRONG — Cognigy code nodes don't support TypeScript generics/assertions:
  const STATUS = {PENDING: 'pending'} as const;
  // RIGHT:
  const STATUS = {PENDING: 'pending'};

#### Bare return at top level → transpile error
  return;  // WRONG — "Illegal return statement"
  // Fix: wrap in function, or just omit the return

#### Deep copy before multi-path assignment
  // WRONG — serializer collapses repeated object references:
  context.pathA.data = myObject;
  context.pathB.data = myObject;  // corruption
  // RIGHT:
  context.pathB.data = JSON.parse(JSON.stringify(myObject));

### httpRequest Node Response Wrapping

The httpRequest node wraps its response body under a `.result` key.
  const body = context.httpResponse.result;   // NOT context.httpResponse directly
  // httpResponse shape: {result: {...actualBody}, status: 200, headers: {...}}

### Standard Structure

Every code node follows this layout (main defined first so intent is immediately readable):

  async function main() { ... }

  async function getVar(path, required) { ... }
  async function setVar(path, value) { ... }
  async function mergeVar(path, value) { ... }
  function log(level, ctx, message) { ... }
  function allSettled(promises) { ... }

  main()

Pattern inside main — get all inputs in parallel with allSettled, surface ALL errors at once:

  async function main() {
    const [userIdResult, prefsResult] = await allSettled([
      getVar('input.data.userId', true),
      getVar('context.userPrefs', false)
    ])
    const errors = [userIdResult, prefsResult]
      .filter(r => r.status === 'rejected')
      .map(r => r.reason.message)
    if (errors.length > 0) {
      errors.forEach(e => log('error', 'main', e))
      return
    }
    const userId = userIdResult.value
    const prefs  = prefsResult.value
    // business logic
    await setVar('context.userId', userId)
  }

### Utility Functions (copy into every node that uses them)

  async function getVar(path, required) {
    const parts = path.split('.')
    let val = { input, context }[parts.shift()]
    for (const part of parts) {
      if (val == null) { val = undefined; break }
      val = val[part]
    }
    if (val == null) {
      if (required) return Promise.reject(new Error(`Required: '${path}' is missing or null`))
      return Promise.resolve(null)
    }
    return Promise.resolve(val)
  }

  async function setVar(path, value) {
    const parts = path.split('.')
    const root = parts.shift()
    const key = parts.pop()
    let obj = { input, context }[root]
    for (const part of parts) {
      if (obj[part] == null) obj[part] = {}
      obj = obj[part]
    }
    obj[key] = value
  }

  async function mergeVar(path, value) {
    const parts = path.split('.')
    const root = parts.shift()
    const key = parts.pop()
    let obj = { input, context }[root]
    for (const part of parts) {
      if (obj[part] == null) obj[part] = {}
      obj = obj[part]
    }
    obj[key] = deepMerge(obj[key], value)
    function deepMerge(target, source) {
      if (source === null || typeof source !== 'object' || Array.isArray(source)) return source
      const result = Object.assign({}, target)
      for (const k of Object.keys(source)) {
        const tgt = target != null ? target[k] : undefined
        result[k] = (typeof source[k] === 'object' && source[k] !== null && !Array.isArray(source[k])
          && typeof tgt === 'object' && !Array.isArray(tgt))
          ? deepMerge(tgt, source[k]) : source[k]
      }
      return result
    }
  }

  function allSettled(promises) {
    return Promise.all(promises.map(p =>
      p.then(value  => ({ status: 'fulfilled' as const, value }))
       .catch(reason => ({ status: 'rejected'  as const, reason }))
    ))
  }

  function log(level, ctx, message) {
    const msg = (ctx ? `[${ctx}] ` : '') + (typeof message === 'object' ? JSON.stringify(message) : String(message))
    if (level === 'error') { api.log('error', msg); api.logDebugError(msg) }
    else if (level === 'debug') { api.log('debug', msg); api.logDebugMessage(msg) }
    else { api.log('info', msg) }
  }

### When to use setVar vs mergeVar

| Scenario | Use |
|---|---|
| Writing a primitive | Either |
| Writing an object, keep sibling keys | `mergeVar` |
| Writing an object, clean slate | `setVar` |
| Writing an array | `setVar` |
```

- [ ] **Step 2: Run build script**

```bash
uv run scripts/build_explain_topics.py
```

Expected: `Done. 24 topic(s) processed.`

- [ ] **Step 3: Verify code-node-patterns content is enriched**

```bash
cd cognigy-mcp
uv run python -c "
from cognigy_mcp.tools._explain_topics_generated import _CONTENT
text = _CONTENT['code-node-patterns']
assert 'setVar' in text, 'setVar utility must be present'
assert 'mergeVar' in text, 'mergeVar utility must be present'
assert 'allSettled' in text, 'allSettled utility must be present'
assert 'api.addToInput' not in text, 'api.addToInput must not be present'
assert 'output-formats' in text, 'cross-reference to output-formats must be present'
print('OK')
"
```

- [ ] **Step 4: Run full tests**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/explain/resources/code-node-patterns.md cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py skills/explain/SKILL.md
git commit -m "feat: overlay runtime-reference content into code-node-patterns (layer 2)"
```

---

## Task 3: Layer 2 — Create output-formats topic

**Files:**
- Create: `skills/explain/resources/code/output-formats.md`
- Source: `runtime-reference/cognigy-output-formats.md`

- [ ] **Step 1: Create `skills/explain/resources/code/output-formats.md`**

```markdown
---
topic: output-formats
description: api.say() channel output shapes — quick replies, buttons, gallery, image, audio, adaptive card
group: code
---

## output-formats — Code Node Channel Output Formats

Use with `api.say(text, data)` in code nodes. All formats use the `_cognigy._default` structure,
which Cognigy adapts per channel.

### Text Only

  api.say('Hello, how can I help?')

### Quick Replies

  api.say('What would you like to do?', {
    _cognigy: { _default: { _quickReplies: {
      type: 'quick_replies',
      text: 'What would you like to do?',
      quickReplies: [
        { contentType: 'postback',       payload: 'check_balance', title: 'Check Balance' },
        { contentType: 'postback',       payload: 'transfer',      title: 'Transfer Money' },
        { contentType: 'trigger_intent', payload: 'help',          title: 'Get Help' }
      ]
    }}}
  })

contentType options: postback | phone_number | trigger_intent

### Buttons

  api.say('Choose an option:', {
    _cognigy: { _default: { _buttons: {
      type: 'buttons',
      text: 'Choose an option:',
      buttons: [
        { type: 'postback',     payload: 'yes',             title: 'Yes' },
        { type: 'postback',     payload: 'no',              title: 'No' },
        { type: 'web_url',      url: 'https://example.com', title: 'Learn More' },
        { type: 'phone_number', payload: '+61400000000',     title: 'Call Us' }
      ]
    }}}
  })

### Gallery (Carousel)

  api.say('', {
    _cognigy: { _default: { _gallery: {
      type: 'carousel',
      items: [
        {
          title: 'Product One',
          subtitle: 'Great product',
          imageUrl: 'https://example.com/image1.jpg',
          buttons: [{ type: 'postback', payload: 'buy_one', title: 'Buy Now' }]
        }
      ]
    }}}
  })

### Image

  api.say('', {
    _cognigy: { _default: { _image: {
      type: 'image',
      imageUrl: 'https://example.com/image.jpg'
    }}}
  })

### Audio

  api.say('', {
    _cognigy: { _default: { _audio: {
      type: 'audio',
      audioUrl: 'https://example.com/audio.wav'
    }}}
  })

### Video

  api.say('', {
    _cognigy: { _default: { _video: {
      type: 'video',
      videoUrl: 'https://www.youtube.com/watch?v=example'
    }}}
  })

### List

  api.say('', {
    _cognigy: { _default: { _list: {
      type: 'list',
      items: [
        {
          title: 'Item One',
          subtitle: 'Description',
          imageUrl: 'https://example.com/img.jpg',
          buttons: [{ type: 'postback', payload: 'select_one', title: 'Select' }]
        }
      ],
      button: { type: 'postback', payload: 'view_all', title: 'View All' }
    }}}
  })

### Adaptive Card

  api.say('', {
    _cognigy: { _default: { _adaptiveCard: {
      type: 'adaptiveCard',
      adaptiveCard: {
        type: 'AdaptiveCard',
        version: '1.0',
        body: [
          { type: 'TextBlock', text: 'Hello World', weight: 'bolder', size: 'medium' }
        ],
        actions: [
          { type: 'Action.Submit', title: 'OK', data: { action: 'ok' } }
        ]
      }
    }}}
  })
```

- [ ] **Step 2: Run build script**

```bash
uv run scripts/build_explain_topics.py
```

Expected: `Done. 25 topic(s) processed.`

- [ ] **Step 3: Verify output-formats is accessible**

```bash
cd cognigy-mcp
uv run python -c "
from cognigy_mcp.tools._explain_topics_generated import TOPICS, _CONTENT
assert 'output-formats' in TOPICS
assert 'quick_replies' in _CONTENT['output-formats']
assert 'adaptiveCard' in _CONTENT['output-formats']
print('OK — output-formats topic accessible, %d total topics' % len(TOPICS))
"
```

- [ ] **Step 4: Run full tests**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/explain/resources/code/output-formats.md cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py skills/explain/SKILL.md
git commit -m "feat: add output-formats topic from cognigy-output-formats.md (layer 2)"
```

---

## Task 4: Layer 3 — Fix issue #40: xapp-event-handling Variant A payload path

**Files:**
- Modify: `skills/explain/resources/xapp/event-handling.md`
- Modify: `cognigy-mcp/tests/tools/test_explain_dev.py`

**Problem:** When `sdk.submit(data)` fires in Variant A, Cognigy wraps the submitted object under `input.data._cognigy._app.payload`, not directly under `input.data`. The current content (copied from explain.py) has two locations that use the wrong flat path:
1. The "Submitted payload arrives as input.data" description and example
2. The "IF node conditions" and "Then branch" sections

- [ ] **Step 1: Write failing test**

Add this test to `cognigy-mcp/tests/tools/test_explain_dev.py`:

```python
def test_xapp_event_handling_variant_a_correct_payload_path(mock_client, state, cache):
    """issue #40: Variant A payload is at input.data._cognigy._app.payload, not input.data directly."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "xapp-event-handling"})
    text = result[0].text
    assert "input.data._cognigy._app.payload" in text, \
        "Variant A IF condition must use _cognigy._app.payload path"
    assert '"_cognigy"' in text, \
        "Must show the full input.data structure with _cognigy nesting"
    # Old incorrect flat path must not be present in the IF conditions section
    # (payload.selectedOption is fine inside the code that accesses the extracted payload)
    assert "input.data.selectedOption" not in text, \
        "Old flat path input.data.selectedOption must be gone"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd cognigy-mcp
uv run pytest tests/tools/test_explain_dev.py::test_xapp_event_handling_variant_a_correct_payload_path -v
```

Expected: FAIL — `input.data._cognigy._app.payload` not in text.

- [ ] **Step 3: Apply correction to event-handling.md**

In `skills/explain/resources/xapp/event-handling.md`, find and replace this block (near the end of the Variant A HTML section):

**Find:**
```
Submitted payload arrives as input.data:
  { "selectedOption": "choice-value" }
```

**Replace with:**
```
When sdk.submit({selectedOption: "choice-value"}) fires, the full input.data structure is:
  {
    "_cognigy": {
      "_app": {
        "payload": { "selectedOption": "choice-value" },
        "type": "submit"
      }
    }
  }
Access the submitted values via: input.data._cognigy._app.payload.<field>
```

Then find and replace the IF node conditions section:

**Find:**
```
Variant A: input.data.selectedOption exists
Variant B: input.data.paymentResult exists  (or your chosen field)

### Then branch — extract and store for next turn

Variant A:
  context.shortTermMemory.selectedOption = input.data.selectedOption;
```

**Replace with:**
```
Variant A (SDK.submit): input.data._cognigy._app.payload.<field> neq ""

  Example: input.data._cognigy._app.payload.selectedOption neq ""

Variant B (webhook inject): input.data.paymentResult exists  (or your chosen field)

### Then branch — extract and store for next turn

Variant A:
  var payload = input.data._cognigy._app.payload;
  context.shortTermMemory.selectedOption = payload.selectedOption;
```

- [ ] **Step 4: Run build script**

```bash
uv run scripts/build_explain_topics.py
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd cognigy-mcp
uv run pytest tests/tools/test_explain_dev.py::test_xapp_event_handling_variant_a_correct_payload_path -v
```

Expected: PASS.

- [ ] **Step 6: Run full tests**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add skills/explain/resources/xapp/event-handling.md cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py cognigy-mcp/tests/tools/test_explain_dev.py
git commit -m "fix: correct Variant A xapp payload path to input.data._cognigy._app.payload (issue #40)"
```

---

## Task 5: Layer 3 — Add voice-silence-timeout topic (issue #41)

**Files:**
- Create: `skills/explain/resources/voice/voice-silence-timeout.md`
- Modify: `cognigy-mcp/tests/tools/test_explain_dev.py`

- [ ] **Step 1: Write failing test**

Add to `cognigy-mcp/tests/tools/test_explain_dev.py`:

```python
def test_voice_silence_timeout_topic_exists(mock_client, state, cache):
    """issue #41: voice-silence-timeout topic must be accessible via explain_dev."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "voice-silence-timeout"})
    text = result[0].text
    assert "Unknown topic" not in text
    assert "noUserInput" in text, "Must document noUserInput system intent"
    assert "userNoInputTimeout" in text, "Must document timeout field"
    assert "reprompt" in text.lower(), "Must document reprompt-then-escalate pattern"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd cognigy-mcp
uv run pytest tests/tools/test_explain_dev.py::test_voice_silence_timeout_topic_exists -v
```

Expected: FAIL — "Unknown topic" returned.

- [ ] **Step 3: Create `skills/explain/resources/voice/voice-silence-timeout.md`**

```markdown
---
topic: voice-silence-timeout
description: Voice Gateway silence detection — three modes, noUserInput intent wiring, reprompt-then-escalate counter
group: voice
---

## voice-silence-timeout — User Input Timeout Handling

**Voice flows only.** Chat channels have no native user input timeout — `Wait for Input` pauses indefinitely.

### Configuration

Set on the **Voice Gateway Parameter Details** node or via **Set Session Config**:

| Field | Default | Purpose |
|---|---|---|
| `userNoInputTimeoutEnable` | `true` | Enable/disable silence detection |
| `userNoInputMode` | `"event"` | `event`, `speech`, or `play` |
| `userNoInputTimeout` | `10000` ms | Silence window before triggering |
| `userNoInputRetries` | `5` | Max triggers before call ends |
| `userNoInputSpeech` | — | TTS text (mode: `speech` only) |
| `userNoInputUrl` | — | Audio URL (mode: `play` only) |

### Mode Comparison

| Mode | Flow re-enters? | Who handles reprompt? |
|---|---|---|
| `event` | Yes — via `noUserInput` system intent | Your flow logic |
| `speech` | No | Voice Gateway plays TTS |
| `play` | No | Voice Gateway plays audio file |

Use `event` when the reprompt should vary by context (e.g. different question on each retry).
Use `speech`/`play` for a fixed global reprompt.

### Flow Handling (event mode)

Silence fires a `USER_INPUT_TIMEOUT` event that re-enters the flow via the `noUserInput` system intent.
Discriminating field: `input.data.event === "USER_INPUT_TIMEOUT"`

Wire an Intent node or Default Reply to the `noUserInput` system intent to intercept these turns.

### Reprompt-Then-Escalate Pattern

Use a counter in `context` to track retries and branch after reaching the limit:

  async function main() {
    const count = (await getVar('context.noInputCount', false)) || 0
    await setVar('context.noInputCount', count + 1)
  }

  IF context.noInputCount < 2  → reprompt (Say node repeating the question)
  IF context.noInputCount >= 2 → handover or end call

Reset `context.noInputCount` to 0 in a code node that runs when a real user utterance arrives,
so retries don't carry over between different question steps.

### Deprecation Note

The generic Voice node was deprecated in Cognigy 4.96.0 and scheduled for removal in Q2 2026.
Configure silence timeout via Voice Gateway Parameter Details or Set Session Config instead.
```

- [ ] **Step 4: Run build script**

```bash
uv run scripts/build_explain_topics.py
```

Expected: `Done. 26 topic(s) processed.`

- [ ] **Step 5: Run tests to verify new topic passes**

```bash
cd cognigy-mcp
uv run pytest tests/tools/test_explain_dev.py::test_voice_silence_timeout_topic_exists -v
```

Expected: PASS.

- [ ] **Step 6: Run full tests**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add skills/explain/resources/voice/voice-silence-timeout.md cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py skills/explain/SKILL.md cognigy-mcp/tests/tools/test_explain_dev.py
git commit -m "feat: add voice-silence-timeout topic (issue #41)"
```

---

## Task 6: Layer 3 — Apply issue #42: remove api.addToInput

**Files:**
- Verify: `skills/explain/resources/code-node-patterns.md` (already corrected in Task 2)
- Modify: `runtime-reference/cognigy-api-reference.md`
- Modify: `cognigy-mcp/tests/tools/test_explain_dev.py`

The `code-node-patterns.md` rewritten in Task 2 already excludes `api.addToInput()` and shows `setVar`/`mergeVar` as the replacement. This task corrects the source-of-truth runtime-reference file that agents read before code node tasks, and adds a regression test.

- [ ] **Step 1: Write failing test**

Add to `cognigy-mcp/tests/tools/test_explain_dev.py`:

```python
def test_code_node_patterns_no_addtoinput(mock_client, state, cache):
    """issue #42: api.addToInput must not appear in code-node-patterns; setVar/mergeVar must."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "code-node-patterns"})
    text = result[0].text
    assert "api.addToInput" not in text, \
        "api.addToInput must be removed — it is unreliable and causes transpile errors"
    assert "setVar" in text, "setVar utility must be documented as the replacement"
    assert "mergeVar" in text, "mergeVar utility must be documented as the replacement"
```

- [ ] **Step 2: Run test to verify it passes (Task 2 already fixed this)**

```bash
cd cognigy-mcp
uv run pytest tests/tools/test_explain_dev.py::test_code_node_patterns_no_addtoinput -v
```

Expected: PASS (Task 2's rewrite already removed api.addToInput). If it fails, the Task 2 rewrite was incomplete — re-check `skills/explain/resources/code-node-patterns.md` and re-run the build script.

- [ ] **Step 3: Remove api.addToInput from `runtime-reference/cognigy-api-reference.md`**

In `runtime-reference/cognigy-api-reference.md`, find the Input Enrichment section:

**Find:**
```markdown
### Input Enrichment
```js
api.addToInput('key', value)     // add data to input for downstream nodes
```
```

**Replace with:**
```markdown
### Input Enrichment

Do NOT use `api.addToInput()` — it is unreliable in code nodes and causes transpile errors.
Write to `input` using the `setVar`/`mergeVar` utility functions instead:

```js
await setVar('input.smsNumber', number)
await mergeVar('input.requestPayload', { url, method, headers, body })
```

`input` properties are turn-scoped: they reset on every new message, unlike `context`.
```

- [ ] **Step 4: Add deprecation notice to runtime-reference files**

At the top of `runtime-reference/cognigy-api-reference.md`, after the first heading, add:

```markdown
> **Deprecated:** This file is superseded by `explain("code-node-patterns")` in cognigy-vibe-mcp.
> Read this for legacy reference only. The MCP explain tool is the authoritative source.
```

At the top of `runtime-reference/cognigy-code-conventions.md`, after the first heading, add:

```markdown
> **Deprecated:** This file is superseded by `explain("code-node-patterns")` in cognigy-vibe-mcp.
> Read this for legacy reference only. The MCP explain tool is the authoritative source.
```

At the top of `runtime-reference/cognigy-output-formats.md`, after the first heading, add:

```markdown
> **Deprecated:** This file is superseded by `explain("output-formats")` in cognigy-vibe-mcp.
> Read this for legacy reference only. The MCP explain tool is the authoritative source.
```

- [ ] **Step 5: Run full tests**

```bash
cd cognigy-mcp
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add runtime-reference/ cognigy-mcp/tests/tools/test_explain_dev.py
git commit -m "fix: remove api.addToInput from runtime-reference and mark files deprecated (issue #42)"
```

---

## Task 7: Promote explain_dev → explain, retire inline strings

**Files:**
- Rewrite: `cognigy-mcp/cognigy_mcp/tools/explain.py`
- Delete: `cognigy-mcp/tests/tools/test_explain_dev.py`
- Modify: `cognigy-mcp/tests/tools/test_explain.py`

Now that all 26 topics are in resource files and the generated module has them all, replace `explain.py`'s inline dicts with imports from the generated module, remove `explain_dev`, and clean up tests.

- [ ] **Step 1: Add regression tests to `test_explain.py` before making any code changes**

Add these tests at the end of `cognigy-mcp/tests/tools/test_explain.py`:

```python
def test_all_migrated_topics_accessible_via_explain(mock_client, state, cache):
    """After promotion, explain must serve all 26 topics from the generated module."""
    handlers = make_handlers(mock_client, state, cache)
    for topic in TOPICS:
        result = handlers["explain"]({"topic": topic})
        text = result[0].text
        assert "Unknown topic" not in text, f"explain({topic!r}) returned Unknown topic"
        assert len(text) > 50, f"explain({topic!r}) returned too-short content"


def test_voice_silence_timeout_accessible_via_explain(mock_client, state, cache):
    """voice-silence-timeout must be accessible via the promoted explain tool."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "voice-silence-timeout"})
    text = result[0].text
    assert "noUserInput" in text
    assert "Unknown topic" not in text


def test_xapp_event_handling_variant_a_payload_path_via_explain(mock_client, state, cache):
    """issue #40 regression: explain must serve corrected xapp-event-handling."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "xapp-event-handling"})
    text = result[0].text
    assert "input.data._cognigy._app.payload" in text
    assert "input.data.selectedOption" not in text


def test_explain_dev_tool_removed(mock_client, state, cache):
    """explain_dev was a migration scaffold — it must not exist in TOOLS after promotion."""
    assert not any(t.name == "explain_dev" for t in TOOLS), \
        "explain_dev must be removed from TOOLS after full migration"
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd cognigy-mcp
uv run pytest tests/tools/test_explain.py::test_explain_dev_tool_removed tests/tools/test_explain.py::test_all_migrated_topics_accessible_via_explain -v
```

Expected: `test_explain_dev_tool_removed` FAILS (explain_dev still in TOOLS). `test_all_migrated_topics_accessible_via_explain` may pass or fail depending on whether TOPICS has been updated yet.

- [ ] **Step 3: Rewrite `cognigy-mcp/cognigy_mcp/tools/explain.py`**

Replace the entire file with:

```python
# cognigy_mcp/tools/explain.py
from __future__ import annotations
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.tools._explain_topics_generated import (
    TOPICS,
    _TOPIC_INDEX,
    _CONTENT,
)

TOOLS: list[Tool] = [
    Tool(
        name="explain",
        description=(
            "Retrieve implementation guidance before brute-forcing or web-searching.\n\n"
            "Topics: " + " | ".join(TOPICS) + "\n\n"
            "Call explain() for orientation and topic descriptions.\n"
            "Call explain(\"topic\") for full reference on that topic."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic name from the list above. Omit for orientation overview.",
                },
            },
        },
    ),
]


def _ok(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _explain(args: dict) -> list[TextContent]:
        topic = args.get("topic", "").strip()
        if not topic:
            return _ok("# cognigy-vibe-mcp Reference Library\n\n" + _TOPIC_INDEX)
        content = _CONTENT.get(topic)
        if content:
            return _ok(content.strip())
        return _ok(
            f"Unknown topic: '{topic}'\n\n"
            f"Available Topics:\n{_TOPIC_INDEX}"
        )

    return {"explain": _explain}
```

- [ ] **Step 4: Delete `cognigy-mcp/tests/tools/test_explain_dev.py`**

```bash
rm cognigy-mcp/tests/tools/test_explain_dev.py
```

- [ ] **Step 5: Run full test suite**

```bash
cd cognigy-mcp
uv run pytest -v
```

Expected: all tests pass. The `test_explain.py` tests now cover all 26 topics via the promoted explain tool.

- [ ] **Step 6: Bump versions**

The inline dicts are retired and explain_dev is removed — this is a breaking change for any caller that used `explain_dev`. Bump to the next minor version.

In `cognigy-mcp/pyproject.toml`, change version (e.g. `"1.3.13"` → `"1.4.0"`).
In `.claude-plugin/plugin.json`, change version to match.

- [ ] **Step 7: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/explain.py cognigy-mcp/tests/tools/test_explain.py cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git rm cognigy-mcp/tests/tools/test_explain_dev.py
git commit -m "feat: promote explain_dev to explain, retire inline content dicts (issue #45)"
```

---

## Task 8: Final verification and push

- [ ] **Step 1: Run full test suite one final time**

```bash
cd cognigy-mcp
uv run pytest -v
```

Expected: all tests pass, no warnings.

- [ ] **Step 2: Verify explain is registered in the server tool list**

```bash
cd cognigy-mcp
uv run python -c "
import os
os.environ['COGNIGY_BASE_URL'] = 'http://localhost'
os.environ['COGNIGY_API_KEY'] = 'test'
from cognigy_mcp.server import create_server
_, tools = create_server()
names = [t.name for t in tools]
print('Tools:', names)
assert 'explain' in names, 'explain must be registered'
assert 'explain_dev' not in names, 'explain_dev must be removed'
print('OK — explain registered, explain_dev gone')
"
```

- [ ] **Step 3: Verify topic count**

```bash
cd cognigy-mcp
uv run python -c "
from cognigy_mcp.tools._explain_topics_generated import TOPICS
print(f'{len(TOPICS)} topics total: {TOPICS}')
assert len(TOPICS) >= 26, f'Expected 26+ topics, got {len(TOPICS)}'
print('OK')
"
```

- [ ] **Step 4: Push and update parent repo**

```bash
git push
```

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```

---

## Acceptance Checklist

- [ ] `skills/explain/resources/` contains 26 markdown files across 5 subdirectory groups + flat
- [ ] `scripts/extract_explain_topics.py` ran cleanly and produced 20 files
- [ ] `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py` contains 26 topics
- [ ] `skills/explain/SKILL.md` is generated with all 26 topics in grouped index
- [ ] `explain("code-node-patterns")` returns content including `setVar`, `mergeVar`, `allSettled` utilities
- [ ] `explain("output-formats")` returns all channel format shapes
- [ ] `explain("xapp-event-handling")` uses `input.data._cognigy._app.payload` — NOT `input.data.selectedOption`
- [ ] `explain("voice-silence-timeout")` returns noUserInput + reprompt pattern
- [ ] `explain("code-node-patterns")` contains no `api.addToInput()` reference
- [ ] `runtime-reference/` files all have deprecation notices pointing to explain tool
- [ ] `explain_dev` tool is absent from TOOLS and from the server tool list
- [ ] All `test_explain.py` tests pass including the 4 new regression tests
- [ ] `test_explain_dev.py` is deleted
