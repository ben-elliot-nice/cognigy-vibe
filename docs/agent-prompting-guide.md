# AI Agent Prompting Guide

Best practices for writing effective `description` and `instructions` fields on the Cognigy AI Agent resource. These fields are inherited by all Jobs — keep them universal, not job-specific.

## Table of Contents
1. [Field Purposes](#field-purposes)
2. [What NOT to Include](#what-not-to-include)
3. [Writing the Description](#writing-the-description)
4. [Writing the Instructions](#writing-the-instructions)
5. [Speaking Style Fields](#speaking-style-fields)
6. [Generation Principle](#generation-principle)

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

## Routing Tool Behavior

**IMPORTANT:** When using `route_to_*` tools (concierge routing to specialists, or specialists returning to concierge), the LLM should execute them **silently without communicating to the user**.

The AI Agent is presented to customers as a singular, unified agent. The routing/orchestration between specialist jobs via tools is an internal implementation detail, not a customer-facing event.

**Exception:** `escalate_to_human` IS a genuine handoff event and should be communicated to the customer.

**Example instruction for Concierge:**
> "When you detect the customer's intent, use the appropriate route_to_* tool. Execute routing tools silently — do not tell the customer you are 'transferring' or 'connecting them' to another specialist."

**Example instruction for Specialists:**
> "If the query is outside your scope, use the return_to_concierge tool silently. Do not say 'let me transfer you' — just execute the tool."

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
