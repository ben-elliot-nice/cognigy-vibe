# Issue #44: Explain Skill Structure + MCP Build Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the markdown-file-based explain architecture end-to-end — resource files as source of truth, a build script that generates both the MCP tool and the Claude Code skill, and an `explain_dev` MCP tool that serves migrated topics without touching the existing `explain` tool.

**Architecture:** Four markdown resource files (frontmatter + body) in `skills/explain/resources/` are the authoritative source. `scripts/build_explain_topics.py` scans them recursively and emits `_explain_topics_generated.py` (for the MCP) and `skills/explain/SKILL.md` (for Claude Code). `explain_dev` is added to `explain.py`, importing the generated module. `publish.yml` runs the build script before `uv build`.

**Tech Stack:** Python 3.11+ stdlib only (re, pathlib, dataclasses) — no new dependencies. pytest for tests. hatchling for packaging. GitHub Actions.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `skills/explain/resources/code-node-patterns.md` | Flat resource: code node API patterns |
| Create | `skills/explain/resources/xapp/index.md` | Nested resource: xApp primer (new content) |
| Create | `skills/explain/resources/xapp/delivery.md` | Nested resource: xApp delivery pattern |
| Create | `skills/explain/resources/xapp/event-handling.md` | Nested resource: non-blocking xApp event loop |
| Create | `skills/explain/SKILL.md.template` | Template: static skill instructions + `{{TOPIC_REGISTRY}}` placeholder |
| Create | `scripts/build_explain_topics.py` | Build script: scans resources, generates Python + SKILL.md |
| Generated | `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py` | Auto-generated: TOPICS, _TOPIC_INDEX, _CONTENT |
| Generated | `skills/explain/SKILL.md` | Auto-generated: rendered skill for Claude Code |
| Create | `cognigy-mcp/tests/tools/test_explain_dev.py` | Tests for explain_dev handler |
| Modify | `cognigy-mcp/cognigy_mcp/tools/explain.py` | Add import + explain_dev Tool + handler |
| Modify | `.github/workflows/publish.yml` | Add build script step before uv build |

---

## Task 1: Create resource markdown files

**Files:**
- Create: `skills/explain/resources/code-node-patterns.md`
- Create: `skills/explain/resources/xapp/index.md`
- Create: `skills/explain/resources/xapp/delivery.md`
- Create: `skills/explain/resources/xapp/event-handling.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p skills/explain/resources/xapp
```

- [ ] **Step 2: Create `skills/explain/resources/code-node-patterns.md`**

Frontmatter + body. The body is copied verbatim from `_CONTENT["code-node-patterns"]` in `cognigy-mcp/cognigy_mcp/tools/explain.py` (lines 775–828). File structure:

```markdown
---
topic: code-node-patterns
description: api.* functions, as const bug, httpRequest .result, no fetch/import
---

## code-node-patterns — Writing Cognigy Code Nodes

### Available API methods
  api.say("text")                    // output text to channel
  api.output({text:"...", data:{}})  // structured output with data payload
  api.log("message")                 // debug log (NOT console.log)
  api.setContext({key: value})       // set context variables
  api.resolve()                      // signal completion (required for async nodes)
  api.reject("error message")        // signal failure
  api.inject({...})                  // inject turn result (Function Execution pattern)

### NOT available
  fetch()          // NO — use HTTP Request node for outbound HTTP
  require()        // NO — no module system
  import           // NO — not ES modules
  console.log()    // NO — use api.log() instead

### TypeScript syntax: no "as const"
  // WRONG — Cognigy code nodes don't support TypeScript generics/assertions:
  const STATUS = {PENDING: 'pending'} as const;
  // RIGHT:
  const STATUS = {PENDING: 'pending'};

### httpRequest node response wrapping
The httpRequest node wraps its response body under a .result key.
  // Code node reading httpRequest output:
  const body = context.httpResponse.result;   // NOT context.httpResponse directly
  // httpResponse shape: {result: {...actualBody}, status: 200, headers: {...}}

### Bare return bug
  return;  // at top level → transpile error "Illegal return statement"
  // Fix: wrap in function, or just omit the return

### Deep copy before multi-path assignment
  // WRONG — serializer collapses repeated object references:
  context.pathA.data = myObject;
  context.pathB.data = myObject;  // corruption
  // RIGHT:
  context.pathB.data = JSON.parse(JSON.stringify(myObject));

### Async pattern (when using await)
  async function main() {
    const result = await someAsyncOperation();
    context.result = result;
    api.resolve();
  }
  main();

### Available libraries
  _          // lodash
  moment     // date/time
  xmljs      // XML parsing
  textcleaner // text utilities
```

