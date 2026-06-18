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

- `explain("multi-agent-architecture")` — xApp notes in Specialist Job Patterns
- `explain("agent-handover")` — handover context artefact

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

Reference `explain("agent-handover")` for the implementation template.

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
