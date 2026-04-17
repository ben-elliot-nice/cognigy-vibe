# Cognigy Skill Uplift — Plan 1: Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the 17-finding skill uplift to reference docs and existing skills — improving output quality for all users of the current plugin without waiting for new skills.

**Architecture:** Pure markdown edits to `docs/` and `skills/`. No TypeScript changes. Each task is independent and can be reviewed in isolation. The rename of `prepare-agent-persona` → `design-agent-persona` is a scoping change (Steps 2-5 are removed from that skill and will live in new skills in Plan 2).

**Tech Stack:** Markdown only. No tests. Verification = read the file and confirm no obvious gaps.

---

## File Map

| Action | Path | Why |
|--------|------|-----|
| Modify | `docs/agent-prompting-guide.md` | Add: silent execution universal, outcome-based framing, tool descriptions as contracts |
| Modify | `docs/cognigy-agent-patterns.md` | Add: action-parameterized pattern, toolResponse channel, handover context pattern |
| Modify | `skills/scope-demo/SKILL.md` | Add: compliance fact #12, out-of-chat/irreversible/auth prompts in Phase 3, structured response note |
| Modify | `docs/scope-demo-output-template.md` | Add: compliance section, demo operations section |
| Rename | `skills/prepare-agent-persona/` → `skills/design-agent-persona/` | Rename + rewrite SKILL.md to Step 1 scope only |
| Modify | `.claude-plugin/plugin.json` | Version bump 1.1.10 → 1.1.11 |
| Modify | `cli/package.json` | Version bump 1.1.10 → 1.1.11 |

All paths relative to `/Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin`.

---

### Task 1: Update `docs/agent-prompting-guide.md`

Three additions: expand silent execution to all tools, add outcome-based framing section, add tool descriptions as compliance contracts section.

**Files:**
- Modify: `docs/agent-prompting-guide.md`

- [ ] **Step 1: Replace "Routing Tool Behavior" section with expanded universal silent execution section**

Find this section (lines 94–106):
```markdown
## Routing Tool Behavior

**IMPORTANT:** When using `route_to_*` tools (concierge routing to specialists, or specialists returning to concierge), the LLM should execute them **silently without communicating to the user**.

The AI Agent is presented to customers as a singular, unified agent. The routing/orchestration between specialist jobs via tools is an internal implementation detail, not a customer-facing event.

**Exception:** `escalate_to_human` IS a genuine handoff event and should be communicated to the customer.

**Example instruction for Concierge:**
> "When you detect the customer's intent, use the appropriate route_to_* tool. Execute routing tools silently — do not tell the customer you are 'transferring' or 'connecting them' to another specialist."

**Example instruction for Specialists:**
> "If the query is outside your scope, use the return_to_concierge tool silently. Do not say 'let me transfer you' — just execute the tool."
```

Replace with:
```markdown
## Tool Execution — Silent by Default

**All tools execute silently.** Never describe, announce, or narrate tool calls to the customer. The AI Agent is one unified experience — tool orchestration is internal, not a customer-facing event.

**ALWAYS rule — include in every agent's instructions:**

```
ALWAYS:
- Execute tools silently — do not announce, describe, or narrate tool calls
- Do not say anything before a tool call if the tool produces a customer-facing message — this causes duplicate output
```

This applies to **all tools**: search tools, action tools, routing tools, xApp tools. None of them should be announced.

**Exception:** `escalate_to_human` IS a customer-facing event — it changes the customer's experience visibly and should be communicated (e.g. "Let me connect you with one of our team members.").

**Routing tools specifically:**
`route_to_*` and `return_to_concierge` execute silently. Do not tell the customer you are transferring or connecting them — the agent is presented as singular.
```

- [ ] **Step 2: Add "Outcome-Based Framing" section** — insert before "Speaking Style Fields"

