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

```
<title>
```

> 3. Copy and paste this body:

```markdown
<body>
```
