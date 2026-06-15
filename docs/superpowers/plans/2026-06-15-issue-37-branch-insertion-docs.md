# Issue #37: Branch Insertion Docs Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the two conflicting guidance locations for Once/IF branch insertion — fix `turn-structure` (which says `appendChild`, contradicting `node-positioning`) and update `cognigy_create` description (which says insertAfter/insertBefore are "BROKEN on AU1" without offering a working alternative).

**Architecture:** Two string changes in two files. `explain.py` `turn-structure` topic replaces `mode="appendChild"` with `mode="append"` to match the existing correct docs in `node-positioning`. `flow_ops.py` `cognigy_create` description softens the "BROKEN" language and adds an explicit "use append on the branch marker" note. Each change is verified by one new regression test written first (TDD).

**Tech Stack:** Python 3.11+, pytest, uv

---

## File Map

| File | Change |
|---|---|
| `cognigy-mcp/cognigy_mcp/tools/explain.py` | Fix `turn-structure` topic: replace `mode="appendChild"` with `mode="append"` for Once branches |
| `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` | Update `cognigy_create` description + validation error: soften "BROKEN on AU1", add branch-marker guidance |
| `cognigy-mcp/tests/tools/test_explain.py` | Add regression test: turn-structure must not use appendChild for Once branches |
| `cognigy-mcp/tests/tools/test_flow_ops.py` | Add regression test: cognigy_create description must document branch marker pattern |
| `cognigy-mcp/pyproject.toml` | Bump version 1.3.10 → 1.3.11 |
| `.claude-plugin/plugin.json` | Bump version 1.3.10 → 1.3.11 |

---

## Task 1: Fix turn-structure topic (explain.py)

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py` (lines ~432–456)
- Test: `cognigy-mcp/tests/tools/test_explain.py`

- [ ] **Step 1: Write the failing test**

Append to `cognigy-mcp/tests/tools/test_explain.py`:

```python
# ── Issue #37: turn-structure contradicts node-positioning on Once branch insertion ──

