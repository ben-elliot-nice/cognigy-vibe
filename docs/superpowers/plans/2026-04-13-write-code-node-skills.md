# Write Code Node Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create four files — two reference docs and two skills — that let Claude write, overwrite, and synthesise code for Cognigy Code Nodes.

**Architecture:** All deliverables are markdown files in the `cognigy-claude-plugin` repo. Reference docs (`docs/cognigy-api-reference.md`, `docs/cognigy-output-formats.md`) hold Cognigy-specific content that skills read at runtime. `skills/select-node/SKILL.md` handles node resolution and relational context. `skills/write-code-node/SKILL.md` is the composite skill that orchestrates everything.

**Tech Stack:** Markdown, Cognigy CLI (`npx tsx cli/src/index.ts`), Cognigy REST API

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `docs/cognigy-api-reference.md` | Create | Runtime objects, api.* functions, available libraries, execution model |
| `docs/cognigy-output-formats.md` | Create | Channel output structures and code examples |
| `skills/select-node/SKILL.md` | Create | Node resolution by id/label/type + relational context extraction |
| `skills/write-code-node/SKILL.md` | Create | Composite skill: create / overwrite / read-synthesize-write |
| `.claude-plugin/plugin.json` | Modify | Version bump |
| `cli/package.json` | Modify | Version bump |

---

## Task 1: Cognigy API Reference doc

**Files:**
- Create: `docs/cognigy-api-reference.md`

- [ ] **Step 1: Create the file**

Create `/Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/docs/cognigy-api-reference.md` with this exact content:

```markdown
# Cognigy Code Node — API Reference

Reference for writing code in Cognigy Code Nodes. Read this before writing any code node code.

## Execution Model

- **Synchronous** — flow continues after the code node finishes
- **1 second maximum** execution time (non-configurable)
- **No `async/await`, `import`, or `require`** — sandboxed scope, no module loading
- **No `console.log`** — use `api.log()` instead
- Uncaught errors halt flow execution
- Timeout errors write to `input.codeNodeError.message`
- Maximum 100 `api.*` calls per node

## Runtime Objects

### `input`
The incoming message object.

| Property | Description |
|---|---|
| `input.text` | Raw user text |
| `input.data` | Structured payload object |
| `input.intentScore` | NLU intent confidence (0–1) |
| `input.intent` | Matched intent name |
| `input.slots` | Detected NLU slots |
| `input.sessionId` | Session identifier |
| `input.userId` | User identifier |
| `input.flowName` | Name of current flow |
| `input.codeNodeError.message` | Error message if execution timed out |

### `context`
Session-scoped persistent storage. Survives across turns.

```js
// Read
const myValue = context.myKey           // direct access
const myValue = api.getContext('myKey') // via api

// Write
api.setContext('myKey', value)
api.addToContext('myKey', value, 'simple') // set/overwrite
api.addToContext('myKey', value, 'array')  // push to array