```markdown
## Outcome-Based Framing

Write instructions that tell the agent **what to achieve**, not what to avoid. Rule-heavy "CRITICAL: never do X" lists produce worse agent behaviour — the LLM doesn't read harder when you stack more rules.

**Anti-pattern (rule-heavy):**
```
CRITICAL: NEVER offer more than one retention deal.
CRITICAL: NEVER apply pressure if customer declines.
CRITICAL: NEVER proceed without confirmation.
```

**Better (outcome-based):**
```
Your goal is to help the customer make an informed choice — not to prevent cancellation. If they want to leave, understand why and present one relevant option clearly. If they decline, accept it and ask what they'd like to do next.
```

**Rule:** If you find yourself writing more than 3 NEVER/CRITICAL lines, reframe as outcomes. Specific compliance obligations belong in **tool descriptions** (where the LLM reads them at decision time), not in standing orders. Standing orders are for universal behavioural rules that apply regardless of which tool is being called.

---
```

- [ ] **Step 3: Add "Tool Descriptions as Compliance Contracts" section** — insert after "Outcome-Based Framing"

```markdown
## Tool Descriptions as Compliance Contracts

Tool descriptions aren't just functional summaries — they carry the compliance contract the LLM reads at the moment of decision. Put the rule **where the LLM is reading when it's about to act**.

**Example — compliance embedded in a tool description:**

```
process_policy_change: Use this tool to cancel, transfer, or downgrade a policy.

ACTION parameter: "cancel" | "transfer" | "downgrade"

COMPLIANCE REQUIREMENTS:
- ONE retention offer per reason. If the customer declines, proceed immediately — do not offer again.
- Cancel uses two-pass confirmation: first call returns summary only and does NOT execute. Second call (confirmed=true) executes.
- Reason routing is MANDATORY before any action.
```

**Why here, not in agent instructions?**

Agent instructions are read at the start of every turn. Tool descriptions are read at the moment the LLM is selecting a tool. Compliance rules for a specific action have maximum effect at point-of-use.

| What belongs in tool descriptions | What stays in agent instructions |
|---|---|
| Rules specific to this tool being called | Universal behavioural rules (tone, auth, silence) |
| Confirmation requirements before executing | Localisation rules |
| Obligation limits (one-offer, single-attempt) | Rules that apply regardless of tool |
| Branching/sequencing requirements | Outcome framing |

---
```

- [ ] **Step 4: Verify the file reads correctly**

Read `docs/agent-prompting-guide.md` and confirm:
- "Tool Execution — Silent by Default" section exists and covers all tools
- "Outcome-Based Framing" section exists with anti-pattern + better example
- "Tool Descriptions as Compliance Contracts" section exists with the table

- [ ] **Step 5: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add docs/agent-prompting-guide.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "docs: uplift agent-prompting-guide with silent execution, outcome-based framing, tool contracts"
```

---

### Task 2: Update `docs/cognigy-agent-patterns.md`

Three additions: action-parameterized tool pattern, toolResponse as communication channel, handover context pattern.

**Files:**
- Modify: `docs/cognigy-agent-patterns.md`

- [ ] **Step 1: Add "Action-Parameterized Approach" subsection** — insert after the "Recommendation" paragraph in the Tool Granularity section (after line 121)

```markdown
### Action-Parameterized Approach

One tool handles multiple related actions via an `action` parameter, with shared guards and branching logic inside the code node.

```json
{
  "toolId": "process_policy_change",
  "description": "Use this tool to cancel, transfer, or downgrade a policy. See COMPLIANCE REQUIREMENTS in this description before calling.\n\nACTION: 'cancel' | 'transfer' | 'downgrade'\n\nCOMPLIANCE REQUIREMENTS:\n- ONE retention offer per reason. If declined, proceed immediately.\n- Cancel: two-pass confirmation. First call returns summary, does NOT execute. Second call (confirmed=true) executes.\n- Reason routing MANDATORY before any action.",
  "useParameters": true,
  "parameters": {
    "type": "object",
    "properties": {
      "action": { "type": "string", "enum": ["cancel", "transfer", "downgrade"] },
      "policyNumber": { "type": "string", "description": "Policy number to modify" },
      "confirmed": { "type": "boolean", "description": "Set true on second call to execute after customer confirms summary" }
    },
    "required": ["action", "policyNumber"],
    "additionalProperties": false
  }
}
```