- [ ] **Step 3: Create `skills/explain/resources/xapp/index.md`** (new content — not in existing dict)

```markdown
---
topic: xapp
description: xApp architecture overview, variant selection, and channel differences
group: xapp
---

## xapp — xApp Overview

xApp is Cognigy's secondary screen feature: a web application delivered alongside a conversation (chat or voice) that lets users complete rich interactions — filling forms, making selections, confirming payments — without leaving the conversation thread.

### Architecture

An xApp session has a URL (`input.apps.url`) generated by the `initAppSession` node. This URL is **ephemeral** — available only on the turn the node fires. Persist it immediately:

  context.shortTermMemory.xappUrl = input.apps.url;

HTML content is pushed to the active session via the `setHTMLAppState` node (extension: `@cognigy/basic-nodes`). The page runs in the user's browser or the channel's xApp viewer.

### Variant A — SDK.submit (no external system)

Use when the user's action IS the result: option selection, form completion, simple confirmation.

The xApp page calls `sdk.submit(payload)`. Cognigy receives this as the next conversation turn. `input.data` contains the submitted payload.

### Variant B — Webhook inject (external system processes the action)

Use when a third party must process the action before the outcome is known: payment processors, document signing, external approvals.

The xApp page POSTs to an external API. That API injects the outcome into Cognigy via the REST sessions endpoint. The xApp page must embed `{{ci.URLToken}}`, `{{ci.userId}}`, `{{ci.sessionId}}` at render time so the external system can construct the inject call.

### Channel differences

- **Digital/chat:** xApp URL can be delivered inline. No SMS step required.
- **Voice:** xApp URL is typically sent via SMS before `aiAgentToolAnswer` returns control to the agent.

### Key constraint

`api.setAppState()` in code nodes cannot push HTML — use the `setHTMLAppState` node. For conditional xApp pushes from code: set a context flag in code, branch on it with an IF node, then call `setHTMLAppState` in the true branch.

### Specialist topics

- `xapp-delivery` — full delivery pattern: initAppSession, setHTMLAppState, code node, SMS, aiAgentToolAnswer
- `xapp-event-handling` — non-blocking event loop: how the flow intercepts submit/inject turns before the AI Agent Job runs
```

- [ ] **Step 4: Create `skills/explain/resources/xapp/delivery.md`**

Copy body verbatim from `_CONTENT["xapp-delivery"]` in `explain.py` (lines 465–514). Frontmatter:

```markdown
---
topic: xapp-delivery
description: session init, postMessage bridge, SDK.submit, dual xApp moments
group: xapp
---

## xapp-delivery — xApp Patterns
... (copy full body from _CONTENT["xapp-delivery"] in explain.py) ...
```

- [ ] **Step 5: Create `skills/explain/resources/xapp/event-handling.md`**

Copy body verbatim from `_CONTENT["xapp-event-handling"]` in `explain.py` (lines 517–737). Frontmatter:

```markdown
---
topic: xapp-event-handling
description: non-blocking xApp pattern: flow structure, ephemeral data capture, SDK.submit vs webhook inject variants
group: xapp
---

## xapp-event-handling — Non-Blocking xApp with Async Event Loop
... (copy full body from _CONTENT["xapp-event-handling"] in explain.py) ...
```

- [ ] **Step 6: Commit**

