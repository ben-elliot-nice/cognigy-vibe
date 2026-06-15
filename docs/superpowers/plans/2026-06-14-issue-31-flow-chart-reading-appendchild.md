# Issue #31: flow-chart-reading IF branch population fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `explain("flow-chart-reading")` to document `mode="append"` (not `mode="appendChild"`) for populating IF node branches, matching the already-correct `explain("node-positioning")`.

**Architecture:** Single string replacement in `explain.py` line 301. One new regression test in `test_explain.py`. No logic changes.

**Tech Stack:** Python 3.11+, pytest, uv

---

## File Map

| File | Change |
|---|---|
| `cognigy-mcp/cognigy_mcp/tools/explain.py` | Fix one line in the `flow-chart-reading` topic |
| `cognigy-mcp/tests/tools/test_explain.py` | Add one regression test |
| `cognigy-mcp/pyproject.toml` | Bump version 1.3.7 → 1.3.8 |
| `.claude-plugin/plugin.json` | Bump version 1.3.7 → 1.3.8 |

---

## Task 1: Fix flow-chart-reading IF branch population

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/explain.py` (line 301)
- Modify: `cognigy-mcp/tests/tools/test_explain.py`

- [ ] **Step 1: Write the failing test**

Append to `cognigy-mcp/tests/tools/test_explain.py`:

```python
# ── Issue #31: flow-chart-reading IF branch population contradicts node-positioning ──

def test_flow_chart_reading_if_branch_uses_append_not_appendchild(mock_client, state, cache):
    """flow-chart-reading must document mode='append' for IF branches, not mode='appendChild'."""
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "flow-chart-reading"})
    text = result[0].text
    assert 'mode="appendChild"' not in text, \
        "flow-chart-reading must not document appendChild for IF branches (contradicts node-positioning)"
    assert 'mode="append"' in text and 'branch-marker' in text, \
        "flow-chart-reading must document mode='append' with branch-marker as target"
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py::test_flow_chart_reading_if_branch_uses_append_not_appendchild -v 2>&1 | tail -20
```

Expected: `FAILED` — AssertionError on `mode="appendChild"` still present.

- [ ] **Step 3: Fix explain.py**

In `cognigy-mcp/cognigy_mcp/tools/explain.py`, replace (in the `### if nodes` section of `flow-chart-reading`):

```python
To add nodes inside a branch: use mode="appendChild", target="<branch-container-_id>".
```

with:

```python
To add nodes inside a branch: use mode="append", target="<branch-marker-_id>" (same rule as Once nodes — append after the marker, not as a child of it).
```

- [ ] **Step 4: Run the test — confirm it passes**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest tests/tools/test_explain.py::test_flow_chart_reading_if_branch_uses_append_not_appendchild -v 2>&1 | tail -10
```

Expected: `PASSED`

- [ ] **Step 5: Run the full test suite — confirm no regressions**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cognigy-mcp
uv run pytest -v 2>&1 | tail -15
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add cognigy-mcp/cognigy_mcp/tools/explain.py
git add cognigy-mcp/tests/tools/test_explain.py
git commit -m "$(cat <<'EOF'
fix: correct IF branch population in flow-chart-reading — append not appendChild (#31)

flow-chart-reading documented mode=appendChild for IF node branches, contradicting
node-positioning (fixed in 1.3.7). Correct mode is append with the branch marker node
as target — appendChild targets the container and breaks UI rendering.
EOF
)"
```

---

## Task 2: Bump versions

**Files:**
- Modify: `cognigy-mcp/pyproject.toml`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Bump cognigy-mcp version**

In `cognigy-mcp/pyproject.toml`, replace:
```toml
version = "1.3.7"
```
with:
```toml
version = "1.3.8"
```

- [ ] **Step 2: Bump plugin version**

In `.claude-plugin/plugin.json`, replace:
```json
  "version": "1.3.7",
```
with:
```json
  "version": "1.3.8",
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
git commit -m "chore: bump version to 1.3.8"
```

---

## Self-Review

**Spec coverage:**
- #31 (flow-chart-reading documents wrong mode for IF branches): Task 1 ✓
- Version bump: Task 2 ✓

**Placeholder scan:** No TBDs. All steps have exact code and commands.

**Type consistency:** No new types. Pure string replacement.
