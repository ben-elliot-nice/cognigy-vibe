# Issue #27 — Branch Population Mode Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `node-positioning` explain topic which incorrectly instructs agents to use `mode: "appendChild"` for Once/IF branch content — the correct mode is `mode: "append"` (sibling-after-marker).

**Architecture:** All changes are in `explain.py` (two content sections) and `test_explain.py` (one test update + one new test). No API layer, no schema, no new tools. Work on existing branch `fix/issues-18-19-23-24` in worktree `.worktrees/fix-issues-18-19-23-24`.

**Tech Stack:** Python 3.14, pytest + uv, cognigy-mcp MCP server

---

## Background

The correct chart structure for a Once node is:

```
[once] Once
  [onFirstExecution] OnFirstTime   ← branch marker (child of Once)
  [code] Init Session Context      ← sibling of marker (also child of Once) ← CONTENT HERE
  [afterwards] Afterwards          ← branch marker (also child of Once)
  [aiAgentJob] Part Enquiry        ← sibling of marker (also child of Once) ← CONTENT HERE
```

Content nodes are **siblings** of the branch marker within the parent's `childIds` — they are NOT children of the marker itself. The same rule applies to IF nodes.

- **Correct:** `mode: "append"`, `target: <branchMarkerId>` — appends as sibling-after-marker within the parent's children
- **WRONG:** `mode: "appendChild"`, `target: <branchMarkerId>` — nests as child OF the marker, breaks Cognigy UI rendering

`appendChild` has one legitimate use: adding `aiAgentJobTool` nodes as children of an `aiAgentJob` node. That section is correct and must not change.

---

## File Map

| File | Change |
|---|---|
| `cognigy-mcp/cognigy_mcp/tools/explain.py` | Fix "Child branch population" (Once) and "IF node branch population" sections — replace `appendChild` with `append`, add WRONG/correct contrast |
| `cognigy-mcp/tests/tools/test_explain.py` | Update `test_node_positioning_documents_if_branch_population` to assert correct mode; add `test_node_positioning_branch_content_uses_append_sibling` |

---