```bash
git add skills/explain/resources/
git commit -m "feat: add explain resource files for code-node-patterns and xapp group"
```

---

## Task 2: Create SKILL.md.template

**Files:**
- Create: `skills/explain/SKILL.md.template`

- [ ] **Step 1: Write the template**

```markdown
---
name: explain
description: Retrieve implementation guidance for Cognigy topics before brute-forcing or web-searching
---

# Explain

## When to Use

Call `explain_dev` before brute-forcing or web-searching for Cognigy implementation guidance. It returns authoritative reference for the topics below — faster and more accurate than inference.

## Available Topics

{{TOPIC_REGISTRY}}

## How to Use

- **Orientation:** `explain_dev()` with no args — returns topic list with one-line descriptions
- **Full reference:** `explain_dev("topic-name")` — returns complete guidance for that topic
- **Fallback:** if the topic is not listed above, use `explain("topic-name")` instead — the legacy tool covers the full 24-topic set until migration is complete

## Notes

This tool covers migrated topics only. The full topic set lives in `explain` until migration is complete (issue #45).
```

- [ ] **Step 2: Commit**

```bash
git add skills/explain/SKILL.md.template
git commit -m "feat: add SKILL.md.template for explain skill"
```

---

## Task 3: Create build script

**Files:**
- Create: `scripts/build_explain_topics.py`

- [ ] **Step 1: Create `scripts/` directory**

```bash
mkdir -p scripts
```

- [ ] **Step 2: Write `scripts/build_explain_topics.py`**

```python
#!/usr/bin/env python3
"""Build explain topics from markdown resource files.

Generates:
  cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
  skills/explain/SKILL.md

Run with: uv run scripts/build_explain_topics.py
"""
from __future__ import annotations
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RESOURCES = REPO_ROOT / "skills" / "explain" / "resources"
TEMPLATE = REPO_ROOT / "skills" / "explain" / "SKILL.md.template"
GENERATED_PY = REPO_ROOT / "cognigy-mcp" / "cognigy_mcp" / "tools" / "_explain_topics_generated.py"
GENERATED_SKILL = REPO_ROOT / "skills" / "explain" / "SKILL.md"


@dataclass
class TopicEntry:
    topic: str
    description: str
    group: str | None
    body: str


def parse_frontmatter(content: str, path: Path) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from markdown content. Returns (metadata, body)."""
    match = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', content, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter found in {path}")
    fm_text = match.group(1)
    body = content[match.end():]
    metadata: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ':' in line:
            key, _, value = line.partition(':')
            metadata[key.strip()] = value.strip()
    return metadata, body


def scan_resources(resources_dir: Path) -> list[TopicEntry]:
    """Recursively scan resources directory and return sorted TopicEntry list."""
    entries: list[TopicEntry] = []
    for md_file in sorted(resources_dir.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        try:
            metadata, body = parse_frontmatter(content, md_file)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        topic = metadata.get("topic", "").strip()
        description = metadata.get("description", "").strip()
        group = metadata.get("group", "").strip() or None
        if not topic:
            print(f"ERROR: Missing 'topic' in frontmatter: {md_file}", file=sys.stderr)
            sys.exit(1)
        if not description:
            print(f"ERROR: Missing 'description' in frontmatter: {md_file}", file=sys.stderr)
            sys.exit(1)
        entries.append(TopicEntry(topic=topic, description=description, group=group, body=body.strip()))
    # Sort: flat topics (no group) first, then grouped by group name then topic
    entries.sort(key=lambda e: (e.group is not None, e.group or "", e.topic))
    return entries


def build_topic_index(entries: list[TopicEntry]) -> str:
    """Build the _TOPIC_INDEX string with group headings."""
    lines: list[str] = ["Topics and what they cover:\n"]
    current_group: str | None = "SENTINEL"
    for entry in entries:
        if entry.group != current_group:
            current_group = entry.group
            if current_group is not None:
                lines.append(f"\n{current_group}:")
        lines.append(f"  {entry.topic:<26} {entry.description}")
    return "\n".join(lines)


def generate_python(entries: list[TopicEntry], output_path: Path) -> None:
    """Write _explain_topics_generated.py."""
    topics_repr = repr([e.topic for e in entries])
    index = build_topic_index(entries)
    content_items = "\n".join(f"    {e.topic!r}: {e.body!r}," for e in entries)
    code = f'''# AUTO-GENERATED by scripts/build_explain_topics.py — do not edit directly
# Source: skills/explain/resources/
from __future__ import annotations

TOPICS: list[str] = {topics_repr}

_TOPIC_INDEX = """
{index}
"""

_CONTENT: dict[str, str] = {{
{content_items}
}}
'''
    output_path.write_text(code, encoding="utf-8")
    print(f"Generated: {output_path.relative_to(REPO_ROOT)}")


def generate_skill_md(entries: list[TopicEntry], template_path: Path, output_path: Path) -> None:
    """Render SKILL.md.template → SKILL.md."""
    template = template_path.read_text(encoding="utf-8")
    index = build_topic_index(entries)
    output_path.write_text(template.replace("{{TOPIC_REGISTRY}}", index), encoding="utf-8")
    print(f"Generated: {output_path.relative_to(REPO_ROOT)}")


def main() -> None:
    if not RESOURCES.exists():
        print(f"ERROR: resources directory not found: {RESOURCES}", file=sys.stderr)
        sys.exit(1)
    entries = scan_resources(RESOURCES)
    if not entries:
        print("ERROR: no topic files found", file=sys.stderr)
        sys.exit(1)
    generate_python(entries, GENERATED_PY)
    generate_skill_md(entries, TEMPLATE, GENERATED_SKILL)
    print(f"Done. {len(entries)} topic(s) processed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
git add scripts/build_explain_topics.py
git commit -m "feat: add build script for explain topics pipeline"
```

