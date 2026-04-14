# scope-demo + prepare-agent-persona Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port two old skills into `cognigy-claude-plugin` as proper composite skills. `scope-demo` gathers demo/brand context and produces a demo plan document. `prepare-agent-persona` takes that context and produces AI agent design artefacts as markdown — no API calls, no creation.

**Architecture:** Each skill is a single `SKILL.md` (matching `select-node` and `write-code-node`). Shared and skill-specific reference docs live in `docs/` at plugin root. `prepare-agent-persona` integrates `cognigy:list` for one optional lookup (existing agents); otherwise both skills are purely conversational/generative.

**Tech Stack:** Markdown, YAML frontmatter. No TypeScript changes. Plugin version bump only.

**Skill boundary:**
- `scope-demo` → business/sales level: customer context, channels, use cases, demo format. Output: `{Customer}-demo-plan.md`
- `prepare-agent-persona` → technical design level: agent identity, job/specialist definitions, routing architecture, context schema. Output: multiple MD design documents. **No JSON schemas. No CLI commands. No API calls.**

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `skills/scope-demo/SKILL.md` | Composite skill — four-phase demo scoping workflow |
| Create | `skills/prepare-agent-persona/SKILL.md` | Composite skill — AI agent design artefact generation |
| Create | `docs/cognigy-capabilities.md` | Platform reference (channels, xApp, AI Agents, integrations) |
| Create | `docs/scope-demo-output-template.md` | Template for demo plan MD file |
| Create | `docs/scope-demo-discovery-questions.md` | Structured discovery guide for scope-demo Phase 1 |
| Create | `docs/agent-prompting-guide.md` | How to write agent description and instructions fields |
| Create | `docs/cognigy-agent-patterns.md` | Architectural patterns (concierge + specialists, tool granularity, etc.) |
| Modify | `.claude-plugin/plugin.json` | Version bump 1.1.6 → 1.1.7 |
| Modify | `cli/package.json` | Version bump 1.1.6 → 1.1.7 |

**Explicitly excluded from `prepare-agent-persona`:**
- `cli-reference.md` — CLI command execution is out of scope for these skills
- JSON schemas ready for API submission — out of scope
- Any `cognigy:create`, `cognigy:update` calls — out of scope

---

### Task 1: Create `docs/cognigy-capabilities.md`

**Files:**
- Create: `docs/cognigy-capabilities.md`

- [ ] **Step 1: Write the file**

```markdown
# Cognigy Platform Capabilities

Reference for demo scoping and design. Use this to understand what Cognigy can do and how to position it in a demo.

---

## Channels

| Channel | Notes |
|---------|-------|
| Voice Gateway | Preferred for voice demos — native SIP, fastest setup, most control |
| CXone Voice | Use when customer is on NICE CXone and wants native integration |
| Webchat | Default for screen-share demos; easy to embed, no telephony required |
| WhatsApp | High-impact for B2C use cases; requires WhatsApp Business API approval |
| SMS | Simple async; useful for appointment reminders, follow-up flows |
| Microsoft Teams | Enterprise internal use cases (IT helpdesk, HR) |
| Email | Async; good for ticketing workflows |
| LINE | APAC B2C |
| Viber | Eastern Europe / Middle East B2C |
| Facebook Messenger | B2C social; declining enterprise relevance |

---

## Voice Integration Patterns

### Cognigy Voice Gateway (preferred)
- Native SIP trunking directly into Cognigy
- Fastest demo setup — no NICE CXone dependency
- Full control over voice quality, barge-in, DTMF
- Best for: any customer not already on CXone, or where speed of demo setup matters

### CXone + Cognigy
- Cognigy acts as the AI brain; CXone handles telephony and agent desktop
- Required when: customer is NICE CXone and wants to see native ACD integration
- More moving parts — plan extra setup time

---

## xApp (Multimodal)

A smartphone UI that activates during a voice call — the caller gets a push notification/SMS link and sees a visual interface while the voice conversation continues.

**What it can show:**
- Carousels (product images, options)
- Adaptive cards (forms, structured data)
- Payment flows
- Maps / location pins
- Confirmation screens

**When to use in a demo:**
- When the customer has a use case where visual context adds value during a call (e.g. "let me show you the options on your phone")
- High-impact differentiator — most competitors don't have this
- Requires: Voice Gateway channel + xApp node in flow

---

## AI & NLU

### Classic NLU
- Intent + entity recognition
- Fast, deterministic, rules-based routing
- Best for: well-defined intents, high-volume contact centre routing

### LLM Nodes
- Call an LLM for complex reasoning, extraction, or generation mid-flow
- Can use Cognigy-hosted models or customer's own LLM
- Best for: nuanced slot-filling, summarisation, dynamic response generation

### AI Agents (Autonomous)
- LLM-powered agents with tools (functions they can call)
- Can handle multi-turn tasks without a rigid flow
- Best for: complex service tasks with variable paths (e.g. account management, troubleshooting)
- Each AI Agent has a system prompt, tools, and a handoff condition

---

## Knowledge AI

RAG (retrieval-augmented generation) over uploaded documents.

**Supported sources:**
- PDF, DOCX, TXT uploads
- URLs (web scraping)
- Plain text

**In a demo context:**
- Can use real customer docs (FAQs, product guides) if available
- Sanitised or fabricated content works fine for demo purposes
- Show: "ask it anything about our product" moments

---

## Multi-Agent Architecture

### Pattern: Concierge + Specialists

```
Caller → Concierge Agent
           ├── authenticate / capture context
           ├── route by intent
           ├── Specialist: Billing
           ├── Specialist: Technical Support
           └── Specialist: Retention
