---
name: scope-demo
description: Design a Cognigy AI agent demo — four-phase conversational workflow covering discovery, design, and structured demo plan generation
---

# Scope Demo

## When to Use

Use this skill when scoping, planning, or designing a Cognigy AI agent demo — whether starting from a brief, email thread, meeting notes, or scratch.

## Reference Docs

Before starting Phase 1, read:

- `references/cognigy-capabilities.md` — Platform reference: channels, xApp, AI Agents, Knowledge AI, integrations, build complexity
- `references/scope-demo-output-template.md` — Template for the demo plan document generated in Phase 4
- `references/scope-demo-discovery-questions.md` — Structured discovery guide for Phase 1 when starting from scratch

---

## Phase 1: Fact Gathering

Collect all 12 required facts before proceeding to Phase 2.

**If context has been provided** (emails, briefs, notes): extract facts from it, then identify and ask only about gaps.

**If starting from scratch:** use `references/scope-demo-discovery-questions.md` as your guide. Ask questions grouped by section — do not dump all questions at once.

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
12. Regulatory/compliance constraints — Any industry-specific obligations that shape what the agent can say or do (e.g. fair dealing requirements, one-offer limits, consent requirements, mandatory disclosures, pressure-tactic prohibitions). These affect agent instructions, tool descriptions, and what constitutes a valid outcome. If none apply, note "no regulated constraints".

**For Fact #11 — Reusable Components:**

Call `get_build_state` and check whether a project is bound (non-empty `project_id` in the state). If a project is bound, call the MCP tools to enumerate existing assets:

```
cognigy_list(resource_type='flows')
cognigy_list(resource_type='aiagents')
```

Present the results and ask: "Which of these are candidates for reuse in this demo?"

If no project is bound, ask the user directly about reusable assets.

Do not proceed to Phase 2 until all 12 facts are collected.

---

## Phase 2: Facts Summary

Present a structured summary of all 12 facts, one heading per fact.

Wait for explicit confirmation before proceeding. If the user corrects a fact, update it and re-present only the corrected fact. Re-confirm before proceeding.

---

## Phase 3: Demo Design

This is a **collaborative design conversation** — do not generate a complete design unilaterally. Work through each area in order, propose options, and wait for input:

1. **Demo structure** — Single scenario vs multiple; how scenarios progress
2. **Narrative arc** — The story, the "aha moment", what this demo must prove
3. **Scenario design** — Persona, agents involved, key moments, xApp usage, live agent handoff
4. **Routing intents** — Concierge intent map: what triggers each specialist agent
5. **Out-of-chat moments** — What happens outside the chat window during this demo? (website UI triggers, xApp scenes, dashboard updates, confirmation screens, SMS/push notifications) This is often the differentiated "wow moment" of the demo.
6. **Irreversible actions** — Does any scenario involve actions the customer cannot undo? (cancellations, purchases, account changes) If so — how are they staged? What does the customer see before committing?
7. **Auth architecture** — When does authentication happen? What does it unlock? Does it persist across scenarios or reset per interaction?

After all seven areas are agreed, ask explicitly:

> "I have everything I need to write the demo plan. Ready for me to generate it?"

**Do not write the output until the user confirms.**

---

## Phase 4: Write Output

Generate the demo plan using `references/scope-demo-output-template.md` as the structure.

**Filename:** `{CustomerName}-{DemoType}-demo-plan.md`
**Location:** If an `output_dir` argument was passed by the caller (e.g. `cognigy-vibe:build-orchestrator` passes its resolved `$DEMO_DIR` — an absolute path, e.g. `"/Users/.../Demo Builds/acme-demo"`), write the file there. Otherwise write to cwd — the directory from which the user launched Claude Code, not the plugin root. If the correct path is unclear, ask. Do NOT write files into the plugin directory.

Populate every section. If something is unknown, state the assumption explicitly — never leave a section blank.

---

## Notes

- Never skip the Phase 2 confirmation gate
- Never write output before the Phase 3 explicit confirmation
- `cognigy_list` MCP calls in Phase 1 are optional — only call them if `.env` is present
- If context covers most facts, extract what you can and only ask about gaps
- Tool responses should return structured data objects, not verbatim scripted strings — let the LLM phrase the response naturally from structured data
