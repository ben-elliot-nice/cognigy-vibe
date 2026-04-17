# Cognigy Skill Uplift — Plan 2: New Design Skills

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four new composite skills covering the design layer between scope-demo and build: `design-agent-jobs`, `design-agent-interfaces`, `design-agent-contracts`, and `design-agent` (orchestrator). Each skill is independently invocable; `design-agent` runs all four in sequence.

**Architecture:** Pure SKILL.md files in new skill directories. No TypeScript changes. Plan 1 (foundation) should be complete before this plan runs — several skills reference `cognigy:design-agent-persona` which is created in Plan 1.

**Tech Stack:** Markdown only. No tests.

**Dependency:** Run Plan 1 first. This plan assumes `skills/design-agent-persona/` already exists.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `skills/design-agent-jobs/SKILL.md` | Job definitions, routing architecture, context schema — produces architecture + context schema docs |
| Create | `skills/design-agent-interfaces/SKILL.md` | Out-of-chat moments, xApp, bidirectional webchat, handover context package — produces interfaces doc |
| Create | `skills/design-agent-contracts/SKILL.md` | Deterministic enforcement layer: guard sub-flows, obligation state schema, structured refusals — produces contracts doc |
| Create | `skills/design-agent/SKILL.md` | Orchestrator: calls all four design skills in sequence — produces all four design documents |
| Modify | `.claude-plugin/plugin.json` | Version bump 1.1.11 → 1.1.12 |
| Modify | `cli/package.json` | Version bump 1.1.11 → 1.1.12 |

All paths relative to `/Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin`.

---

### Task 1: Create `skills/design-agent-jobs/SKILL.md`

**Files:**
- Create: `skills/design-agent-jobs/SKILL.md`

- [ ] **Step 1: Write the file**

