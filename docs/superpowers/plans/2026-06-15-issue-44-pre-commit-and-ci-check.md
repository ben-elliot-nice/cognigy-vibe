# Issue #44: Pre-Commit Hook + CI Staleness Check

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure generated files (`SKILL.md` and `_explain_topics_generated.py`) never drift from their `resources/*.md` sources — enforced locally by a pre-commit hook and in CI by a PR diff check.

**Architecture:** A `.githooks/pre-commit` script detects staged `resources/*.md` files, re-runs the build script, and stages the generated outputs before the commit lands. A separate GitHub Actions workflow (`.github/workflows/check-explain-topics.yml`) runs on every PR that touches `resources/` or the build script, regenerates the outputs, and fails with a clear message if `git diff` detects any delta versus what was committed.

**Tech Stack:** Bash (hook script), GitHub Actions, `uv run` (already available in both environments). No new dependencies.

---

## Context

This plan covers deliverables 4 and 5 from issue #44, which are absent from the existing plan (`2026-06-15-issue-44-explain-skill-pipeline.md`):

- **Deliverable 4** — local pre-commit hook
- **Deliverable 5 (partial)** — the PR diff check workflow (the `publish.yml` build step is covered in the existing plan)

**Prerequisite:** The existing plan must be complete before this one is executed. Specifically, `scripts/build_explain_topics.py` must exist and run cleanly, and `skills/explain/resources/` must contain at least one topic file.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `.githooks/pre-commit` | Hook: detect staged resources, regenerate, stage outputs |
| Create | `.github/workflows/check-explain-topics.yml` | CI: regenerate + diff check on PRs |

---

## Task 1: Pre-commit hook

**Files:**
- Create: `.githooks/pre-commit`

The hook fires before every commit. It checks whether any `skills/explain/resources/*.md` files are staged. If so, it runs the build script and stages the two generated outputs so they're included in the same commit. The commit then proceeds normally.

- [ ] **Step 1: Create `.githooks/` directory and write the hook**

```bash
mkdir -p .githooks
```

Create `.githooks/pre-commit` with this content:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Check if any explain resource files are staged
if git diff --cached --name-only | grep -q '^skills/explain/resources/'; then
  echo "[pre-commit] explain resources changed — regenerating..."
  uv run scripts/build_explain_topics.py
  git add \
    skills/explain/SKILL.md \
    cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
  echo "[pre-commit] generated files staged."
fi
```

- [ ] **Step 2: Make the hook executable**

```bash
chmod +x .githooks/pre-commit
```

- [ ] **Step 3: Configure git to use `.githooks/`**

```bash
git config core.hooksPath .githooks
```

Verify:

```bash
git config core.hooksPath
```

Expected output: `.githooks`

- [ ] **Step 4: Smoke-test the hook manually**

Stage one of the resource files (or create a trivial change to it) without running the build script first, then trigger the hook directly:

```bash
# Make a trivial, reversible change to a resource file
echo "" >> skills/explain/resources/code-node-patterns.md
git add skills/explain/resources/code-node-patterns.md

# Run the hook directly (same as git commit would do)
bash .githooks/pre-commit
```

Expected output:
```
[pre-commit] explain resources changed — regenerating...
Generated: cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
Generated: skills/explain/SKILL.md
Done. 4 topic(s) processed.
[pre-commit] generated files staged.
```

- [ ] **Step 5: Verify generated files were staged**

```bash
git diff --cached --name-only
```

Expected: includes `skills/explain/SKILL.md` and `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py`.

- [ ] **Step 6: Revert the trivial change**

```bash
git restore skills/explain/resources/code-node-patterns.md
git restore --staged skills/explain/resources/code-node-patterns.md skills/explain/SKILL.md cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
```

- [ ] **Step 7: Confirm hook does NOT fire on unrelated staged files**

Stage a file outside `skills/explain/resources/`:

```bash
touch /tmp/dummy_test_file.txt
echo "test" >> README.md
git add README.md
bash .githooks/pre-commit
git restore --staged README.md
git restore README.md
```

Expected: no output (hook exits silently without running the build script).

- [ ] **Step 8: Commit**

```bash
git add .githooks/pre-commit
git commit -m "feat: add pre-commit hook to regenerate explain topics when resources change"
```

---

## Task 2: GitHub Actions PR diff check

**Files:**
- Create: `.github/workflows/check-explain-topics.yml`

This workflow runs on pull requests that touch `skills/explain/resources/**` or `scripts/build_explain_topics.py`. It regenerates the outputs, then fails if `git diff` finds any delta — meaning `SKILL.md` or `_explain_topics_generated.py` was not regenerated after a `resources/` change.

- [ ] **Step 1: Write `.github/workflows/check-explain-topics.yml`**

```yaml
name: Check explain topics

on:
  pull_request:
    paths:
      - 'skills/explain/resources/**'
      - 'scripts/build_explain_topics.py'

jobs:
  check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: Regenerate explain topics
        run: uv run scripts/build_explain_topics.py

      - name: Fail if generated files are out of sync
        run: |
          if ! git diff --exit-code \
              skills/explain/SKILL.md \
              cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py; then
            echo ""
            echo "ERROR: Generated files are out of sync with resources/."
            echo "Run 'uv run scripts/build_explain_topics.py' locally and commit the result."
            exit 1
          fi
```

- [ ] **Step 2: Verify the workflow file is valid YAML**

```bash
python3 -c "
import yaml, sys
with open('.github/workflows/check-explain-topics.yml') as f:
    yaml.safe_load(f)
print('Valid YAML')
"
```

Expected: `Valid YAML`

- [ ] **Step 3: Simulate a failure case locally**

Manually edit a resource file without regenerating, then run the diff check the same way the workflow does:

```bash
echo "" >> skills/explain/resources/code-node-patterns.md
uv run scripts/build_explain_topics.py
# Now edit the resource AGAIN without regenerating
echo "# extra line" >> skills/explain/resources/code-node-patterns.md

git diff --exit-code \
    skills/explain/SKILL.md \
    cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
```

Expected: exit code 0 (no diff) — the generated files still match the last build run. This confirms that the check catches the case where someone commits a `resources/` change without regenerating.

Restore:

```bash
git restore skills/explain/resources/code-node-patterns.md
git restore skills/explain/SKILL.md cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/check-explain-topics.yml
git commit -m "ci: add PR check to fail if explain generated files are out of sync"
```

---

## Acceptance Checklist

- [ ] `.githooks/pre-commit` exists and is executable
- [ ] `git config core.hooksPath` returns `.githooks`
- [ ] Hook fires when `skills/explain/resources/*.md` files are staged and regenerates + stages both outputs
- [ ] Hook does NOT fire when only unrelated files are staged
- [ ] `.github/workflows/check-explain-topics.yml` exists and is valid YAML
- [ ] Workflow triggers on PRs touching `skills/explain/resources/**` or `scripts/build_explain_topics.py`
- [ ] Workflow fails with a clear message when committed generated files differ from what the build script would produce
