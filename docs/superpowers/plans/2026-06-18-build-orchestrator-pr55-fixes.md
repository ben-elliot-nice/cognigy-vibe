# Build Orchestrator PR #55 Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five issues found in code review of PR #55 (`cognigy:build-orchestrator`) — two critical documentation errors that will cause build failures on every run, two important format mismatches that produce broken output, and one stale warning plus one minor label inconsistency.

**Architecture:** All changes are doc-only edits to a single markdown skill file. No code changes, no version bump required (skills/ change only — but per CLAUDE.md, skills/ changes DO require a version bump; include it). Work is in the checked-out worktree at `.claude/worktrees/build-orchestrator/`.

**Tech Stack:** Markdown, git

## Global Constraints

- All edits are to `.claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md` only (plus the version bump files).
- Do NOT alter any prose outside the specific lines called out in each task — this is a targeted fix, not a rewrite.
- Verify each fix with `grep` before and after to confirm the change landed correctly.
- Per CLAUDE.md: after any skills/ change, bump patch version in both `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json` (1.4.3 → 1.4.4).
- All git commands are separate Bash calls (per CLAUDE.md shell rule).
- All work happens in `.claude/worktrees/build-orchestrator/` — commit from there, which commits to the `feat/build-orchestrator-skill` branch.

---

### Task 1: Fix `get_flow_chart` return shape (Critical #1)

Four locations in the file claim the wrong response key (`hierarchyString` instead of `hierarchy`) and omit the required `format` parameter.

**Files:**
- Modify: `.claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md` (lines 865, 871–872, 879, 966–969, 1620)

**Interfaces:**
- Produces: correct `get_flow_chart` documentation consumed by Tasks 2–5 (no cross-task dependency — these are independent text fixes)

- [ ] **Step 1: Verify the four incorrect occurrences exist before editing**

```bash
grep -n "hierarchyString\|get_flow_chart { flow_id.*}" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected output includes lines 865, 872, 879, 968, 1620 with the incorrect text.

- [ ] **Step 2: Fix §1.6 prose description (line 865)**

In `SKILL.md`, replace:

```
The primary source of truth is now `get_flow_chart`, which returns the live flow structure with a relations array + readable hierarchy string.
```

With:

```
The primary source of truth is now `get_flow_chart { format: "both" }`, which returns the live flow structure with a `nodes` array, a `relations` array, and a readable `hierarchy` string.
```

- [ ] **Step 3: Fix §1.6 Step 1 code block and caption (lines 869–879)**

Replace:

```
1. **Read the live flow structure.**
   ```
   get_flow_chart { flow_id: "<flow.id>" }
   → returns { nodes: [...], relations: [...], hierarchyString: "..." }
   ```
   This is the source of truth.

2. **Read each node's full config via `cognigy_get`** as needed for verbatim Code-body / Say-text capture. Iterate over `nodes` from step 1.

3. **Generate `[CUSTOMER]_FLOW_INSERTS.md`** from the hierarchy string + relations + per-node `cognigy_get` reads. Required sections:
   1. Architecture diagram (ASCII) — derived from `hierarchyString`
```

With:

```
1. **Read the live flow structure.**
   ```
   get_flow_chart { flow_id: "<flow.id>", format: "both" }
   → returns { nodes: [...], relations: [...], hierarchy: "..." }
   ```
   Pass `format: "both"` to get the node/relation arrays AND the readable hierarchy string in one call. (`format: "hierarchy"` — the default — returns only `{ hierarchy: "..." }`; `format: "raw"` returns only `{ nodes, relations }`.) This is the source of truth.

2. **Read each node's full config via `cognigy_get`** as needed for verbatim Code-body / Say-text capture. Iterate over `nodes` from step 1.

3. **Generate `[CUSTOMER]_FLOW_INSERTS.md`** from the hierarchy string + relations + per-node `cognigy_get` reads. Required sections:
   1. Architecture diagram (ASCII) — derived from `hierarchy`