```markdown
---
name: design-agent-jobs
description: Design Cognigy AI agent specialist jobs, routing architecture, and context schema — produces agent architecture and context schema markdown documents. Run after cognigy:design-agent-persona.
---

# Design Agent Jobs

## When to Use

Use this skill to design the specialist job layer — what each job does, how jobs route between each other, and what data flows through the conversation. Run after `cognigy:design-agent-persona` when the persona document is available.

**This skill does not create or modify any Cognigy resources.**

## Reference Docs

Before starting, navigate to `<plugin-root>` (two directories up from `skills/design-agent-jobs/`) and read:

- `docs/agent-prompting-guide.md` — Tool descriptions as compliance contracts, outcome-based framing
- `docs/cognigy-agent-patterns.md` — Concierge + Specialists pattern, tool granularity, action-parameterized pattern, toolResponse channel, handover context pattern

---

## Context Check

Before asking any questions, look for:
1. A demo plan (`*-demo-plan.md`) — read it for use cases, agent architecture, channels, integrations
2. A persona doc (`*-agent-persona.md`) — read it for agent name, compliance framing, auth scope

If neither exists, ask the user to run `cognigy:scope-demo` and `cognigy:design-agent-persona` first.

---

## Step 1: Job / Specialist Definitions

For each specialist agent in the demo scope, work through these collaboratively. Do not generate outputs yet.

For each job:
1. **Name** — What is this specialist called? (e.g. "Billing Specialist")
2. **Purpose** — In one sentence, what does this job handle?
3. **Instructions** — What outcome should this job achieve? What should it always do / never do within its scope? Keep outcome-based, not rule-heavy. Max ~500 chars.
4. **Tools** — What can this job do? List as plain-English actions (e.g. "look up policy details", "process cancellation", "return to concierge"). For each tool, ask:
   - Does it take parameters?
   - Are there compliance rules that only apply at the moment this tool is called? (If yes, these go in the tool description — see `docs/agent-prompting-guide.md`)
   - Is this action irreversible or high-stakes? If yes → how is it staged? What does the customer see before committing? What happens if they say no?
5. **Knowledge** — Does this job need a dedicated knowledge store? If so, what content?
6. **Tool granularity preference** — Granular (one tool per action), consolidated (one tool, LLM synthesises), or action-parameterized (one tool, action parameter, shared guards)? See `docs/cognigy-agent-patterns.md` for trade-offs.

Present a summary table for confirmation before proceeding:

| Specialist | Purpose | Tools | Irreversible actions | Knowledge |
|------------|---------|-------|----------------------|-----------|
| {Name} | {One sentence} | {List} | {Yes/No — if yes, staging pattern} | {Yes/No} |

---

## Step 2: Routing Architecture

Design the concierge routing logic:

1. **Pre-routing** — What does the concierge do before routing? (authenticate, capture intent, gather context fields)
2. **Routing triggers** — What intent or phrase triggers each specialist?
3. **Post-job routing** — When a specialist finishes, does it return to concierge or end the conversation?
4. **Escalation** — Is there a live agent escalation path? What triggers it? What context is handed over?
5. **Auth architecture** — Confirm from persona doc: when does auth happen, what does it set in context, does it persist?

Present a routing intent map for confirmation:

| Intent / Trigger | Routed To |
|-----------------|-----------|
| {e.g. "I want to cancel my policy"} | Cancellation Specialist |
| {e.g. "I need to make a claim"} | Claims Specialist |
| {e.g. customer requests human} | Human Agent Escalation |

Also confirm escalation handover: what structured data should the live agent receive? Reference `docs/cognigy-agent-patterns.md` Handover Context Pattern for the design pattern.

---

## Step 3: Context Schema

Design what data flows through the conversation:

1. **Concierge captures** — What does the concierge gather before routing? (identity, auth state, reason for contact, policy details)
2. **Specialist state** — What does each specialist need to store temporarily during its job? (selected product, confirmation flags, dispute reference)
3. **Shared session memory** — What should the LLM be able to "remember" across the conversation? (`context.shortTermMemory.*` fields)
4. **toolResponse** — Confirm the standard pattern: every tool branch writes its result to `context.toolResponse` before Resolve Tool Action. (Reference `docs/cognigy-agent-patterns.md`)
5. **Handover context** — Design the `context.handoverContext` object — what fields, which consumer (ACD vs Agent Assist)

Present context schema in plain English (variable paths + descriptions) for confirmation:

**Concierge captures:**
- `context.authVerified` — boolean, set after auth
- `context.shortTermMemory.customerName` — captured at auth
- `context.shortTermMemory.intent` — top-level reason for contact
- `context.toolResponse` — initialise to `""` at session start

**[Specialist name] uses:**
- `context.shortTermMemory.[field]` — {description}

---

## Step 4: Write Output Documents

After all three steps are confirmed, generate the following files. Write to the directory from which the user launched Claude Code — not the plugin root.

### File 1: `{CustomerName}-agent-architecture.md`

Sections:
- Agent Map (table: agent name, role, tools, irreversible actions)
- Routing Intent Map (table: trigger → specialist)
- Mermaid architecture diagram (`graph TD` format) showing concierge → specialists → escalation paths
- Specialist Job Definitions (one subsection per specialist: purpose, instructions, tools with descriptions, knowledge, granularity choice, irreversible action staging if applicable)

### File 2: `{CustomerName}-context-schema.md`

Sections:
- Schema overview (what flows through the conversation and why)
- Variable table (path | owner | description | LLM-visible | lifetime)
- toolResponse pattern (initialisation + per-tool example)
- Handover context design (fields, consumer mapping)

---

## Notes

- This skill produces design documents only — no Cognigy resources are created
- Write output to the user's working directory, not the plugin directory
- Tool descriptions from Step 1 should carry compliance rules at point-of-use (see `docs/agent-prompting-guide.md`)
- For xApp, website triggers, and handover interface → `cognigy:design-agent-interfaces`
- For deterministic contract enforcement → `cognigy:design-agent-contracts`
- Mermaid diagrams use `graph TD` format
```

- [ ] **Step 2: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add skills/design-agent-jobs/SKILL.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "feat: add design-agent-jobs composite skill"
```

---

### Task 2: Create `skills/design-agent-interfaces/SKILL.md`

**Files:**
- Create: `skills/design-agent-interfaces/SKILL.md`

- [ ] **Step 1: Write the file**

```markdown
---
name: design-agent-interfaces
description: Design the Cognigy AI agent's touchpoints outside the conversation window — xApp scenes, bidirectional webchat patterns, and the live agent handover package. Produces an interfaces design document.
---

# Design Agent Interfaces

## When to Use

Use this skill to design everything the agent touches outside the chat or voice stream itself — what gets sent to the phone, what the website does during the conversation, and what the live agent receives on escalation. Run after `cognigy:scope-demo` when the demo plan is available.

**This skill does not create or modify any Cognigy resources.**

## Reference Docs

Before starting, navigate to `<plugin-root>` (two directories up from `skills/design-agent-interfaces/`) and read:

- `docs/cognigy-agent-patterns.md` — Handover Context Pattern, xApp notes in Specialist Job Patterns

---

## Context Check

