# submit-issue Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a `cognigy:submit-issue` skill that lets the LLM file a detailed GitHub issue from conversation context — no user input required.

**Architecture:** A single `SKILL.md` file containing step-by-step instructions for the LLM: extract issue content from conversation context, check for `gh` CLI, submit via `gh issue create` or fall back to manual copy-paste instructions. No code, no MCP changes — skills in this repo are markdown instruction documents only.

**Tech Stack:** Markdown skill file, `gh` CLI for submission, `plugin.json` version bump.

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `skills/submit-issue/SKILL.md` | Full skill instructions |
| Modify | `.claude-plugin/plugin.json` | Patch version bump (skills change) |

---

### Task 1: Create the skill file

**Files:**
- Create: `skills/submit-issue/SKILL.md`

- [ ] **Step 1: Create the directory**

```bash
mkdir skills/submit-issue
```

- [ ] **Step 2: Write the skill file**

Create `skills/submit-issue/SKILL.md` with exactly this content:

```markdown
---
name: submit-issue
description: When you encounter a bug or unexpected behaviour in this plugin (MCP server or a skill), use this skill to file a detailed GitHub issue from conversation context — no user input required.
---

# cognigy:submit-issue

File a GitHub issue for a bug or unexpected behaviour in this plugin (an MCP server tool or a cognigy skill). Synthesises all relevant context from the current conversation and submits directly — no user input required.

## Step 1: Synthesise issue content from conversation context

From the current conversation, extract:

- **Component**: The specific MCP tool (e.g. `cognigy_create`, `resolve_resource`) or skill (e.g. `add-aiagent-job`) that failed. Use `unknown` if unclear.
- **What happened**: The observed behaviour — what actually occurred.
- **What was expected**: The correct/intended behaviour.
- **Reproduction steps**: Numbered steps that would reproduce the failure.
- **Error output**: Raw error text, stack trace, API response, or tool result. Use `none captured` if unavailable.
- **Root cause hypothesis**: Your analysis of what likely caused the failure. Use `unknown` if not determined.
- **Context**: Any other relevant details — Cognigy environment, flow name, node type, API endpoint, etc.

**Title format:**

```
[<component>] <short description of the failure>
```

Examples:
- `[cognigy_create] 500 error when creating aiAgentJob node`
- `[add-aiagent-job skill] resolve_resource returns no match for valid flow name`

**Body:**

```markdown
## Component
<component>

## What happened
<observed behaviour>

## What was expected
<correct/intended behaviour>

## Reproduction steps
<numbered steps>

## Error output
<raw error text, or "none captured">

## Root cause hypothesis
<analysis, or "unknown">

## Context
<environment, flow, node type, API details, etc.>
```

## Step 2: Check for gh CLI

Run:

```bash
which gh
```

## Step 3a: Submit via gh (if available)

If `which gh` succeeded, run:

```bash
gh issue create \
  --repo ben-elliot-nice/cognigy-claude-plugin \
  --title "<title>" \
  --body "<body>"
```

Report the created issue URL to the user.

## Step 3b: Manual fallback (if gh not available)

If `which gh` failed, tell the user:

> `gh` CLI is not installed. To file this issue manually:
>
> 1. Open: https://github.com/ben-elliot-nice/cognigy-claude-plugin/issues/new
> 2. Copy and paste this title:

` `` `
<title>
` `` `

> 3. Copy and paste this body:

` `` `markdown
<body>
` `` `
```

- [ ] **Step 3: Verify the file was created**

```bash
cat skills/submit-issue/SKILL.md
```

Expected: file content matches exactly what was written. Frontmatter has `name` and `description`. Three steps are present: synthesise, check gh, submit or fallback.

- [ ] **Step 4: Commit**

```bash
git add skills/submit-issue/SKILL.md
git commit -m "feat: add submit-issue skill"
```

---

### Task 2: Bump plugin version

**Files:**
- Modify: `.claude-plugin/plugin.json`

Per `CLAUDE.md`: any change to `skills/` requires a patch increment to `.claude-plugin/plugin.json`. Current version is `1.3.13`.

- [ ] **Step 1: Update version in plugin.json**

Edit `.claude-plugin/plugin.json`, changing `"version": "1.3.13"` to `"version": "1.3.14"`. The full file should be:

```json
{
  "name": "cognigy",
  "description": "Cognigy AI agent development skills for Claude Code",
  "version": "1.3.14",
  "author": {
    "name": "Ben Elliot",
    "email": "ben.elliot@nice.com"
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "chore: bump plugin version to 1.3.14"
```

---

### Task 3: Push and update marketplace

- [ ] **Step 1: Push to remote**

```bash
git push
```

- [ ] **Step 2: Update marketplace parent repo**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```
