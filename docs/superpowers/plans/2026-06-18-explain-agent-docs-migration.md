# Explain Agent Docs Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `docs/agent-prompting-guide.md` and `docs/cognigy-agent-patterns.md` into 5 explain resource topics, update the 4 consuming skills to use `explain()` calls, and delete the source docs.

**Architecture:** Five new markdown files under `skills/explain/resources/aiagent/` feed the existing build pipeline (`scripts/build_explain_topics.py`), which regenerates `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py` and `skills/explain/SKILL.md`. Consuming skills are updated to call `explain("topic")` instead of reading docs files directly.

**Tech Stack:** Python 3.x, uv, pytest — no new dependencies.

## Global Constraints

- All resource files must have frontmatter with `topic`, `description`, and `group: aiagent`
- Build command: `uv run scripts/build_explain_topics.py` from repo root
- Test command: `uv run pytest cognigy-mcp/tests/ -q` from repo root
- Baseline: 35 tests passing before any changes
- Version bump required on every PR touching `cognigy-mcp/` or `skills/`: patch increment in both `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json` (current: `1.4.2` → `1.4.3`)
- Working directory: `.claude/worktrees/issue-58-explain-docs-migration`

---

### Task 1: Write agent-persona-authoring resource file

**Files:**
- Create: `skills/explain/resources/aiagent/agent-persona-authoring.md`

**Interfaces:**
- Produces: `explain("agent-persona-authoring")` topic (available after Task 6 build step)

- [ ] **Step 1: Create the file**

```markdown
---
topic: agent-persona-authoring
description: AI Agent description and instructions field authoring — structure, constraints, speaking style
group: aiagent
---

## agent-persona-authoring — Authoring AI Agent Fields

### Field purposes

| Field | Focus | Maps to |
|---|---|---|
| `description` | WHO the agent is — character, role, communication style | Persona statement |
| `instructions` | HOW the agent operates — rules, localisation, scope, behavioral DO/DON'Ts | Standing orders for all jobs |

### What NOT to put in description or instructions
These belong in Job instructions, not the AI Agent level:
- Tool names or when to use them
- Data paths (`context.shortTermMemory`, `input.*`)
- Step-by-step process flows
- Routing logic or handoff instructions
- Job-specific operational details

### description structure
Cast the character — communication style only. Target ~300 chars.

  You are a [ROLE] [working for / at] [COMPANY].
  You are [2-3 personality adjectives]. [What drives your approach — 1 sentence].
  You speak in a [TONE] way. You are [knowledge level] about [domain].

Example:
  You are a parts and service specialist at ASV Connect.
  You are warm, efficient, and direct. You understand that mechanics need accurate answers fast.
  You speak in a clear, no-nonsense way. You know automotive parts and trade supply inside out.

Do NOT write: "You help customers find parts. When they ask about stock, check the catalog."
That is operational detail — it belongs in Job instructions.

### instructions structure
Standing orders every job follows. Max 1000 chars.

  LOCALISATION:
  - [Currency, date format, spelling, phone format]

  ALWAYS:
  - [Behavioral DOs]

  NEVER:
  - [Behavioral DON'Ts]

Scope boundaries (in-scope/out-of-scope) belong in Job instructions, not here.
Only universal rules that apply to ALL jobs go in AI Agent instructions.

Localisation examples — Australia:
- Currency: Australian Dollars (AUD / $, not USD)
- Dates: DD/MM/YYYY
- Spelling: Australian English (colour, authorise, centre, realise)
- Phone: 04XX XXX XXX (mobile), (0X) XXXX XXXX (landline)

### Speaking style fields
Do NOT replicate tone guidance in description or instructions — use platform fields:

| Field | Options | Effect |
|---|---|---|
| `speakingStyle.formality` | `formal` / `balanced` / `informal` | Register and language formality |
| `speakingStyle.completeness` | `concise` / `balanced` / `verbose` | Response length and detail level |

### Generation principle
Elicit brand preferences in plain language, then translate into prompt text.
Do not use what the user said verbatim.

User says: "friendly and helpful, not too formal"
Generate: "You are warm, approachable, and genuinely invested in solving the customer's
problem. You speak in a conversational tone — like a knowledgeable friend, not a call centre script."

Always show generated description and instructions for user review before finalising.
```