Look for a demo plan (`*-demo-plan.md`) in the working directory. Read it for:
- Channel(s) in scope (voice, webchat, WhatsApp)
- Out-of-chat moments noted in Phase 3 area 5
- xApp in scope flag from Technical Requirements
- Handover escalation path

If no demo plan is available, ask the user to describe the demo's channel setup and key moments before proceeding.

---

## Step 1: Out-of-Chat Moments Inventory

Ask: "During this demo, what happens outside the chat window?"

Work through each category:

1. **Flow → Website triggers** — Does the flow send events or data to the website during the conversation? (e.g. highlight a product, open a form, update a dashboard widget, show a confirmation panel)
2. **Website → Flow events** — Does the website send events back into the flow? (e.g. form submission, button click confirmation, payment result, authentication token)
3. **Push / SMS** — Does the flow send anything to the customer's phone outside the chat? (xApp link via SMS, notification, callback request)
4. **Backend / dashboard** — Does the flow update any backend system or dashboard in real-time during the demo? (claim created, policy updated, support ticket opened)

For each identified moment, capture: trigger (what causes it), payload (what data moves), direction (flow→outside or outside→flow), and the demo impact (why this is a "wow moment").

---

## Step 2: xApp Scene Design

For each xApp moment identified in Step 1:

1. **Scene name** — What is this scene called?
2. **Trigger** — Which tool call or node activates this xApp?
3. **Channel requirement** — Voice only (requires phone number for SMS link) or webchat (shows inline)?
4. **Content type** — What does the xApp show? (adaptive card, carousel, payment form, confirmation screen, map, image)
5. **Data payload** — What data does the flow pass to the xApp? List field names and sources (e.g. `policyNumber` from `context.shortTermMemory.policyNumber`)
6. **Customer action** — Does the customer interact with the xApp? If yes — what do they do, and what event comes back to the flow?
7. **Fallback** — If xApp cannot be delivered (wrong channel, no phone number), what happens instead?

---

## Step 3: Bidirectional Webchat Patterns

For each website → flow event identified in Step 1:

1. **Event name** — What is the event called in the flow? (snake_case)
2. **Trigger** — What does the customer do on the website that sends this event?
3. **Payload** — What data does the website send with the event? (e.g. `{ confirmed: true, policyNumber: "ABC123" }`)
4. **Flow handling** — What does the flow do when it receives this event? (resume waiting state, branch on payload, update context)
5. **Demo setup** — What needs to be configured in the website/Cognigy endpoint to enable this pattern?

---

## Step 4: Handover Context Package

Design the live agent handover package:

1. **Consumer 1 — ACD / routing system** — What structured fields does the routing system need? (customer identity, policy, intent, escalation reason)
2. **Consumer 2 — Agent Assist / live agent reading** — What natural language summary does the agent need to pick up without asking the customer to repeat themselves?
3. **Data sources** — For each field, where does the data live in context?
4. **Timing** — When is `context.handoverContext` built? (at escalation tool call, or maintained throughout conversation)

Reference `docs/cognigy-agent-patterns.md` Handover Context Pattern for the implementation template.

---

## Step 5: Write Output

Generate `{CustomerName}-agent-interfaces.md`. Write to the directory from which the user launched Claude Code — not the plugin root.

### Sections:

**Out-of-Chat Moments**
Table: moment name | trigger | direction | payload summary | demo impact

**xApp Scenes**
One subsection per scene: trigger, channel requirements, content type, data payload, customer interaction, fallback

**Bidirectional Webchat**
One subsection per event: event name, trigger, payload schema, flow handling, setup requirements

**Handover Context Package**
- `context.handoverContext` object design (with field names and data sources)
- Natural language summary template for Agent Assist
- Consumer mapping table

---

## Notes

- This skill produces a design document only — no Cognigy resources are created
- Write output to the user's working directory, not the plugin directory
- For job definitions and routing → `cognigy:design-agent-jobs`
- For contract enforcement → `cognigy:design-agent-contracts`
```

- [ ] **Step 2: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add skills/design-agent-interfaces/SKILL.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "feat: add design-agent-interfaces composite skill"
```

---

### Task 3: Create `skills/design-agent-contracts/SKILL.md`

This skill designs the **deterministic enforcement layer** — guard sub-flows, obligation state schema, and structured refusals. Based on research confirming that: (1) tool branches are full synchronous flows the LLM cannot bypass, (2) Resolve Tool Action is the single exit point, (3) If Nodes with `context.*` conditions enforce guards without LLM involvement.

**Files:**
- Create: `skills/design-agent-contracts/SKILL.md`

- [ ] **Step 1: Write the file**

