# code-node-patterns Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the missing Runtime Objects section to `code-node-patterns.md`, annotate the Context API functions with a preference note for util functions, move the file to the `code/` subdir with `group: code`, and regenerate all derived artifacts.

**Architecture:** The explain skill is source-of-truth for code node authoring. Resource markdown files under `skills/explain/resources/` are compiled by `build_explain_topics.py` into a generated Python module and `SKILL.md`. Moving `code-node-patterns.md` into the `code/` subdir and adding `group: code` to its frontmatter aligns it with all other code-related topics. Adding Runtime Objects content makes `cognigy-api-reference.md` fully redundant (its deprecation notice already points here).

**Tech Stack:** Python (uv), pytest, markdown

## Global Constraints

- Version bump required after any `skills/` change: patch-increment both `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json` (current: `1.4.2` → `1.4.3`)
- Build script run: `uv run scripts/build_explain_topics.py` from repo root
- Tests run: `cd cognigy-mcp && uv run pytest tests/tools/test_explain.py -q`
- Never edit `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py` or `skills/explain/SKILL.md` directly — both are generated
- Do not use `&&` to chain shell commands — each step is a separate Bash call

---

### Task 1: Write failing regression tests for new content

**Files:**
- Modify: `cognigy-mcp/tests/tools/test_explain.py`

**Interfaces:**
- Consumes: existing `make_handlers`, `mock_client`, `state`, `cache` fixtures (already in conftest.py)
- Produces: 4 new test functions that will fail until Task 2 adds the content

- [ ] **Step 1: Append the following tests to `cognigy-mcp/tests/tools/test_explain.py`**

```python
# ── Issue #59: Runtime Objects section in code-node-patterns ────────────────

def test_code_node_patterns_input_object_documented(mock_client, state, cache):
    """code-node-patterns must document the input object property table."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    assert "input.text" in text, "Must document input.text"
    assert "input.slots" in text, "Must document input.slots"
    assert "input.sessionId" in text, "Must document input.sessionId"
    assert "input.userId" in text, "Must document input.userId"
    assert "input.intentScore" in text, "Must document input.intentScore"


def test_code_node_patterns_analyticsdata_documented(mock_client, state, cache):
    """code-node-patterns must document analyticsdata direct assignment."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    assert "analyticsdata" in text, "Must document analyticsdata object"
    assert "custom1" in text, "Must document custom1 through custom10 fields"


def test_code_node_patterns_last_conversation_entries_documented(mock_client, state, cache):
    """code-node-patterns must document lastConversationEntries."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    assert "lastConversationEntries" in text, "Must document lastConversationEntries array"


def test_code_node_patterns_context_prefers_utils_over_api(mock_client, state, cache):
    """code-node-patterns must note that setVar/mergeVar are preferred over api.setContext."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "code-node-patterns"})
    text = result[0].text
    # Must explicitly call out the preference — not just list both equally
    assert "prefer" in text.lower() or "Prefer" in text, \
        "Must state preference for setVar/mergeVar over api.setContext"
    assert "api.setContext" in text, \
        "Must still document api.setContext (it exists, just not preferred)"
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_explain.py -q -k "code_node_patterns"` from the repo root

Expected: 4 FAILED (content not yet in file)

- [ ] **Step 3: Commit the failing tests**

```
git add cognigy-mcp/tests/tools/test_explain.py
git commit -m "test: failing tests for code-node-patterns Runtime Objects (issue #59)"
```

---

### Task 2: Add Runtime Objects section, update Context note, move file, add group: code, rebuild

**Files:**
- Delete: `skills/explain/resources/code-node-patterns.md` (moved via git mv)
- Create: `skills/explain/resources/code/code-node-patterns.md`
- Regenerated: `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py`
- Regenerated: `skills/explain/SKILL.md`

**Interfaces:**
- Consumes: existing file content at `skills/explain/resources/code-node-patterns.md`
- Produces: `skills/explain/resources/code/code-node-patterns.md` with `group: code` frontmatter and new Runtime Objects section; passing tests from Task 1

- [ ] **Step 1: Move the file with git**

Run: `git mv skills/explain/resources/code-node-patterns.md skills/explain/resources/code/code-node-patterns.md`

- [ ] **Step 2: Update frontmatter — add `group: code`**

The current frontmatter (lines 1–4) is:
```
---
topic: code-node-patterns
description: api.* functions, execution model, utility functions (getVar/setVar/mergeVar), as const bug, httpRequest .result
---
```

Replace with:
```
---
topic: code-node-patterns
description: api.* functions, execution model, runtime objects (input/context/profile/analyticsdata), utility functions (getVar/setVar/mergeVar), as const bug, httpRequest .result
group: code
---
```