- [ ] **Step 2: Verify frontmatter parses**

Run: `uv run python -c "
import re, pathlib
f = pathlib.Path('skills/explain/resources/aiagent/agent-persona-authoring.md').read_text()
m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', f, re.DOTALL)
assert m, 'No frontmatter'
fm = dict(l.partition(':')[0::2] for l in m.group(1).splitlines() if ':' in l)
assert fm['topic'].strip() == 'agent-persona-authoring'
assert fm['group'].strip() == 'aiagent'
print('OK')
"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/explain/resources/aiagent/agent-persona-authoring.md
git commit -m "feat: add agent-persona-authoring explain topic"
```

---

### Task 2: Write agent-behavioral-rules resource file

**Files:**
- Create: `skills/explain/resources/aiagent/agent-behavioral-rules.md`

**Interfaces:**
- Produces: `explain("agent-behavioral-rules")` topic (available after Task 6 build step)

- [ ] **Step 1: Create the file**

```markdown
---
topic: agent-behavioral-rules
description: Silent tool execution, outcome-based framing, compliance rules in tool descriptions
group: aiagent
---

## agent-behavioral-rules — AI Agent Behavioral Rules

### Silent tool execution
All tools execute silently. Never describe, announce, or narrate tool calls to the customer.

Include in every agent's instructions:

  ALWAYS:
  - Execute tools silently — do not announce, describe, or narrate tool calls
  - Do not say anything before a tool call if the tool produces a customer-facing message — this causes duplicate output

This applies to all tools: search tools, action tools, routing tools, xApp tools.

Exception: `escalate_to_human` IS customer-facing — communicate it explicitly:
  "Let me connect you with one of our team members."

Routing tools (`route_to_*`, `return_to_concierge`) execute silently. The agent is presented as singular.

### Outcome-based framing
Write instructions that tell the agent what to achieve, not what to avoid.
Rule-heavy CRITICAL/NEVER lists produce worse behaviour.

Anti-pattern:
  CRITICAL: NEVER offer more than one retention deal.
  CRITICAL: NEVER apply pressure if customer declines.
  CRITICAL: NEVER proceed without confirmation.

Better:
  Your goal is to help the customer make an informed choice — not to prevent cancellation.
  If they want to leave, understand why and present one relevant option clearly.
  If they decline, accept it and ask what they'd like to do next.

Rule: more than 3 NEVER/CRITICAL lines → reframe as outcomes instead.
Specific compliance obligations belong in tool descriptions, not standing orders.

### Tool descriptions as compliance contracts
Tool descriptions are read at the moment the LLM selects a tool.
Put compliance rules where the LLM is reading when it is about to act.

  process_policy_change: Use this tool to cancel, transfer, or downgrade a policy.

  ACTION parameter: "cancel" | "transfer" | "downgrade"

  COMPLIANCE REQUIREMENTS:
  - ONE retention offer per reason. If the customer declines, proceed immediately — do not offer again.
  - Cancel uses two-pass confirmation: first call returns summary only and does NOT execute. Second call (confirmed=true) executes.
  - Reason routing is MANDATORY before any action.

What belongs where:

| Tool descriptions | Agent instructions |
|---|---|
| Rules specific to this tool being called | Universal behavioural rules (tone, auth, silence) |
| Confirmation requirements before executing | Localisation rules |
| Obligation limits (one-offer, single-attempt) | Rules that apply regardless of tool |
| Branching/sequencing requirements | Outcome framing |
```

- [ ] **Step 2: Verify frontmatter parses**

