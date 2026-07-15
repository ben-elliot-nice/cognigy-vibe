---
name: design-agent-jobs
description: Design Cognigy AI agent specialist jobs, routing architecture, and context schema — produces agent architecture and context schema markdown documents. Run after cognigy-vibe:design-agent-persona.
---

# Design Agent Jobs

## When to Use

Use this skill to design the specialist job layer — what each job does, how jobs route between each other, and what data flows through the conversation. Run after `cognigy-vibe:design-agent-persona` when the persona document is available.

**This skill does not create or modify any Cognigy resources.**

## Reference Docs

Before starting, navigate to `<plugin-root>` (three directories up from `plugin/skills/design-agent-jobs/`) and read:

- `explain("agent-behavioral-rules")` — silent execution, outcome-based framing, tool descriptions as contracts
- `explain("multi-agent-architecture")` — Concierge + Specialists, specialist job types, context schema
- `explain("agent-tool-patterns")` — tool granularity options, toolResponse channel
- `explain("agent-handover")` — escalation pattern, handover context artefact

---

## Context Check

Before asking any questions, look for the following in `output_dir` if that argument was supplied, otherwise in the user's working directory:
1. A demo plan (`*-demo-plan.md`) — read it for use cases, agent architecture, channels, integrations
2. A persona doc (`*-agent-persona.md`) — read it for agent name, compliance framing, auth scope

If neither exists, ask the user to run `cognigy-vibe:scope-demo` and `cognigy-vibe:design-agent-persona` first.

---

## Step 1: Job / Specialist Definitions

For each specialist agent in the demo scope, work through these collaboratively. Do not generate outputs yet.

For each job:
1. **Name** — What is this specialist called? (e.g. "Billing Specialist")
2. **Purpose** — In one sentence, what does this job handle?
3. **Instructions** — What outcome should this job achieve? What should it always do / never do within its scope? Keep outcome-based, not rule-heavy. Max ~500 chars.
4. **Tools** — What can this job do? List as plain-English actions (e.g. "look up policy details", "process cancellation", "return to concierge"). For each tool, ask:
   - Does it take parameters?
   - Are there compliance rules that only apply at the moment this tool is called? (If yes, these go in the tool description — see `explain("agent-behavioral-rules")`)
   - Is this action irreversible or high-stakes? If yes → how is it staged? What does the customer see before committing? What happens if they say no?
5. **Knowledge** — Does this job need a dedicated knowledge store? If so, what content?
6. **Tool granularity preference** — Granular (one tool per action), consolidated (one tool, LLM synthesises), or action-parameterized (one tool, action parameter, shared guards)? See `explain("agent-tool-patterns")` for trade-offs.

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

Also confirm escalation handover: what structured data should the live agent receive? Reference `explain("agent-handover")` for the design pattern.

---

## Step 3: Context Schema

Design what data flows through the conversation:

1. **Concierge captures** — What does the concierge gather before routing? (identity, auth state, reason for contact, policy details)
2. **Specialist state** — What does each specialist need to store temporarily during its job? (selected product, confirmation flags, dispute reference)
3. **Shared session memory** — What should the LLM be able to "remember" across the conversation? (`context.shortTermMemory.*` fields)
4. **toolResponse** — Confirm the standard pattern: every tool branch writes its result to `context.toolResponse` before Resolve Tool Action. (Reference `explain("agent-tool-patterns")`)
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

After all three steps are confirmed, generate the following files. If an `output_dir` argument was supplied by the caller, write the files there. Otherwise write to the directory from which the user launched Claude Code — not the plugin root.

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
- Write output to the `output_dir` argument if supplied by the caller (e.g. `cognigy-vibe:build-orchestrator` passes its resolved `$DEMO_DIR` — an absolute path, e.g. `"/Users/.../Demo Builds/acme-demo"`); otherwise write to the user's working directory. Never write into the plugin directory.
- Tool descriptions from Step 1 should carry compliance rules at point-of-use (see `explain("agent-behavioral-rules")`)
- For xApp, website triggers, and handover interface → `cognigy-vibe:design-agent-interfaces`
- For deterministic contract enforcement → `cognigy-vibe:design-agent-contracts`
- Mermaid diagrams use `graph TD` format
