# AI Agent Prompting Guide

Best practices for writing effective `description` and `instructions` fields on the Cognigy AI Agent resource. These fields are inherited by all Jobs — keep them universal, not job-specific.

## Table of Contents
1. [Field Purposes](#field-purposes)
2. [What NOT to Include](#what-not-to-include)
3. [Writing the Description](#writing-the-description)
4. [Writing the Instructions](#writing-the-instructions)
5. [Tool Execution — Silent by Default](#tool-execution--silent-by-default)
6. [Outcome-Based Framing](#outcome-based-framing)
7. [Tool Descriptions as Compliance Contracts](#tool-descriptions-as-compliance-contracts)
8. [Speaking Style Fields](#speaking-style-fields)
9. [Generation Principle](#generation-principle)

---

## Field Purposes

| Field | Focus | Maps To |
|---|---|---|
| `description` | WHO the agent is — character, role, communication style | Persona statement |
| `instructions` | HOW the agent operates — rules, localisation, scope, behavioral DO/DON'Ts | Standing orders for all jobs |

---

## What NOT to Include

Never put these in `description` or `instructions` at the AI Agent level — they belong in **Job instructions**:

- Tool names or when to use them
- Data paths (`context.shortTermMemory`, `input.*`)
- Step-by-step process flows
- Routing logic or handoff instructions
- Job-specific operational details

---

## Writing the Description

A persona statement — cast the character, don't write a spec. Focused on communication style only.

**Structure:**
```
You are a [ROLE] [working for / at] [COMPANY].

You are [2-3 personality adjectives]. [What drives your approach — 1 sentence].

You speak in a [TONE] way. You are [knowledge level] about [domain].
```

**Good:**
> You are a parts and service specialist at ASV Connect.
> You are warm, efficient, and direct. You understand that mechanics and tradespeople need accurate answers fast.
> You speak in a clear, no-nonsense way. You know automotive parts and trade supply inside out.

**Bad** (contains operational/process detail):
> You help customers find parts. When they ask about stock, check the catalog. If they want to buy, route them to sales.

Keep it under ~300 characters. It's a persona statement, not a brief.

---

## Writing the Instructions

Standing orders every job follows automatically. Structure it clearly so rules are unambiguous. **Max 1000 characters.**

**Recommended structure:**

```
LOCALISATION:
- [Currency, date format, spelling, phone format rules]

ALWAYS:
- [Behavioral DOs]

NEVER:
- [Behavioral DON'Ts]
```

**NOTE:** Scope boundaries (in-scope/out-of-scope) belong in **Job instructions**, not AI Agent instructions. The AI Agent instructions should only contain universal rules that apply to ALL jobs.

**Localisation examples — Australia:**
- Currency: Australian Dollars (use AUD / $, not USD)
- Dates: DD/MM/YYYY format
- Spelling: Australian English (colour, authorise, centre, realise)
- Phone numbers: 04XX XXX XXX (mobile), (0X) XXXX XXXX (landline)

**Behavioral rule examples:**
- Always: acknowledge the customer's situation before moving to solutions
- Always: confirm understanding before taking action on an account
- Never: make promises about delivery timescales or pricing you cannot verify
- Never: discuss competitor products or make price comparisons

---

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

---

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

## Speaking Style Fields

`speakingStyle` is captured as structured platform fields. Do **not** replicate tone guidance in `description` or `instructions` — the platform applies these automatically.

| Field | Options | Effect |
|---|---|---|
| `speakingStyle.formality` | `formal` / `balanced` / `informal` | Register and language formality |
| `speakingStyle.completeness` | `concise` / `balanced` / `verbose` | Response length and detail level |

---

## Generation Principle

What a user says about their brand personality is rarely suitable as a direct LLM prompt. Elicit preferences in plain language, then translate into effective prompt text.

**Example:**

User says: *"friendly and helpful, not too formal"*

Generated description:
> You are warm, approachable, and genuinely invested in solving the customer's problem. You speak in a conversational tone — like a knowledgeable friend, not a call centre script.

Always show the generated `description` and `instructions` for user review before finalising.
