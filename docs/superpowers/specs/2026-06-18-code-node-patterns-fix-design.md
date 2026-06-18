# Design: code-node-patterns fix (Issue #59)

**Date:** 2026-06-18  
**Branch:** fix/code-node-patterns-59  
**Issue:** [#59](https://github.com/ben-elliot-nice/cognigy-claude-plugin/issues/59)

## Problem

Two gaps from the PR #49 migration:

1. **Missing Runtime Objects content** — `cognigy-api-reference.md` has a Runtime Objects section covering `input`, `context`, `profile`, `analyticsdata`, and `lastConversationEntries`. This was not migrated into `code-node-patterns.md`. The deprecation notice on `cognigy-api-reference.md` points to the explain topic as authoritative, but the topic is missing this content — so the runtime-reference file is not yet redundant.

2. **Wrong directory placement** — `code-node-patterns.md` sits at `skills/explain/resources/code-node-patterns.md` (root level) with no `group:` in its frontmatter. All other code-related topics live under `skills/explain/resources/code/` with `group: code`. This predates the subdirectory structure.

## Changes

### 1. Add Runtime Objects section

Insert a new `### Runtime Objects` section into `code-node-patterns.md` immediately after the existing `### Execution Model` section.

Content covers:

- **`input`** — property table: `text`, `data`, `intentScore`, `intent`, `slots`, `sessionId`, `userId`, `flowName`, `codeNodeError.message`
- **`context`** — direct read access (`context.myKey`), plus a preference note: use `setVar`/`mergeVar` utility functions for writes rather than `api.setContext`/`api.addToContext`. The `api.*` context methods remain listed under API Functions but gain a "prefer utils" callout.
- **`profile`** — `api.updateProfile` and `api.addContactMemory` documented as the current write path. Note: a util function equivalent to `setVar` for profile is tracked in issue #61 and not in scope here.
- **`analyticsdata`** — `custom1`–`custom10`, `intent`, `inputText` direct assignment
- **`lastConversationEntries`** — array of last 10 turns, shape `{ user: '...', bot: '...' }`

### 2. Update Context API Functions sub-section

The existing `#### Context` block under `### API Functions` lists `api.setContext`, `api.getContext`, `api.addToContext`, etc. Add a single-line callout above this block:

> Prefer `setVar`/`mergeVar` for writes — see Utility Functions below. Use `api.*` context methods only when you need array-push semantics (`addToContext` with `'array'`).

### 3. Move file and add `group: code`

- Move `skills/explain/resources/code-node-patterns.md` → `skills/explain/resources/code/code-node-patterns.md`
- Add `group: code` to frontmatter

### 4. Regenerate explain topics

Run `uv run scripts/build_explain_topics.py` to update:
- `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py`
- `skills/explain/SKILL.md`

### 5. Verify deprecation notice

Confirm `runtime-reference/cognigy-api-reference.md` deprecation notice remains accurate — it should be, since after this change the explain topic fully covers all content from the runtime-reference file.

## Out of scope

- Profile utility function (`setProfileVar` or equivalent) — tracked in issue #61
- Any other changes to `cognigy-api-reference.md` beyond verifying the deprecation notice

## Files changed

| File | Change |
|---|---|
| `skills/explain/resources/code-node-patterns.md` | Deleted (moved) |
| `skills/explain/resources/code/code-node-patterns.md` | Created (moved + content added) |
| `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py` | Regenerated |
| `skills/explain/SKILL.md` | Regenerated |
| `runtime-reference/cognigy-api-reference.md` | Verified; update wording if needed |

## Version bump

Per CLAUDE.md rules: after any change to `skills/`, increment patch version in both `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json`.