```markdown
---
name: design-agent-contracts
description: Design the deterministic enforcement layer for Cognigy AI agent contracts — guard sub-flows, obligation state schema, and structured refusals. Compliance obligations enforced by flow logic, not LLM instruction-following. Produces a contracts design document.
---

# Design Agent Contracts

## When to Use

Use this skill to design the deterministic enforcement layer for compliance obligations — the Cognigy flow structures that enforce contracts regardless of what the LLM decides, rather than relying on the LLM to follow instructions.

**Key principle:** The LLM calls a tool. What happens inside that tool call is owned by Cognigy nodes, not the LLM. `Resolve Tool Action` is the single exit point — the contracts layer controls exactly what the LLM receives back.

Run after `cognigy:design-agent-jobs` when the architecture document is available.

**This skill does not create or modify any Cognigy resources.**

## How Cognigy Enforcement Works

Before starting, understand the execution model:

1. LLM calls a tool → flow routes to the tool branch
2. The tool branch executes **synchronously** (LLM waits)
3. Any sequence of nodes runs: Code Nodes, If Nodes, HTTP Requests, Set Context, Execute Flow
4. `Resolve Tool Action` sends the result back to the LLM
5. LLM resumes — it sees only what `Resolve Tool Action` returned

The LLM cannot bypass or skip the tool branch. A blocked action returns a structured refusal string — the LLM stays coherent and the contract is provably enforced.

**Guard pattern:**
```
Tool Branch
  └─ Execute Flow: contract-guard-<obligation-name>
       ├─ If Node: context.contracts.prerequisiteMet === true
       │    Then → [action nodes] → Resolve Tool Action (success result)
       │    Else → Resolve Tool Action ("BLOCKED: prerequisite not met")
       └─ Set Context: record obligation state after action
```

## Reference Docs

Before starting, navigate to `<plugin-root>` (two directories up from `skills/design-agent-contracts/`) and read:

- `docs/cognigy-agent-patterns.md` — toolResponse channel, handover context pattern

---

## Context Check

Look for in the working directory:
1. Demo plan (`*-demo-plan.md`) — for regulatory constraints (Fact #12) and scenario overview
2. Architecture doc (`*-agent-architecture.md`) — for tool list and irreversible action flags

If neither exists, ask the user to describe the tools and compliance obligations before proceeding.

---

## Step 1: Obligation Catalogue

For each tool in the architecture doc, assess whether it requires a deterministic enforcement guard:

Ask for each tool: "Does this tool have a compliance obligation that must be enforced by the flow — not just described in the tool description?"

Obligations that typically require enforcement:
- **One-offer limits** — the flow must track whether an offer has been made and block a second one
- **Two-pass confirmation** — an irreversible action must not execute on the first call; the flow enforces the summary-first pattern
- **Prerequisite gates** — a tool must not run unless a prior step has completed (e.g. auth verified, disclosure acknowledged)
- **Reason routing** — a routing decision must have been made before an action tool can fire
- **Post-action state** — after an action, the flow must record that it happened to prevent repetition

For each obligation, capture:

| Tool | Obligation type | Precondition (`context.*` check) | Post-condition (state to set) | Guard sub-flow name |
|------|----------------|----------------------------------|-------------------------------|---------------------|
| {e.g. process_cancellation} | Two-pass confirmation | `context.contracts.cancellationSummaryShown === true` | `context.contracts.cancellationExecuted = true` | `contract-guard-cancellation-confirmation` |

---

## Step 2: Context State Schema

Design the `context.contracts` namespace for tracking obligation state:

Ask: "For each obligation — what boolean or value needs to be tracked in context to enforce it?"

Example schema:
```javascript
context.contracts = {
  // Auth
  authVerified: false,            // Set by concierge after authentication

  // Offer limits
  retentionOffered: false,        // Set after first retention offer — blocks second
  retentionOfferReason: null,     // Which reason the offer was made for

  // Confirmation gates
  cancellationSummaryShown: false, // Set after summary returned — enables execution
  cancellationExecuted: false,     // Set after execution — prevents re-execution

  // Prerequisite tracking
  disclosureAcknowledged: false,   // Set after mandatory disclosure confirmed
  reasonCaptured: false            // Set after reason routing completed
}
```

**Initialise all fields at session start** (Set Context Node at flow entry). Default every flag to `false` / `null`.

Present the proposed schema for confirmation.

---

## Step 3: Guard Sub-Flow Designs

For each obligation in the catalogue, design the guard sub-flow. A guard sub-flow is a reusable Execute Flow that enforces one obligation and can be called from any tool branch.

For each guard:

1. **Sub-flow name** — `contract-guard-<obligation-name>` (kebab-case)
2. **If condition** — The CognigyScript expression that must evaluate to `true` for the action to proceed (e.g. `context.contracts.cancellationSummaryShown === true`)
3. **Then path** — What executes when the condition is met (proceed with action, then set post-condition state)
4. **Else path** — What `Resolve Tool Action` returns when the condition is NOT met (structured refusal string)
5. **State update** — What `context.contracts.*` fields are set after successful execution

**Structured refusal format:**
```javascript
context.toolResponse = {
  success: false,
  blocked: true,
  reason: "{Plain English explanation the LLM can relay naturally to the customer}"
}
```

Present all guard designs for confirmation.

---

## Step 4: Write Output

Generate `{CustomerName}-agent-contracts.md`. Write to the directory from which the user launched Claude Code — not the plugin root.

### Sections:

**Enforcement Approach**
One paragraph explaining why obligations are enforced deterministically (not via LLM instructions) and how the guard pattern works.

**Obligation Catalogue**
Full table from Step 1.

**Context State Schema**
The `context.contracts` initialisation block (ready to use in a Set Context Node) with field-by-field annotations.

**Guard Sub-Flow Designs**
One subsection per guard:
- Sub-flow name
- If condition (CognigyScript)
- Then path description
- Else path: structured refusal object
- State update: which `context.contracts.*` fields are set

**Integration Notes**
How tool branches should call each guard (Execute Flow pattern), and where to place the initialisation node.

---

## Notes

- This skill produces a design document only — no Cognigy resources are created
- Write output to the user's working directory, not the plugin directory
- Guard sub-flows are reusable — one guard can be called from multiple tool branches
- Obligations enforced here are separate from compliance language in tool descriptions — both are needed: tool descriptions inform the LLM's decision, guard sub-flows enforce the outcome
- The LLM cannot bypass a guard — the tool branch structure is designer-controlled
```