The code node branches on `input.aiAgent.toolArgs.action`. Auth guard and policy resolution run once at the top, shared across all branches.

**Pros:** Shared auth guards, shared policy resolution, single tool description to maintain, cleaner LLM decision space.
**Cons:** Tool description must carry branching rules clearly or the LLM may misuse the `action` parameter.
**When to use:** Related actions sharing preconditions, policy resolution, and response shape — e.g. all policy modification operations.

---
```

- [ ] **Step 2: Add "`context.toolResponse` — Tool Communication Channel" section** — insert after the Context Schema Examples section (after the Banking Demo block)

```markdown
## `context.toolResponse` — Tool Communication Channel

Every tool branch writes its result to `context.toolResponse`. The Resolve Tool Action Node surfaces this to the LLM as the tool's output. This is the architectural backbone of tool-to-LLM communication in Cognigy.

**Pattern — Code Node at end of every tool branch:**

```javascript
// Success case:
context.toolResponse = {
  success: true,
  summary: "Policy ABC123 cancellation scheduled for 30/04/2026.",
  data: {
    policyNumber: "ABC123",
    effectiveDate: "2026-04-30",
    refundAmount: 42.50
  }
}

// Blocked/refused case:
context.toolResponse = {
  success: false,
  blocked: true,
  reason: "Retention offer already made for this reason. Proceeding with cancellation."
}
```

Resolve Tool Action Node then sends `context.toolResponse` to the LLM.

**Initialise at session start (Set Context Node):**

```javascript
context.toolResponse = ""
```

**Four context variable categories:**

| Category | Path | LLM-visible | Lifetime |
|---|---|---|---|
| Transient | `input.*` | Yes | Per turn — wiped each turn |
| Session memory | `context.shortTermMemory.*` | Yes | Full session |
| Tool result | `context.toolResponse` | Yes (via Resolve Tool Action) | Overwritten each tool call |
| State / config | `context.<namespace>.*` | No (by default) | Full session |

---
```

- [ ] **Step 3: Add "Handover Context Pattern" section** — insert after the Return to Concierge Pattern section

```markdown
## Handover Context Pattern

When escalating to a human agent, design the handover package as a structured artefact — not just a summary string. Identify both consumers and what they need.

**Consumer 1: ACD / routing system** — structured fields for screen pop and routing:

```javascript
context.handoverContext = {
  customer: {
    name: context.shortTermMemory.customerName,
    policyNumber: context.shortTermMemory.policyNumber,
    authenticated: context.authVerified
  },
  conversation: {
    intent: context.shortTermMemory.intent,
    summary: context.shortTermMemory.conversationSummary,
    retentionAttempted: context.shortTermMemory.retentionOffered ?? false
  },
  escalation: {
    reason: input.aiAgent.toolArgs.reason,
    timestamp: new Date().toISOString()
  }
}
```

**Consumer 2: Agent Assist / live agent reading** — natural language summary:

```javascript
context.shortTermMemory.handoverSummary =
  `Customer ${context.shortTermMemory.customerName} ` +
  `called about ${context.shortTermMemory.intent}. ` +
  (context.shortTermMemory.retentionOffered ?
    "Retention offer was made and declined. " : "") +
  `Policy: ${context.shortTermMemory.policyNumber}. ` +
  `Authenticated: ${context.authVerified ? "Yes" : "No"}.`
```

**Design the package upfront** — identify both consumers, what they need, and which context paths hold that data. The handover context is a designed artefact, not an afterthought.

---
```

- [ ] **Step 4: Verify the file reads correctly**

Read `docs/cognigy-agent-patterns.md` and confirm three new sections are present and correctly placed.

- [ ] **Step 5: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add docs/cognigy-agent-patterns.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "docs: uplift cognigy-agent-patterns with action-parameterized pattern, toolResponse, handover context"
```

---

