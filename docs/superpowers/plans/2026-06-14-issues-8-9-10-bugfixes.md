# Issues #8, #9, #10 Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three bugs found during exploratory testing: `talk_to_agent` silent empty output on `minimal=true`, `cognigy_create` KeyError crash for knowledge sources, and incorrect field documentation in `explain("knowledge-store")`.

**Architecture:** Three independent fixes across two tool files and the explain content dict. Each fix is paired with tests that reproduce the bug first, then confirm the fix. No new files — all changes are to existing files.

**Tech Stack:** Python 3.11+, pytest, respx (HTTP mocking), uv

---

## File Map

| File | Change |
|---|---|
| `cognigy-mcp/cognigy_mcp/tools/testing.py` | Fix minimal text extraction (Issue #8) |
| `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` | Fix safe `_id` access on create (Issue #9) |
| `cognigy-mcp/cognigy_mcp/tools/explain.py` | Fix knowledge-store topic content (Issue #10) |
| `cognigy-mcp/tests/tools/test_testing.py` | Add minimal=true tests |
| `cognigy-mcp/tests/tools/test_flow_ops.py` | Add knowledge source create test |
| `cognigy-mcp/tests/tools/test_explain.py` | Add knowledge-store content assertions |
| `cognigy-mcp/pyproject.toml` | Bump version 1.3.2 → 1.3.3 |
| `.claude-plugin/plugin.json` | Bump version 1.3.2 → 1.3.3 |

---

## Context: Root Causes

**Issue #8 root cause:** `dict.get(key, default)` only uses `default` when the key is absent. If the Cognigy endpoint response contains an `"output"` key with a falsy value (e.g., `""`), the chain `data.get("output", data.get("text", ""))` returns `""` without ever reaching the `text` fallback. Python `or` chaining (`a or b or c`) correctly skips falsy values regardless of key presence.

**Issue #9 root cause:** Lines 410–411 of `flow_ops.py` use `result["_id"]` (direct dict access that raises `KeyError`) instead of `result.get("_id")`. The Cognigy knowledge source creation API response does not include `_id` in the same field structure as other resources.

**Issue #10 root cause:** The `explain.py` knowledge-store topic was written with incorrect assumptions about the Cognigy API body fields. Confirmed field constraints: `knowledgeStoreId` is not allowed (the store ID is already in the URL path), `content` is not a body field (text goes in chunks after creation), and `"text"` is not a valid type value (only `"manual"` is valid).

---

## Task 1: Fix `talk_to_agent` minimal text extraction (Issue #8)

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/testing.py:78-83`
- Test: `cognigy-mcp/tests/tools/test_testing.py`

- [ ] **Step 1: Write failing tests**

Add to `cognigy-mcp/tests/tools/test_testing.py` after the existing `test_talk_to_agent_flow_id_not_found_shows_known_endpoints` test:

```python
def test_talk_to_agent_minimal_returns_text(real_client, state, cache):
    """minimal=True should return the text field from the response."""
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={
                "text": "How can I help with your parts enquiry?",
                "data": {},
                "sessionId": "sess-1",
            })
        )
        result = handlers["talk_to_agent"]({
            "message": "Hi",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
            "minimal": True,
        })
    data = json.loads(result[0].text)
    assert data["outputText"] == "How can I help with your parts enquiry?"
    assert data["sessionId"] == "sess-1"


def test_talk_to_agent_minimal_with_empty_output_field(real_client, state, cache):
    """Regression: falsy 'output' key must not suppress the 'text' fallback."""
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={
                "text": "Hello there",
                "output": "",
                "data": {},
            })
        )
        result = handlers["talk_to_agent"]({
            "message": "Hi",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
            "minimal": True,
        })
    data = json.loads(result[0].text)
    assert data["outputText"] == "Hello there"


def test_talk_to_agent_minimal_with_outputs_array(real_client, state, cache):
    """minimal=True should extract text from outputs[] array when top-level text absent."""
    handlers = make_handlers(real_client, state, cache)
    with respx.mock:
        respx.post(f"{ENDPOINT_BASE}/tok123").mock(
            return_value=httpx.Response(200, json={
                "outputs": [
                    {"text": "Array output text", "type": "output"},
                ],
                "sessionId": "sess-1",
            })
        )
        result = handlers["talk_to_agent"]({
            "message": "Hi",
            "endpoint_token": "tok123",
            "session_id": "sess-1",
            "user_id": "user-1",
            "minimal": True,
        })
    data = json.loads(result[0].text)
    assert data["outputText"] == "Array output text"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_testing.py::test_talk_to_agent_minimal_returns_text tests/tools/test_testing.py::test_talk_to_agent_minimal_with_empty_output_field tests/tools/test_testing.py::test_talk_to_agent_minimal_with_outputs_array -v