```

- [ ] **Step 4: Fix §1.7 Phase A Step 1 code block (lines 966–969)**

Replace:

```
1. **Read the live chart.**
   ```
   get_flow_chart { flow_id: "<flowId>" }
   ```
```

With:

```
1. **Read the live chart.**
   ```
   get_flow_chart { flow_id: "<flowId>", format: "raw" }
   ```
   Use `format: "raw"` here — Phase A walks node IDs and relation chains, not the human-readable hierarchy string.
```

- [ ] **Step 5: Fix §7 cheatsheet `get_flow_chart` row (line 1620)**

Replace:

```
| cognigy-vibe | `get_flow_chart` | Returns `nodes`, `relations` array, and a readable `hierarchyString`. Primary source for as-built generation (§1.6). Required AFTER `create_ai_agent` (find `aiAgentJob` node ID) and AFTER creating `once` (find auto-created `onFirstExecution` / `afterwards` IDs). |
```

With:

```
| cognigy-vibe | `get_flow_chart` | Returns shape depends on `format` param: `"hierarchy"` (default) → `{ hierarchy: "..." }` only; `"raw"` → `{ nodes: [...], relations: [...] }` only; `"both"` → all three fields. Key is `hierarchy`, NOT `hierarchyString`. Use `format: "both"` for as-built generation (§1.6); use `format: "raw"` when walking node IDs (§1.7 Phase A). Required AFTER `create_ai_agent` (find `aiAgentJob` node ID) and AFTER creating `once` (find auto-created `onFirstExecution` / `afterwards` IDs). |
```

- [ ] **Step 6: Verify all four fixes landed — no `hierarchyString` should remain**

```bash
grep -n "hierarchyString" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: no output.

```bash
grep -n "get_flow_chart" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: all occurrences now include `format:` or describe the format parameter correctly.

- [ ] **Step 7: Commit**

```bash
git -C .claude/worktrees/build-orchestrator add skills/build-orchestrator/SKILL.md
```

```bash
git -C .claude/worktrees/build-orchestrator commit -m "fix: correct get_flow_chart return shape — hierarchy key, format param"
```

---

### Task 2: Fix extension name for AI Agent nodes (Critical #2)

Two lines document the extension for `aiAgentJobTool`/`aiAgentToolAnswer`/`aiAgentJob` as `cognigy-ai-agent`. The correct extension is `@cognigy/basic-nodes`.

**Files:**
- Modify: `.claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md` (lines 593, 1608)

- [ ] **Step 1: Verify both incorrect occurrences exist**

```bash
grep -n "cognigy-ai-agent" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: lines 593 and 1608.

- [ ] **Step 2: Fix §1.4 insertion rule prose (line 593)**

Replace:

```
Extension is auto-injected for `cognigy-ai-agent` / `cxone-utils` / `@cognigy/voicegateway2`.
```

With:

```
Extension is auto-injected for `@cognigy/basic-nodes` (AI Agent nodes) / `cxone-utils` / `@cognigy/voicegateway2`.
```

- [ ] **Step 3: Fix §7 cheatsheet `cognigy_create` row (line 1608)**

Replace:

```
`cognigy-ai-agent` for `aiAgentJobTool`/`aiAgentToolAnswer`/`aiAgentJob`
```

With:

```
`@cognigy/basic-nodes` for `aiAgentJobTool`/`aiAgentToolAnswer`/`aiAgentJob`
```

- [ ] **Step 4: Verify no `cognigy-ai-agent` remains**

```bash
grep -n "cognigy-ai-agent" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git -C .claude/worktrees/build-orchestrator add skills/build-orchestrator/SKILL.md
```

```bash
git -C .claude/worktrees/build-orchestrator commit -m "fix: correct AI Agent node extension name — @cognigy/basic-nodes not cognigy-ai-agent"
```

---

### Task 3: Fix §1.4b xApp scaffold — add missing IF node creation (Important #3)

The "build from scratch" path in §1.4b Step 2 only creates the `setHTMLAppState` node, targeting `<ifThenElse.childIds[0]>` — but never creates the IF node itself. A Claude following this on a fresh build will fail immediately.

**Files:**
- Modify: `.claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md` (lines 601, 610, 622–636)