### Task 3: Update `skills/scope-demo/SKILL.md`

Three changes: add Fact #12 (compliance), expand Phase 3 with three new design areas, add structured response note.

**Files:**
- Modify: `skills/scope-demo/SKILL.md`

- [ ] **Step 1: Add Fact #12 to Phase 1**

After fact 11 (`11. Reusable components from previous demos`), add:

```markdown
12. Regulatory/compliance constraints — Any industry-specific obligations that shape what the agent can say or do (e.g. fair dealing requirements, one-offer limits, consent requirements, mandatory disclosures, pressure-tactic prohibitions). These affect agent instructions, tool descriptions, and what constitutes a valid outcome. If none apply, note "no regulated constraints".
```

- [ ] **Step 2: Expand Phase 3 with three new design areas**

After area 4 (`4. **Routing intents** — Concierge intent map: what triggers each specialist agent`), add:

```markdown
5. **Out-of-chat moments** — What happens outside the chat window during this demo? (website UI triggers, xApp scenes, dashboard updates, confirmation screens, SMS/push notifications) This is often the differentiated "wow moment" of the demo.
6. **Irreversible actions** — Does any scenario involve actions the customer cannot undo? (cancellations, purchases, account changes) If so — how are they staged? What does the customer see before committing?
7. **Auth architecture** — When does authentication happen? What does it unlock? Does it persist across scenarios or reset per interaction?
```

- [ ] **Step 3: Add structured response note to Notes section**

Add this bullet to the existing Notes section:

```markdown
- Tool responses should return structured data objects, not verbatim scripted strings — let the LLM phrase the response naturally from structured data
```

- [ ] **Step 4: Verify the file reads correctly**

Read `skills/scope-demo/SKILL.md` and confirm 12 facts in Phase 1, 7 areas in Phase 3, and the new note.

- [ ] **Step 5: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add skills/scope-demo/SKILL.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "feat: uplift scope-demo with compliance fact, out-of-chat/irreversible/auth design prompts"
```

---

### Task 4: Update `docs/scope-demo-output-template.md`

Two additions: compliance section in Technical Requirements, Demo Operations section at end.

**Files:**
- Modify: `docs/scope-demo-output-template.md`

- [ ] **Step 1: Add Compliance/Regulatory subsection to Technical Requirements**

After the Knowledge AI subsection, add:

```markdown
### Compliance / Regulatory

- **Regulatory context:** {Industry/market obligations — e.g. CoFI (NZ), FCA (UK), or "none"}
- **Key constraints:** {Bullet list of obligations affecting agent behaviour — e.g. one-offer limit per reason, mandatory disclosure before cancellation, two-pass confirmation for irreversible actions}
- **How encoded:** {Where these rules live — agent instructions, tool descriptions, or both}
```

- [ ] **Step 2: Add Demo Operations section at end of template** — after Open Questions & Assumptions

```markdown
---

## Demo Operations

### Repeatability

- **Stateful actions in this demo:** {List any actions that change persistent state — e.g. cancellations, bookings, account updates — or "none (fully stateless)"}
- **Reset mechanism:** {How to restore demo to initial state before running again — e.g. "POST /reset-demo", "reload seed data", "n/a — all stub responses, no persistent state"}
- **Reset steps:** {Step-by-step — or "n/a"}

### Seed Data Requirements

| Record | Value | Purpose |
|--------|-------|---------|
| {e.g. Customer account} | {e.g. Policy ABC123, 4-year tenure, no recent claims} | {e.g. Enables retention offer scenario} |
```

- [ ] **Step 3: Verify the file reads correctly**

Read `docs/scope-demo-output-template.md` and confirm both new sections are present and correctly placed.

- [ ] **Step 4: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add docs/scope-demo-output-template.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "docs: add compliance and demo operations sections to scope-demo output template"
```

---

### Task 5: Rename + rewrite `prepare-agent-persona` → `design-agent-persona`

Rename the skill directory, update the SKILL.md to the new scoped definition (Step 1 only — Steps 2-5 move to Plan 2 new skills).