```

Expected: 1 or more tests FAIL (the empty_output_field test should definitely fail; the others may also fail depending on actual API shape)

- [ ] **Step 3: Fix the minimal text extraction in `testing.py`**

Replace lines 78–83 in `cognigy-mcp/cognigy_mcp/tools/testing.py`:

```python
            if args.get("minimal"):
                session_info = data.get("data", {})
                return _ok({
                    "outputText": session_info.get("output", data.get("output", data.get("text", ""))),
                    "sessionId": session_id,
                })
```

With:

```python
            if args.get("minimal"):
                text = (
                    data.get("text")
                    or next((o.get("text") for o in data.get("outputs", []) if o.get("text")), None)
                    or ""
                )
                return _ok({"outputText": text, "sessionId": session_id})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_testing.py -v
```

Expected: ALL tests PASS including the three new ones

- [ ] **Step 5: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/cognigy_mcp/tools/testing.py cognigy-mcp/tests/tools/test_testing.py
git commit -m "fix: talk_to_agent minimal=true no longer returns empty outputText (fixes #8)"
```

---

## Task 2: Fix `cognigy_create` safe `_id` access (Issue #9)

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py:407-411`
- Test: `cognigy-mcp/tests/tools/test_flow_ops.py`

- [ ] **Step 1: Write failing test**

Add to `cognigy-mcp/tests/tools/test_flow_ops.py` after the existing `test_cognigy_create_saves_to_state` test:

```python
def test_cognigy_create_knowledge_source_without_id_field(mock_client, state, cache):
    """cognigy_create must not raise KeyError when API response lacks _id.
    Repro: creating a knowledge source returns a response without _id.
    """
    mock_client.post.return_value = {
        "name": "Battery Trade-In Policy",
        "type": "manual",
        "referenceId": "ks-source-ref-123",
        # No "_id" key — this is what the knowledge source API returns
    }
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["cognigy_create"]({
        "resource_type": "knowledgestores/ks123/sources",
        "body": {"name": "Battery Trade-In Policy", "type": "manual"},
    })
    data = json.loads(result[0].text)
    assert "error" not in data
    assert data.get("referenceId") == "ks-source-ref-123"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_flow_ops.py::test_cognigy_create_knowledge_source_without_id_field -v
```

Expected: FAIL with `KeyError: '_id'`

- [ ] **Step 3: Fix the safe `_id` access in `flow_ops.py`**

Find these lines in `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` (around line 407):

```python
        result = client.post(path, body)
        # Auto-save to state
        name = result.get("name") or result.get("label")
        if name:
            state.set(rtype, name, value={"id": result["_id"]})
        cache.set(rtype, result["_id"], result)
```

Replace with:

```python
        result = client.post(path, body)
        # Auto-save to state
        resource_id = result.get("_id") or result.get("id")
        name = result.get("name") or result.get("label")
        if name and resource_id:
            state.set(rtype, name, value={"id": resource_id})
        if resource_id:
            cache.set(rtype, resource_id, result)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_flow_ops.py -v
```

Expected: ALL tests PASS including the new one

- [ ] **Step 5: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py cognigy-mcp/tests/tools/test_flow_ops.py
git commit -m "fix: cognigy_create no longer crashes with KeyError when API response lacks _id (fixes #9)"
```

---