- [ ] **Step 1: Verify current broken text at line 622**

```bash
sed -n '620,637p' \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: Step 2 prose mentions "build it from scratch:" and jumps straight to a `cognigy_create` for `setHTMLAppState` without a preceding `cognigy_create` for the `if` node.

- [ ] **Step 2: Fix the recommended-pattern description and layout diagram (lines 601, 610)**

Replace:

```
**Recommended pattern: conditional push via `ifThenElse` guard** (per plugin `explain("xapp-delivery")`). One `setHTMLAppState` node lives per scene type, gated behind an `ifThenElse` that checks a `context.xappTrigger` flag. Tool branches that fire that scene set the flag in their Code mock; tool branches that don't, leave the flag false. This avoids redundant `setHTMLAppState` nodes propagated through every tool branch.
```

With:

```
**Recommended pattern: conditional push via `if` gate** (per plugin `explain("xapp-delivery")`). One `setHTMLAppState` node lives per scene type, gated behind an `if` node (type `"if"`, NOT `"ifThenElse"`) that checks a `context.xappTrigger` flag. Tool branches that fire that scene set the flag in their Code mock; tool branches that don't, leave the flag false. This avoids redundant `setHTMLAppState` nodes propagated through every tool branch.
```

Replace in the layout diagram:

```
       └─ [ifThenElse: context.xappTrigger === true]
```

With:

```
       └─ [if: context.xappTrigger === true]   // type "if", NOT "ifThenElse"
```

- [ ] **Step 3: Replace §1.4b Step 2 with the corrected two-call scaffold**

Replace the entire Step 2 block — from `2. **Create the` through the closing `is the only reliable mode.` line — with:

````markdown
2. **Create the `if` + `setHTMLAppState` scaffold once** (idempotent). To detect an existing scaffold: call `get_flow_chart { flow_id: "<flowId>", format: "raw" }` and look for an `if` node whose condition references `context.xappTrigger`. Per plugin `explain("node-positioning")` (v1.4.0), an IF node auto-creates two **branch-marker** children in `childIds[]`: **`childIds[0]` = the Then (true) branch marker, `childIds[1]` = the Else marker.** Content inside a branch must be a **sibling appended after the marker** — `mode: "append"`, `target: <childIds[0]>` (the Then marker `_id`). Do NOT walk to a "true-branch tail" manually, and do NOT `appendChild` onto the marker (that nests inside it and breaks UI rendering). If the scaffold exists, append the new scene after the Then marker. If not, build from scratch — two calls:
   ```
   // Step 2a — create the IF gate node
   cognigy_create {
     resource_type: "node",
     flow_id: "<flowId>",
     body: {
       type: "if",
       mode: "append",
       target: "<resetXappTriggersCodeNodeId>",
       label: "xApp trigger gate",
       config: { conditions: [{ type: "cognigyScript", condition: "context.xappTrigger === true" }] }
     }
   }
   → returns { _id: "<ifNodeId>" }

   // Step 2b — read the branch-marker IDs the IF node auto-created
   get_flow_chart { flow_id: "<flowId>", format: "raw" }
   // Find the node with _id === "<ifNodeId>"; read childIds[0] (Then branch marker)

   // Step 2c — create the setHTMLAppState node inside the Then branch
   cognigy_create {
     resource_type: "node",
     flow_id: "<flowId>",
     body: {
       type: "setHTMLAppState",
       mode: "append",
       target: "<ifNodeId.childIds[0] — the Then branch marker>",
       label: "xApp — <scene_name>",
       config: {}
     }
   }
   ```
   Extension is auto-injected (`@cognigy/basic-nodes` for `if`; `cxone-utils` for `setHTMLAppState`). **Do NOT use `insertAfter` / `insertBefore`** — broken on AU1 (return 500); `append` against the branch marker is the only reliable mode.
````

- [ ] **Step 4: Verify the IF node creation step is now present**

```bash
grep -n "Step 2a\|Step 2b\|Step 2c\|ifNodeId" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: matches on the new Step 2a/2b/2c labels.