// Delete
api.deleteContext('myKey')
api.resetContext()  // clear all
```

### `profile`
Contact profile data (persistent across sessions).

```js
api.updateProfile('fieldName', value)
api.addContactMemory({ label: 'preference', value: 'dark mode' })
```

### `analyticsdata`
Analytics record for the current execution. Write to capture custom analytics.

```js
analyticsdata.custom1 = 'value'   // custom1 through custom10 (max 1024 chars each)
analyticsdata.intent = 'override' // override detected intent in analytics
analyticsdata.inputText = 'text'
```

### `lastConversationEntries`
Array of the last 10 conversation turns.

```js
const lastTurn = lastConversationEntries[0] // { user: '...', bot: '...' }
```

## Available Libraries

### Lodash (`_`)
```js
const last = _.last(arr)
const grouped = _.groupBy(items, 'type')
const unique = _.uniq(arr)
```
Full docs: https://lodash.com/docs/4.17.10

### Moment.js (`moment`)
```js
const now = moment()
const utc = moment.utc()
const formatted = moment().format('YYYY-MM-DD HH:mm')
const diff = moment(dateA).diff(moment(dateB), 'days')
```
Full docs: https://momentjs.com/docs/

### XML-js (`xmljs`)
```js
const json = xmljs.xml2json(xmlString, { compact: true, spaces: 4 })
```

### Text Cleaner (`getTextCleaner`)
```js
const cleaner = getTextCleaner('en-US', {})
const cleaned = cleaner.clean(input.text)
```

## API Functions

### Output
```js
api.say('Hello!', data?)         // send reply to user
api.output('Hello!', data?)      // alias for api.say()
```

For channel-specific output, pass a `_cognigy` payload as `data`. See `docs/cognigy-output-formats.md`.

### Context
```js
api.setContext('key', value)
api.getContext('key')
api.addToContext('key', value, 'simple' | 'array')
api.removeFromContext('key')
api.deleteContext('key')
api.resetContext()
api.getConversationTranscript()  // returns conversation history
```

### Flow Control
```js
api.setNextNode('nodeId')        // override next node in execution path
api.stopExecution()              // halt flow
api.addConditionalEntrypoint()   // trigger flow on conditional event
api.resetNextNodes()             // clear navigation overrides
```

### Logging & Analytics
```js
api.log('debug' | 'info' | 'error', message)
api.completeGoal('goalName')
api.trackAnalyticsStep('stepName')
api.getLLMTokenUsageForSession()
```

### Input Enrichment
```js
api.addToInput('key', value)     // add data to input for downstream nodes
```

### Profile
```js
api.updateProfile('fieldName', value)
api.addContactMemory({ label: 'key', value: 'val' })
api.activateProfile()
api.deactivateProfile()
api.deleteProfile()
api.mergeProfile('targetProfileId')
```

### Handover
```js
api.handover('provider', options?)
```

### xApps
```js
api.setAppState(stateObject)
```

### CognigyScript
```js
api.parseCognigyScript('{{ input.text }}')
api.parseCognigyScriptCondition('{{ input.slots.city.value == "Sydney" }}')
api.parseCognigyScriptText('Hello {{ input.text }}!')
```

## Code Style

```js
// ✅ Good
const val = context.myKey ?? 'default'
api.log('debug', JSON.stringify(someObject))
api.setContext('result', processedValue)

// ❌ Avoid
var x = ...                  // use const/let
console.log(...)             // not available
async function foo() {...}   // no async/await
import _ from 'lodash'       // no imports
require('something')         // no require
```
```

- [ ] **Step 2: Verify the file was created**

```bash
wc -l /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/docs/cognigy-api-reference.md
```

Expected: line count > 100

- [ ] **Step 3: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add docs/cognigy-api-reference.md
git commit -m "docs: add Cognigy code node API reference"
```

---

## Task 2: Cognigy Output Formats doc

**Files:**
- Create: `docs/cognigy-output-formats.md`

- [ ] **Step 1: Create the file**

Create `/Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/docs/cognigy-output-formats.md` with this exact content:

```markdown
# Cognigy Output Formats

Channel output formats for use in Cognigy Code Nodes with `api.say(text, data)` or `api.output(text, data)`.

All formats use the `_cognigy._default` structure which Cognigy automatically adapts for each channel.

## Text Only

```js
api.say('Hello, how can I help?')
```

## Text with Quick Replies

```js
api.say('What would you like to do?', {
  _cognigy: {
    _default: {
      _quickReplies: {
        type: 'quick_replies',
        text: 'What would you like to do?',
        quickReplies: [
          { contentType: 'postback', payload: 'check_balance', title: 'Check Balance' },
          { contentType: 'postback', payload: 'transfer',      title: 'Transfer Money' },
          { contentType: 'postback', payload: 'help',          title: 'Get Help' }
        ]
      }
    }
  }
})
```

