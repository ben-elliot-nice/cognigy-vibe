---
name: design-agent
description: Orchestrate the full Cognigy AI agent design workflow — runs design-agent-persona, design-agent-jobs, design-agent-interfaces, and design-agent-contracts in sequence. Can also run individual design skills on demand.
---

# Design Agent

## When to Use

Use this skill when you want to run the full agent design workflow in one session, or when you want to pick and choose which design stages to run.

Requires a demo plan from `cognigy-vibe:scope-demo`. If an `output_dir` argument was supplied (e.g. `cognigy-vibe:build-orchestrator` passes `"Demo Builds/<customer>-demo"`), the demo plan is in that directory. Otherwise look in the user's working directory.

## Design Skills

The workflow is composed of four skills, each independently callable:

| Skill | What it produces |
|-------|-----------------|
| `cognigy-vibe:design-agent-persona` | `{Customer}-agent-persona.md` — identity, instructions, compliance framing |
| `cognigy-vibe:design-agent-jobs` | `{Customer}-agent-architecture.md` + `{Customer}-context-schema.md` — jobs, routing, context |
| `cognigy-vibe:design-agent-interfaces` | `{Customer}-agent-interfaces.md` — xApp, webchat, handover context |
| `cognigy-vibe:design-agent-contracts` | `{Customer}-agent-contracts.md` — guard sub-flows, obligation state, refusals |

---

## Context Check

Look for a demo plan (`*-demo-plan.md`) in `output_dir` if that argument was supplied; otherwise look in the user's working directory. If none exists, stop and ask the user to run `cognigy-vibe:scope-demo` first.

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

Invoke `cognigy-vibe:design-agent-persona`. When complete and output confirmed, proceed.

**Context pass to Stage 2:** The generated `{Customer}-agent-persona.md` is in `output_dir` (or cwd if no `output_dir` was supplied) — pass the same `output_dir` to design-agent-jobs so it reads from the right location.

### Stage 2: Jobs

Invoke `cognigy-vibe:design-agent-jobs`. When complete and output confirmed, proceed.

**Context pass to Stage 3:** The generated architecture and context schema docs are in `output_dir` (or cwd) — pass the same `output_dir` to design-agent-interfaces and design-agent-contracts so they read from the right location.

### Stage 3: Interfaces

Invoke `cognigy-vibe:design-agent-interfaces`. When complete and output confirmed, proceed.

**Note:** Interfaces can run in parallel with contracts (they have no dependency on each other). If the user wants to run them in parallel, offer that option.

### Stage 4: Contracts

Invoke `cognigy-vibe:design-agent-contracts`. When complete and output confirmed, the full design is done.

---

## Selected Stages (Option B)

Ask which stages the user wants. Run only those, in the natural order (persona before jobs, jobs before contracts).

---

## Completion

When all selected stages are complete, summarise the output files produced and confirm they're all in `output_dir` (or the user's working directory if no `output_dir` was supplied):

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
- Output files are written to the `output_dir` argument if supplied by the caller (e.g. `cognigy-vibe:build-orchestrator` passes `"Demo Builds/<customer>-demo"`); otherwise written to the user's working directory. Pass `output_dir` through to each sub-skill invocation. Never write into the plugin directory.
- Each sub-skill can also be invoked directly without going through this orchestrator
- To build after designing → see `explain("agent-job-node")` for the aiAgentJob node creation sequence