## Task 3: Fix `explain("knowledge-store")` topic content (Issue #10)

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py` (the `"knowledge-store"` entry in `_CONTENT`)
- Test: `cognigy-mcp/tests/tools/test_explain.py`

- [ ] **Step 1: Write failing test**

Add to `cognigy-mcp/tests/tools/test_explain.py` after `test_explain_unknown_topic_returns_topic_list`:

```python
def test_explain_knowledge_store_has_correct_source_creation_fields(mock_client, state, cache):
    """Regression: knowledge-store topic must not document invalid API fields."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "knowledge-store"})
    text = result[0].text

    # Must document the correct type value
    assert '"manual"' in text or "'manual'" in text, "Should document type: 'manual'"

    # Must document chunks endpoint
    assert "chunks" in text, "Should document adding content as chunks"

    # Must NOT document invalid fields that the API rejects with 400
    assert "knowledgeStoreId" not in text, "knowledgeStoreId is not a valid body field"
    assert '"text"' not in text or 'type: "text"' not in text, "type: 'text' is not a valid source type"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py::test_explain_knowledge_store_has_correct_source_creation_fields -v
```

Expected: FAIL (current content has `knowledgeStoreId` and `type: "text"`)

- [ ] **Step 3: Update the knowledge-store topic in `explain.py`**

Find the `"knowledge-store"` key in `_CONTENT` in `cognigy-mcp/cognigy_mcp/tools/explain.py`. The current content for the `### Create a source` and following sections is:

```python
### Create a source
  Path: POST /v2.0/knowledgestores/{ksId}/sources
  Use cognigy_invoke or cognigy_create with custom path.
  Body: {"knowledgeStoreId": "<ksId>", "name": "My Docs", "type": "text", "content": "..."}

### Trigger ingestion via connector
```

Replace that block with:

```python
### Create a source
  Path: POST /v2.0/knowledgestores/{ksId}/sources
  cognigy_create(resource_type="knowledgestores/{ksId}/sources",
    body={"name": "My Source", "type": "manual"})

  INVALID fields (API returns 400):
  - knowledgeStoreId → not needed (ksId is already in the resource_type path)
  - content → not a create-time field; text is added as chunks after creation
  - type: "text" → not a valid type; use "manual"

### Add text chunks to a source
  After creating the source, add its text content as chunks:
  cognigy_create(resource_type="knowledgestores/{ksId}/sources/{sourceId}/chunks",
    body={"text": "The battery trade-in policy allows..."})
  Retrieve sourceId from the cognigy_create response (referenceId or follow with cognigy_list).

### Trigger ingestion via connector
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py -v
```

Expected: ALL tests PASS including the new one

- [ ] **Step 5: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/cognigy_mcp/tools/explain.py cognigy-mcp/tests/tools/test_explain.py
git commit -m "fix: explain(knowledge-store) now documents correct source creation fields (fixes #10)"
```

---

## Task 4: Full test suite + version bump

**Files:**
- Modify: `cognigy-mcp/pyproject.toml` (version `1.3.2` → `1.3.3`)
- Modify: `.claude-plugin/plugin.json` (version `1.3.2` → `1.3.3`)

- [ ] **Step 1: Run full test suite to confirm no regressions**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/ -v
```

Expected: ALL 97 tests PASS (94 existing + 3 new from this plan — one per issue)

- [ ] **Step 2: Bump version in `pyproject.toml`**

In `cognigy-mcp/pyproject.toml`, change:

```toml
version = "1.3.2"
```

To:

```toml
version = "1.3.3"
```

- [ ] **Step 3: Bump version in `plugin.json`**

In `.claude-plugin/plugin.json`, change:

```json
"version": "1.3.2",
```

To:

```json
"version": "1.3.3",
```

- [ ] **Step 4: Commit version bump**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "chore: bump version to 1.3.3"
```

- [ ] **Step 5: Push and update parent repo**

```bash
git push
```

Then run the post-push command from CLAUDE.md:

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```

- [ ] **Step 6: Close issues on GitHub**

```bash
gh issue close 8 --repo ben-elliot-nice/cognigy-claude-plugin --comment "Fixed in v1.3.3: minimal=true now correctly extracts outputText using or-chaining instead of dict.get fallbacks."
gh issue close 9 --repo ben-elliot-nice/cognigy-claude-plugin --comment "Fixed in v1.3.3: cognigy_create now uses result.get('_id') to avoid KeyError when API response omits _id."
gh issue close 10 --repo ben-elliot-nice/cognigy-claude-plugin --comment "Fixed in v1.3.3: explain(knowledge-store) now documents the correct body (name + type: manual only), invalid fields, and chunk creation."
```

---

## Self-Review

**Spec coverage:**
- Issue #8 (`talk_to_agent` minimal empty output): ✓ Task 1 fixes and tests it
- Issue #9 (`cognigy_create` KeyError): ✓ Task 2 fixes and tests it
- Issue #10 (`explain` wrong fields): ✓ Task 3 fixes and tests it
- Version bump: ✓ Task 4

**Placeholder scan:** No TBDs, no "similar to Task N", all code is complete and runnable.

**Type consistency:** No new types introduced. All changes are within existing function signatures. `result.get("_id") or result.get("id")` is consistent with the pattern already used in the minimal dict at line 414.