Quick reply `contentType` options: `postback`, `phone_number`, `trigger_intent`.

## Text with Buttons

```js
api.say('Choose an option:', {
  _cognigy: {
    _default: {
      _buttons: {
        type: 'buttons',
        text: 'Choose an option:',
        buttons: [
          { type: 'postback',     payload: 'yes',              title: 'Yes' },
          { type: 'postback',     payload: 'no',               title: 'No' },
          { type: 'web_url',      url: 'https://example.com',  title: 'Learn More' },
          { type: 'phone_number', payload: '+61400000000',      title: 'Call Us' }
        ]
      }
    }
  }
})
```

## Gallery (Carousel)

```js
api.say('', {
  _cognigy: {
    _default: {
      _gallery: {
        type: 'carousel',
        items: [
          {
            title: 'Product One',
            subtitle: 'Great product',
            imageUrl: 'https://example.com/image1.jpg',
            buttons: [
              { type: 'postback', payload: 'buy_one', title: 'Buy Now' }
            ]
          },
          {
            title: 'Product Two',
            subtitle: 'Another great product',
            imageUrl: 'https://example.com/image2.jpg',
            buttons: [
              { type: 'web_url', url: 'https://example.com/two', title: 'View' }
            ]
          }
        ]
      }
    }
  }
})
```

## Image

```js
api.say('', {
  _cognigy: {
    _default: {
      _image: {
        type: 'image',
        imageUrl: 'https://example.com/image.jpg'
      }
    }
  }
})
```

## Audio

```js
api.say('', {
  _cognigy: {
    _default: {
      _audio: {
        type: 'audio',
        audioUrl: 'https://example.com/audio.wav'
      }
    }
  }
})
```

## Video

```js
api.say('', {
  _cognigy: {
    _default: {
      _video: {
        type: 'video',
        videoUrl: 'https://www.youtube.com/watch?v=example'
      }
    }
  }
})
```

## List

```js
api.say('', {
  _cognigy: {
    _default: {
      _list: {
        type: 'list',
        items: [
          {
            title: 'Item One',
            subtitle: 'Description',
            imageUrl: 'https://example.com/img.jpg',
            buttons: [{ type: 'postback', payload: 'select_one', title: 'Select' }]
          }
        ],
        button: { type: 'postback', payload: 'view_all', title: 'View All' }
      }
    }
  }
})
```

## Adaptive Card

```js
api.say('', {
  _cognigy: {
    _default: {
      _adaptiveCard: {
        type: 'adaptiveCard',
        adaptiveCard: {
          type: 'AdaptiveCard',
          version: '1.0',
          body: [
            { type: 'TextBlock', text: 'Hello World', weight: 'bolder', size: 'medium' }
          ],
          actions: [
            { type: 'Action.Submit', title: 'OK', data: { action: 'ok' } }
          ]
        }
      }
    }
  }
})
```
```

- [ ] **Step 2: Verify the file was created**

```bash
wc -l /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/docs/cognigy-output-formats.md
```

Expected: line count > 80

- [ ] **Step 3: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add docs/cognigy-output-formats.md
git commit -m "docs: add Cognigy output formats reference"
```

---

## Task 3: select-node skill

**Files:**
- Create: `skills/select-node/SKILL.md`

- [ ] **Step 1: Create the directory and file**

Create `/Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/skills/select-node/SKILL.md` with this exact content:

```markdown
---
name: select-node
description: Resolve a Cognigy flow node by ID, label, or type — returns nodeId plus relational context (prev/next nodes in the graph)
---

# Cognigy Select Node

Resolves a node reference within a Cognigy flow into a confirmed nodeId plus relational context — what comes immediately before and after it in the flow graph.

## When to Use

Use this skill whenever you need to identify a specific node in a flow, whether to read it, update it, or insert before/after it. Any composite skill that targets a flow node should call this skill rather than re-implementing node discovery.

## Finding the CLI

When Claude Code loads this skill, it injects `Base directory for this skill: <path>` into context. That path ends in `skills/select-node`. Go two directories up to get the plugin root. The CLI entry point is `<plugin-root>/cli/src/index.ts`.

## Inputs

- `flowId` — Required. From the user, `.env`, or a calling skill.
- Node hint — Optional. One of: a nodeId (24-char hex string), a label string, or a node type (`code`, `say`, `if`, `question`, `start`, `end`, etc.).

## Steps

### 1. Resolve the node

**If a nodeId was provided (24-char hex, no spaces):**
```bash
npx tsx <plugin-root>/cli/src/index.ts get node <nodeId> --flowId <flowId>
```
- Exit 0 → node confirmed. Proceed to step 2.
- Exit 1 `requires --flowId` → ask user for flowId, then retry.
- Exit 1 other error → tell user the node was not found, stop.

**If a label, type, or nothing was provided:**
```bash
npx tsx <plugin-root>/cli/src/index.ts get chart --flowId <flowId>
```
From the response `nodes[]` array:
- Filter by label (case-insensitive substring match) or type if a hint was given.
- If exactly one match → proceed to step 2 with that nodeId.
- If multiple matches → present the list with label, type, and `_id` for each. Ask: *"Which node did you mean?"* Wait for selection.
- If no matches → tell user, show all available nodes (label + type), ask them to choose.

**Exit 2 on any CLI call:**
Output contains `{ "requiresConfirmation": true, "path": "..." }`. Ask: *"I found a .env at `<path>` — OK to use?"* If confirmed, re-run adding `--env-path <path>`.

### 2. Extract relational context

Get the chart if not already fetched:
```bash
npx tsx <plugin-root>/cli/src/index.ts get chart --flowId <flowId>
```

From the `relations[]` array, for the resolved `nodeId`:
- **successor (`next`)**: find the relation where `relation.node === nodeId` → `relation.next`
- **predecessor (`prev`)**: find any relation where `relation.next === nodeId` → `relation.node`
- **children**: `relation.children[]` on the node's own relation entry (non-empty for If/Then/Else nodes)

Resolve labels and types for prev/next/children by looking them up in the `nodes[]` array.

### 3. Confirm with user

Present the resolved node before returning:

> "Found: **[label]** (`[type]`)
> — preceded by **[prev label]** (`[prev type]`)
> — followed by **[next label]** (`[next type]`)
>
> Is this the right node?"

If confirmed, the resolved context is ready:
```
nodeId:   <id>
label:    <label>
type:     <type>
prev:     { nodeId, label, type } | null
next:     { nodeId, label, type } | null
children: [{ nodeId, label, type }]
```

If declined → return to step 1 and ask the user to clarify.

## Notes

- Do not proceed past step 3 without explicit user confirmation.
- If `flowId` is not provided and not in `.env`, ask the user before running anything.
- The chart endpoint returns all nodes with types and labels. Prefer it over `list nodes` which returns only metadata.
- For nodes with no predecessor (e.g. Start), `prev` is `null`. For nodes with no successor (e.g. End, terminal code nodes), `next` is `null`.
```

- [ ] **Step 2: Verify the file was created**

```bash
cat /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/skills/select-node/SKILL.md | head -5
```

Expected: first line is `---`

- [ ] **Step 3: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add skills/select-node/SKILL.md
git commit -m "feat: add select-node skill for flow node resolution"
```

---

## Task 4: write-code-node skill

**Files:**
- Create: `skills/write-code-node/SKILL.md`

- [ ] **Step 1: Create the directory and file**

Create `/Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/skills/write-code-node/SKILL.md` with this exact content:

```markdown
---
name: write-code-node
description: Write, overwrite, or synthesise code for a Cognigy Code Node — handles create, overwrite, and read-synthesize-write modes
---

