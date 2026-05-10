# Cognigy Plugin Skill Uplift Findings
## Source: AMI Insurance Demo — IAG Art of the Possible

This document captures insights from reviewing the AMI Insurance demo documentation against the `scope-demo` and `prepare-agent-persona` Cognigy plugin skills. Each finding identifies a gap in the skill definition and references the source document/s that surfaced it.

---

## scope-demo skill

### 1. NZ Regulatory / Compliance Design

The docs treat compliance as a first-class design constraint — CoFI, Fair Insurance Code, one-retention-offer rule, no pressure tactics. These aren't afterthoughts; they shape the entire agent behaviour and tool descriptions.

The skill has no concept of regulatory or compliance context as a discovery fact or design input. A demo for a financial services customer in a regulated market needs this captured early — it changes what the agent can say, what retention offers are permissible, and how escalation works.

**Uplift:** Add a compliance/regulatory constraints fact to Phase 1, and a compliance section to the output template.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Motor_Cancellation_Config.md` — NZ Regulatory & Compliance Requirements section (full table of CoFI and ICNZ Fair Insurance Code obligations and their implementations)
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 8 (`process_policy_change` tool description): compliance requirements encoded as COMPLIANCE REQUIREMENTS block in tool description
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_MultiAgent_Build_Guide.md` — Section 6.6 Retention Agent instructions: "NZ Compliance — ONE retention offer per reason. If declined, proceed immediately."

---

### 2. Tool Descriptions as Compliance Contracts

The docs make a specific architectural point: tool descriptions shouldn't just describe what a tool does — they should carry the compliance contract the LLM reads at decision time. The `process_policy_change` tool description encodes the retention offer rules, two-pass cancellation flow, and reason-routing obligation directly in the description field.

This is a genuinely sophisticated design pattern the skill doesn't surface. A builder following the skill would design tools functionally, not as policy-carrying contracts.

**Uplift:** Phase 3 scenario design should prompt: "What rules or constraints does each tool need to enforce in its description?"

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 8 intro: "Update the tool descriptions on the AI Agent Job node. These carry the compliance contract the LLM reads at decision time." Full `process_policy_change` tool description with embedded COMPLIANCE REQUIREMENTS block.

---

### 3. Bidirectional Channel Integration as a Design Moment

The Webchat v3 integration doc describes a specific pattern — chat triggers website UI, website sends confirmations back — that is one of the main "wow moments" of the demo. This isn't just a technical detail; it's a demo design decision that separates this from a standard chatbot.

The skill treats channels as a technical fact (webchat, voice, etc.) but doesn't prompt thinking about what the channel can do — multimodal moments, side-channel triggers, UI orchestration. xApp gets a mention in the capabilities doc but the broader idea of "what can the channel do beyond chat?" isn't surfaced in Phase 3 design.

**Uplift:** Phase 3 should prompt: "What happens outside the chat window during this demo?" — website triggers, xApp, dashboard updates, confirmation flows.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Webchat_v3_Integration_Pattern.md` — full document; particularly the architecture overview, Direction 1 (Flow → Website) and Direction 2 (Website → Flow) sections
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Motor_Cancellation_Config.md` — Part 10 (Website Authentication Mechanism) and Part 15 (Frontend Architecture)

---

### 4. Two-Pass Confirmation as a Deliberate UX Pattern

The cancellation flow uses a two-pass design: first call returns a summary, second call with `confirmed=true` executes. This is an explicit design decision — not just how the code works, but a customer experience pattern about not executing irreversible actions without a visible summary and explicit confirmation.

The skill doesn't prompt for this kind of thinking. Phase 3 asks about "key moments" but doesn't prompt: "Are there irreversible actions in this demo, and how does the agent handle them?"

