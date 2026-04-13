# Write Code Node — Skills Design

**Date:** 2026-04-13
**Status:** Approved

---

## Overview

Two new skills: `select-node` (reusable node resolution) and `write-code-node` (composite code authoring). Together they let Claude find a node in a Cognigy flow, read its code, write new code, or create a new code node at a specified position in the graph.

---

## Architecture

```
write-code-node (composite)
    └── select-node (reusable sub-skill)
            └── cognigy:get chart
            └── cognigy:get node
    └── cognigy:get node          (read-synthesize-write mode)
    └── cognigy:update node       (overwrite / read-synthesize-write)
    └── cognigy:create node       (create mode)
```

`select-node` is a standalone skill. Any future composite skill that needs to target a flow node by label, type, or position should call it rather than re-implementing node discovery.

---

## Skill 1: `select-node`

### Purpose

Resolves a node reference (nodeId, label, or type hint) within a flow into a confirmed nodeId plus relational context — what comes before and after it in the flow graph. This context is required any time a skill needs to insert, update, or inspect a specific node.

### Inputs

| Input | Source |
|---|---|
| `flowId` | Required. From user, env, or calling skill. |
| Node hint | Optional. One of: nodeId, label string, or node type. |

### Resolution logic

1. **nodeId provided** → `get node <nodeId> --flowId` to confirm it exists. Extract relational context from chart.
2. **Label or type provided** → `get chart --flowId` → filter `nodes[]` by label (case-insensitive) or type. If one match, confirm with user. If multiple matches, present the list and ask the user to choose.
3. **Nothing provided** → `get chart --flowId` → present all nodes with their labels and types → user selects.

### Relational context

From the chart `relations[]` array:

- **successor (`next`)**: the relation entry where `relation.node === nodeId` → `relation.next`
- **predecessor (`prev`)**: the relation entry where `relation.next === nodeId` → `relation.node`
- **children**: `relation.children[]` (for branching nodes like If/Then/Else)

Return shape (passed to calling skill or presented to user):

```
nodeId:    <id>
label:     <label>
type:      <type>
prev:      { nodeId, label } | null
next:      { nodeId, label } | null
children:  [{ nodeId, label }]
```

### Output

Present the resolved node to the user for confirmation before returning:
> "Found node: **[label]** (`type`) — preceded by **[prev label]**, followed by **[next label]**. Is this the right node?"

If confirmed, pass the resolved context to the calling skill or present it to the user.

---

## Skill 2: `write-code-node`

### Purpose

Write, overwrite, or synthesise code for a Cognigy code node. Handles three modes of operation and embeds the Cognigy API reference so Claude can write correct code without external lookups.

### Mode detection

| Mode | Trigger |
|---|---|
| **Create** | User asks to create a new code node (no existing node targeted) |
| **Overwrite** | User targets an existing node AND provides the new code directly |
| **Read-synthesize-write** | User targets an existing node AND describes a change without providing the code |

### Steps by mode

#### Create

1. Ask user: what should the node do? Where should it be inserted (before/after which node)?
2. Call `select-node` to resolve the insertion reference node and get its relational context.
3. Write the code based on user's description (see API reference below).
4. Present the code to the user for review before writing.
5. `create node --flowId <id> --type code --label <label> --target <refNodeId> --mode append`
   - `--target` is the node to insert after (from `select-node`)
   - `--mode append` places the new node after target and inherits its `next` pointer
6. Confirm success: `get node <newNodeId> --flowId` and show the written code.

#### Overwrite

1. Call `select-node` to confirm the target node (user may provide nodeId or label).
2. Present the code to the user for review if not already confirmed.
3. `update node <nodeId> --flowId <id> --config '{"code":"<code>"}'`
4. Confirm: `get node <nodeId> --flowId` and show `config.code` from the response.

#### Read-synthesize-write

1. Call `select-node` to confirm the target node.
2. `get node <nodeId> --flowId` → read `config.code`.
3. Present existing code to user.
4. Synthesise new code incorporating user's requested changes.
5. Present the new code to user for review and confirmation before writing.
6. `update node <nodeId> --flowId <id> --config '{"code":"<new code>"}'`
7. Confirm: `get node <nodeId> --flowId` and show `config.code`.

### Code review gate

**Always present generated or modified code to the user for review before writing.** Never write to the API without user confirmation of the code content.

---

## Cognigy Code Node API Reference

Stored as standalone reference docs, not embedded inline in the skill. The skill reads them at runtime via the `Finding the CLI` path pattern. This keeps skill files focused on instructions and makes the reference independently maintainable.

**Reference files (to be created):**
- `docs/cognigy-api-reference.md` — runtime objects (`input`, `context`, `profile`, `analyticsdata`), all `api.*` functions, available libraries (`_`, `moment`, `xmljs`)
- `docs/cognigy-output-formats.md` — channel output structures and code examples for text, quick replies, gallery, buttons, etc.

The skill instructs Claude: *"Before writing any code, read `<plugin-root>/docs/cognigy-api-reference.md` and `<plugin-root>/docs/cognigy-output-formats.md`."*