Run: `uv run python -c "
import re, pathlib
f = pathlib.Path('skills/explain/resources/aiagent/agent-behavioral-rules.md').read_text()
m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', f, re.DOTALL)
assert m, 'No frontmatter'
fm = dict(l.partition(':')[0::2] for l in m.group(1).splitlines() if ':' in l)
assert fm['topic'].strip() == 'agent-behavioral-rules'
assert fm['group'].strip() == 'aiagent'
print('OK')
"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/explain/resources/aiagent/agent-behavioral-rules.md
git commit -m "feat: add agent-behavioral-rules explain topic"
```

---

### Task 3: Write multi-agent-architecture resource file

**Files:**
- Create: `skills/explain/resources/aiagent/multi-agent-architecture.md`

**Interfaces:**
- Produces: `explain("multi-agent-architecture")` topic (available after Task 6 build step)

- [ ] **Step 1: Create the file**

```markdown
---
topic: multi-agent-architecture
description: Concierge + Specialists pattern, specialist job types, routing, context schema, stub agent
group: aiagent
---

## multi-agent-architecture — Multi-Agent Architecture Patterns

### Concierge + Specialists pattern
Standard architecture for complex AI agent systems.

  Inbound Contact
       │
  Concierge Flow
  - Intent detect
  - Authenticate
  - Gather context
       │
  ┌────┼────┐
  │    │    │
  Spec 1  Spec 2  Spec N

### Concierge role
Front-of-house orchestrator.

Tools: `route_to_specialist_1` ... `route_to_specialist_n`, `escalate_to_human`

Capabilities: intent detection, customer auth/identification, context gathering, intelligent routing, context preservation on handoff.

### Specialist role
Domain-specific expert. Every specialist has `return_to_concierge`:

  {
    "toolId": "return_to_concierge",
    "description": "Return user to concierge agent when query is outside this specialist's scope.",
    "useParameters": false
  }

Use when customer asks about a different domain or specialist cannot handle the request.

### Specialist job patterns

**Information Retrieval** — search catalogs, knowledge bases, databases
Tools: `search_catalog`, `get_item_details`, `check_availability`
Instructions: Gather search criteria. Use search tools. Present findings and offer follow-up.
xApp: product images, specs, comparisons

**Transaction** — execute transactions, process payments, create orders
Tools: info retrieval tools + `create_order`, `process_payment`, `apply_discount`
Instructions: Confirm order details (items, quantities, pricing). Use payment tool. Provide confirmation.
xApp: payment form, order summary, confirmation

**Booking** — schedule appointments, manage calendar
Tools: `check_availability`, `create_booking`, `cancel_booking`, `reschedule_booking`
Instructions: Check availability. Collect details (name, contact, service type). Confirm and send confirmation.
xApp: calendar view, booking confirmation

**Support** — troubleshooting, account management, returns
Tools: `lookup_order`, `process_return`, `update_account`, `escalate_to_human`
Instructions: Gather order/account details. Use tools to resolve. Escalate with summary if unable to resolve.

**Stub** — placeholder for a not-yet-built specialist
Tools: none, or just `return_to_concierge`
Instructions: "You are a specialist agent for [domain]. For this demo phase, provide basic assistance and return to concierge for complex queries."
Benefit: enables knowledge-based responses even without full tool implementation.

### Context schema categories

| Category | Path | LLM-visible | Lifetime |
|---|---|---|---|
| Transient | `input.*` | Yes | Per turn — wiped each turn |
| Session memory | `context.shortTermMemory.*` | Yes | Full session |
| Tool result | `context.toolResponse` | Yes (via Resolve Tool Action) | Overwritten each tool call |
| State / config | `context.<namespace>.*` | No (by default) | Full session |

Initialise at session start (Set Context Node):
  context.toolResponse = ""
  context.shortTermMemory = {}

Context schema example — e-commerce:
  context.ecommerce.config = { defaultBranch: "melbourne", supportedRegions: ["au", "nz"] }
  context.shortTermMemory.customerProfile = { name: "", accountId: "", accountType: "retail" }
  context.shortTermMemory.activeCart = { items: [], total: 0 }
  context.shortTermMemory.lastProductViewed = {}
```

- [ ] **Step 2: Verify frontmatter parses**