**Uplift:** Phase 3 should include a prompt around high-stakes or irreversible actions — how are they staged, what does the customer see before committing?

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 5 (Process Change code node): "Cancel uses two-pass confirmation: First call returns summary, does NOT execute. Second call (with confirmed=true): executes via HTTP Request."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Current_Flow_Fix_Guide.md` — Change 5, "CRITICAL: Customer Says No to Cancellation" block

---

### 5. Session-Wide Auth as an Explicit Design Choice

The docs are emphatic that auth happens once and persists for the entire session across multiple policies. This is a deliberate design decision that removes friction and enables the multi-policy demo arc. It's stated explicitly in multiple docs and encoded in the agent instructions.

The skill doesn't prompt for authentication architecture as a design question. When to auth, how often, and what persists across the conversation are real decisions that affect demo flow.

**Uplift:** Phase 3 should include an auth design prompt — when does auth happen, what does it unlock, does it persist?

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 9 (AI Agent Instructions, Authentication): "Once the customer has logged in, context.authVerified becomes true. It stays true for the whole session. Never ask them to log in again, regardless of how many policies they want to manage."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Current_Flow_Fix_Guide.md` — Change 5, "CRITICAL: Authentication is Session-Wide" block
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_MultiAgent_Build_Guide.md` — Section 6.4 Concierge instructions: "Once authenticated, context.authVerified stays true for the ENTIRE conversation"

---

### 6. Structured vs Verbatim Tool Responses

The Production Rewrite Guide makes a clear distinction between two approaches to tool responses: verbatim "SAY:" strings vs structured data objects that the LLM phrases naturally. It argues for structured responses on quality grounds.

This is a build-quality principle the skill doesn't surface. A builder following the skill could easily end up with the anti-pattern (scripted strings) without knowing there's a better approach.

**Uplift:** The skill's implementation notes section (or a build principles section) should capture the structured-response pattern as a recommended practice.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section overview table: "Tool responses: Before = Verbatim SAY: strings built in JS. After = Structured data objects — LLM phrases naturally." Sections 3–6 each include a "What changed" note explaining the shift.

---

### 7. Demo Reset as an Operational Requirement

The repo has a Reset Demo endpoint that restores all policies to their original state. This is a practical operational need for a repeatable live demo that the skill never mentions.

**Uplift:** The output template should have a "demo operations" section — reset mechanism, seed data management, what breaks if you demo twice without resetting.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Current_Flow_Fix_Guide.md` — Change 7: "The reset endpoint in server.js has already been updated to INSERT the Navara if missing."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Motor_Cancellation_Config.md` — Part 12 (Demo Scenario): references reset flow implicitly through seed data requirements

---

## prepare-agent-persona skill

### 1. Compliance as a Persona-Shaping Input, Not Just a Topic Restriction

Step 1 question 5 asks "are there topics the agent must never discuss or behaviours it must always exhibit?" — framed as guardrails.

The AMI docs show something more fundamental: regulatory compliance reshapes the agent's identity and relationship to the customer. Mia isn't just forbidden from pressure tactics — she's explicitly framed as "an advisor helping them make an informed choice, not a salesperson trying to prevent cancellation." That framing affects tone, retention offer limits, how she handles declined confirmations, everything.

The skill treats compliance as a constraint layer on top of an otherwise neutral persona. The AMI design shows it's a persona-defining input.

**Uplift:** Add a distinct question in Step 1 — "Are there regulatory, legal, or ethical constraints that shape how this agent must behave?" — and treat the answer as persona-defining rather than just a guardrail list.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 9 (AI Agent Instructions, Your Goals): "You are not a salesperson trying to prevent cancellation — you are an advisor helping them make an informed choice."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Motor_Cancellation_Config.md` — NZ Regulatory & Compliance Requirements section
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Current_Flow_Fix_Guide.md` — Change 5 (AI Agent Instructions rewrite)

---

### 2. Outcome-Based Instructions vs Rule-Heavy "Do X Not Y"

The Production Rewrite Guide's central insight — cutting from 11K chars of "CRITICAL: never do X" rules to 5.5K chars of outcome-based guidance — is a quality principle for writing agent instructions that the skill doesn't surface at all.

The prompting guide says keep instructions under 1000 chars (good), but doesn't tell you how to structure them for quality. A builder following the skill could write rule-heavy instructions that technically comply with the 1000-char limit but produce worse agent behaviour.

**Uplift:** Add guidance to `agent-prompting-guide.md` on outcome-based framing — "tell the agent what to achieve, not what to avoid. Rules belong in tool descriptions, not in standing orders."

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 9 "What changed" bullets: "Cut from ~11K chars to ~5.5K chars. Reframed as outcome-based guidance rather than rule lists. Removed the 20+ 'CRITICAL:' repetitions (the LLM doesn't read harder)."

---

### 3. Tool Descriptions as Compliance Contracts

The skill's Step 2 asks for tools as "plain-English actions" — what the tool does. The AMI docs show that tool descriptions also carry the compliance contract the LLM reads at decision time. The `process_policy_change` description encodes the one-offer rule, the two-pass confirmation requirement, and the reason-routing obligation — all in the tool description, not the agent instructions.

This is a deliberate architecture: put the rule where the LLM is reading when it's about to make the decision. A builder following the skill would write short descriptive tool descriptions and put all the rules in agent instructions — the anti-pattern.

**Uplift:** Step 2 should add: "For each tool — are there rules that only apply at the moment this tool is called? If so, encode them in the tool description rather than agent instructions."

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 8 intro: "These carry the compliance contract the LLM reads at decision time." Full `process_policy_change` tool description with embedded COMPLIANCE REQUIREMENTS block.

---

### 4. Silent Tool Execution as a Universal Standing Order

The `agent-prompting-guide.md` mentions silent routing tool execution for `route_to_*` tools specifically. The AMI docs make it a universal standing order for all tools: "Execute tools silently. Never describe tools to the customer. Do not announce that you are using tools."

A builder following the current guide might reasonably conclude that only routing tools should be silent, and have the agent announce "let me check that for you" before every tool call — which causes duplicate messages and breaks the demo.

**Uplift:** Generalise the silent execution rule in `agent-prompting-guide.md` to all tools, with routing tools as a specific example. Make it a default ALWAYS rule in the instructions template.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 9 (AI Agent Instructions, How You Work): "Do not announce that you are using tools."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_MultiAgent_Build_Guide.md` — Section 6.4 Concierge instructions: "Execute tools silently. Never describe tools to the customer. Do NOT say anything before calling a tool if the tool will produce a customer-facing message — this causes duplicate messages."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Current_Flow_Fix_Guide.md` — Change 5, "CRITICAL: Tool Execution" block

---

### 5. Channel-Specific Formatting as a Standing Order

The skill asks about tone (formal/balanced/informal) and completeness (concise/balanced/verbose), and maps these to platform fields. But the AMI docs show a third dimension that lives in the instructions field: channel-specific formatting rules.

"No markdown. No bullet points. Short sentences. Line breaks between distinct points." These aren't captured by formality or completeness settings — they're webchat-specific rendering constraints that must be in the instructions text. The skill currently produces no instructions text for formatting — it defers entirely to the platform fields.

**Uplift:** Step 1 should ask "what channel will this agent primarily operate on?" and then derive channel-appropriate formatting rules as part of the generated instructions — not just formality and completeness sliders.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 9 (Tone): "No markdown, no bullet points in chat."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_MultiAgent_Build_Guide.md` — Section 6.4 Concierge instructions: "Short, clear sentences. Line breaks between points. No markdown, no bullet points."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Current_Flow_Fix_Guide.md` — Change 5, "CRITICAL: Chat Formatting" block

---

### 6. Auth Scope as a Persona-Level Standing Order

Auth architecture is currently absent from the skill. The AMI docs show it belongs in the agent-level instructions as a standing order: "authentication is session-wide — once verified, never re-authenticate regardless of how many policies the customer manages."

This is a universal rule (applies to all jobs), so it belongs in the AI Agent instructions, not in individual job definitions. The skill's Step 3 (routing) partly touches on auth but only as a concierge pre-routing step — not as a session-wide behavioural rule.

**Uplift:** Step 1 should include: "Does this agent authenticate users? If so — when does auth happen, what does it unlock, and does it persist across the conversation?" Generate the answer as a standing order in the instructions field.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 9 (Authentication): "Once the customer has logged in, context.authVerified becomes true. It stays true for the whole session."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Current_Flow_Fix_Guide.md` — Change 5, "CRITICAL: Authentication is Session-Wide" block
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_MultiAgent_Build_Guide.md` — Section 6.4 Concierge instructions: "Once authenticated, context.authVerified stays true for the ENTIRE conversation — NEVER re-authenticate for subsequent requests."

---

### 7. Action-Parameterized Tools — A Missing Pattern

The patterns guide offers two tool design patterns: granular (separate tool per action) and consolidated (one tool, LLM synthesises). The AMI design uses a third: action-parameterized — one tool, multiple actions via an `action` parameter (`cancel`, `transfer`, `downgrade`), with branching logic and shared guards inside the code node.

This pattern is specifically useful when actions share auth guards, policy resolution, and response structure but have different payloads. It's a deliberate design choice with distinct trade-offs the skill doesn't surface.

**Uplift:** Add the action-parameterized pattern to `cognigy-agent-patterns.md` with its trade-offs — good for related actions with shared guards, but the tool description must carry the branching rules clearly.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 5 (Process Change): single `process_policy_change` tool with `action` parameter branching cancel/transfer/downgrade, shared auth guard at top
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_MultiAgent_Build_Guide.md` — Section 8.7 (Process Change): same pattern reproduced in multi-agent context
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Motor_Cancellation_Config.md` — Tool 5 (`process_policy_change`): original implementation of the pattern

---

### 8. `toolResponse` as a Communication Channel

The patterns guide covers context schema with examples of `shortTermMemory` and config namespaces. The AMI docs reveal a fourth category of context variable that the skill and patterns guide don't mention: `context.toolResponse` as the communication channel between code nodes and the AI Agent.

Every tool branch writes its result to `context.toolResponse`. The Resolve Tool Action surfaces it to the LLM. This is the architectural backbone of how Cognigy tools communicate results back to the LLM — and it's entirely absent from the context schema guidance.

**Uplift:** Add `toolResponse` as a standard context variable to the patterns guide, with the pattern explained: code node writes structured object → Resolve Tool Action surfaces it to the LLM.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Sections 3–6 (every tool branch); Section 1 Set Context explicitly initialises: `context.toolResponse = ""`
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_MultiAgent_Build_Guide.md` — Sections 8.3–8.10 (all code nodes use the pattern)
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Motor_Cancellation_Config.md` — Part 13 Context Variables Reference table: `context.toolResponse` listed with "All code tool nodes" as owner

---

### 9. Handover Context as a Designed Artefact

The skill's Step 3 asks what context is handed over on escalation. But the AMI docs show this is a deliberately designed package — customer identity, auth state, target policy, conversation summary, escalation reason, timestamp — structured so the live agent can pick up without asking the customer to repeat themselves.

The skill treats it as a routing question. It's actually a UX and data design decision.

**Uplift:** Step 3 should include a handover design prompt: "What does the live agent need to know to pick up without the customer repeating themselves? Design the handover package." This should produce a named artefact in the context schema output doc.

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 6 (Process Escalation): `context.handoverContext` object design with explicit fields for customer, policy, conversation, escalation_reason, timestamp
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Motor_Cancellation_Config.md` — Tool 6 (`escalate_to_agent`) code node: builds both `context.handoverContext` and `context.shortTermMemory` as separate handover structures with different consumers (CXone vs Agent Assist)