---

## Task 4: Run build script and verify generated files

**Files:**
- Verify generated: `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py`
- Verify generated: `skills/explain/SKILL.md`

- [ ] **Step 1: Run the build script**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
uv run scripts/build_explain_topics.py
```

Expected output:
```
Generated: cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
Generated: skills/explain/SKILL.md
Done. 4 topic(s) processed.
```

- [ ] **Step 2: Verify generated Python module is importable and has correct topics**

```bash
cd cognigy-mcp
uv run python -c "
from cognigy_mcp.tools._explain_topics_generated import TOPICS, _CONTENT, _TOPIC_INDEX
print('TOPICS:', TOPICS)
assert 'code-node-patterns' in TOPICS
assert 'xapp' in TOPICS
assert 'xapp-delivery' in TOPICS
assert 'xapp-event-handling' in TOPICS
assert len(TOPICS) == 4
assert all(len(_CONTENT[t]) > 100 for t in TOPICS)
print('OK')
"
```

- [ ] **Step 3: Verify SKILL.md was rendered (no template placeholder remaining)**

```bash
grep -c "{{TOPIC_REGISTRY}}" skills/explain/SKILL.md && echo "FAIL: placeholder not replaced" || echo "OK: placeholder replaced"
grep "code-node-patterns" skills/explain/SKILL.md && echo "OK: topics present"
```

Expected: `grep -c` returns 0 (exits 1, triggering the `|| echo "OK"` branch). Topics present.

- [ ] **Step 4: Commit generated files**

```bash
git add cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py skills/explain/SKILL.md
git commit -m "chore: generate explain topics pipeline outputs"
```

---

## Task 5: Write failing tests for explain_dev

**Files:**
- Create: `cognigy-mcp/tests/tools/test_explain_dev.py`

- [ ] **Step 1: Write test file**

```python
# cognigy-mcp/tests/tools/test_explain_dev.py
import pytest
from cognigy_mcp.tools.explain import TOOLS, make_handlers
from cognigy_mcp.tools._explain_topics_generated import TOPICS as DEV_TOPICS