Run: `uv run python -c "
import re, pathlib
f = pathlib.Path('skills/explain/resources/aiagent/multi-agent-architecture.md').read_text()
m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', f, re.DOTALL)
assert m, 'No frontmatter'
fm = dict(l.partition(':')[0::2] for l in m.group(1).splitlines() if ':' in l)
assert fm['topic'].strip() == 'multi-agent-architecture'
assert fm['group'].strip() == 'aiagent'
print('OK')
"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/explain/resources/aiagent/multi-agent-architecture.md
git commit -m "feat: add multi-agent-architecture explain topic"
```

---

### Task 4: Write agent-tool-patterns resource file

**Files:**
- Create: `skills/explain/resources/aiagent/agent-tool-patterns.md`

**Interfaces:**
- Produces: `explain("agent-tool-patterns")` topic (available after Task 6 build step)

- [ ] **Step 1: Create the file**

```markdown
---
topic: agent-tool-patterns
description: Tool granularity options (granular/consolidated/action-parameterized) and context.toolResponse channel
group: aiagent
---

## agent-tool-patterns — AI Agent Tool Design Patterns

### Tool granularity options

**Granular** — separate tool per action (real-world)
  { "toolId": "search_catalog_by_part_number", "description": "Search parts catalog by exact part number" }
  { "toolId": "search_catalog_by_vehicle", "description": "Search parts catalog by vehicle make/model/year" }
  { "toolId": "check_stock_by_branch", "description": "Check stock availability at specific branch" }

Pros: precise control, automates complexity
Cons: more tools to build, higher implementation effort

**Consolidated** — fewer tools, LLM synthesises (demo-friendly)
  {
    "toolId": "search_catalog",
    "description": "Search parts catalog and retrieve part details, pricing, and stock. Returns comprehensive data for LLM to synthesize."
  }

Pros: faster to build, fewer integration points
Cons: LLM must synthesise complex responses

**Action-parameterized** — one tool, multiple related actions via `action` parameter
  {
    "toolId": "process_policy_change",
    "description": "Use this tool to cancel, transfer, or downgrade a policy.\n\nACTION: 'cancel' | 'transfer' | 'downgrade'\n\nCOMPLIANCE REQUIREMENTS:\n- ONE retention offer per reason. If declined, proceed immediately.\n- Cancel: two-pass confirmation. First call returns summary, does NOT execute. Second call (confirmed=true) executes.",
    "useParameters": true,
    "parameters": {
      "type": "object",
      "properties": {
        "action": { "type": "string", "enum": ["cancel", "transfer", "downgrade"] },
        "policyNumber": { "type": "string", "description": "Policy number to modify" },
        "confirmed": { "type": "boolean", "description": "Set true on second call to execute after customer confirms" }
      },
      "required": ["action", "policyNumber"],
      "additionalProperties": false
    }
  }

The code node branches on `input.aiAgent.toolArgs.action`.
Auth guard and policy resolution run once at the top, shared across all branches.

Pros: shared auth guards, single tool description to maintain, cleaner LLM decision space
Cons: tool description must carry branching rules clearly or LLM may misuse the `action` parameter
When to use: related actions sharing preconditions — e.g. all policy modification operations

When in doubt, ask:
- "Do you prefer granular tools (more precise, more build effort), consolidated tools (faster build, LLM synthesises), or action-parameterized (related actions with shared guards)?"

### context.toolResponse — tool communication channel
Every tool branch writes its result to `context.toolResponse`.
The Resolve Tool Action Node surfaces this to the LLM as the tool output.

  // Success:
  context.toolResponse = {
    success: true,
    summary: "Policy ABC123 cancellation scheduled for 30/04/2026.",
    data: { policyNumber: "ABC123", effectiveDate: "2026-04-30", refundAmount: 42.50 }
  }

  // Blocked/refused:
  context.toolResponse = {
    success: false,
    blocked: true,
    reason: "Retention offer already made for this reason. Proceeding with cancellation."
  }

Initialise at session start (Set Context Node): `context.toolResponse = ""`
```