**Files:**
- Rename: `skills/prepare-agent-persona/` → `skills/design-agent-persona/`
- Rewrite: `skills/design-agent-persona/SKILL.md`

- [ ] **Step 1: Rename the directory**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin mv skills/prepare-agent-persona skills/design-agent-persona
```

- [ ] **Step 2: Overwrite `skills/design-agent-persona/SKILL.md`** with this content:

```markdown
---
name: design-agent-persona
description: Design the Cognigy AI agent's identity and behavioural standing orders — brand voice, compliance framing, channel formatting, and auth scope. Produces agent-level description and instructions fields. Run cognigy:design-agent-jobs for job definitions, routing, and context schema.
---

# Design Agent Persona

## When to Use

Use this skill to design the AI Agent resource's identity layer — the `description` and `instructions` fields that all specialist jobs inherit. Run after `cognigy:scope-demo` when a demo plan is available.

**This skill covers persona only.** For job definitions, routing architecture, and context schema → `cognigy:design-agent-jobs`. For xApp and channel interfaces → `cognigy:design-agent-interfaces`. For contract enforcement → `cognigy:design-agent-contracts`.

## Reference Docs

Before starting, navigate to `<plugin-root>` (two directories up from `skills/design-agent-persona/`) and read:

- `docs/agent-prompting-guide.md` — Field purposes, silent execution, outcome-based framing, tool descriptions as contracts, speaking style fields

---

## Context Check