def test_explain_dev_tool_exported():
    assert any(t.name == "explain_dev" for t in TOOLS)


def test_explain_dev_tool_description_contains_all_topic_names():
    tool = next(t for t in TOOLS if t.name == "explain_dev")
    for topic in DEV_TOPICS:
        assert topic in tool.description, f"Topic '{topic}' missing from explain_dev description"


def test_explain_dev_no_args_returns_orientation(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({})
    text = result[0].text
    assert "code-node-patterns" in text
    assert "xapp" in text
    assert "Topics" in text


def test_explain_dev_known_topic_returns_content(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    for topic in DEV_TOPICS:
        result = handlers["explain_dev"]({"topic": topic})
        text = result[0].text
        assert len(text) > 100, f"Topic '{topic}' returned too-short content: {text!r}"
        assert "Unknown topic" not in text, f"Topic '{topic}' was not found"


def test_explain_dev_xapp_primer_mentions_variants(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "xapp"})
    text = result[0].text
    assert "Variant A" in text
    assert "Variant B" in text


def test_explain_dev_unknown_topic_returns_error_with_available_topics(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "node-positioning"})
    text = result[0].text
    assert "node-positioning" in text          # echoes the bad topic name
    assert "code-node-patterns" in text        # lists what IS available


def test_explain_dev_does_not_serve_legacy_content(mock_client, state, cache):
    """explain_dev must return an error for topics that only exist in the legacy explain tool."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain_dev"]({"topic": "node-positioning"})
    text = result[0].text
    assert "Unknown topic" in text
    # Legacy content for node-positioning starts with this heading
    assert "Inserting and Moving Nodes" not in text


def test_existing_explain_tool_unchanged(mock_client, state, cache):
    """Existing explain tool must still work after explain_dev is added."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "append" in text
    assert "Unknown topic" not in text
```

- [ ] **Step 2: Run tests — expect failures**

```bash
cd cognigy-mcp
uv run pytest tests/tools/test_explain_dev.py -v
```

Expected: all tests FAIL with `KeyError: 'explain_dev'` or `AssertionError` (tool not yet registered).

---

## Task 6: Implement explain_dev in explain.py

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py`

- [ ] **Step 1: Add import at the top of explain.py**

After the existing imports (after line 8 `from cognigy_mcp.state import ProjectState`), add:

```python
from cognigy_mcp.tools._explain_topics_generated import (
    TOPICS as _DEV_TOPICS,
    _TOPIC_INDEX as _DEV_TOPIC_INDEX,
    _CONTENT as _DEV_CONTENT,
)
```

- [ ] **Step 2: Add explain_dev Tool to the TOOLS list**

The `TOOLS` list currently ends with the `explain` Tool (around line 1307). Add `explain_dev` as a second entry in the list:

```python
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
    Tool(
        name="explain_dev",
        description=(
            "Retrieve implementation guidance for migrated Cognigy topics.\n\n"
            "Topics: " + " | ".join(_DEV_TOPICS) + "\n\n"
            "Call explain_dev() for orientation.\n"
            "Call explain_dev(\"topic\") for full reference on that topic.\n"
            "For topics not listed here, use explain() instead."
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
```

- [ ] **Step 3: Add _explain_dev handler inside make_handlers and return it**

The `make_handlers` function currently defines `_explain` and returns `{"explain": _explain}`. Add the new handler and include it in the return dict:

```python
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

    def _explain_dev(args: dict) -> list[TextContent]:
        topic = args.get("topic", "").strip()
        if not topic:
            return _ok("# cognigy-vibe-mcp Dev Reference Library\n\n" + _DEV_TOPIC_INDEX)
        content = _DEV_CONTENT.get(topic)
        if content:
            return _ok(content.strip())
        return _ok(
            f"Unknown topic: '{topic}'\n\n"
            f"Available Topics:\n{_DEV_TOPIC_INDEX}"
        )

    return {"explain": _explain, "explain_dev": _explain_dev}
```