def test_turn_structure_once_branch_uses_append_not_appendchild(mock_client, state, cache):
    """turn-structure must document mode='append' for Once branch population, not mode='appendChild'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "turn-structure"})
    text = result[0].text
    assert 'mode="appendChild"' not in text, \
        "turn-structure must not document appendChild for Once branches (contradicts node-positioning)"
    assert 'mode="append"' in text, \
        "turn-structure must document mode='append' for branch population"
    assert "onfirst" in text.lower(), \
        "turn-structure must show branch marker _id as the append target"
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py::test_turn_structure_once_branch_uses_append_not_appendchild -v 2>&1 | tail -20
```

Expected: `FAILED` — AssertionError because `mode="appendChild"` is currently in the topic text.

- [ ] **Step 3: Fix explain.py — replace the Programmatic child branch population section**

In `cognigy-mcp/cognigy_mcp/tools/explain.py`, find and replace the entire `### Programmatic child branch population` section inside the `turn-structure` topic. Replace this exact block:

```python
### Programmatic child branch population
Once nodes auto-create OnFirstTime and Afterwards branches — do NOT attempt to create
them manually (returns HTTP 400 "operation conflicts with constraints").

To add a node to a child branch via the API:
1. GET the flow chart to find the Once node and its childIds
2. The childIds array contains the branch node _ids
3. Create your node with mode="appendChild", target="<branch-node-id>"

Full example — adding a Code node to OnFirstTime:
  // Step 1: get_flow_chart to find the Once node
  // Chart shows Once node "once-abc" with childIds ["onfirst-xyz", "after-xyz"]

  // Step 2: create the Code node as child of OnFirstTime branch
  cognigy_create(resource_type="node", body={
    "flowId": "<flow-id>",
    "type": "code",
    "label": "Load Guest Profile",
    "mode": "appendChild",
    "target": "onfirst-xyz",
    "config": {"code": "const profile = await api.httpRequest({...});"}
  })

Unlike aiAgentJobTool branches (which use append after the tool node),
Once branches use appendChild with the branch node as target.
```

With this:

```python
### Programmatic child branch population
Once nodes auto-create OnFirstTime and Afterwards branches — do NOT attempt to create
them manually (returns HTTP 400 "operation conflicts with constraints").

To add a node to a child branch via the API:
1. GET the flow chart to find the Once node and its childIds
2. The childIds array contains the branch marker _ids (onFirstExecution and afterwards)
3. Create your node with mode="append", target="<branch-marker-id>"

The node inserts as a sibling after the branch marker — it renders inside that branch section.
Do NOT use mode="appendChild" on a branch marker: that nests the node INSIDE the marker, breaking UI rendering.

Full example — adding a Code node to OnFirstTime:
  // Step 1: get_flow_chart to find the Once node
  // Chart shows Once node "once-abc" with childIds ["onfirst-xyz", "after-xyz"]
  //   "onfirst-xyz" = OnFirstTime branch marker (_id)
  //   "after-xyz"   = Afterwards branch marker (_id)

  // Step 2: create the Code node as sibling after OnFirstTime marker
  cognigy_create(resource_type="node", body={
    "flowId": "<flow-id>",
    "type": "code",
    "label": "Load Guest Profile",
    "mode": "append",
    "target": "onfirst-xyz",
    "config": {"code": "const profile = await api.httpRequest({...});"}
  })

Same rule as IF node branches — mode="append" after the branch marker, not appendChild into it.
See node-positioning for the appendChild vs append distinction.
```

- [ ] **Step 4: Run the test — confirm it passes**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py::test_turn_structure_once_branch_uses_append_not_appendchild -v 2>&1 | tail -10
```

Expected: `PASSED`

- [ ] **Step 5: Run the full test suite — confirm no regressions**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest -v 2>&1 | tail -20
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/cognigy_mcp/tools/explain.py
git add cognigy-mcp/tests/tools/test_explain.py
git commit -m "$(cat <<'EOF'
fix: correct Once branch insertion in turn-structure — append not appendChild (#37)

turn-structure documented mode=appendChild for Once branch population, contradicting
node-positioning. Correct mode is append with the branch marker as target — appendChild
nests the node inside the marker and breaks UI rendering.
EOF
)"
```

---

## Task 2: Fix cognigy_create description and validation message (flow_ops.py)

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/flow_ops.py` (lines ~57–64 and ~413–417)
- Test: `cognigy-mcp/tests/tools/test_flow_ops.py`

- [ ] **Step 1: Write the failing test**

Append to `cognigy-mcp/tests/tools/test_flow_ops.py`:

```python
# ── Issue #37: cognigy_create description misleads on branch insertion ──

def test_cognigy_create_description_documents_branch_marker_pattern():
    """cognigy_create description must tell users to append on branch marker for Once/IF branches."""
    tool = next(t for t in TOOLS if t.name == "cognigy_create")
    assert "branch marker" in tool.description, \
        "cognigy_create description must mention 'branch marker' pattern for Once/IF branch insertion"
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_flow_ops.py::test_cognigy_create_description_documents_branch_marker_pattern -v 2>&1 | tail -20
```

Expected: `FAILED` — AssertionError because "branch marker" is not yet in the description.

- [ ] **Step 3: Fix flow_ops.py — update tool description**

In `cognigy-mcp/cognigy_mcp/tools/flow_ops.py`, replace the `cognigy_create` tool description (lines ~57–64):

```python
        description="POST to create a new Cognigy resource. Auto-saves name→ID to .state.json. "
                    "For nodes, body must include: "
                    "type (e.g. 'say', 'code', 'once', 'httpRequest', 'aiAgentJob'), "
                    "mode — one of: 'appendChild' (add as child of target container), "
                    "'append' (add as last sibling after target), "
                    "'insertAfter' or 'insertBefore' (relative to sibling, BROKEN on AU1), "
                    "target (the _id of the reference node), "
                    "and flowId (the flow _id).",
```

With:

```python
        description="POST to create a new Cognigy resource. Auto-saves name→ID to .state.json. "
                    "For nodes, body must include: "
                    "type (e.g. 'say', 'code', 'once', 'httpRequest', 'aiAgentJob'), "
                    "mode — one of: 'appendChild' (add as child of container, used for aiAgentJobTool only), "
                    "'append' (add as sibling after target — also the correct mode for Once/IF branch insertion: "
                    "target the branch marker _id, not the parent Once/IF node), "
                    "'insertAfter' or 'insertBefore' (may return 500 on AU1 — use append instead), "
                    "target (the _id of the reference node), "
                    "and flowId (the flow _id).",
```

- [ ] **Step 4: Fix flow_ops.py — update the validation error message**

In the same file, replace the validation error message (lines ~413–417):

```python
                        f'Invalid value for field "mode": "{body["mode"]}". '
                        f'Valid values: appendChild (add as child of container node), '
                        f'append (add as last sibling), '
                        f'insertAfter (insert after target sibling — BROKEN on AU1), '
                        f'insertBefore (insert before target sibling — BROKEN on AU1).'
```

With:

```python
                        f'Invalid value for field "mode": "{body["mode"]}". '
                        f'Valid values: appendChild (child of container, aiAgentJobTool only), '
                        f'append (sibling after target — also correct for Once/IF branch insertion: target the branch marker _id), '
                        f'insertAfter (may return 500 on AU1 — prefer append), '
                        f'insertBefore (may return 500 on AU1 — prefer append).'
```

- [ ] **Step 5: Run the test — confirm it passes**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_flow_ops.py::test_cognigy_create_description_documents_branch_marker_pattern -v 2>&1 | tail -10
```

Expected: `PASSED`

- [ ] **Step 6: Run the full test suite — confirm no regressions**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest -v 2>&1 | tail -20
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/cognigy_mcp/tools/flow_ops.py
git add cognigy-mcp/tests/tools/test_flow_ops.py
git commit -m "$(cat <<'EOF'
fix: update cognigy_create description to document branch marker insertion pattern (#37)

The BROKEN on AU1 note for insertAfter/insertBefore caused users to think there was no
API workaround for branch insertion. Added explicit guidance: use mode=append targeting
the branch marker _id for Once/IF branch population. Softened insertAfter/insertBefore
language from BROKEN to may return 500.
EOF
)"
```

---

## Task 3: Bump versions

**Files:**
- Modify: `cognigy-mcp/pyproject.toml`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump cognigy-mcp version**

In `cognigy-mcp/pyproject.toml`, replace:
```toml
version = "1.3.10"
```
with:
```toml
version = "1.3.11"
```

- [ ] **Step 2: Bump plugin version**

In `.claude-plugin/plugin.json`, replace:
```json
  "version": "1.3.10",
```
with:
```json
  "version": "1.3.11",
```

- [ ] **Step 3: Update uv.lock**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv lock
```

- [ ] **Step 4: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/pyproject.toml .claude-plugin/plugin.json cognigy-mcp/uv.lock
git commit -m "chore: bump version to 1.3.11"
```

---

## Self-Review

**Spec coverage:**
- Fix `turn-structure` topic using `mode="appendChild"` for Once branches: Task 1 ✓
- Fix `cognigy_create` description "BROKEN on AU1" without alternative: Task 2 ✓
- Version bump: Task 3 ✓

**Placeholder scan:** No TBDs, no "similar to Task N" shortcuts. All steps have exact code, exact commands, exact expected output.

**Type consistency:** No new types introduced. Pure string replacements. Replacement text in explain.py matches the "onfirst-xyz" naming used in the existing example (test assertion `"onfirst" in text.lower()` is correct).

**Note on insertAfter/insertBefore:** The issue asks whether these modes actually work on AU1. This plan softens the language (BROKEN → may return 500) without claiming they work. Verification requires an AU1 deployment and is out of scope for a documentation fix.
