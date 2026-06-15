---
topic: code-node-patterns
description: api.* functions, as const bug, httpRequest .result, no fetch/import
---

## code-node-patterns — Writing Cognigy Code Nodes

### Available API methods
  api.say("text")                    // output text to channel
  api.output({text:"...", data:{}})  // structured output with data payload
  api.log("message")                 // debug log (NOT console.log)
  api.setContext({key: value})       // set context variables
  api.resolve()                      // signal completion (required for async nodes)
  api.reject("error message")        // signal failure
  api.inject({...})                  // inject turn result (Function Execution pattern)

### NOT available
  fetch()          // NO — use HTTP Request node for outbound HTTP
  require()        // NO — no module system
  import           // NO — not ES modules
  console.log()    // NO — use api.log() instead

### TypeScript syntax: no "as const"
  // WRONG — Cognigy code nodes don't support TypeScript generics/assertions:
  const STATUS = {PENDING: 'pending'} as const;
  // RIGHT:
  const STATUS = {PENDING: 'pending'};

### httpRequest node response wrapping
The httpRequest node wraps its response body under a .result key.
  // Code node reading httpRequest output:
  const body = context.httpResponse.result;   // NOT context.httpResponse directly
  // httpResponse shape: {result: {...actualBody}, status: 200, headers: {...}}

### Bare return bug
  return;  // at top level → transpile error "Illegal return statement"
  // Fix: wrap in function, or just omit the return

### Deep copy before multi-path assignment
  // WRONG — serializer collapses repeated object references:
  context.pathA.data = myObject;
  context.pathB.data = myObject;  // corruption
  // RIGHT:
  context.pathB.data = JSON.parse(JSON.stringify(myObject));

### Async pattern (when using await)
  async function main() {
    const result = await someAsyncOperation();
    context.result = result;
    api.resolve();
  }
  main();

### Available libraries
  _          // lodash
  moment     // date/time
  xmljs      // XML parsing
  textcleaner // text utilities
