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

- `explain("agent-tool-patterns")` — toolResponse channel
- `explain("agent-handover")` — handover context pattern

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