---

### 10. Irreversible Actions and Staged Confirmation

The skill doesn't prompt for a category of agent behaviour the AMI docs model explicitly: what happens when an agent is about to take an irreversible action?

Mia has a standing order that cancellation requires a two-pass pattern — summary first, execution only after explicit confirmation. "Customer says no" also has a standing order: don't end the conversation, ask what they'd like instead. These are general design decisions about high-stakes moments that apply across many use cases (payments, deletions, commitments).

**Uplift:** Step 2 (job definitions) should prompt: "Does this specialist take any irreversible or high-stakes actions? If so — how should it stage confirmation, and what should it do if the customer says no?"

**Sources:**
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Production_Rewrite_Guide.md` — Section 5 (Process Change): "Cancel uses two-pass confirmation: First call returns summary, does NOT execute. Second call (with confirmed=true): executes via HTTP Request." Section 9 (AI Agent Instructions): "If the Customer Says 'No' to a Confirmation — do not assume they want to end the conversation."
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_Current_Flow_Fix_Guide.md` — Change 5, "CRITICAL: Customer Says No to Cancellation" block
- `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/AMI_MultiAgent_Build_Guide.md` — Section 6.6 Retention Agent instructions: "MANDATORY: Reason Routing Before Any Action... Skipping this is a compliance failure."