- [ ] **Step 2: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add skills/design-agent-contracts/SKILL.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "feat: add design-agent-contracts composite skill"
```

---

### Task 4: Create `skills/design-agent/SKILL.md`

Orchestrator skill. Calls all four design skills in sequence, or lets the user select specific ones.

**Files:**
- Create: `skills/design-agent/SKILL.md`

- [ ] **Step 1: Write the file**

```markdown
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
> **B — Select stages**: tell me which ones you need

If starting from scratch: option A.
If persona is already done: option B, start from jobs."

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
- To build after designing → use `cognigy:add-aiagent-job` and related atomic skills
```

- [ ] **Step 2: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add skills/design-agent/SKILL.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "feat: add design-agent orchestrator composite skill"
```

---

### Task 5: Version Bump, Push, Submodule

**Files:**
- Modify: `.claude-plugin/plugin.json` — `"version": "1.1.11"` → `"version": "1.1.12"`
- Modify: `cli/package.json` — `"version": "1.1.11"` → `"version": "1.1.12"`

- [ ] **Step 1: Bump `.claude-plugin/plugin.json`**

Change `"version": "1.1.11"` to `"version": "1.1.12"`.

- [ ] **Step 2: Bump `cli/package.json`**

Change `"version": "1.1.11"` to `"version": "1.1.12"`.

- [ ] **Step 3: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add .claude-plugin/plugin.json cli/package.json docs/superpowers/plans/2026-04-17-cognigy-skill-uplift-new-skills.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "chore: bump version to 1.1.12"
```

- [ ] **Step 4: Push**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin push
```

- [ ] **Step 5: Update submodule**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```

---

## Self-Review

**Spec coverage:**
- ✅ design-agent-jobs — Steps 2-5 from old prepare-agent-persona, with irreversible action prompts (#17), tool descriptions as contracts (#10), handover context (#16), toolResponse (#15)
- ✅ design-agent-interfaces — out-of-chat moments (#3), xApp design, bidirectional webchat, handover package (#16)
- ✅ design-agent-contracts — deterministic enforcement (user's clarification), guard sub-flows, obligation state schema, structured refusals. Correctly NOT about tool description language.
- ✅ design-agent — orchestrator with mode selection, full workflow + selective stages
- ✅ All four skills reference each other appropriately
- ✅ All output docs written to user's working directory, not plugin root

**Placeholder scan:** None. All SKILL.md content is complete and actionable.

**Plan ordering:** Plan 1 must complete before Plan 2 — design-agent-persona must exist for design-agent-jobs to reference it, and version numbers sequence from 1.1.10 → 1.1.11 (Plan 1) → 1.1.12 (Plan 2).
