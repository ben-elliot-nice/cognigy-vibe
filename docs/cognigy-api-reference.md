# Cognigy Code Node — API Reference

Reference for writing code in Cognigy Code Nodes. Read this before writing any code node code.

## Execution Model

- **Flow waits** — the flow continues only after the code node finishes executing
- **1 second maximum** execution time (non-configurable)
- **No top-level `await`** — async/await works inside an async function (e.g. `async function main() {}`), but not at the root level of the node
- **No `import` or `require`** — sandboxed scope, no module loading
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
await somePromise            // top-level await not supported — wrap in async function
import _ from 'lodash'       // no imports
require('something')         // no require
```
