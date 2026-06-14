# cognigy_mcp/tools/explain.py
from __future__ import annotations
import json
from mcp.types import Tool, TextContent
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState

TOPICS = [
    "node-positioning", "node-wiring", "agent-tool-branch", "node-config-update",
    "flow-chart-reading", "tool-conditions", "two-pass-confirm", "turn-structure",
    "xapp-delivery", "xapp-event-handling", "cognigyScript", "code-node-patterns", "voice-gateway",
    "outbound-trigger", "knowledge-store", "endpoint-config", "function-execution",
    "session-injection", "extension-map", "node-types", "mcp-comparison", "tool-selection",
]

_TOPIC_INDEX = """
Topics and what they cover:

  node-positioning     append vs appendChild modes, child branch population, insertAfter 500 bug on AU1
  node-wiring          chart structure, relations array, sequential vs child chains
  agent-tool-branch    aiAgentJobTool + code + toolAnswer assembly, tool args access
  node-config-update   full-replace semantics, merge_config pattern, silent field deletion
  flow-chart-reading   reading chart output, node type strings, extension field
  tool-conditions      CognigyScript condition field, hiding tools from LLM
  two-pass-confirm     inter-turn flag management, STOP gate wording
  turn-structure       Once/OnFirstTime/Afterwards, input.execution, context reset prevention, child branch API patterns
  xapp-delivery        session init, postMessage bridge, SDK.submit, dual xApp moments
  xapp-event-handling  non-blocking xApp pattern: flow structure, ephemeral data capture, SDK.submit vs webhook inject variants
  cognigyScript        interpolation contexts, what works where
  code-node-patterns   api.* functions, as const bug, httpRequest .result, no fetch/import
  voice-gateway        VG endpoint routing, Set Session Config, SIP headers, DTMF
  outbound-trigger     6-step CXone trigger, Accept-Encoding: identity requirement
  knowledge-store      chunking, connector run, source management
  endpoint-config      referenceId vs _id gotcha, urlToken caching
  function-execution   async pattern, inject-back via sessions API
  session-injection    context/state inject for in-session testing
  extension-map        complete type → extension lookup table
  node-types           quick reference for all node type strings
  mcp-comparison       when to use cognigy-vibe vs NiCE official MCP
  tool-selection       when to use push_code_node vs cognigy_create vs cognigy_update

Call explain() for orientation and topic descriptions.
Call explain("topic") for full reference on that topic.
"""