Check whether a demo plan from `scope-demo` is available (e.g. a `*-demo-plan.md` file in the working directory). If so, read it and extract:
- Customer name and brand
- Primary channel(s) in scope
- Regulatory/compliance constraints (Fact #12 from demo plan)
- Use cases / intents

If no demo plan is available, ask the user to provide brand and channel context before proceeding.

---

## Step 1: Brand Voice, Compliance & Behavioural Standing Orders

Work through these questions collaboratively. Do not generate outputs yet.

1. **Agent name** — What is the agent called? (e.g. "Aria from TechCorp")
2. **Tone** — How should the agent present itself? (formal / balanced / informal)
3. **Verbosity** — How much should it say? (concise / balanced / verbose)
4. **Brand voice** — Is there a brand voice guide or examples of how the company communicates? (search online if needed)
5. **Compliance framing** — Are there regulatory, legal, or ethical constraints that shape this agent's identity and relationship to the customer? This is persona-defining, not just a guardrail list. (e.g. "You are an advisor helping the customer make an informed choice — not a salesperson preventing cancellation.")
6. **Primary channel** — What channel will this agent primarily operate on? (webchat, voice, WhatsApp) — drives channel-specific formatting rules.
7. **Auth scope** — Does this agent authenticate users? If so — when does auth happen, what does it unlock, and does it persist across the conversation?
8. **Universal constraints** — Any firm Always/Never rules that apply across every interaction, regardless of which job is active?

Read `docs/agent-prompting-guide.md` before drafting. Apply outcome-based framing — see "Outcome-Based Framing" section.

**When generating `instructions`, always include:**
- `LOCALISATION` block (currency, dates, spelling, phone format for the market)
- Channel formatting rules from question 6:
  - Webchat: "No markdown, no bullet points. Short sentences. Line breaks between distinct points."
  - Voice: "Responses must be spoken naturally — no lists, no formatting characters."
  - WhatsApp: "Use plain text. Minimal formatting."
- Silent execution: "Execute tools silently. Do not announce or narrate tool calls. Do not say anything before a tool call if the tool produces a customer-facing message."
- Auth persistence rule from question 7 (e.g. "Once context.authVerified is true, never re-authenticate for the remainder of the session.")
- Compliance framing from question 5 — stated as an outcome/identity, not a rule list
- ALWAYS/NEVER rules from question 8

Draft both `description` (~300 chars) and `instructions` (~1000 chars max) and present for review before proceeding.

Confirm: "Happy with this persona? I'll lock it in."

---

## Step 2: Write Output

Generate `{CustomerName}-agent-persona.md`. Write to the directory from which the user launched Claude Code — not the plugin root.

### Sections:

**Agent Identity**
- Name
- `description` field value (ready to paste into Cognigy)
- `instructions` field value (ready to paste into Cognigy)
- Speaking style: `formality` / `completeness` values

**Brand Voice Notes**
- How the persona was derived
- Compliance framing rationale (if applicable)
- Channel formatting decisions and why
- Auth scope rule (if applicable)

---

## Notes

- This skill produces a design document only — no Cognigy resources are created
- Write output to the user's working directory, not the plugin directory
- For jobs, routing, and context schema → `cognigy:design-agent-jobs`
- For xApp, bidirectional webchat, and handover context → `cognigy:design-agent-interfaces`
- For deterministic contract enforcement → `cognigy:design-agent-contracts`
- For the full design workflow in one go → `cognigy:design-agent`
```

- [ ] **Step 3: Verify the renamed file reads correctly**

Read `skills/design-agent-persona/SKILL.md` and confirm it has the correct frontmatter name, the updated Step 1 questions (8 questions), channel formatting block, and references to the other new skills.

- [ ] **Step 4: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add skills/design-agent-persona/SKILL.md
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "feat: rename prepare-agent-persona → design-agent-persona, scope to Step 1, add compliance/channel/auth prompts"
```

---

### Task 6: Version Bump, Push, Submodule

**Files:**
- Modify: `.claude-plugin/plugin.json` — `"version": "1.1.10"` → `"version": "1.1.11"`
- Modify: `cli/package.json` — `"version": "1.1.10"` → `"version": "1.1.11"`

- [ ] **Step 1: Bump `.claude-plugin/plugin.json`**

Change `"version": "1.1.10"` to `"version": "1.1.11"`.

- [ ] **Step 2: Bump `cli/package.json`**

Change `"version": "1.1.10"` to `"version": "1.1.11"`.

- [ ] **Step 3: Stage and commit**

```bash
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin add .claude-plugin/plugin.json cli/package.json
git -C /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin commit -m "chore: bump version to 1.1.11"
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

**Spec coverage (17 findings):**
- ✅ #1 — Compliance as design input: scope-demo Phase 1 Fact #12, output template Compliance section
- ✅ #2 — Tool descriptions as contracts: scope-demo Phase 3 note, agent-prompting-guide.md new section
- ✅ #3 — Out-of-chat moments: scope-demo Phase 3 area 5
- ✅ #4 — Two-pass confirmation: scope-demo Phase 3 area 6 (irreversible actions)
- ✅ #5 — Auth architecture: scope-demo Phase 3 area 7, design-agent-persona Step 1 question 7
- ✅ #6 — Structured vs verbatim: scope-demo Notes
- ✅ #7 — Demo reset: output template Demo Operations section
- ✅ #8 — Compliance as persona-defining: design-agent-persona Step 1 question 5
- ✅ #9 — Outcome-based framing: agent-prompting-guide.md new section
- ✅ #10 — Tool descriptions as contracts: agent-prompting-guide.md new section, design-agent-persona references it
- ✅ #11 — Silent execution universal: agent-prompting-guide.md "Tool Execution — Silent by Default"
- ✅ #12 — Channel formatting as standing order: design-agent-persona Step 1 question 6 + generated instructions block
- ✅ #13 — Auth scope as standing order: design-agent-persona Step 1 question 7 + generated instructions block
- ✅ #14 — Action-parameterized pattern: cognigy-agent-patterns.md new section
- ✅ #15 — toolResponse channel: cognigy-agent-patterns.md new section
- ✅ #16 — Handover context as artefact: cognigy-agent-patterns.md new section
- ✅ #17 — Irreversible actions/staged confirmation: scope-demo Phase 3 area 6

**Placeholder scan:** None. All new content is explicit and complete.

**Out of scope for Plan 1 (covered in Plan 2):**
- design-agent-jobs, design-agent-interfaces, design-agent-contracts, design-agent skills
