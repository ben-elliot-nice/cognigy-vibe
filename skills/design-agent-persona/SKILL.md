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

- `explain("agent-persona-authoring")` — field purposes, description/instructions structure, speaking style fields
- `explain("agent-behavioral-rules")` — silent execution, outcome-based framing, tool descriptions as contracts

---

## Context Check

Check whether a demo plan from `scope-demo` is available (e.g. a `*-demo-plan.md` file in `output_dir` if that argument was supplied, otherwise in the user's working directory). If so, read it and extract:
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

Read `explain("agent-persona-authoring")` and `explain("agent-behavioral-rules")` before drafting.

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

Generate `{CustomerName}-agent-persona.md`. If an `output_dir` argument was supplied by the caller, write the file there. Otherwise write to the directory from which the user launched Claude Code — not the plugin root.

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
- Write output to the `output_dir` argument if supplied by the caller (e.g. `cognigy:build-orchestrator` passes `"Demo Builds/<customer>-demo"`); otherwise write to the user's working directory. Never write into the plugin directory.
- For jobs, routing, and context schema → `cognigy:design-agent-jobs`
- For xApp, bidirectional webchat, and handover context → `cognigy:design-agent-interfaces`
- For deterministic contract enforcement → `cognigy:design-agent-contracts`
- For the full design workflow in one go → `cognigy:design-agent`
- To build after designing → use `cognigy:add-aiagent-job` (creates nodes via MCP tools)
