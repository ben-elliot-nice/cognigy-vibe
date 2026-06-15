# Design: submit-issue skill

**Date:** 2026-06-16
**Skill name:** `cognigy:submit-issue`

## Purpose

A skill invoked when the LLM encounters a bug, unexpected behaviour, or failure in this plugin — either in an MCP server tool or a cognigy skill. The LLM synthesises everything it already knows from conversation context and submits a detailed GitHub issue without any user interaction.

## Trigger

Invoked when:
- An MCP server tool returns an unexpected error or wrong result
- A skill produces incorrect output or fails mid-execution
- The user reports that something in this plugin isn't working

## What the skill does

1. Synthesises the following from conversation context (no user questions):
   - Affected component (MCP tool name, skill name, or "unknown")
   - What happened (observed behaviour)
   - What was expected (correct/intended behaviour)
   - Reproduction steps
   - Error output (raw error text, stack trace, API response)
   - Root cause hypothesis (or "unknown" if not determined)
   - Additional context (Cognigy environment, flow, node type, etc.)
2. Formats a title and body using the standard template
3. Submits via `gh issue create` if available, otherwise falls back to manual instructions
4. Reports the outcome to the user

## Issue title format

```
[<component>] <short description of the failure>
```

Examples:
- `[cognigy_create] 500 error when creating aiAgentJob node`
- `[add-aiagent-job skill] resolve_resource returns no match for valid flow name`

## Issue body template

```markdown
## Component
[MCP server tool name | skill name | other]

## What happened
[Observed behaviour]

## What was expected
[Correct/intended behaviour]

## Reproduction steps
[Numbered steps extracted from conversation context]

## Error output
[Raw error text, stack trace, or API response — "none captured" if unavailable]

## Root cause hypothesis
[LLM's analysis of likely cause — "unknown" if not determined]

## Context
[Any other relevant details: Cognigy environment, flow involved, node type, etc.]
```

## Submission mechanism

### gh available

```bash
which gh
```

If found, submit:

```bash
gh issue create \
  --repo ben-elliot-nice/cognigy-claude-plugin \
  --title "<title>" \
  --body "<body>"
```

Report the created issue URL to the user.

### gh not available

Tell the user `gh` is not installed, then present:

1. Link to open: `https://github.com/ben-elliot-nice/cognigy-claude-plugin/issues/new`
2. Issue title in a code block (copy-paste ready)
3. Issue body in a code block (copy-paste ready)

Do not attempt to install `gh` or call the GitHub API directly.

## Skill file location

`skills/submit-issue/SKILL.md`

## No user interaction

The LLM is the sole author. It does not ask the user questions, show a draft for approval, or wait for confirmation before submitting. All content is derived from conversation context.