---

## Summary

| # | Skill | Gap | Uplift Target |
|---|---|---|---|
| 1 | scope-demo | Compliance/regulatory context as a design input | Phase 1 required facts + output template |
| 2 | scope-demo | Tool descriptions as compliance contracts | Phase 3 design prompts |
| 3 | scope-demo | Out-of-chat moments (website triggers, xApp, dashboard) | Phase 3 scenario design |
| 4 | scope-demo | Irreversible actions and staged confirmation patterns | Phase 3 key moments prompt |
| 5 | scope-demo | Auth architecture (when, what persists, session scope) | Phase 3 scenario design |
| 6 | scope-demo | Structured vs verbatim tool responses | Implementation notes / build principles |
| 7 | scope-demo | Demo reset and operational repeatability | Output template — demo operations section |
| 8 | prepare-agent-persona | Compliance as persona-defining, not just guardrails | Step 1 + instructions generation |
| 9 | prepare-agent-persona | Outcome-based vs rule-heavy instructions | `agent-prompting-guide.md` |
| 10 | prepare-agent-persona | Tool descriptions as compliance contracts | Step 2 + `agent-prompting-guide.md` |
| 11 | prepare-agent-persona | Silent tool execution — universal, not just routing | `agent-prompting-guide.md` ALWAYS rules |
| 12 | prepare-agent-persona | Channel formatting as a standing order | Step 1 + instructions generation |
| 13 | prepare-agent-persona | Auth scope as a universal standing order | Step 1 + instructions generation |
| 14 | prepare-agent-persona | Action-parameterized tool pattern | `cognigy-agent-patterns.md` |
| 15 | prepare-agent-persona | `toolResponse` as communication channel | `cognigy-agent-patterns.md` context schema section |
| 16 | prepare-agent-persona | Handover context as a designed artefact | Step 3 + context schema output doc |
| 17 | prepare-agent-persona | Irreversible actions and staged confirmation | Step 2 job definitions |

---

*Generated from review of `/Users/Ben.Elliot/repos/IAG-Art-of-the-Possible/docs/` against Cognigy plugin skill definitions.*
*Skills reviewed: `cognigy:scope-demo`, `cognigy:prepare-agent-persona`*
