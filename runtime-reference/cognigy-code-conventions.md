# Cognigy Code Node — Conventions

> **Deprecated:** This file is superseded by `explain("code-node-patterns")` in cognigy-vibe-mcp.
> Read this for legacy reference only. The MCP explain tool is the authoritative source.

Structural conventions for writing maintainable Cognigy Code Nodes. Follow these patterns unless there is a specific reason not to.

## Structure

Every code node follows this layout:

```
async function main() { ... }

async function getVar(path, required) { ... }
async function setVar(path, value) { ... }
async function mergeVar(path, value) { ... }
function log(level, context, message) { ... }
function allSettled(promises) { ... }

main()
```

- `main()` is defined first so the intent of the node is immediately readable
- Utility functions are defined between `main` and the `main()` call
- `main()` is called at the end — the node is synchronous at the root level, but `main` itself is async

---

## main()

Contains all business logic. Pattern inside main:

```js
async function main() {
  // 1. Get all inputs in parallel — surfaces ALL missing vars at once
  const [userIdResult, prefsResult] = await allSettled([
    getVar('input.data.userId', true),
    getVar('context.userPrefs', false)
  ])

  const errors = [userIdResult, prefsResult]
    .filter(r => r.status === 'rejected')
    .map(r => r.reason.message)

  if (errors.length > 0) {
    errors.forEach(e => log('error', 'main', e))
    return
  }

  const userId = userIdResult.value
  const prefs  = prefsResult.value

  // 2. Business logic — all required vars guaranteed present here

  // 3. Write results non-destructively
  await mergeVar('context.userProfile', { lastSeen: Date.now() })
  // or replace entirely:
  await setVar('context.sessionFlag', true)
}
```

---

## Utility Functions

Copy these into every code node that uses them. Do not modify them — they are convention, not business logic.

### getVar(path, required)

Reads a value by dot-notation path from `input` or `context`. Rejects the Promise if the value is missing and `required` is true; resolves `null` if missing and `required` is false.

Call with optional chaining on any intermediate path segments that may not exist.

```js
// Usage
const userId  = await getVar('input.data.userId', true)   // throws if missing
const prefs   = await getVar('context.userPrefs', false)  // null if missing

async function getVar(path, required) {
  const parts = path.split('.')
  let val = { input, context }[parts.shift()]
  for (const part of parts) {
    if (val == null) { val = undefined; break }
    val = val[part]
  }
  if (val == null) {
    if (required) return Promise.reject(new Error(`Required: '${path}' is missing or null`))
    return Promise.resolve(null)
  }
  return Promise.resolve(val)
}
```

### setVar(path, value)

Writes a value by dot-notation path to `input` or `context`, creating intermediate objects as needed. Replaces the target value entirely.

Use when you want a full reset of the target key.

```js
// Usage
await setVar('context.sessionFlag', true)
await setVar('input.data.processedAt', Date.now())

async function setVar(path, value) {
  const parts = path.split('.')
  const root = parts.shift()
  const key = parts.pop()
  let obj = { input, context }[root]
  for (const part of parts) {
    if (obj[part] == null) obj[part] = {}
    obj = obj[part]
  }
  obj[key] = value
}
```

### mergeVar(path, value)

Deep-merges a value into the existing object at the given path. Creates intermediate objects if they don't exist. Arrays are replaced, not concatenated.

Use when you want to update some keys without destroying sibling keys.

```js
// Usage — only updates lastSeen, leaves other userProfile keys intact
await mergeVar('context.userProfile', { lastSeen: Date.now() })

async function mergeVar(path, value) {
  const parts = path.split('.')
  const root = parts.shift()
  const key = parts.pop()
  let obj = { input, context }[root]
  for (const part of parts) {
    if (obj[part] == null) obj[part] = {}
    obj = obj[part]
  }
  obj[key] = deepMerge(obj[key], value)

  function deepMerge(target, source) {
    if (source === null || typeof source !== 'object' || Array.isArray(source)) return source
    const result = Object.assign({}, target)
    for (const k of Object.keys(source)) {
      const tgt = target != null ? target[k] : undefined
      result[k] = (typeof source[k] === 'object' && source[k] !== null && !Array.isArray(source[k]) && typeof tgt === 'object' && !Array.isArray(tgt))
        ? deepMerge(tgt, source[k])
        : source[k]
    }
    return result
  }
}
```

### allSettled(promises)

`Promise.allSettled` polyfill — Cognigy's TypeScript target is too old to include it natively. The `as const` on status strings is required so TypeScript can narrow the union type and allow `r.reason` / `r.value` access after filtering.

```js
// Usage
const [userIdResult, prefsResult] = await allSettled([
  getVar('input.data.userId', true),
  getVar('context.userPrefs', false)
])

function allSettled(promises) {
  return Promise.all(promises.map(p =>
    p.then(value  => ({ status: 'fulfilled' as const, value }))
     .catch(reason => ({ status: 'rejected'  as const, reason }))
  ))
}
```

---

### log(level, context, message)

Unified logging utility. Prefixes the message with `[context]` when context is provided. Calls the appropriate Cognigy API methods for each level.

Supported levels: `'info'`, `'debug'`, `'error'`

Objects passed as `message` are automatically JSON-stringified.

```js
// Usage
log('info',  'main',   'Processing started')        // [main] Processing started
log('error', 'getVar', e.message)                   // [getVar] Required: 'input.data.userId' is missing
log('debug', 'main',   { userId, prefs })           // [main] {"userId":"abc","prefs":null}
log('info',  null,     'no context prefix')         // no context prefix

function log(level, context, message) {
  const msg = (context ? `[${context}] ` : '') + (typeof message === 'object' ? JSON.stringify(message) : String(message))

  if (level === 'error') {
    api.log('error', msg)
    api.logDebugError(msg)
  } else if (level === 'debug') {
    api.log('debug', msg)
    api.logDebugMessage(msg)
  } else {
    api.log('info', msg)
  }
}
```

---

## When to use setVar vs mergeVar

| Scenario | Use |
|---|---|
| Writing a primitive (string, number, boolean) | Either — behaviour is identical |
| Writing an object and you want to keep existing sibling keys | `mergeVar` |
| Writing an object and you want a clean slate | `setVar` |
| Writing an array | `setVar` (mergeVar replaces arrays anyway, but intent is clearer) |