- [ ] **Step 2: Verify frontmatter parses**

Run: `uv run python -c "
import re, pathlib
f = pathlib.Path('skills/explain/resources/aiagent/agent-tool-patterns.md').read_text()
m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', f, re.DOTALL)
assert m, 'No frontmatter'
fm = dict(l.partition(':')[0::2] for l in m.group(1).splitlines() if ':' in l)
assert fm['topic'].strip() == 'agent-tool-patterns'
assert fm['group'].strip() == 'aiagent'
print('OK')
"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/explain/resources/aiagent/agent-tool-patterns.md
git commit -m "feat: add agent-tool-patterns explain topic"
```

---

### Task 5: Write agent-handover resource file

**Files:**
- Create: `skills/explain/resources/aiagent/agent-handover.md`

**Interfaces:**
- Produces: `explain("agent-handover")` topic (available after Task 6 build step)

- [ ] **Step 1: Create the file**

```markdown
---
topic: agent-handover
description: Escalation to human pattern and handover context artefact design (two-consumer model)
group: aiagent
---

## agent-handover — Escalation and Handover Patterns

### escalate_to_human tool definition
  {
    "toolId": "escalate_to_human",
    "description": "Escalate to human agent when unable to resolve or customer requests human assistance",
    "useParameters": true,
    "parameters": {
      "type": "object",
      "properties": {
        "reason": { "type": "string", "description": "Reason for escalation" },
        "conversationSummary": { "type": "string", "description": "Summary of conversation for handoff to human agent" }
      },
      "required": ["reason", "conversationSummary"]
    }
  }

### When to escalate
- Customer requests human explicitly
- Required information unavailable to the agent
- Complex or exception scenario not covered by available tools
- Technical issue preventing resolution

### Handover context artefact — two-consumer model
Design the handover package upfront. Two distinct consumers need different data.

**Consumer 1: ACD / routing system** — structured fields for screen pop and routing

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

**Consumer 2: Agent Assist / live agent reading** — natural language summary

  context.shortTermMemory.handoverSummary =
    `Customer ${context.shortTermMemory.customerName} ` +
    `called about ${context.shortTermMemory.intent}. ` +
    (context.shortTermMemory.retentionOffered ?
      "Retention offer was made and declined. " : "") +
    `Policy: ${context.shortTermMemory.policyNumber}. ` +
    `Authenticated: ${context.authVerified ? "Yes" : "No"}.`

Identify both consumers, their required data, and which context paths hold that data
before writing the escalation code node. The handover context is a designed artefact.
```

- [ ] **Step 2: Verify frontmatter parses**

Run: `uv run python -c "
import re, pathlib
f = pathlib.Path('skills/explain/resources/aiagent/agent-handover.md').read_text()
m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', f, re.DOTALL)
assert m, 'No frontmatter'
fm = dict(l.partition(':')[0::2] for l in m.group(1).splitlines() if ':' in l)
assert fm['topic'].strip() == 'agent-handover'
assert fm['group'].strip() == 'aiagent'
print('OK')
"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/explain/resources/aiagent/agent-handover.md
git commit -m "feat: add agent-handover explain topic"
```

---

### Task 6: Build, write tests, verify

**Files:**
- Modify: `cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py` (generated — do not edit directly)
- Modify: `skills/explain/SKILL.md` (generated — do not edit directly)
- Modify: `cognigy-mcp/tests/tools/test_explain.py`

**Interfaces:**
- Consumes: all 5 resource files from Tasks 1–5
- Produces: 5 new callable `explain()` topics; tests covering content correctness

- [ ] **Step 1: Write failing tests for the 5 new topics**

Add to `cognigy-mcp/tests/tools/test_explain.py`:

```python
# ── Issue #58: agent docs migration ─────────────────────────────────────────

def test_agent_persona_authoring_has_field_purposes(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "agent-persona-authoring"})
    text = result[0].text
    assert "description" in text
    assert "instructions" in text
    assert "speakingStyle" in text


def test_agent_behavioral_rules_has_silent_execution(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "agent-behavioral-rules"})
    text = result[0].text
    assert "silently" in text
    assert "escalate_to_human" in text
    assert "outcome" in text.lower()


def test_multi_agent_architecture_has_concierge_pattern(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "multi-agent-architecture"})
    text = result[0].text
    assert "return_to_concierge" in text
    assert "shortTermMemory" in text
    assert "toolResponse" in text


def test_agent_tool_patterns_has_granularity_options(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "agent-tool-patterns"})
    text = result[0].text
    assert "action-parameterized" in text.lower() or "action_parameterized" in text.lower() or "Action-parameterized" in text
    assert "context.toolResponse" in text
    assert "Granular" in text or "granular" in text


def test_agent_handover_has_two_consumer_model(mock_client, state, cache):
    handlers = make_handlers(mock_client, state, cache)
    result = handlers["explain"]({"topic": "agent-handover"})
    text = result[0].text
    assert "escalate_to_human" in text
    assert "handoverContext" in text
    assert "handoverSummary" in text
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `uv run pytest cognigy-mcp/tests/tools/test_explain.py -k "agent_persona or agent_behavioral or multi_agent or agent_tool_patterns or agent_handover" -v`

Expected: 5 failures — `KeyError` or topic not found

- [ ] **Step 3: Run the build**

Run: `uv run scripts/build_explain_topics.py`

Expected output includes:
```
Generated: cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
Generated: skills/explain/SKILL.md
Done. XX topic(s) processed.
```

Verify the 5 new topics appear in the generated SKILL.md:
Run: `grep -E "agent-persona-authoring|agent-behavioral-rules|multi-agent-architecture|agent-tool-patterns|agent-handover" skills/explain/SKILL.md`

Expected: 5 lines, one per topic

- [ ] **Step 4: Run full test suite — confirm all pass**

Run: `uv run pytest cognigy-mcp/tests/ -q`

Expected: all tests pass (35 existing + 5 new = 40 total)

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/cognigy_mcp/tools/_explain_topics_generated.py
git add skills/explain/SKILL.md
git add cognigy-mcp/tests/tools/test_explain.py
git commit -m "feat: build 5 new aiagent explain topics, add tests (issue #58)"
```

---

### Task 7: Update consuming skills

**Files:**
- Modify: `skills/design-agent-persona/SKILL.md`
- Modify: `skills/design-agent-jobs/SKILL.md`
- Modify: `skills/design-agent-contracts/SKILL.md`
- Modify: `skills/design-agent-interfaces/SKILL.md`

**Interfaces:**
- Consumes: 5 new explain topics (callable after Task 6)

- [ ] **Step 1: Update design-agent-persona/SKILL.md**

Replace the Reference Docs section (around line 14–18):

Old:
```
- `docs/agent-prompting-guide.md` — Field purposes, silent execution, outcome-based framing, tool descriptions as contracts, speaking style fields
```

New:
```
- `explain("agent-persona-authoring")` — field purposes, description/instructions structure, speaking style fields
- `explain("agent-behavioral-rules")` — silent execution, outcome-based framing, tool descriptions as contracts
```

Also update line ~47:

Old:
```
Read `docs/agent-prompting-guide.md` before drafting. Apply outcome-based framing — see "Outcome-Based Framing" section.
```

New:
```
Read `explain("agent-persona-authoring")` and `explain("agent-behavioral-rules")` before drafting.
```

- [ ] **Step 2: Update design-agent-jobs/SKILL.md**

Replace both lines in the Reference Docs section (lines 18–19):

Old:
```
- `docs/agent-prompting-guide.md` — Tool descriptions as compliance contracts, outcome-based framing
- `docs/cognigy-agent-patterns.md` — Concierge + Specialists pattern, tool granularity, action-parameterized pattern, toolResponse channel, handover context pattern
```

New:
```
- `explain("agent-behavioral-rules")` — silent execution, outcome-based framing, tool descriptions as contracts
- `explain("multi-agent-architecture")` — Concierge + Specialists, specialist job types, context schema
- `explain("agent-tool-patterns")` — tool granularity options, toolResponse channel
- `explain("agent-handover")` — escalation pattern, handover context artefact
```