```

**Concierge responsibilities:**
- Authentication (PIN, account lookup)
- Intent detection (what does the caller want?)
- Context capture (account number, reason for call)
- Routing to correct specialist

**Specialist responsibilities:**
- Domain-specific logic
- Tool calls (CRM lookup, case creation, payment processing)
- Handoff back to concierge or to live agent

---

## Integrations

| Type | Options | Demo approach |
|------|---------|---------------|
| CRM | Salesforce, Dynamics, ServiceNow, Zendesk | HTTP Request node + stub API or sandbox |
| Ticketing | ServiceNow, Jira, Zendesk | Same as CRM |
| Payment | Stripe, custom PCI flow | Stub or xApp payment card form |
| Backend / ERP | SAP, custom APIs | HTTP Request + stub JSON response |
| Knowledge bases | Confluence, SharePoint, PDFs | Knowledge AI ingestion |

**For demos:** stub APIs (returning realistic hardcoded JSON) are almost always sufficient and much faster to set up than live integrations.

---

## Demo Environment Patterns

### Live Voice Call (highest impact)
- Dial a real number, speak to the bot, xApp activates on phone
- Requires: Voice Gateway setup, SIP trunk, phone number
- Impact: shows the real thing — hardest to dismiss

### Screen Share + Webchat
- Share screen, interact with webchat widget
- Quickest to set up, no telephony
- Impact: lower than voice, but good for use cases that are inherently digital

### Walkthrough / Simulation
- Pre-recorded or guided click-through
- Use only as fallback — reduces credibility

---

## Build Complexity Flags

| Feature | Complexity | Notes |
|---------|------------|-------|
| Basic webchat flow | Low | 1–2 days |
| Voice Gateway + NLU routing | Medium | 3–5 days |
| xApp multimodal | Medium | +1–2 days on top of voice |
| AI Agents (autonomous) | Medium-High | Depends on tool complexity |
| Live CRM integration | High | +3–5 days; prefer stub for demos |
| Knowledge AI | Low-Medium | 1 day if docs are ready |
| Multi-agent architecture | High | 5–10 days depending on scope |
```

- [ ] **Step 2: Commit**

```bash
git add docs/cognigy-capabilities.md
git commit -m "docs: add cognigy-capabilities reference for scope-demo skill"
```

---

### Task 2: Create `docs/scope-demo-discovery-questions.md`

**Files:**
- Create: `docs/scope-demo-discovery-questions.md`

- [ ] **Step 1: Write the file**

