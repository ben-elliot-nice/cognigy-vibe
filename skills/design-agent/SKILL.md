---
name: design-agent
description: Orchestrate the full Cognigy AI agent design workflow — runs design-agent-persona, design-agent-jobs, design-agent-interfaces, and design-agent-contracts in sequence. Can also run individual design skills on demand.
---

# Design Agent

## When to Use

Use this skill when you want to run the full agent design workflow in one session, or when you want to pick and choose which design stages to run.

Requires a demo plan from `cognigy:scope-demo` in the working directory before starting.

## Design Skills

The workflow is composed of four skills, each independently callable:

| Skill | What it produces |
|-------|-----------------|
| `cognigy:design-agent-persona` | `{Customer}-agent-persona.md` — identity, instructions, compliance framing |
| `cognigy:design-agent-jobs` | `{Customer}-agent-architecture.md` + `{Customer}-context-schema.md` — jobs, routing, context |
| `cognigy:design-agent-interfaces` | `{Customer}-agent-interfaces.md` — xApp, webchat, handover context |
| `cognigy:design-agent-contracts` | `{Customer}-agent-contracts.md` — guard sub-flows, obligation state, refusals |

---

## Context Check

Look for a demo plan (`*-demo-plan.md`) in the working directory. If none exists, stop and ask the user to run `cognigy:scope-demo` first.

---

## Mode Selection

Ask the user:

> "Which design stages do you want to run?
>
> **A — Full workflow** (recommended): persona → jobs → interfaces → contracts
> **B — Select stages**: tell me which ones you need"

If starting from scratch: option A.
If persona is already done: option B, start from jobs.

---

## Full Workflow (Option A)

Run the four skills in sequence. After each skill completes and the user confirms the output, move to the next.

### Stage 1: Persona

Invoke `cognigy:design-agent-persona`. When complete and output confirmed, proceed.

**Context pass to Stage 2:** The generated `{Customer}-agent-persona.md` is available in the working directory — design-agent-jobs will read it automatically.

### Stage 2: Jobs

Invoke `cognigy:design-agent-jobs`. When complete and output confirmed, proceed.

**Context pass to Stage 3:** The generated architecture and context schema docs are available — design-agent-interfaces and design-agent-contracts will read them.

### Stage 3: Interfaces

Invoke `cognigy:design-agent-interfaces`. When complete and output confirmed, proceed.

**Note:** Interfaces can run in parallel with contracts (they have no dependency on each other). If the user wants to run them in parallel, offer that option.

### Stage 4: Contracts

Invoke `cognigy:design-agent-contracts`. When complete and output confirmed, the full design is done.

---

## Selected Stages (Option B)

Ask which stages the user wants. Run only those, in the natural order (persona before jobs, jobs before contracts).

---

## Completion

When all selected stages are complete, summarise the output files produced and confirm they're all in the working directory:

```
Design complete. Files produced:
- {Customer}-agent-persona.md       ← description, instructions, compliance framing
- {Customer}-agent-architecture.md  ← jobs, routing intent map, Mermaid diagram
- {Customer}-context-schema.md      ← context variable table, toolResponse, handover
- {Customer}-agent-interfaces.md    ← xApp, webchat, handover package design
- {Customer}-agent-contracts.md     ← guard sub-flows, obligation state, refusals
```

---

## Notes

- This skill does not create or modify any Cognigy resources
- Output files are written to the user's working directory, not the plugin directory
- Each sub-skill can also be invoked directly without going through this orchestrator
- To build after designing → use `cognigy:add-aiagent-job` (creates nodes via MCP tools)