```bash
grep -n "ifThenElse.childIds\|ifThenElse.*guard\|\[ifThenElse:" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: no output (all `ifThenElse` labels in §1.4b replaced). Note: `ifThenElse` in the `manage_flow_nodes` row (line 1606) and inbound-submit reference (line 662) are correct — leave those.

- [ ] **Step 5: Commit**

```bash
git -C .claude/worktrees/build-orchestrator add skills/build-orchestrator/SKILL.md
```

```bash
git -C .claude/worktrees/build-orchestrator commit -m "fix: add missing IF node cognigy_create in §1.4b xApp scaffold from-scratch path"
```

---

### Task 4: Fix §5 end-call tool parameter format (Important #4)

Both `end_call` and `end_call_resolved` show a stringified `create_tool` parameter block. The canonical path uses `push_agent_tool` with `.tool.json`, which requires either real JSON Schema objects or — for param-free tools — omitting `parameters` entirely.

**Files:**
- Modify: `.claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md` (lines 1460, 1489)

- [ ] **Step 1: Verify both incorrect lines exist**

```bash
grep -n "Parameters.*type.*object.*properties" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: two matches, one for `end_call` (~line 1460) and one for `end_call_resolved` (~line 1489).

- [ ] **Step 2: Fix `end_call` Parameters line (line 1460)**

Replace:

```
**Parameters:** `'{"type":"object","properties":{},"required":[]}'`
```

(the one under `### end_call`) with:

```
**Parameters:** None — param-free tool. **Omit `parameters` from the `.tool.json` entirely** (per §1.3: "omit `parameters` entirely for param-free tools"). Do not use the stringified `create_tool` format here — this tool is authored via `push_agent_tool` with a `.tool.json` file.
```

- [ ] **Step 3: Fix `end_call_resolved` Parameters line (line 1489)**

Replace:

```
**Parameters:** `'{"type":"object","properties":{},"required":[]}'`
```

(the one under `### end_call_resolved`) with:

```
**Parameters:** None — param-free tool. **Omit `parameters` from the `.tool.json` entirely** (same as `end_call` above).
```

- [ ] **Step 4: Verify no stringified parameter blocks remain in §5**

```bash
grep -n "Parameters.*type.*object.*properties" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git -C .claude/worktrees/build-orchestrator add skills/build-orchestrator/SKILL.md
```

```bash
git -C .claude/worktrees/build-orchestrator commit -m "fix: §5 end_call parameter format — omit parameters in .tool.json for param-free tools"
```

---

### Task 5: Fix stale `cognigy_list` singular-gives-404 warning (Important #5)

Two locations warn that `cognigy_list` returns 404 on singular `resource_type`. The server now normalises common singulars — the warning is false and will cause unnecessary friction.

**Files:**
- Modify: `.claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md` (lines 311, 1602)

- [ ] **Step 1: Verify both stale warning occurrences**