```markdown
# Scope Demo Discovery Questions

Use these questions during Phase 1 of the scope-demo skill when the user does not have a pre-existing brief. Ask questions grouped by section — do not dump all questions at once. Move to the next section once you have clear answers for the current one.

---

## Section 1: Customer & Industry

1. Who is the customer, and what industry/vertical are they in?
2. What is their approximate scale — how many agents, contact volume, or customer interactions per month?

---

## Section 2: Business Problem

1. What is the primary business problem they're trying to solve? (e.g. reduce handle time, improve CSAT, deflect volume, replace a legacy IVR)
2. Is there a specific trigger for this demo — a live RFP, a proof of concept, an internal champion trying to build a case?

---

## Section 3: Channels & Contact Volume

1. What channels do they handle today — voice, chat, email, social?
2. Which channels are in scope for this demo?
3. Do they have a rough sense of contact volume or peak patterns?

---

## Section 4: Use Cases & Intents

1. What are the top 3–5 reasons customers contact them today?
2. Which of those are the best candidates for automation — high volume, relatively structured, clear resolution path?
3. Are there any use cases they've specifically asked to see?

---

## Section 5: Agent Architecture

1. Does this feel like a single-agent demo (one bot handles everything) or a multi-agent demo (concierge + specialists)?
2. Is there a live agent handoff moment we need to show?

---

## Section 6: Technical Environment

1. What CRM or backend systems are relevant? (Salesforce, Dynamics, ServiceNow, custom?)
2. Do we have access to a sandbox or stub API, or will we need to fabricate responses?
3. Is there any existing data — FAQs, product docs, knowledge base content — we can use for Knowledge AI?

---

## Section 7: Multimodal / xApp

1. Is there a use case where showing something visually during a voice call would add impact? (e.g. product options, payment, confirmation)
2. Has the customer seen xApp before, or would this be new to them?

---

## Section 8: Phasing & Demo Scope

1. Is this an MVP demo or a more complete vision?
2. Are there things they've explicitly said are out of scope for now?
3. How much build time do we have before the demo?

---

## Section 9: Demo Format & Timeline

1. Is this a live call demo, a screen-share demo, or a walkthrough?
2. What is the demo date?
3. Who will be in the room — technical evaluators, business stakeholders, executives?

---

## Section 10: Reusable Assets

1. Have we built anything for this customer or a similar customer before?
2. Are there flows, agents, or integrations from other demos we can repurpose?
```

- [ ] **Step 2: Commit**

```bash
git add docs/scope-demo-discovery-questions.md
git commit -m "docs: add scope-demo discovery questions reference"
```

---

### Task 3: Create `docs/scope-demo-output-template.md`

**Files:**
- Create: `docs/scope-demo-output-template.md`

- [ ] **Step 1: Write the file**

```markdown
# Demo Plan Output Template

Use this structure when generating the demo plan document in Phase 4 of the scope-demo skill. Populate every section. If something is unknown, state the assumption explicitly rather than leaving it blank.

**Filename:** `{CustomerName}-{DemoType}-demo-plan.md`

---

# {Customer Name} — {Demo Type} Demo Plan

## Overview

| Field | Value |
|-------|-------|
| Customer | {Customer name and industry} |
| Demo Date | {Date} |
| Demo Format | {Live call / Screen share / Walkthrough} |
| Primary Business Problem | {One sentence} |
| Key Differentiators to Prove | {Bullet list of 2–4 things this demo must demonstrate} |

---

## Demo Narrative & Phase Structure

### Story Arc

{2–3 sentences: who is the caller/user, what do they need, what happens, what's the "aha moment"?}

### Demo Phases

| Phase | Description | Key Moment |
|-------|-------------|------------|
| 1 | {Phase name and description} | {What should land with the audience} |
| 2 | {Phase name and description} | {What should land with the audience} |

### Scenario Details

**Scenario N: {Name}**
- **Persona:** {Who is the caller/user}
- **Entry point:** {Channel, trigger}
- **Agents involved:** {Concierge, Specialist: X, etc.}
- **Flow summary:** {Step-by-step in plain English}
- **Key moments:** {The 2–3 beats that should impress the audience}
- **xApp usage:** {Yes/No — if yes, what does it show and when}
- **Live agent handoff:** {Yes/No — if yes, describe the trigger}

---

## Agent Architecture

### Agent Map

| Agent | Role | Tools / Capabilities |
|-------|------|----------------------|
| Concierge | Auth, intent detection, routing | {e.g. account lookup, PIN validation} |
| Specialist: {Name} | {Domain} | {e.g. CRM lookup, case creation} |

### Routing Intent Map

| Intent | Routes To |
|--------|-----------|
| {Intent phrase} | {Agent name} |

---

## Technical Requirements

### Channels

| Channel | Purpose | Setup Notes |
|---------|---------|-------------|
| {Voice Gateway / Webchat / etc.} | {Primary / fallback} | {Any config notes} |

### Voice & xApp

- **SIP trunk required:** {Yes/No}
- **Phone number required:** {Yes/No}
- **xApp in scope:** {Yes/No — if yes, list scenes}

### Integrations

| System | Type | Demo approach (live / stub / fabricated) |
|--------|------|------------------------------------------|
| {CRM name} | CRM | {Stub — returns hardcoded account data} |

### Sample Data

{Describe what data needs to be prepared: account records, product info, FAQ docs, etc.}

### Knowledge AI

- **In scope:** {Yes/No}
- **Source documents:** {List docs to ingest, or note they need to be fabricated}

---

## Cognigy Implementation Notes

### Features to Demonstrate

- [ ] {Feature 1}
- [ ] {Feature 2}

### Reusable Components

| Component | Source | Adaptation needed |
|-----------|--------|-------------------|
| {Flow / agent name} | {Previous demo / existing project} | {What needs changing} |

### Build Complexity

| Component | Estimate | Notes |
|-----------|----------|-------|
| {Concierge flow} | {1–2 days} | |
| **Total** | **{X days}** | |

---

## Success Criteria & Key Messages

### This demo succeeds if the audience leaves believing:

- [ ] {Key message 1}
- [ ] {Key message 2}

### Requirements checklist

- [ ] All {N} intents demonstrated
- [ ] Voice call completed end-to-end without manual intervention

---

## Open Questions & Assumptions

| Item | Status | Owner |
|------|--------|-------|
| {Question or assumption} | {Open / Assumed} | {Name or TBD} |
```