### Task 1: Fix branch population docs and tests (fixes #27)

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py` (lines 90–125 — both branch population sections)
- Modify: `cognigy-mcp/tests/tools/test_explain.py` (update IF branch test; add new Once/IF sibling test)

- [ ] **Step 1: Write the new failing test**

Add to `cognigy-mcp/tests/tools/test_explain.py` (after the existing `test_node_positioning_documents_if_branch_population` function):

```python
def test_node_positioning_branch_content_uses_append_sibling(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "sibling" in text.lower(), "Should explain append creates a sibling of the branch marker, not a child"
    assert "WRONG" in text, "Should explicitly label appendChild as wrong for branch content insertion"
```

- [ ] **Step 2: Run the new test to verify it fails**

```bash
cd cognigy-mcp && uv run pytest tests/tools/test_explain.py::test_node_positioning_branch_content_uses_append_sibling -v
```

Expected: FAIL — "sibling" not in text, "WRONG" not in text.

- [ ] **Step 3: Update the IF branch test**

In `cognigy-mcp/tests/tools/test_explain.py`, replace the existing `test_node_positioning_documents_if_branch_population` function:

Current:
```python
def test_node_positioning_documents_if_branch_population(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "IF node" in text or "if node" in text.lower(), "Should document IF node branch pattern"
    assert "Then" in text and "Else" in text, "Should name both branch containers"
    assert "childIds[0]" in text or "children[0]" in text, "Should document how to find branch container IDs"
    assert "appendChild" in text, "Should document appendChild for branch population"
```

Replace with:
```python
def test_node_positioning_documents_if_branch_population(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "node-positioning"})
    text = result[0].text
    assert "IF node" in text or "if node" in text.lower(), "Should document IF node branch pattern"
    assert "Then" in text and "Else" in text, "Should name both branch containers"
    assert "childIds[0]" in text or "children[0]" in text, "Should document how to find branch marker IDs"
    assert '"append"' in text, "Should document append (not appendChild) as the correct mode for branch content"
```

Note: `"appendChild"` will still appear in the text (in the WRONG example and in the aiAgentJobTool section) — we're just removing the assertion that *implied* it was the right mode for branch content.

- [ ] **Step 4: Fix the "Child branch population (Once node example)" section in explain.py**

In `cognigy-mcp/cognigy_mcp/tools/explain.py`, replace the entire "Child branch population" section:

Current (lines ~90–104):
```
### Child branch population (Once node example)
Once nodes auto-create two child branch nodes: OnFirstTime and Afterwards.
Each branch appears as a separate node in the chart with its own _id.

To add a node into a branch:
1. Find the branch node in the chart (e.g. OnFirstTime child of the Once node)
2. Use mode: "appendChild" with target set to the BRANCH NODE's _id

Common pitfall: targeting the parent Once node's _id instead of the branch node.
The branch node's _id is what you need — it's the container for child nodes.

Example: chart shows Once node "a1b2" with childIds ["c3d4", "e5f6"]
  - "c3d4" is the OnFirstTime branch node
  - "e5f6" is the Afterwards branch node
  - To add a Code node to OnFirstTime, target "c3d4", NOT "a1b2"
```

Replace with:
```
### Child branch population (Once node example)
Once nodes auto-create two branch marker nodes: OnFirstTime and Afterwards.
Each marker appears as a child of the Once node with its own _id.

Content inside a branch must be a SIBLING of the marker (append after it), not a child of it:
  CORRECT: mode: "append",      target: <branchMarkerId>   ← sibling-after-marker, renders inside branch
  WRONG:   mode: "appendChild", target: <branchMarkerId>   ← child OF marker, breaks UI rendering

Example: Once node "a1b2" with childIds ["c3d4", "e5f6"]
  - "c3d4" is the OnFirstTime branch marker
  - "e5f6" is the Afterwards branch marker
  - To add a Code node to OnFirstTime:
    cognigy_create(body={"mode": "append", "target": "c3d4", "flowId": "..."})
    → Code becomes sibling of c3d4 within Once's children = renders inside OnFirstTime section

Common pitfall: targeting the parent Once node's _id ("a1b2") instead of the branch marker ("c3d4").
```

- [ ] **Step 5: Fix the "IF node branch population" section in explain.py**

In the same file, replace the "IF node branch population" section:

Current (lines ~106–124):
```
### IF node branch population
IF nodes (type: "if") auto-create two branch container nodes when created.
Each branch container has its own _id and appears in the IF node's childIds[]:
  - childIds[0] = Then branch container
  - childIds[1] = Else branch container

To add a node into an IF branch:
1. Create the IF node via cognigy_create (see flow-chart-reading for correct config schema)
2. GET the flow chart — find the IF node's childIds array
3. childIds[0] is the Then container _id, childIds[1] is the Else container _id
4. Create child nodes with mode: "appendChild", target: <branch-container-_id>

Example: IF node "if-abc" with childIds ["then-xyz", "else-xyz"]
  - To add a Say node to the Then branch: mode="appendChild", target="then-xyz"
  - To add a Code node to the Else branch: mode="appendChild", target="else-xyz"

Common pitfall: targeting the IF node's own _id ("if-abc") instead of the branch container.
The IF node itself is NOT the container — use its childIds entries.
This is the same pattern as Once → OnFirstTime/Afterwards branches (see above).
```

Replace with:
```
### IF node branch population
IF nodes (type: "if") auto-create two branch marker nodes when created.
Each marker appears in the IF node's childIds[]:
  - childIds[0] = Then branch marker
  - childIds[1] = Else branch marker

Content inside a branch must be a SIBLING of the marker (same rule as Once above):
  CORRECT: mode: "append",      target: <branchMarkerId>
  WRONG:   mode: "appendChild", target: <branchMarkerId>

Steps to populate an IF branch:
1. Create the IF node via cognigy_create (see flow-chart-reading for correct config schema)
2. GET the flow chart — find the IF node's childIds array
3. childIds[0] is the Then marker _id, childIds[1] is the Else marker _id
4. Create content nodes with mode: "append", target: <branch-marker-_id>

Example: IF node "if-abc" with childIds ["then-xyz", "else-xyz"]
  - To add a Say node to Then: mode="append", target="then-xyz"
  - To add a Code node to Else: mode="append", target="else-xyz"

Common pitfall: targeting the IF node's own _id ("if-abc") instead of the branch marker.
```

- [ ] **Step 6: Run the new failing test — verify it now passes**

```bash
uv run pytest tests/tools/test_explain.py::test_node_positioning_branch_content_uses_append_sibling -v
```

Expected: PASS

- [ ] **Step 7: Run the full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass (106 + 1 new = 107 passing).

- [ ] **Step 8: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/explain.py cognigy-mcp/tests/tools/test_explain.py
git commit -m "fix: correct branch population mode in node-positioning — append not appendChild (fixes #27)"
```

---

## Self-Review

**Spec coverage:**
- #27 — Both Once and IF branch sections corrected, WRONG/CORRECT contrast added ✓
- `appendChild` legitimate use (aiAgentJobTool) left unchanged ✓
- Existing IF branch test updated to assert correct mode ✓
- New test asserts "sibling" concept and "WRONG" label ✓

**Placeholder scan:** No TBD/TODO. All code blocks are complete and match current file content.

**Type consistency:** No new functions or types. All string literals match the exact current content in explain.py lines 90–124.

**Noted scope boundary:** The `_TOPIC_INDEX` description line ("append vs appendChild modes, child branch population") is still accurate after the fix — `appendChild` is still documented (as WRONG for branches, correct for aiAgentJobTool). No update needed.
