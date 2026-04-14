# Scaffold AI Agent Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a `cognigy:scaffold-aiagent` composite skill that adds an AI Agent Job node (and optional tool nodes) to an existing Cognigy flow.

**Architecture:** A single `SKILL.md` composite skill that orchestrates `cognigy:list`, `cognigy:select-node`, and `cognigy:create` atomic skills — no TypeScript changes required. The skill assumes the flow already exists and asks the user to identify it, resolves the AI Agent by name, uses `cognigy:select-node` to identify the insertion point, then creates the job node and any tool nodes.

**Tech Stack:** SKILL.md (markdown skill file), existing CLI + atomic skills

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Create | `skills/scaffold-aiagent/SKILL.md` | The composite skill |
| Modify | `cli/package.json` | Version bump `1.1.10` → `1.1.11` |
| Modify | `.claude-plugin/plugin.json` | Version bump `1.1.10` → `1.1.11` |

---

## Known API Behaviour (from live testing — do not guess)

- `mode: append` — correct mode for inserting a job node after a target (e.g. Start). **`insertAfter` returns a 500 from the Cognigy API — do not use it.**
- `mode: appendChild` — correct mode for attaching tool nodes as children of the job node.
- `aiAgent` config field — takes the agent's **`referenceId`** (UUID, e.g. `d484bc76-...`), NOT `_id`.
- All node operations require `--flowId` as a flag.

---

## Task 1: Write `skills/scaffold-aiagent/SKILL.md`

**Files:**
- Create: `skills/scaffold-aiagent/SKILL.md`

- [ ] **Step 1: Create the skill file**

Write `skills/scaffold-aiagent/SKILL.md` with the following exact content:

```markdown
---
name: scaffold-aiagent
description: Add an AI Agent Job node (and optional tool nodes) to an existing Cognigy flow — resolves the AI Agent and insertion point, then creates all nodes via atomic skills. Use when a flow already exists and you need to add an AI Agent Job with its tools.
---

# Scaffold AI Agent Job

Add an AI Agent Job node to an existing Cognigy flow and attach tool nodes to it.

## Assumptions

- The flow already exists. Do not create it — if not found, stop and tell the user.
- The AI Agent already exists. If not found, stop and tell the user.

---

## Step 1: Resolve the Flow

Ask: "Which flow should the AI Agent Job node be added to? You can give a name or ID."

If the user gives a name (not a 24-char hex ID), invoke `cognigy:list` for `flow` to find it.
- If exactly one match → use it.
- If multiple matches → show them and ask the user to choose.
- If no match → stop. Tell the user the flow was not found.

Capture: `flowId`

---

## Step 2: Resolve the AI Agent

Ask: "Which AI Agent should back this job? You can give a name or ID."

If the user gives a name, invoke `cognigy:list` for `ai-agent` (pass `--projectId <projectId>` if known) to find it.
- If exactly one match → use it.
- If multiple matches → show them and ask the user to choose.
- If no match → stop. Tell the user the agent was not found.

Capture the agent's **`referenceId`** field (UUID format, e.g. `d484bc76-6d77-487f-b97e-6d18f728c232`).
Do NOT use `_id` — the `aiAgent` config field requires the `referenceId`.

Capture: `agentReferenceId`, `agentName`

---

## Step 3: Gather Job Details

Ask in a single prompt:

1. **Job label** — display name for the node (e.g. "Renewals Specialist")
2. **Job description** — what this specialist handles (1-2 sentences; leave blank if not needed)
3. **Job instructions** — standing guidance for this job (leave blank if not needed)
4. **Tools** — list of tools to add as child nodes. For each tool collect:
   - `toolId` — snake_case identifier (e.g. `return_to_concierge`)
   - `label` — display name (e.g. "Return to Concierge")
   - `description` — use format: `"Use this tool when {condition}. Expects {params}. Returns {outcome}."`
   - `useParameters` — yes or no. If yes, ask for the JSON Schema for parameters.

If the user doesn't provide description, instructions, or tools, use empty strings and skip tool creation.

---

## Step 4: Resolve Insertion Point

Ask: "Where in the flow should the job node be inserted? (default: after the Start node)"

Invoke `cognigy:select-node` with:
- `flowId` from Step 1
- The user's target hint (default: `start` type if no hint given)

Capture: `targetNodeId` (the `nodeId` returned by `cognigy:select-node`)

---

## Step 5: Create the AI Agent Job Node

Invoke `cognigy:create` for `node` with these arguments:
- `--flowId <flowId>`
- `--type aiAgentJob`
- `--extension @cognigy/basic-nodes`
- `--label "<job label>"`
- `--target <targetNodeId>`
- `--mode append`
- `--config` with the following JSON object:

```json
{
  "aiAgent": "<agentReferenceId>",
  "name": "<job label>",
  "description": "<job description>",
  "instructions": "<job instructions>",
  "toolChoice": "auto",
  "memoryType": "inherit",
  "temperature": 0.7,
  "maxTokens": 4000,
  "knowledgeSearchBehavior": "onDemand"
}
```

Capture: `jobNodeId` (the `_id` from the response)

---

## Step 6: Create Tool Nodes

For each tool gathered in Step 3, invoke `cognigy:create` for `node` with:
- `--flowId <flowId>`
- `--type aiAgentJobTool`
- `--extension @cognigy/basic-nodes`
- `--label "<tool label>"`
- `--target <jobNodeId>`
- `--mode appendChild`

For tools with `useParameters: false`, use this `--config`:
```json
{
  "toolId": "<toolId>",
  "description": "<tool description>",
  "useParameters": false
}
```

For tools with `useParameters: true`, use this `--config`:
```json
{
  "toolId": "<toolId>",
  "description": "<tool description>",
  "useParameters": true,
  "parameters": {
    "type": "object",
    "properties": {
      "<paramName>": {
        "type": "<string|number|boolean>",
        "description": "<param description>"
      }
    },
    "required": ["<paramName>"],
    "additionalProperties": false
  }
}
```

Create all tools before moving to Step 7.

---

## Step 7: Report

Present a summary table of all created resources:

| Resource | Name | ID |
|---|---|---|
| Flow (existing) | `<flow name>` | `<flowId>` |
| AI Agent (existing) | `<agentName>` | `<agentReferenceId>` |
| Job Node | `<job label>` | `<jobNodeId>` |
| Tool: `<toolId>` | `<tool label>` | `<tool _id>` |

---

## Notes

- `mode: append` MUST be used for the job node. `insertAfter` returns a 500 from the Cognigy API.
- `mode: appendChild` MUST be used for tool nodes — they are children of the job node.
- The `aiAgent` config field takes the agent's `referenceId` (UUID), not `_id`.
- All node operations require `--flowId`.
- Never hardcode `npx tsx` CLI calls — always invoke atomic skills by name.
```