- [ ] **Step 2: Commit**

```bash
git add docs/scope-demo-output-template.md
git commit -m "docs: add scope-demo output template"
```

---

### Task 4: Create `skills/scope-demo/SKILL.md`

**Files:**
- Create: `skills/scope-demo/SKILL.md`

- [ ] **Step 1: Write the file**

```markdown
---
name: scope-demo
description: Design a Cognigy AI agent demo — four-phase conversational workflow covering discovery, design, and structured demo plan generation
---

# Scope Demo

## When to Use

Use this skill when scoping, planning, or designing a Cognigy AI agent demo — whether starting from a brief, email thread, meeting notes, or scratch.

## Reference Docs

Before starting Phase 1, navigate to `<plugin-root>` (two directories up from `skills/scope-demo/`) and read:

- `docs/cognigy-capabilities.md` — Platform reference: channels, xApp, AI Agents, Knowledge AI, integrations, build complexity
- `docs/scope-demo-output-template.md` — Template for the demo plan document generated in Phase 4
- `docs/scope-demo-discovery-questions.md` — Structured discovery guide for Phase 1 when starting from scratch

---

## Phase 1: Fact Gathering

Collect all 11 required facts before proceeding to Phase 2.

**If context has been provided** (emails, briefs, notes): extract facts from it, then identify and ask only about gaps.

**If starting from scratch:** use `docs/scope-demo-discovery-questions.md` as your guide. Ask questions grouped by section — do not dump all questions at once.

**Required facts:**

1. Customer name and industry/vertical
2. Primary business problem
3. Target channels (voice, webchat, WhatsApp, etc.)
4. Key use cases/intents
5. Phasing expectations (MVP vs long-term)
6. Demo format (live call, screen share, Cognigy environment)
7. Demo timeline/date
8. Competitive context
9. Integration landscape
10. Available data (real, sanitised, fabricated)
11. Reusable components from previous demos

**For Fact #11 — Reusable Components:**

If the user has a connected Cognigy project (`.env` present in the working directory), call `cognigy:list` to enumerate existing assets:

```
cognigy:list resource=flows
cognigy:list resource=agents
```

Present the results and ask: "Which of these are candidates for reuse in this demo?"

If no `.env` is present, ask the user directly about reusable assets.

Do not proceed to Phase 2 until all 11 facts are collected.

---

## Phase 2: Facts Summary

Present a structured summary of all 11 facts, one heading per fact.

Wait for explicit confirmation before proceeding. If the user corrects a fact, update it and re-present only the corrected fact. Re-confirm before proceeding.

---

## Phase 3: Demo Design

This is a **collaborative design conversation** — do not generate a complete design unilaterally. Work through each area in order, propose options, and wait for input:

1. **Demo structure** — Single scenario vs multiple; how scenarios progress
2. **Narrative arc** — The story, the "aha moment", what this demo must prove
3. **Scenario design** — Persona, agents involved, key moments, xApp usage, live agent handoff
4. **Routing intents** — Concierge intent map: what triggers each specialist agent

After all areas are agreed, ask explicitly:

> "I have everything I need to write the demo plan. Ready for me to generate it?"

**Do not write the output until the user confirms.**

---

## Phase 4: Write Output

Generate the demo plan using `docs/scope-demo-output-template.md` as the structure.

**Filename:** `{CustomerName}-{DemoType}-demo-plan.md`
**Location:** Write to the directory from which the user launched Claude Code — their working directory, not the plugin root. If the correct path is unclear, ask. Do NOT write files into the plugin directory.

Populate every section. If something is unknown, state the assumption explicitly — never leave a section blank.

---

## Notes

- Never skip the Phase 2 confirmation gate
- Never write output before the Phase 3 explicit confirmation
- `cognigy:list` in Phase 1 is optional — only call it if `.env` is present
- If context covers most facts, extract what you can and only ask about gaps
```