```bash
grep -n "singular gives 404" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: two matches.

- [ ] **Step 2: Fix MCP tool split table row (line 311)**

Replace:

```
| `cognigy_list` | List resources. `resource_type` must be **plural** (`projects`, `flows`, `tools`, etc.) — singular gives 404. See §7 cheatsheet. |
```

With:

```
| `cognigy_list` | List resources. `resource_type` accepts both singular (`flow`) and plural (`flows`) — the server normalises common singulars. Prefer plural to match the Cognigy API directly. See §7 cheatsheet. |
```

- [ ] **Step 3: Fix §7 cheatsheet `cognigy_list` row (line 1602)**

Replace:

```
| cognigy-vibe | `cognigy_list` | `resource_type` is **plural** (`projects`, `flows`, `endpoints`, `connections`, `large-language-models`, `tools`). Singular gives 404. |
```

With:

```
| cognigy-vibe | `cognigy_list` | `resource_type` accepts both singular (`flow`) and plural (`flows`) — the server normalises common singulars to their plural form. Prefer plural to match the Cognigy API directly. |
```

- [ ] **Step 4: Verify no stale 404 warning remains**

```bash
grep -n "singular gives 404" \
  .claude/worktrees/build-orchestrator/skills/build-orchestrator/SKILL.md
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git -C .claude/worktrees/build-orchestrator add skills/build-orchestrator/SKILL.md
```

```bash
git -C .claude/worktrees/build-orchestrator commit -m "fix: update cognigy_list docs — server normalises singulars, drop stale 404 warning"
```

---

### Task 6: Bump plugin and MCP version (1.4.3 → 1.4.4)

Per CLAUDE.md, any `skills/` change requires a patch version bump in both `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json`.

**Files:**
- Modify: `.claude/worktrees/build-orchestrator/.claude-plugin/plugin.json` (version field)
- Modify: `.claude/worktrees/build-orchestrator/cognigy-mcp/pyproject.toml` (version field)
- Modify: `.claude/worktrees/build-orchestrator/cognigy-mcp/uv.lock` (auto-updated by uv)

- [ ] **Step 1: Verify current version in both files**

```bash
grep "version" .claude/worktrees/build-orchestrator/.claude-plugin/plugin.json
```

```bash
grep "^version" .claude/worktrees/build-orchestrator/cognigy-mcp/pyproject.toml
```

Expected: both show `1.4.3`.

- [ ] **Step 2: Bump `.claude-plugin/plugin.json`**

In `.claude/worktrees/build-orchestrator/.claude-plugin/plugin.json`, change:

```json
"version": "1.4.3",
```

To:

```json
"version": "1.4.4",
```

- [ ] **Step 3: Bump `cognigy-mcp/pyproject.toml`**

In `.claude/worktrees/build-orchestrator/cognigy-mcp/pyproject.toml`, change:

```toml
version = "1.4.3"
```

To:

```toml
version = "1.4.4"
```

- [ ] **Step 4: Update uv.lock**

```bash
uv lock --project .claude/worktrees/build-orchestrator/cognigy-mcp
```

- [ ] **Step 5: Verify the bump landed**

```bash
grep "version" .claude/worktrees/build-orchestrator/.claude-plugin/plugin.json
```

```bash
grep "^version" .claude/worktrees/build-orchestrator/cognigy-mcp/pyproject.toml
```

Expected: both show `1.4.4`.

- [ ] **Step 6: Commit**

```bash
git -C .claude/worktrees/build-orchestrator add .claude-plugin/plugin.json cognigy-mcp/pyproject.toml cognigy-mcp/uv.lock
```

```bash
git -C .claude/worktrees/build-orchestrator commit -m "chore: bump to 1.4.4 — build-orchestrator skill doc fixes"
```

---

### Task 7: Create branch, push, and comment on PR

- [ ] **Step 1: Create a new branch from the current worktree HEAD**

The worktree is currently on detached HEAD at the tip of `feat/build-orchestrator-skill`. Create a named branch so we can push without touching the contributor's branch:

```bash
git -C .claude/worktrees/build-orchestrator checkout -b fix/build-orchestrator-pr55-review
```

- [ ] **Step 2: Verify branch and commits look right**

```bash
git -C .claude/worktrees/build-orchestrator log --oneline origin/feat/build-orchestrator-skill..HEAD
```

Expected: 6 commits (one per task above).

- [ ] **Step 3: Push the new branch**

```bash
git -C .claude/worktrees/build-orchestrator push -u origin fix/build-orchestrator-pr55-review
```

- [ ] **Step 4: Comment on PR #55 with the branch link**

```bash
gh pr comment 55 --body "Review fixes applied on a separate branch: \`fix/build-orchestrator-pr55-review\`. Changes: corrected \`get_flow_chart\` return shape (\`hierarchy\` key, \`format: \"both\"\`/\`\"raw\"\`), fixed AI Agent node extension name (\`@cognigy/basic-nodes\`), added missing IF node \`cognigy_create\` in §1.4b from-scratch path, fixed \`end_call\`/\`end_call_resolved\` parameter format in §5 (omit \`parameters\` in \`.tool.json\`), removed stale \`cognigy_list\` 404 warning. Bumped to 1.4.4."
```