# Cognigy Write Code Node

Write code for a Cognigy Code Node. Supports three modes: creating a new code node at a specified position, overwriting existing code, or reading existing code and synthesising changes.

## When to Use

Use this skill when the user wants to:
- Write code for a new code node in a flow
- Replace the code in an existing code node
- Update or improve existing code node code based on a description

## Finding the CLI and Reference Docs

When Claude Code loads this skill, it injects `Base directory for this skill: <path>` into context. That path ends in `skills/write-code-node`. Go two directories up to get the plugin root.

**Before writing any code**, read these reference files:
- `<plugin-root>/docs/cognigy-api-reference.md` — runtime objects (`input`, `context`, `profile`, `analyticsdata`), `api.*` functions, available libraries
- `<plugin-root>/docs/cognigy-output-formats.md` — channel output structures and code examples

The CLI entry point is `<plugin-root>/cli/src/index.ts`.

## Mode Detection

Determine mode from the user's request before starting:

| Mode | Signal |
|---|---|
| **Create** | User wants a new code node ("add a code node", "create a code node that...") |
| **Overwrite** | User targets an existing node AND provides the new code directly |
| **Read-synthesize-write** | User targets an existing node AND describes what to change without providing the full code |

---

## Create Mode

1. If not already provided, ask: what should the code do, what label should the node have, and after which existing node should it be inserted?

2. Invoke the `cognigy:select-node` skill to resolve the insertion reference node and get its relational context (`nodeId` of the node to insert after).

3. Read `<plugin-root>/docs/cognigy-api-reference.md` and `<plugin-root>/docs/cognigy-output-formats.md`.

4. Write the code.

5. **Code review gate — non-negotiable:** Present the code to the user before writing:
   > "Here's the code I'll write to the new node — please review before I create it:"
   > ````js
   > [code here]
   > ````
   > "OK to proceed?"

   Do NOT call the CLI until the user confirms.

6. Create the node:
```bash
npx tsx <plugin-root>/cli/src/index.ts create node \
  --flowId <flowId> \
  --type code \
  --label "<label>" \
  --target <refNodeId> \
  --mode append
```
`--target` is the `nodeId` from `select-node`. `--mode append` inserts the new node after target and automatically wires the graph relations.

7. From the response, capture `_id` (the new nodeId). Confirm by fetching and showing `config.code`:
```bash
npx tsx <plugin-root>/cli/src/index.ts get node <newNodeId> --flowId <flowId>
```

---

## Overwrite Mode

1. Invoke `cognigy:select-node` to confirm the target node (user may provide nodeId or label).

2. Read `<plugin-root>/docs/cognigy-api-reference.md` and `<plugin-root>/docs/cognigy-output-formats.md`.

3. **Code review gate — non-negotiable:** Present the code before writing:
   > "Here's the code I'll write — please review:"
   > ````js
   > [code here]
   > ````
   > "OK to proceed?"

   Do NOT call the CLI until the user confirms.

4. Write the code:
```bash
npx tsx <plugin-root>/cli/src/index.ts update node <nodeId> \
  --flowId <flowId> \
  --config '{"code":"<escaped code>"}'
```
Escape newlines as `\n` and double quotes as `\"` within the JSON string value.

5. Confirm by fetching and showing `config.code`:
```bash
npx tsx <plugin-root>/cli/src/index.ts get node <nodeId> --flowId <flowId>
```

---

## Read-Synthesize-Write Mode

1. Invoke `cognigy:select-node` to confirm the target node.

2. Read the existing code:
```bash
npx tsx <plugin-root>/cli/src/index.ts get node <nodeId> --flowId <flowId>
```
Extract `config.code` from the response and show it to the user.

3. Read `<plugin-root>/docs/cognigy-api-reference.md` and `<plugin-root>/docs/cognigy-output-formats.md`.

4. Synthesise the new code incorporating the user's requested changes.