- [ ] **Step 2: Commit**

```bash
git add skills/scope-demo/SKILL.md
git commit -m "feat: add scope-demo composite skill"
```

---

### Task 5: Create `docs/agent-prompting-guide.md`

**Files:**
- Create: `docs/agent-prompting-guide.md`

- [ ] **Step 1: Write the file**

Port from `old-plugin/scaffold-aiagent/references/agent-prompting-guide.md` — full content, unchanged. This is a reference doc for `prepare-agent-persona`.

Content covers:
- `description` field: WHO the agent is (persona statement, max ~300 chars)
- `instructions` field: HOW the agent behaves (standing orders, max 1000 chars) — LOCALISATION / ALWAYS / NEVER sections
- Speaking style fields: formality (formal/balanced/informal), completeness (concise/balanced/verbose)
- What NOT to include in each field
- Routing tool behaviour (route_to_* executes silently; escalate_to_human is communicated)
- Generation principle: elicit user preferences in plain language, then translate to effective prompt text

- [ ] **Step 2: Commit**

```bash
git add docs/agent-prompting-guide.md
git commit -m "docs: add agent-prompting-guide reference for prepare-agent-persona skill"
```

---

### Task 6: Create `docs/cognigy-agent-patterns.md`

**Files:**
- Create: `docs/cognigy-agent-patterns.md`

- [ ] **Step 1: Write the file**

Port from `old-plugin/scaffold-aiagent/references/patterns.md` — full content, unchanged. This is a reference doc for `prepare-agent-persona`.

Content covers:
- Concierge + Specialists pattern (architecture diagram and tool structure)
- Tool granularity: granular vs consolidated approaches with pros/cons
- Context schema examples (e-commerce, automotive, banking)
- Specialist job patterns: information retrieval, transaction, booking, support
- Escalation to human pattern
- Return to concierge pattern
- Stub agent pattern

- [ ] **Step 2: Commit**

```bash
git add docs/cognigy-agent-patterns.md
git commit -m "docs: add cognigy-agent-patterns reference for prepare-agent-persona skill"
```

---

### Task 7: Create `skills/prepare-agent-persona/SKILL.md`

**Files:**
- Create: `skills/prepare-agent-persona/SKILL.md`

- [ ] **Step 1: Write the file**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add skills/prepare-agent-persona/SKILL.md
git commit -m "feat: add prepare-agent-persona composite skill"
```

---

### Task 8: Version Bump

**Files:**
- Modify: `.claude-plugin/plugin.json` — `"version": "1.1.6"` → `"version": "1.1.7"`
- Modify: `cli/package.json` — `"version": "1.1.6"` → `"version": "1.1.7"`

- [ ] **Step 1: Update `.claude-plugin/plugin.json`**

Change `"version": "1.1.6"` to `"version": "1.1.7"`.

- [ ] **Step 2: Update `cli/package.json`**

Change `"version": "1.1.6"` to `"version": "1.1.7"`.

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json cli/package.json
git commit -m "chore: bump version to 1.1.7"
```

---

### Task 9: Push and Update Submodule

- [ ] **Step 1: Push**

```bash
git push
```

- [ ] **Step 2: Update submodule in marketplace repo**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```

---

## Self-Review

**Spec coverage:**
- ✅ `scope-demo` — four-phase workflow, all 11 facts, `cognigy:list` for reusable assets, confirmation gates, output template
- ✅ `prepare-agent-persona` — five steps covering persona, jobs, routing, context schema, output docs
- ✅ No API creation in `prepare-agent-persona` — confirmed by absence of `cognigy:create`/`cognigy:update` and explicit "no Cognigy resources are created" note
- ✅ `cli-reference.md` excluded — not ported
- ✅ All reference docs ported from old skills
- ✅ Version bump covered
- ✅ Submodule update covered
- ✅ Output location explicit: user's CWD, not plugin root, in both skills

**Placeholder scan:** Tasks 5 and 6 reference source files for full content — these need to be read at implementation time, not guessed. No other placeholders.

**Convention check:** Both SKILL.md files match `write-code-node` / `select-node` patterns.