_CONTENT: dict[str, str] = {
    "node-positioning": """
## node-positioning — Inserting and Moving Nodes

### Mode: append (SAFE on AU1)
Only reliable insertion mode. Target = node you want to insert AFTER.
  body: {"type": "say", "label": "My Node", "mode": "append", "target": "<previousNodeId>"}

### Mode: appendChild (for tool branch nodes)
Use when adding aiAgentJobTool as a child of an aiAgentJob node.
  body: {"type": "aiAgentJobTool", "mode": "appendChild", "target": "<aiAgentJobNodeId>"}

### BROKEN on AU1 (return 500 "Error while reading ChartData")
  - insertAfter
  - insertBefore

### Move an existing node
Use cognigy_invoke with operation="move":
  body: {"mode": "append", "target": "<nodeId to insert after>"}

### Common mistakes
- Using chartReference as target → 404 "Failed to find chart node"
- New flows have Start and End nodes; list them first to get Start ID as initial append target
- Child nodes (tool branches) only exist in childIds[], NOT in next chain — append returns 404 on them

### Child branch population (Once node example)
Once nodes auto-create two child branch nodes: OnFirstTime and Afterwards.
Each branch appears as a separate node in the chart with its own _id.

To add a node into a branch:
1. Find the branch node in the chart (e.g. OnFirstTime child of the Once node)
2. Use mode: "appendChild" with target set to the BRANCH NODE's _id

Common pitfall: targeting the parent Once node's _id instead of the branch node.
The branch node's _id is what you need — it's the container for child nodes.

Example: chart shows Once node "a1b2" with childIds ["c3d4", "e5f6"]
  - "c3d4" is the OnFirstTime branch node
  - "e5f6" is the Afterwards branch node
  - To add a Code node to OnFirstTime, target "c3d4", NOT "a1b2"
""",

    "node-wiring": """
## node-wiring — Understanding the Flow Chart Structure

### Chart shape
GET /v2.0/flows/{flowId}/chart returns:
  {
    "nodes": [...],       // all node objects (metadata only — no config)
    "relations": [...]    // positional relationships
  }

### Relations entry shape
  {
    "node": "abc",         // the node ID this relation describes
    "_id": "rel-id",       // the relation's own MongoDB ID (different from node _id)
    "next": "def",         // next node in sequential chain (null if last)
    "children": ["..."]    // child node IDs (e.g. tool branches, if-node branches)
  }

### Sequential chain vs children
- Sequential: follow "next" links from start node
- Children: follow "children" array from parent (aiAgentJob, if node branches)
- Tool branches are children of aiAgentJob, NOT in sequential chain

### IMPORTANT: Chart endpoint returns metadata only
GET /v2.0/flows/{flowId}/chart does NOT include node config fields (code, conditions, toolId).
To read a node's config: cognigy_get(resource_type="node", resource_id=nodeId, flow_id=flowId)

### Non-core node types require extension field
  {"type": "initAppSession", "extension": "@cognigy/basic-nodes"}
  {"type": "setHTMLAppState", "extension": "@cognigy/basic-nodes"}
  {"type": "aiAgentJob", "extension": "@cognigy/basic-nodes"}
  {"type": "aiAgentJobTool", "extension": "@cognigy/basic-nodes"}
  {"type": "aiAgentToolAnswer", "extension": "@cognigy/basic-nodes"}
""",

    "agent-tool-branch": """
## agent-tool-branch — Building the AI Agent Tool Chain

### Three-node pattern
Every AI Agent tool is a branch of three nodes under an aiAgentJob:
  aiAgentJob
  └── aiAgentJobTool       (the tool node — appendChild of aiAgentJob)
       └── Code Node       (implementation — append after tool node)
            └── aiAgentToolAnswer  (surfaces result — append after code node)

### Step 1: Create aiAgentJobTool
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "aiAgentJobTool",
    "extension": "@cognigy/basic-nodes",
    "label": "my_tool",
    "mode": "appendChild",
    "target": "<aiAgentJobNodeId>",
    "config": {}
  })

### Step 2: Update aiAgentJobTool config
  cognigy_update(resource_type="node", resource_id=<toolNodeId>, merge_config=True, body={
    "config": {
      "toolId": "<toolId from Cognigy tools library>",
      "description": "What this tool does",
      "useParameters": True,
      "parameters": [{"name": "amount", "type": "number", "description": "Amount to charge"}]
    }
  })

### Step 3: Append Code node
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "code", "label": "[TOOL] my_tool",
    "mode": "append", "target": "<toolNodeId>",
    "config": {"code": "context.toolResponse = {summary: 'Done'}; api.resolve();"}
  })

### Step 4: Append aiAgentToolAnswer
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "aiAgentToolAnswer", "extension": "@cognigy/basic-nodes",
    "mode": "append", "target": "<codeNodeId>",
    "config": {}
  })

### Reading tool arguments in the code node
Parameters the LLM collected are available as:
  const amount = input.aiAgent.toolArgs.amount;
  const reason = input.aiAgent.toolArgs.reason;
These are NOT in input.data — they come via input.aiAgent.toolArgs.<paramName>.

### Tool conditions (hide tool from LLM when false)
  cognigy_update(..., body={"condition": "!context.authVerified"})
  Note: condition is a TOP-LEVEL field, NOT inside config.

### context.toolResponse
  Code node writes: context.toolResponse = {summary: "...", data: {...}}
  aiAgentToolAnswer reads context.toolResponse and surfaces it to the LLM.
  toolResponse.summary = what the LLM reads back to the customer naturally.
""",

    "node-config-update": """
## node-config-update — Safe Config Updates

### CRITICAL: Cognigy PATCH is FULL REPLACE on config
If you PATCH {"config": {"code": "..."}} on a code node that also has
{"config": {"code": "...", "preview": "..."}} — the preview field is SILENTLY DELETED.

### Always use merge_config=True for partial updates
  cognigy_update(resource_type="node", resource_id=..., merge_config=True, body={
    "config": {"code": "new code here"}
  })
This will GET current config, deep-merge your changes, then PATCH.

### Safe pattern for any update
  1. cognigy_get to see current state
  2. cognigy_update with merge_config=True
  3. cognigy_get again to confirm

### Known fields silently deleted if not included
- code nodes: preview, triggers
- aiAgentJobTool: conditions array when updating toolId only
- Any node: position.x/y when updating config without including position

### GoTo node: use referenceId (UUID), NOT _id (hex)
GoTo nodes reference their target flow by UUID referenceId, not the hex _id.
  // flow._id = "64a3f1c2b9e7d05a8c4f2e91"    ← hex, DO NOT use
  // flow.referenceId = "550e8400-e29b-..."     ← UUID, USE THIS
Get referenceId from cognigy_get(resource_type="flows", resource_id=...) → result.referenceId

### Chart endpoint returns metadata only
GET /v2.0/flows/{id}/chart returns node structure and positions only.
Node config fields are NOT included — use cognigy_get(resource_type="node", ...) to read config.
""",

    "flow-chart-reading": """
## flow-chart-reading — Reading get_flow_chart Output

### Verified node type strings (exact, case-sensitive)
Core types (no extension needed):
  say, question, code, setContext, goTo, once, lookup, log, stopBot, httpRequest
  if (note: NOT "ifThenElse")

AI Agent types (extension: "@cognigy/basic-nodes"):
  aiAgentJob, aiAgentJobTool, aiAgentToolAnswer

xApp/Voice types (extension: "@cognigy/basic-nodes"):
  initAppSession  (NOT "xAppInitSession")
  setHTMLAppState (NOT "setHTMLxAppState")

### Reading node objects
  {
    "_id": "abc123",       // use this as node_id in tool calls
    "type": "say",
    "label": "Greeting",  // human-readable
    "config": {...},       // type-specific configuration (ONLY in cognigy_get, not chart)
    "position": {"x": 0, "y": 100}
  }

### if nodes (NOT "ifThenElse")
Can be created via cognigy_create. Type string is "if".
  cognigy_create(resource_type="node", flow_id=..., body={
    "type": "if",
    "mode": "append",
    "target": "<previousNodeId>",
    "config": {
      "condition": {
        "type": "rule",
        "rule": {
          "left": "context.someVar",
          "operand": "neq",    // equals, notEquals (neq), contains, greaterThan, lessThan
          "right": "someValue"
        }
      }
    }
  })
Creating an if node auto-creates two branch container nodes: Then (childIds[0]) and Else (childIds[1]).
To add nodes inside a branch: use mode="appendChild", target="<branch-container-_id>".
Branches are in childIds[]: index 0 = Then (true), index 1 = Else (false).

### Reading the hierarchy string
get_flow_chart returns "hierarchy": a tree string like:
  [start] Start (abc)
  [say] Greeting (def)
  [aiAgentJob] Concierge (ghi)
    [aiAgentJobTool] authenticate_caller (jkl)
      [code] [TOOL] authenticate_caller (mno)
      [aiAgentToolAnswer] Tool Answer (pqr)
""",

    "tool-conditions": """
## tool-conditions — Controlling Tool Visibility

### What conditions do
The condition field on an aiAgentJobTool is a CognigyScript expression.
When falsy → tool is hidden from the LLM. LLM cannot call what it cannot see.
This is more reliable than code guards (LLM can ignore code; can't call hidden tool).

### Setting a condition
  cognigy_update(resource_type="node", resource_id=<toolNodeId>,
    merge_config=False,   # condition is top-level, not in config
    body={"condition": "!context.authVerified"}
  )

### Condition examples
  "!context.authVerified"                    // show authenticate_caller only before auth
  "context.contracts.booking.stage === 0"    // show only at correct workflow stage
  "context.shortTermMemory.policyLoaded"     // show after policy is loaded

### Removing a condition (always show)
  body={"condition": ""}  or  body={"condition": null}

### CognigyScript in conditions
- Use context.* variables (set by code nodes or Set Context nodes)
- Use input.data.* for per-turn data
- Operators: ===, !==, &&, ||, !, >, <
- No function calls, no complex expressions

### Context namespace visibility
- context.shortTermMemory.*  → VISIBLE to LLM (included in agent context)
- context.contracts.*        → NOT visible to LLM (use for enforcement state)
- context.ami.*              → NOT visible to LLM (use for config/flags)
""",

    "two-pass-confirm": """
## two-pass-confirm — Staged Confirmation Pattern

### Problem
LLM will collapse propose+execute into a single tool call without explicit instructions.

### Pattern
Pass 1: Tool called without confirmation flag → returns summary, does NOT execute.
Pass 2: Tool called with confirmation flag → executes.

### Tracking state between turns
  // Code node (Pass 1):
  context.contracts.myTool = {pendingConfirm: true, ...details};
  context.toolResponse = {summary: "I'll do X. Confirm?"};

  // Code node (Pass 2):
  if (!context.contracts.myTool?.pendingConfirm) {
    context.toolResponse = {error: "No pending confirmation"};
    return;
  }
  // execute...
  context.contracts.myTool = null;  // clear
  context.toolResponse = {summary: "Done."};

### toolResponse.summary vs pre-call instructions
- toolResponse.summary: what LLM reads BACK to customer after tool completes
- Tool description: rules LLM reads BEFORE deciding to call the tool
- Do NOT put "Say this to the customer" in tool description — it runs before the call

### STOP gate wording that works
In AI job instructions:
  "Your ONLY spoken output before calling confirm_action is: [exact words].
   Stop there. DO NOT add anything else. Call the tool."

### Inter-turn flag via context.contracts.*
Use context.contracts namespace — LLM cannot see this namespace (short-term memory blind spot).
context.shortTermMemory IS visible to LLM. context.contracts.* is NOT.
""",

    "turn-structure": """
## turn-structure — Canonical Cognigy Turn Architecture

### Standard flow structure
  Start
  └── Once
      ├── OnFirstTime (runs once at session start)
      │   ├── Set Context (config, auth flags, etc.)
      │   ├── Code: Build Greeting (builds context.greetingText)
      │   └── Say: Proactive Greeting (outputs context.greetingText)
      └── Afterwards (runs every turn after the first)
          └── AI Agent Job (Concierge)
  End

### Why this matters
Set Context in the main chain runs every turn — resets context on every message.
Set Context in OnFirstTime runs once — persists for the session.
AI Agent Job in Afterwards — never runs on the very first turn (greeting runs instead).

### First-turn signal
input.execution === 1 is the canonical way to detect the first turn in a code node.
Do NOT use turn-count variables or session flags for this.
  if (input.execution === 1) {
    // first turn setup
  }

### Proactive greeting pattern
  // Code node:
  const name = context.shortTermMemory?.customerName || 'there';
  context.greetingText = `Hello ${name}, I'm Vera. How can I help you today?`;
  // Then: Say node outputs {{context.greetingText}}
This guarantees on-brand, correctly personalised greeting with zero LLM latency.

### Flow close pattern
  Once → next → End
The Once node's "next" pointer leads to End for clean termination.
Do NOT put any nodes after End or the flow will loop.

### Context reset prevention
If context resets every turn, check:
  1. Set Context is in main chain (move to OnFirstTime)
  2. Flow is being reset by a goTo with reset=true
  3. Multiple flows calling into each other with shared context

### Programmatic child branch population
Once nodes auto-create OnFirstTime and Afterwards branches — do NOT attempt to create
them manually (returns HTTP 400 "operation conflicts with constraints").

To add a node to a child branch via the API:
1. GET the flow chart to find the Once node and its childIds
2. The childIds array contains the branch node _ids
3. Create your node with mode="appendChild", target="<branch-node-id>"

Full example — adding a Code node to OnFirstTime:
  // Step 1: get_flow_chart to find the Once node
  // Chart shows Once node "once-abc" with childIds ["onfirst-xyz", "after-xyz"]

  // Step 2: create the Code node as child of OnFirstTime branch
  cognigy_create(resource_type="node", body={
    "flowId": "<flow-id>",
    "type": "code",
    "label": "Load Guest Profile",
    "mode": "appendChild",
    "target": "onfirst-xyz",
    "config": {"code": "const profile = await api.httpRequest({...});"}
  })

Unlike aiAgentJobTool branches (which use append after the tool node),
Once branches use appendChild with the branch node as target.
""",

    "xapp-delivery": """
## xapp-delivery — xApp Patterns

### Session init
initAppSession node generates input.apps.url (EPHEMERAL — only available this turn).
Immediately after: Code node reads and persists it:
  context.xappSessionUrl = input.apps.url;

### Sending the xApp URL
SMS via CXone:
  const smsBody = `Click here: ${context.xappSessionUrl}`;
  // Use CXone SMS API via httpRequest node

### Passing context to the xApp page
Embed CognigyScript in iframe src URL params:
  https://my-app.com/page?name={{context.shortTermMemory.customerName}}&token={{context.xappSessionUrl}}

### Page submits back to Cognigy
Option A (webchat): window.parent.postMessage({type: 'cognigy-submit', payload: {...}}, '*')
Option B (SDK): SDK.submit({...})
PostMessage bridge in iframe:
  window.addEventListener('message', (e) => {
    if (e.data?.type === 'cognigy-submit') SDK.submit(e.data.payload);
  });

### Reading submission in flow
SDK path:  input.data._cognigy._app.payload
Webchat:   input.data (direct)

### Session guard pattern
xApp session URL must be persisted in context — input.apps.url is ephemeral.
  if (!context.xappSessionUrl) {
    // session was lost — reinitiate
  }

### api.setAppState() limitation + conditional push pattern
api.setAppState() in code nodes CANNOT push HTML content or external URLs.
Use the setHTMLAppState node instead (type: "setHTMLAppState", extension: "@cognigy/basic-nodes").
Pattern for conditional xApp push from code:
  1. Code node: context.xappTrigger = true;
  2. ifThenElse: condition = context.xappTrigger === true
  3. setHTMLAppState node (in true branch)
  4. Code node: context.xappTrigger = false;

### Dual xApp moments
Some flows need TWO distinct xApp interactions (form then status update).
Each is a separate initAppSession cycle. Store URLs separately:
  context.xappSessionUrl      // first moment
  context.xappDocUploadUrl    // second moment
This pattern is NOT in the Cognigy documentation — it is discovered during build.
""",

    "xapp-event-handling": """
## xapp-event-handling — Non-Blocking xApp with Async Event Loop

### What this pattern solves

An agent cannot pause mid-turn waiting for a user to act on a secondary screen — the session would time out. This pattern splits the interaction across two turns:

- **Turn N (delivery turn):** the tool branch pushes the xApp, calls aiAgentToolAnswer immediately, and returns control to the agent. The agent confirms and holds the conversation open naturally.
- **Turn N+M (event turn):** when the user submits the xApp (or an external system injects a result), a discriminating field arrives in input.data. An IF node at the very top of the flow intercepts it before the AI Agent Job runs. The flow handles the result and ends the turn without treating it as a user utterance.

**Channels:** Works on voice and digital. On voice, the xApp URL is typically delivered via SMS before aiAgentToolAnswer. On digital/chat, the xApp may be delivered inline — no SMS step required.

---

### Two variants — choose by what triggers the result

**Variant A — SDK.submit() (no external system)**
Use when the user's action IS the result: selection, option pick, address confirmation, simple form.
The xApp calls sdk.submit(data) on user action. Cognigy receives it as the next turn. input.data contains the submitted payload.
No session identity required in the xApp HTML.

**Variant B — Webhook inject (external system processes the action)**
Use when a 3rd party must process the action before the result is known: payment processors, document signing, external approvals.
The xApp POSTs to an external API. That API calls the Cognigy Sessions endpoint to inject the outcome. input.data contains the injected payload.
The xApp HTML must embed {{ci.URLToken}}, {{ci.userId}}, {{ci.sessionId}} at render time.

Why not SDK.submit() for Variant B: the user tapping "pay" is not payment succeeding. The payment processor's callback is the authoritative event.

---

### Flow structure (both variants)

```
Start
└── ifThenElse  ← checks EVERY turn for xApp submit / webhook inject
    ├── Then → [extract + normalise code node] → Say (optional ack) → Once → End
    └── Else → Once
                ├── OnFirstTime → [init nodes] → AI Agent Job
                └── Afterwards  → AI Agent Job
                                    └── [tool branch: xApp delivery chain]
```

The IF node sits between Start and Once. It runs on every turn. The AI Agent Job only runs from Afterwards — it never sees the submit/inject turn directly.

---

### Tool branch delivery sequence

#### 1. Say node (voice only — skip for digital)
Immediate audio feedback before the xApp fires.
  "One moment — I'll send that to your phone."

#### 2. initAppSession
Generates input.apps.url (EPHEMERAL — only available this turn).
Configure: backgroundColor, logoUrl, pageTitle, appLoadingText.

#### 3. setHTMLAppState
Push HTML to the xApp session. waitForInput: false is mandatory — this is what makes the pattern non-blocking.
  config: { mode: "full", waitForInput: false, closeOnSubmit: true, autoOpen: false }

#### 4. Code node — capture ephemeral data + set toolResponse
CRITICAL: input.apps.url and input.aiAgent.toolArgs.* both expire at end of this turn.
This node must run immediately after setHTMLAppState.

  // Persist xApp URL
  context.shortTermMemory.xappUrl = input.apps.url;

  // Persist whatever tool args the LLM collected
  context.shortTermMemory.pendingField = input.aiAgent.toolArgs.your_field;

  // Set spoken response for agent
  context.toolResponse = {
    success: true,
    summary: "I've sent that to your screen — complete it when you're ready.",
    data: { xappSent: true }
  };
  api.resolve();

#### 5. SMS delivery (voice only)
Send context.shortTermMemory.xappUrl to the caller via SMS. Skip entirely for digital channels.

#### 6. aiAgentToolAnswer
  { "answer": "{{JSON.stringify(context.toolResponse)}}", "maxLoops": 4 }

Returns control to the agent with the tool result. Nothing is waiting for the xApp.
The agent speaks the summary and holds a normal conversation.

---

### xApp HTML — Variant A (SDK.submit)

  <script src="https://xapp.cognigy.ai/sdk/cognigy-xapp-sdk.js"></script>
  <script>
    const sdk = new CognigyXAppSDK();
    function submitChoice(value) {
      sdk.submit({ selectedOption: value });
    }
  </script>
  <!-- Render options from injected context data -->
  <script>
    const OPTIONS = {{JSON.stringify(context.shortTermMemory.options)}};
    // render buttons calling submitChoice(...)
  </script>

Submitted payload arrives as input.data:
  { "selectedOption": "choice-value" }

---

### xApp HTML — Variant B (Webhook inject)

  <script>
    const SESSION = {
      urlToken:  '{{ci.URLToken}}',
      userId:    '{{ci.userId}}',
      sessionId: '{{ci.sessionId}}'
    };
    async function submitAction(outcome) {
      await fetch('https://your-api.example.com/webhook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outcome, ...SESSION })
      });
    }
  </script>

External API then injects into Cognigy via the REST endpoint (same channel as talk_to_agent):
  POST https://cognigy-endpoint-{env}.nicecxone.com/{urlToken}
  {
    "userId": "<userId from SESSION>",
    "sessionId": "<sessionId from SESSION>",
    "text": "",
    "data": { "paymentResult": { "success": "true", "reference": "PAY-123" } }
  }

IMPORTANT: The management API (/v2.0/projects/…/sessions/…) does NOT support injection on
AU1 — it returns 404. The correct injection path is the REST endpoint host shown above,
not the management API. The xApp HTML's SESSION object already contains the urlToken,
userId, and sessionId needed to construct this call.

Injected payload arrives as input.data.paymentResult (or whatever field you choose).

---

### IF node conditions

Choose a discriminating field that ONLY appears in submit/inject payloads, never in a regular turn.

Variant A: input.data.selectedOption exists
Variant B: input.data.paymentResult exists  (or your chosen field)

### Then branch — extract and store for next turn

Variant A:
  context.shortTermMemory.selectedOption = input.data.selectedOption;

Variant B (watch for string booleans — external APIs often return "true"/"false" not true/false):
  var result = input.data.paymentResult;
  context.shortTermMemory.paymentSuccess = result.success === 'true';

Write results to context.shortTermMemory (LLM-visible). The agent picks them up naturally on the next user utterance.

For immediate spoken acknowledgement, add a Say node in the Then branch before the flow ends.

### Else branch
Empty. Falls through to Once for normal turns. Do not add nodes here.

---

### Gotchas

**input.apps.url is one-turn only.** Miss it and the URL is gone — no recovery without re-running initAppSession (different URL).

**input.aiAgent.toolArgs.* is one-turn only.** The LLM's collected parameters only exist on the tool execution turn. Persist to context in the code node immediately after setHTMLAppState.

**waitForInput: false must be set on setHTMLAppState.** If omitted or true, the flow blocks.

**The IF node's next pointer matters.** Both branches fall through to next. Ensure next points to Once, not null.

**Else branch is empty by design.** Normal turns are handled by Once → Afterwards. Do not add nodes to Else.

**Submit/inject turns must not reach the AI Agent Job.** The Then branch flows to Once → End. If a submit payload leaks into Afterwards, the agent interprets it as a user utterance.

**Variant B: string booleans.** External APIs commonly send "true"/"false" strings. Normalise explicitly: result.success === 'true', not result.success === true.

**Variant B: do not use SDK.submit() when a 3rd party processes the action.** User tap ≠ successful processing. Use webhook inject so the external system's outcome — not the user's gesture — is the authoritative event.
""",

    "cognigyScript": """
## cognigyScript — CognigyScript Interpolation

### Syntax
{{context.namespace.field}}
{{input.data.fieldName}}
{{profile.firstName}}

### Confirmed working contexts
- Say node text field
- AI Agent Job instruction fields
- setHTMLAppState node HTML content
- Endpoint URL parameters (iframe src attribute values)
- Node labels (cosmetic only)

### NOT available
- Inside code node JavaScript bodies (use context.* variables directly in JS)
- Inside JSON string values in httpRequest payloadJSON (unconfirmed, test carefully)

### payloadJSON in httpRequest
CognigyScript interpolation in payloadJSON is UNCONFIRMED.
Safe approach: use a Code node to build the payload object and store in context,
then reference it from the httpRequest via the context variable.

### Common pattern: build in code, reference in node
  // Code node:
  context.smsPayload = {
    to: context.shortTermMemory.mobile,
    body: `Your code is ${context.otpCode}`
  };
  // httpRequest node config: use {{context.smsPayload}} if payloadJSON works,
  // or pipe through code node instead.
""",

    "code-node-patterns": """
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
""",

    "voice-gateway": """
## voice-gateway — Voice Channel Patterns

### VG Entrypoint + Channel Settings — required pairing
VG Entrypoint and Channel Settings are paired in the Cognigy UI.
Channel Settings holds the TTS/STT config and instructions (NOT the VG Entrypoint).
Both must exist.

### Set Session Config node
- Required for all voice flows (TTS engine, STT engine, barge-in, silence timeout)
- Place in OnFirstTime branch (not main chain — avoid re-init every turn)
- Copy-paste identical across demos: create once, copy to other flows

### VG endpoint routing — undocumented UI configuration
The Cognigy endpoint for a voice flow must route DIRECTLY to the main flow.
It must NOT route through VG Entrypoint (a common mistake that breaks voice).
Configured in the Cognigy endpoint settings UI — NOT in any code file.
After creating a voice endpoint, open it in the Cognigy UI and set the flow target manually.

### DTMF input
Comes in via: input.data.dtmf (string, e.g. "1" or "2")
Use an ifThenElse or lookup node to branch on DTMF value.

### ANI (caller ID) from voice / SIP header paths
  input.data.payload.from          // ANI — caller's phone number (SIP format: "+61412345678")
  input.data.payload.to            // DNIS — dialled number
  input.data.payload.callerEmail   // email from SIP header (if CXone passes it)
  input.data.payload.headers       // full SIP headers object

### REST vs Voice streaming differences
REST endpoint with outputImmediately:true:
  - Terminates connection on tool_calls before all output is delivered
  - Single-pass response recommended
Voice pipeline:
  - Synchronous — all tool handling completes before response delivered to caller
  - Two-pass confirmation pattern works correctly on voice
""",

    "outbound-trigger": """
## outbound-trigger — CXone Outbound Call Trigger

### 6-step sequence (run in backend/code node)

Step 1: OAuth token
  POST https://na1.nice-incontact.com/authentication/v1/token/access-token
  Headers: Accept-Encoding: identity  ← CRITICAL (Node 18+ undici decompression bug)
  Body: {grant_type, username, password, ...}

Step 2: Extract tenantId from JWT
  const payload = JSON.parse(atob(token.split('.')[1]));
  const tenantId = payload.tenantId;

Step 3: Get cluster API base URL
  GET https://cxone-configuration.niceincontact.com/config?tenantId={tenantId}
  Headers: Accept-Encoding: identity
  Returns: {api_base_url: "https://na1.nice-incontact.com"}

Step 4: Find script by PATH (not by static ID)
  GET {api_base_url}/services/v16.0/scripts
  Headers: Accept-Encoding: identity, Authorization: Bearer {token}
  Script ID is at: response.header.masterId (not obvious)
  Filter: scripts.find(s => s.scriptName === "My Script Name")
  → DO NOT hardcode script IDs — they differ across environments

Step 5: PATCH claim/session state FIRST
  Do this BEFORE starting the outbound call.
  Reason: UI must update even if CXone call fails.

Step 6: Start script
  POST {api_base_url}/services/v16.0/scripts/{scriptId}/start
  Headers: Accept-Encoding: identity
  Body: {scriptId, parameters: {phone: "+61412345678", ...}}

### Accept-Encoding: identity — WHY THIS IS CRITICAL
Node 18 switched HTTP client to undici. Undici auto-decompresses gzip but
CXone sends malformed compressed responses. identity disables compression.
Omitting this header causes JSON parse errors on ALL CXone API responses.
""",

    "knowledge-store": """
## knowledge-store — Managing Knowledge Sources

### Resource hierarchy
Project → KnowledgeStore → Sources → Chunks

### List knowledge stores
  cognigy_list(resource_type="knowledgestores", project_id=...)

### Create a source
  cognigy_create(resource_type="knowledgestores/{ksId}/sources",
    body={"name": "My Source", "type": "manual"})

  INVALID fields (API returns 400):
  - knowledgeStoreId → not needed (ksId is already in the resource_type path)
  - content → not a create-time field; text is added as chunks after creation
  - type: "text" → not a valid type; use "manual"

### Add text chunks to a source
  After creating the source, add its text content as chunks:
  cognigy_create(resource_type="knowledgestores/{ksId}/sources/{sourceId}/chunks",
    body={"text": "The battery trade-in policy allows..."})
  Retrieve sourceId from the cognigy_create response (referenceId or follow with cognigy_list).

### Trigger ingestion via connector
  cognigy_invoke(resource_type="knowledgestore", resource_id=<ksId>,
    operation="run", body={"connector_id": "<connectorId>"})
Path: POST /v2.0/knowledgestores/{ksId}/connectors/{connectorId}/run

### Query chunks (for debugging)
  Path: GET /v2.0/knowledgestores/{ksId}/sources/{sourceId}/chunks

### Using in a flow
Knowledge AI node references the knowledge store by ID.
Get the ID from state: resolve_resource(name="My Store", resource_type="knowledgestores")
""",

    "endpoint-config": """
## endpoint-config — Creating and Referencing Endpoints

### CRITICAL: Use flowReferenceId (UUID), NOT _id (hex)
Endpoint creation requires the flow's referenceId (a UUID), NOT the _id (hex string).

  // Get the flow first:
  flow = cognigy_get(resource_type="flows", resource_id=flowId)
  // flow._id = "64a3f1c2..."      ← hex, DO NOT use as flowReferenceId
  // flow.referenceId = "550e8400-..."  ← UUID, USE THIS

  cognigy_create(resource_type="endpoints", body={
    "name": "My REST Endpoint",
    "channel": "rest",
    "flowId": flow._id,
    "flowReferenceId": flow.referenceId,   ← required
    "projectId": projectId,
  })

### urlToken caching
After endpoint creation, sync_remote_state caches the urlToken in state:
  state.endpoints["My REST Endpoint"]["urlToken"] = "tok123"
This allows talk_to_agent to find the token without an API call.

### Endpoint URL format
  {COGNIGY_ENDPOINT_BASE}/{urlToken}
  where COGNIGY_ENDPOINT_BASE = COGNIGY_BASE_URL with cognigy-api- → cognigy-endpoint-

### AU1 domain derivation
  cognigy-api-au1.nicecxone.com → cognigy-endpoint-au1.nicecxone.com
""",

    "function-execution": """
## function-execution — Cognigy Functions (Async Pattern)

### What Cognigy Functions are
Serverless JS/TS functions that run outside the flow on Cognigy infrastructure.
Used for long-running async operations (>30s timeout for flows).

### Execute a function
  cognigy_invoke(resource_type="functions", resource_id=<functionId>,
    operation="execute", body={"parameters": {...}})
Path: POST /v2.0/functions/{functionId}/instances

### Check instance status
  cognigy_get(resource_type="functioninstances", resource_id=<instanceId>)
Returns: {status: "pending"|"running"|"done"|"error", result: {...}}

### Inject result back into conversation
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="inject-context", body={"context": {"functionResult": result}})

### In-flow pattern
Use Function Execution node (not raw API) when available.
The node handles invoke + polling + inject natively.

### Session ID for inject
The sessionId is the same value used in talk_to_agent.
In production: comes from input.sessionId within the flow.
""",

    "session-injection": """
## session-injection — Injecting State for Testing

### Inject context variables
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="inject-context",
    body={"context": {"authVerified": True, "customerName": "Alice"}})

### Inject flow state (navigate to a flow)
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="inject-state",
    body={"state": "FlowName"})

### Reset context
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="reset-context", body={})

### Reset state (return to start)
  cognigy_invoke(resource_type="sessions", resource_id=<sessionId>,
    operation="reset-state", body={})

### Session ID
sessionId = the userId value passed to talk_to_agent.
New userId → fresh session. Same userId → continue existing session.

### Testing workflow
  1. talk_to_agent(message="...", user_id="test-1", session_id="test-1")
  2. Inject context to simulate a specific state
  3. talk_to_agent(message="...", user_id="test-1", session_id="test-1")  // continues
  4. Verify response matches expected behaviour
""",

    "extension-map": """
## extension-map — Node Type → Extension Reference

Every Cognigy node type belongs to an extension package. cognigy_create auto-injects
the extension field using two sources in priority order:

1. Static map (built-in types, always available)
2. Dynamic index built by sync_remote_state from installed project extensions

For custom extensions: run sync_remote_state once after installing or updating an
extension in the Cognigy UI. cognigy_create will then auto-inject the correct
extension for any node type that extension defines — no manual lookup needed.

### Voice Gateway nodes (extension: "@cognigy/voicegateway2")
  setSessionConfig    Voice Gateway session config (TTS, STT, barge-in, timeouts)
  hangup              End the call cleanly
  sendMetadata        Send metadata to the voice channel

### AI Agent nodes (extension: "@cognigy/basic-nodes")
  aiAgentJob          The AI Agent job node (persona + instructions)
  aiAgentJobTool      A tool branch under an aiAgentJob
  aiAgentToolAnswer   Surfaces tool result back to the LLM

### xApp nodes (extension: "@cognigy/basic-nodes")
  initAppSession      Generate xApp session URL (stored in input.apps.url)
  setHTMLAppState     Push HTML content to an active xApp session

### Basic nodes (extension: "@cognigy/basic-nodes")
  say                 Speak text to the caller
  code                Run a JavaScript code node
  wait                Wait for user input (terminates turn)
  once                Execute children once, then bypass
  goTo                Jump to another flow
  question            Ask a question and capture input
  httpRequest         Make an outbound HTTP call
  setContext          Set context variables
  if                  Conditional branch (NOT "ifThenElse") — create via cognigy_create
  lookup              Pattern-match branch

### Custom extension nodes
Not listed here — discovered automatically at sync_remote_state time.
Use get_build_state(resource_type="extension_map") to inspect the live index.
If you pass extension explicitly, your value takes precedence over both maps.
404 "resource not found" at a valid chart/nodes URL usually means a missing or
wrong extension — run sync_remote_state then retry.
""",

    "node-types": """
## node-types — Quick Reference

This is an alias for flow-chart-reading + extension-map combined.

### Verified type strings (exact, case-sensitive)
  say               Speak text
  code              JavaScript execution
  wait              Await user input
  once              First-turn gate (auto-creates onFirstExecution + afterwards children)
  goTo              Flow jump (requires flow referenceId UUID — NOT hex _id)
  question          Question + input capture
  httpRequest       Outbound HTTP
  setContext        Set context variables
  if                Conditional (NOT "ifThenElse") — create via cognigy_create
  lookup            Pattern-match branch
  setSessionConfig  Voice Gateway config (extension: @cognigy/voicegateway2)
  hangup            End call (extension: @cognigy/voicegateway2)
  initAppSession    xApp session init (extension: @cognigy/basic-nodes)
  setHTMLAppState   xApp HTML push (extension: @cognigy/basic-nodes)
  aiAgentJob        AI Agent job (extension: @cognigy/basic-nodes)
  aiAgentJobTool    AI Agent tool branch (extension: @cognigy/basic-nodes)
  aiAgentToolAnswer Tool result surface (extension: @cognigy/basic-nodes)

For extension details: explain("extension-map")
For chart reading and hierarchy: explain("flow-chart-reading")
For building tool branches: explain("agent-tool-branch")
""",

    "mcp-comparison": """
## mcp-comparison — cognigy-vibe vs Official NiCE MCP

Two MCPs operate on the same Cognigy API with different purposes.

### Official NiCE MCP (@cognigy/mcp-server)
Strengths:
- create_ai_agent: creates project + agent + flow + endpoint in ONE call
- create_tool: creates aiAgentJobTool + Resolve Tool Action pair, auto-wired
- manage_flow_nodes: inline node creation with flat config shapes (text: "..." works)
- list_resources, delete_resource: fast discovery and cleanup

Limitations:
- Does NOT support: once, onFirstExecution, afterwards, setSessionConfig, hangup, wait
- Does NOT propagate persona/LLM/temperature/toolChoice to the AI Agent Job Node after creation
- Returned endpointUrl uses cognigy-api-au1 (returns 401) — must substitute cognigy-endpoint-au1
- create_tool returns a field called toolId that is actually the mongo _id of the node (misleading)

### cognigy-vibe (this server)
Strengths:
- cognigy_create: any node type, with extension auto-injection
- cognigy_update: always-fresh-GET + merge_config deep-merge (safe partial updates)
- push_code_node: file-first conflict detection
- get_flow_chart: hierarchy string + raw relations
- sync_remote_state: full project state snapshot
- 17-topic explain library

Limitations:
- No convenience methods — no single call to create a full agent

### Recommended split (two-MCP pattern)
Use NiCE for:         create_ai_agent, create_tool, manage_flow_nodes (say/code/question inside tool branches)
Use cognigy-vibe for: once/setSessionConfig/hangup node creation, patching aiAgentJob config after creation,
                      push_code_node, get_flow_chart, cognigy_update with merge_config

### Critical gotcha — NiCE does NOT patch the AI Agent Job Node
After create_ai_agent, the AI Agent Job Node has generic defaults (name: "Customer Support Specialist",
default LLM, toolChoice: "auto", generic memoryContextInjection).
ALWAYS follow create_ai_agent with cognigy_update on the aiAgentJob node to set your persona config.
""",

    "tool-selection": """
## tool-selection — Choosing the Right Tool

### Decision tree
- "Creating a Code node from a local .js/.ts file?" → push_code_node (provides conflict detection against Cognigy UI edits)
- "Creating any other node (Say, Once, HTTP Request, AI Agent Job, etc.)?" → cognigy_create
- "Creating an HTML/xApp node from a local .html file?" → push_html_node (sets mode='full' automatically)
- "Updating an existing node's config?" → cognigy_update with merge_config=true
- "Reading a node or resource?" → cognigy_get

### Why push_code_node for Code nodes?
push_code_node provides conflict detection: if someone edited the node in the Cognigy UI
since your last push, the push is blocked with a diff. cognigy_create has no such protection.

### File-backed vs direct
- push_code_node / push_html_node: local file → remote node, with conflict detection
- cognigy_create: create node from scratch, no local file backing

### What about AI Agent Tools?
The now-removed push_tool_from_file was targeting a hallucinated API endpoint.
AI Agent tool configuration is done through the aiAgentJobTool node config in a flow.
See explain("agent-tool-branch") for the three-node pattern.
""",
}

TOOLS: list[Tool] = [
    Tool(
        name="explain",
        description=(
            "Retrieve implementation guidance before brute-forcing or web-searching.\n\n"
            "Topics: " + " | ".join(TOPICS) + "\n\n"
            "Call explain() for orientation and topic descriptions.\n"
            "Call explain(\"topic\") for full reference on that topic."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic name from the list above. Omit for orientation overview.",
                },
            },
        },
    ),
]


def _ok(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def make_handlers(client: CognigyClient, state: ProjectState, cache: Cache) -> dict:

    def _explain(args: dict) -> list[TextContent]:
        topic = args.get("topic", "").strip()
        if not topic:
            return _ok("# cognigy-vibe-mcp Reference Library\n\n" + _TOPIC_INDEX)
        content = _CONTENT.get(topic)
        if content:
            return _ok(content.strip())
        return _ok(
            f"Unknown topic: '{topic}'\n\n"
            f"Available Topics:\n{_TOPIC_INDEX}"
        )

    return {"explain": _explain}