Update inline references (search for `docs/agent-prompting-guide.md` and `docs/cognigy-agent-patterns.md` within the file body):

| Old | New |
|---|---|
| `see \`docs/agent-prompting-guide.md\`` | `see \`explain("agent-behavioral-rules")\`` |
| `See \`docs/cognigy-agent-patterns.md\` for trade-offs.` | `See \`explain("agent-tool-patterns")\` for trade-offs.` |
| `Reference \`docs/cognigy-agent-patterns.md\` Handover Context Pattern` | `Reference \`explain("agent-handover")\`` |
| `(Reference \`docs/cognigy-agent-patterns.md\`)` | `(Reference \`explain("agent-tool-patterns")\`)` |
| `(see \`docs/agent-prompting-guide.md\`)` | `(see \`explain("agent-behavioral-rules")\`)` |

- [ ] **Step 3: Update design-agent-contracts/SKILL.md**

Replace the reference line (line 44):

Old:
```
- `docs/cognigy-agent-patterns.md` — toolResponse channel, handover context pattern
```

New:
```
- `explain("agent-tool-patterns")` — toolResponse channel
- `explain("agent-handover")` — handover context pattern
```

- [ ] **Step 4: Update design-agent-interfaces/SKILL.md**

Replace the reference line (line 18):

Old:
```
- `docs/cognigy-agent-patterns.md` — Handover Context Pattern, xApp notes in Specialist Job Patterns
```

New:
```
- `explain("multi-agent-architecture")` — xApp notes in Specialist Job Patterns
- `explain("agent-handover")` — handover context artefact
```

Also update inline reference (line 84):

Old:
```
Reference `docs/cognigy-agent-patterns.md` Handover Context Pattern for the implementation template.
```

New:
```
Reference `explain("agent-handover")` for the implementation template.
```

- [ ] **Step 5: Verify no remaining references to the old docs files**

Run: `grep -r "docs/agent-prompting-guide\|docs/cognigy-agent-patterns" skills/`

Expected: no output

- [ ] **Step 6: Commit**

```bash
git add skills/design-agent-persona/SKILL.md skills/design-agent-jobs/SKILL.md skills/design-agent-contracts/SKILL.md skills/design-agent-interfaces/SKILL.md
git commit -m "feat: update design skills to use explain() topics instead of docs file reads (issue #58)"
```

---

### Task 8: Delete source docs, version bump, final verification

**Files:**
- Delete: `docs/agent-prompting-guide.md`
- Delete: `docs/cognigy-agent-patterns.md`
- Modify: `cognigy-mcp/pyproject.toml` (version `1.4.2` → `1.4.3`)
- Modify: `.claude-plugin/plugin.json` (version `1.4.2` → `1.4.3`)

- [ ] **Step 1: Delete the source docs files**

```bash
git rm docs/agent-prompting-guide.md docs/cognigy-agent-patterns.md
```

- [ ] **Step 2: Bump versions**

In `cognigy-mcp/pyproject.toml`, change:
```
version = "1.4.2"
```
to:
```
version = "1.4.3"
```

In `.claude-plugin/plugin.json`, change:
```
"version": "1.4.2",
```
to:
```
"version": "1.4.3",
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest cognigy-mcp/tests/ -q`

Expected: 40 tests passing, 0 failures

- [ ] **Step 4: Confirm docs files are gone and no dangling references remain**

Run: `grep -r "docs/agent-prompting-guide\|docs/cognigy-agent-patterns" . --include="*.md" --exclude-dir=".git"`

Expected: no output (spec/plan files in docs/superpowers/ referencing them are historical — acceptable)

- [ ] **Step 5: Commit**

```bash
git add cognigy-mcp/pyproject.toml .claude-plugin/plugin.json
git commit -m "chore: bump to 1.4.3 — agent docs migrated to explain topics, source docs removed (issue #58)"
```