The content for both files is defined below for use during implementation.

### Execution model

- **Synchronous** — execution completes before the flow continues
- **1 second maximum** execution time (non-configurable)
- **No `async/await`, `import`, or `require`** — sandboxed scope, no module loading
- **No `console.log`** — use `api.log()` instead
- Uncaught errors halt flow execution; timeout errors write to `input.codeNodeError.message`

### Runtime objects

| Object | Description |
|---|---|
| `input` | Incoming message. `input.text` — raw user text. `input.data` — structured payload. `input.intentScore`, `input.slots` — NLU results. `input.sessionId`, `input.userId`, `input.flowName` available. |
| `context` | Session-scoped persistent storage. Read directly as `context.myKey`. Write via `api.setContext()`. |
| `profile` | Contact profile data. |
| `analyticsdata` | Analytics record for this execution. Writable: `analyticsdata.custom1` through `analyticsdata.custom10` (strings, max 1024 chars each). Also writable: `intent`, `intentScore`, `inputText`. |
| `lastConversationEntries` | Array of the last 10 conversation turns in `{ user, bot }` format. |

### Available libraries

| Library | Usage |
|---|---|
| `_` | Lodash. `_.last(arr)`, `_.groupBy(...)` etc. |
| `moment` | Date/time. `moment().format('YYYY-MM-DD')`, `moment.utc()` etc. |
| `xmljs` | XML parsing. `xmljs.xml2json(xml, { compact: true })` |
| `getTextCleaner(locale, options)` | Text normalisation. Returns a TextCleaner instance. |

### Key `api.*` functions

**Output**
- `api.say(text, data?)` — Send a text reply. `data` is the `_cognigy` channel payload.
- `api.output(text, data?)` — Alias for `api.say()`.

**Channel output structure** — nest inside `data` parameter:
```js
// Text with quick replies (default channel)
api.say("Pick one:", {
  _cognigy: { _default: {
    _quickReplies: {
      type: "quick_replies",
      text: "Pick one:",
      quickReplies: [
        { contentType: "postback", payload: "yes", title: "Yes" },
        { contentType: "postback", payload: "no",  title: "No" }
      ]
    }
  }}
})

// Gallery card
api.say("", {
  _cognigy: { _default: {
    _gallery: {
      type: "carousel",
      items: [{ title: "Title", subtitle: "Sub", imageUrl: "https://...", buttons: [] }]
    }
  }}
})
```

**Context**
- `api.setContext(key, value)` — Set a context key.
- `api.getContext(key)` — Read a context key.
- `api.addToContext(key, value, mode?)` — Append (mode: `'simple'` or `'array'`).
- `api.deleteContext(key)` — Remove a key.
- `api.resetContext()` — Clear all context.

**Logging**
- `api.log(level, message)` — Levels: `'debug'`, `'info'`, `'error'`.

**Flow control**
- `api.setNextNode(nodeId)` — Override next node.
- `api.stopExecution()` — Halt flow.

**Input enrichment**
- `api.addToInput(key, value)` — Add data to `input` for downstream nodes.

**Analytics**
- `api.completeGoal(goalName)` — Mark a goal completed.
- `api.trackAnalyticsStep(step)` — Record a custom analytics step.

**Profile**
- `api.updateProfile(key, value)` — Update a contact profile field.
- `api.addContactMemory(memory)` — Add a profile memory entry.

**Handover**
- `api.handover(provider, options?)` — Route to human agent.

**xApps**
- `api.setAppState(state)` — Set xApp session state.

### Code style conventions

- Use `const` / `let`, not `var`
- Guard against missing context/input: `const val = context.myKey ?? 'default'`
- Use `api.log('debug', value)` not `console.log`
- Keep execution under 1 second — no loops over large datasets, no synchronous HTTP calls
- Store complex objects to context as objects (not JSON strings): `api.setContext('data', { key: val })`

---

## Error handling

| Error | Response |
|---|---|
| Node not found by nodeId | Tell user, suggest `list` or `get chart` to find it |
| Multiple nodes match label | Present the list, ask user to choose |
| API 400 on create | Show error detail — likely missing required field (`type`, `target`) |
| API 400 on update | Show error detail — likely malformed `config` object |
| User declines code review | Stop. Do not write. Ask if they want to revise. |

---

## File layout

```
docs/
  cognigy-api-reference.md       ← runtime objects, api.* functions, available libraries
  cognigy-output-formats.md      ← channel output structures with code examples

skills/
  select-node/SKILL.md           ← node resolution, relational context
  write-code-node/SKILL.md       ← composite: create / overwrite / read-synthesize-write
```

All files live in the cognigy-claude-plugin repository.

---

## Open questions (resolved)

| Question | Decision |
|---|---|
| Create new nodes in scope for v1? | Yes |
| `select-node` as standalone reusable skill? | Yes |
| Always confirm code before writing? | Yes — hard gate |
| Cognigy API reference inline or external lookup? | Inline in skill |
| Async/await in code nodes? | No — sandboxed synchronous scope |
