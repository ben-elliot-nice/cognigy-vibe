---
name: prepare-agent-persona
description: Design Cognigy AI agent personas and architecture — produces markdown design artefacts covering agent identity, specialist jobs, routing, and context schema. No API calls or resource creation.
---

# Prepare Agent Persona

## When to Use

Use this skill after `scope-demo` (or when equivalent context about the customer, use cases, and agent architecture is already available). This skill translates the demo scope into concrete AI agent design artefacts — all as markdown documents, ready for review before anything is built.

**This skill does not create or modify any Cognigy resources.**

## Reference Docs

Before starting, navigate to `<plugin-root>` (two directories up from `skills/prepare-agent-persona/`) and read:

- `docs/agent-prompting-guide.md` — How to write agent `description` and `instructions` fields
- `docs/cognigy-agent-patterns.md` — Architectural patterns: concierge + specialists, tool granularity, context schema examples

---

## Context Check

Before asking any questions, check whether a demo plan from `scope-demo` is available (e.g. a `*-demo-plan.md` file in the working directory). If so, read it and extract:

- Customer name and industry
- Use cases / intents
- Agent architecture (single vs multi-agent, which specialists)
- Channels in scope
- Integration landscape

If no demo plan is available, ask the user to provide this context before proceeding.

---

## Step 1: Brand Voice & Agent Identity

Work through these questions collaboratively. Do not generate outputs yet.

1. What is the agent's name? (This becomes the brand identity — e.g. "Aria from TechCorp")
2. How should the agent present itself? (Tone: formal / balanced / informal)
3. How verbose should responses be? (Completeness: concise / balanced / verbose)
4. Is there a brand voice guide or examples of how the company communicates?
5. Are there topics the agent must never discuss or behaviours it must always exhibit?

Use `docs/agent-prompting-guide.md` to translate the user's answers into the `description` and `instructions` fields. Draft both fields and present them for review before moving on.

Confirm: "Happy with this persona? I'll lock it in before we move to the job definitions."

---

## Step 2: Job / Specialist Definitions

For each specialist agent identified in the demo scope, work through:

1. **Name** — What is this specialist called? (e.g. "Billing Specialist")
2. **Purpose** — In one sentence, what does this specialist do?
3. **Instructions** — What are the standing orders for this job? (what it should always / never do, tone adjustments if different from main agent)
4. **Tools** — What can this specialist do? List as plain-English actions (e.g. "look up account balance", "raise a billing dispute", "return to concierge")
5. **Knowledge** — Does this specialist need access to a knowledge store? If so, what content?

Present a summary table of all specialists and confirm before proceeding.

| Specialist | Purpose | Tools | Knowledge |
|------------|---------|-------|-----------|
| {Name} | {One sentence} | {List} | {Yes/No + content} |

---

## Step 3: Routing Architecture

Design the concierge routing logic:

1. What intents (caller phrases/goals) trigger each specialist?
2. What does the concierge do before routing — authenticate, capture context, or both?
3. What happens when a specialist finishes — return to concierge, or end call?
4. Is there a live agent escalation path? If so, what triggers it and what context is handed over?

Present a routing intent map for confirmation:

| Intent | Routed To |
|--------|-----------|
| {e.g. "I want to pay my bill"} | Billing Specialist |
| {e.g. "I need technical help"} | Support Specialist |
| {e.g. "I want to speak to someone"} | Human Agent Escalation |

---

## Step 4: Context Schema

Design what data flows through the conversation:

1. What needs to be captured at the start (by the concierge) and passed to specialists? (e.g. account number, authenticated status, reason for call)
2. What does each specialist need to store temporarily during its job? (e.g. selected product, dispute reference)
3. Is there anything the LLM should be able to "remember" across the conversation? (short-term memory)

Present a context schema in plain English (not JSON) for confirmation:

**Concierge captures:**
- `context.accountNumber` — captured during auth
- `context.authenticated` — boolean, set after PIN validation
- `context.intent` — top-level reason for contact

**Billing Specialist uses:**
- `context.billing.selectedInvoice` — invoice chosen for dispute
- `context.billing.disputeReference` — returned from stub API

---

## Step 5: Write Output Documents

After all four steps are confirmed, generate the following files. Write to the directory from which the user launched Claude Code — their working directory, not the plugin root. If the correct path is unclear, ask. Do NOT write files into the plugin directory.

### File 1: `{CustomerName}-agent-persona.md`

Sections:
- Agent Identity (name, description field value, instructions field value, speaking style)
- Brand Voice Notes (how the persona was derived, any constraints)

### File 2: `{CustomerName}-agent-architecture.md`

Sections:
- Agent Map (table: agent name, role, tools)
- Routing Intent Map (table: intent → specialist)
- Mermaid architecture diagram showing concierge → specialists → escalation paths
- Specialist Job Definitions (one subsection per specialist: purpose, instructions, tools, knowledge)

### File 3: `{CustomerName}-context-schema.md`

Sections:
- Schema overview (what flows through the conversation and why)
- Variable table (variable path, owner agent, description, type)
- LLM short-term memory fields (if any)

---

## Notes

- This skill produces design documents only — no Cognigy resources are created
- Always confirm after Step 1 (persona) and Step 2 (specialist table) before proceeding
- Use `docs/cognigy-agent-patterns.md` to inform architecture recommendations — refer to it for tool granularity and context schema examples
- Mermaid diagrams should use `graph TD` format