5. **Code review gate — non-negotiable:** Present the updated code before writing:
   > "Here's the updated code — please review before I save it:"
   > ````js
   > [new code here]
   > ````
   > "OK to proceed?"

   Do NOT call the CLI until the user confirms.

6. Write the updated code:
```bash
npx tsx <plugin-root>/cli/src/index.ts update node <nodeId> \
  --flowId <flowId> \
  --config '{"code":"<escaped code>"}'
```

7. Confirm by fetching and showing `config.code`:
```bash
npx tsx <plugin-root>/cli/src/index.ts get node <nodeId> --flowId <flowId>
```

---

## Exit Code Handling

For all CLI calls:
- **Exit 2** — `.env` found via git root walk. Output contains `{ "requiresConfirmation": true, "path": "..." }`. Ask: *"I found a .env at `<path>` — OK to use?"* If confirmed, re-run adding `--env-path <path>`. If declined, stop.
- **Exit 1** — Show the `error` field. Common cases:
  - `No .env file found` → invoke `cognigy:init` to set up the connection, then retry
  - `requires --flowId` → ask user for the flowId, then retry
  - `API error 400` on create — likely missing `--type` or `--target`; show error detail
  - `API error 400` on update — likely malformed `config` JSON; check escaping
  - `API error 401` → token invalid or expired

## Notes

- **The code review gate is non-negotiable.** Never write to the API without user confirmation of the code content.
- `update node` returns nothing (204 No Content) — always confirm with a follow-up `get node`.
- `flowId` may come from the user, from `COGNIGY_FLOW_ID` in `.env`, or from a prior step.
- When escaping code for the `--config` JSON value: replace `\` with `\\`, `"` with `\"`, newlines with `\n`, tabs with `\t`.
- Do not use `async/await`, `import`, or `require` in generated code — code nodes run synchronously in a sandboxed scope.
```

- [ ] **Step 2: Verify the file was created**

```bash
cat /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/skills/write-code-node/SKILL.md | head -5
```

Expected: first line is `---`

- [ ] **Step 3: Commit**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add skills/write-code-node/SKILL.md
git commit -m "feat: add write-code-node composite skill"
```

---

## Task 5: Version bump and push

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `cli/package.json`

- [ ] **Step 1: Read current versions**

```bash
cat /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/.claude-plugin/plugin.json
cat /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin/cli/package.json
```

Note the current versions.

- [ ] **Step 2: Bump both to the next patch version**

In `.claude-plugin/plugin.json`, increment `"version"` by one patch (e.g. `"1.1.0"` → `"1.1.1"`).
In `cli/package.json`, set `"version"` to the same value.

- [ ] **Step 3: Commit and push**

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/cognigy-claude-plugin
git add .claude-plugin/plugin.json cli/package.json
git commit -m "chore: bump version to <new-version>"
git push
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `docs/cognigy-api-reference.md` with runtime objects, api.* functions, libraries | Task 1 |
| `docs/cognigy-output-formats.md` with channel output examples | Task 2 |
| `select-node` skill with nodeId/label/type resolution | Task 3 |
| `select-node` returns relational context (prev/next/children) | Task 3 |
| `select-node` confirms with user before returning | Task 3 |
| `write-code-node` detects create/overwrite/read-synthesize-write mode | Task 4 |
| Create mode: uses `select-node`, `--target --mode append` | Task 4 |
| Overwrite mode: uses `select-node`, updates `config.code` | Task 4 |
| Read-synthesize-write: reads existing code, synthesises, confirms, writes | Task 4 |
| Code review gate on all modes | Task 4 |
| Skills read reference docs before writing code | Task 4 |
| Error handling for all exit codes and API errors | Task 4 |
| Version bump | Task 5 |

**Placeholder scan:** No TBDs or TODOs. All file contents are complete.

**Type consistency:** No code — markdown only. No type mismatches possible.