- [ ] **Step 4: Run explain_dev tests — expect pass**

```bash
cd cognigy-mcp
uv run pytest tests/tools/test_explain_dev.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Run full test suite — check no regressions**

```bash
uv run pytest -v
```

Expected: all existing tests pass. Pay attention to `tests/tools/test_explain.py` — the existing `explain` tool must be unaffected.

- [ ] **Step 6: Bump versions**

`explain_dev` is a new tool — patch-bump both the MCP package and the plugin manifest.

`cognigy-mcp/pyproject.toml` — change version: `"1.3.12"` → `"1.3.13"`

`.claude-plugin/plugin.json` — change version: `"1.3.12"` → `"1.3.13"`

- [ ] **Step 7: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/explain.py cognigy-mcp/tests/tools/test_explain_dev.py cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "feat: add explain_dev MCP tool reading from generated topic module"
```

---

## Task 7: Update publish.yml

**Files:**
- Modify: `.github/workflows/publish.yml`

- [ ] **Step 1: Add build step to publish.yml**

The existing `publish.yml` has a `setup-uv` step followed by a `Build package` step. Add the new step between them:

Current (around line 41–50):
```yaml
      - uses: astral-sh/setup-uv@v5
        if: steps.check.outputs.skip == 'false'
        with:
          enable-cache: true

      - name: Build package
        if: steps.check.outputs.skip == 'false'
        run: |
          cd cognigy-mcp
          uv build
```

After change:
```yaml
      - uses: astral-sh/setup-uv@v5
        if: steps.check.outputs.skip == 'false'
        with:
          enable-cache: true

      - name: Generate explain topics
        if: steps.check.outputs.skip == 'false'
        run: uv run scripts/build_explain_topics.py

      - name: Build package
        if: steps.check.outputs.skip == 'false'
        run: |
          cd cognigy-mcp
          uv build
```

The script runs from the repo root (checkout root), which is where both `skills/` and `cognigy-mcp/` live. `uv` is already available from `setup-uv`. The `cd cognigy-mcp` in Build package is unaffected.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "ci: run explain topics build script before uv build in publish workflow"
```

---

## Task 8: End-to-end smoke test and final push

- [ ] **Step 1: Run full test suite one more time**

```bash
cd cognigy-mcp
uv run pytest -v
```

Expected: all tests pass, no warnings about explain or explain_dev.

- [ ] **Step 2: Verify explain_dev is registered in the server tool list**

```bash
uv run python -c "
import os
os.environ['COGNIGY_BASE_URL'] = 'http://localhost'
os.environ['COGNIGY_API_KEY'] = 'test'
from cognigy_mcp.server import create_server
_, tools = create_server()
names = [t.name for t in tools]
print('Tools:', names)
assert 'explain' in names
assert 'explain_dev' in names
print('OK')
"
```

Expected: both `explain` and `explain_dev` appear in the tool list.

- [ ] **Step 3: Push and update parent repo**

```bash
git push
```

Then update the marketplace parent repo:

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```

---

## Acceptance Checklist

- [ ] `skills/explain/resources/` contains 4 files across flat and nested layout
- [ ] `skills/explain/SKILL.md.template` exists with `{{TOPIC_REGISTRY}}` placeholder
- [ ] `scripts/build_explain_topics.py` runs cleanly and produces both outputs
- [ ] `skills/explain/SKILL.md` is generated and committed (no `{{TOPIC_REGISTRY}}` remaining)
- [ ] `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py` is generated and committed
- [ ] `explain_dev("code-node-patterns")` returns content via MCP handler
- [ ] `explain_dev("xapp")` returns the new xApp primer content
- [ ] `explain_dev("xapp-delivery")` and `explain_dev("xapp-event-handling")` return migrated content
- [ ] `explain_dev()` with no args returns the grouped topic index
- [ ] `explain_dev("node-positioning")` returns "Unknown topic" error
- [ ] All existing `test_explain.py` tests still pass
- [ ] `publish.yml` runs the build script before `uv build`