- [ ] **Step 2: Verify the file was written correctly**

```bash
head -5 /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/skills/scaffold-aiagent/SKILL.md
```

Expected output: the frontmatter block starting with `---` and `name: scaffold-aiagent`.

- [ ] **Step 3: Commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add skills/scaffold-aiagent/SKILL.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "feat: add scaffold-aiagent composite skill"
```

---

## Task 2: Bump versions

**Files:**
- Modify: `cli/package.json` line 3
- Modify: `.claude-plugin/plugin.json` line 4

- [ ] **Step 1: Bump `cli/package.json`**

In `cli/package.json`, change:
```json
"version": "1.1.10",
```
to:
```json
"version": "1.1.11",
```

- [ ] **Step 2: Bump `.claude-plugin/plugin.json`**

In `.claude-plugin/plugin.json`, change:
```json
"version": "1.1.10",
```
to:
```json
"version": "1.1.11",
```

- [ ] **Step 3: Commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add cli/package.json .claude-plugin/plugin.json
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "chore: bump version to 1.1.11"
```

---

## Task 3: Push and update marketplace submodule

- [ ] **Step 1: Push**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin push
```

- [ ] **Step 2: Update marketplace submodule**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```

---

## Self-Review

**Spec coverage:**
- ✅ Flow assumed to exist — skill asks for it, does not create it
- ✅ `cognigy:select-node` used for insertion point resolution
- ✅ AI Agent resolved by name via `cognigy:list`
- ✅ `referenceId` (not `_id`) used for `aiAgent` config field
- ✅ `mode: append` used for job node (not `insertAfter`)
- ✅ `mode: appendChild` used for tool nodes
- ✅ Tools with and without parameters handled
- ✅ Atomic skills called by name — no hardcoded CLI paths
- ✅ Version bumps in both files
- ✅ Marketplace submodule update included

**Placeholder scan:** None found — all steps contain exact content.

**Type consistency:** No TypeScript involved — N/A.