- [ ] **Step 3: Add Runtime Objects section**

Insert the following block immediately after the `### Execution Model` section (after line 17, before `### NOT available`):

```markdown
### Runtime Objects

These objects are available as globals in every code node.

#### `input`
The incoming message for the current turn. Read-only — use `setVar`/`mergeVar` to write back.

| Property | Description |
|---|---|
| `input.text` | Raw user text |
| `input.data` | Structured payload object |
| `input.intentScore` | NLU intent confidence (0–1) |
| `input.intent` | Matched intent name |
| `input.slots` | Detected NLU slots |
| `input.sessionId` | Session identifier |
| `input.userId` | User identifier |
| `input.flowName` | Name of current flow |
| `input.codeNodeError.message` | Error message if execution timed out |

#### `context`
Session-scoped persistent storage. Survives across turns.

Direct read access: `const val = context.myKey`

For writes, prefer `setVar`/`mergeVar` (see Utility Functions) over `api.setContext`. Use `api.addToContext` only when you need array-push semantics (`'array'` mode).

#### `profile`
Contact profile data (persistent across sessions). Write via `api.updateProfile` or `api.addContactMemory` — no direct mutation equivalent exists yet (tracked in issue #61).

#### `analyticsdata`
Analytics record for the current execution. Write to capture custom analytics.

```js
analyticsdata.custom1 = 'value'   // custom1 through custom10 (max 1024 chars each)
analyticsdata.intent = 'override' // override detected intent in analytics
analyticsdata.inputText = 'text'
```

#### `lastConversationEntries`
Array of the last 10 conversation turns.

```js
const lastTurn = lastConversationEntries[0] // { user: '...', bot: '...' }
```

```

- [ ] **Step 4: Update the Context API functions sub-section**

Find the `#### Context` heading under `### API Functions`. Add the following line immediately after the heading and before the first `api.setContext` line:

```
Prefer `setVar`/`mergeVar` for writes — see Utility Functions below. Use `api.addToContext` with `'array'` mode when you need array-push semantics.
```

- [ ] **Step 5: Run the build script to regenerate derived files**

Run: `uv run scripts/build_explain_topics.py`

Expected output:
```
Generated: cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
Generated: skills/explain/SKILL.md
Done. N topic(s) processed.
```

If the script errors, check: (a) the frontmatter is valid (no missing `topic:` or `description:`), (b) there are no duplicate `topic:` values across the resources directory.

- [ ] **Step 6: Run all explain tests**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_explain.py -q`

Expected: all tests pass (35 original + 4 new = 39 passed)

If any of the 4 new tests still fail, re-check the content added in Steps 3–4.

- [ ] **Step 7: Commit**

```
git add skills/explain/resources/code/code-node-patterns.md
git add cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
git add skills/explain/SKILL.md
git commit -m "feat: add Runtime Objects section to code-node-patterns, move to code/ subdir (issue #59)"
```

---

### Task 3: Version bump and deprecation notice verification

**Files:**
- Modify: `cognigy-mcp/pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Verify: `runtime-reference/cognigy-api-reference.md` (update wording if needed)

**Interfaces:**
- Consumes: completed content from Task 2
- Produces: version `1.4.3` in both version files; accurate deprecation notice

- [ ] **Step 1: Bump version in `cognigy-mcp/pyproject.toml`**

Change: `version = "1.4.2"` → `version = "1.4.3"`

- [ ] **Step 2: Bump version in `.claude-plugin/plugin.json`**

Change: `"version": "1.4.2"` → `"version": "1.4.3"`

- [ ] **Step 3: Verify `runtime-reference/cognigy-api-reference.md` deprecation notice**

Read the first 5 lines of `runtime-reference/cognigy-api-reference.md`. The current notice reads:

> **Deprecated:** This file is superseded by `explain("code-node-patterns")` in cognigy-vibe-mcp.
> Read this for legacy reference only. The MCP explain tool is the authoritative source.

After this change, `explain("code-node-patterns")` fully covers all content from this file. The notice is accurate as-is. No edit needed unless the wording references specific content that has moved.

If the notice needs updating, make the minimal wording change to keep it accurate.

- [ ] **Step 4: Run full explain test suite one final time**

Run: `cd cognigy-mcp && uv run pytest tests/tools/test_explain.py -q`

Expected: 39 passed, 0 failed

- [ ] **Step 5: Commit**

```
git add cognigy-mcp/pyproject.toml
git add .claude-plugin/plugin.json
git commit -m "chore: bump version to 1.4.3 (code-node-patterns fix, issue #59)"
```
