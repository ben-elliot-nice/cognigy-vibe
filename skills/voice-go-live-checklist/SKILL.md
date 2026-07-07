---
name: voice-go-live-checklist
description: Audit a Cognigy voice agent against 15 readiness criteria before go-live — checks platform config (LLM, endpoint, demo URL), flow structure (init chain, Set Session Config, silence handling, end-call pair), and advisory items (DTMF, bargeIn). Produces a structured pass/fail report with inline remediation guidance. Run after build-orchestrator or any time before a live demo.
---

# Voice Go-Live Checklist

Run this skill before going live with a voice agent — after a `build-orchestrator` session, after manual edits in the UI, or as a periodic drift check.

**This skill is observe-only.** It reports what it finds; it does not fix anything.

---

## Step 1: Resolve context

Call `sync_remote_state` with no arguments to check if a project is already bound in MCP state.

- **If a project is bound:** confirm with the user:
  > "Found project **[project name]**, flow **[flow name]**. Run the go-live checklist on these?"
  - If yes: proceed to Step 2 using the existing `projectId`, `agentId`, `flowId`.
  - If no: ask which project to use, then call `sync_remote_state({ project_id: "<id>" })`.
- **If no project is bound:** ask:
  > "Which project should I audit? Give a name or project ID."
  Then call `sync_remote_state({ project_id: "<id>" })` to load state.

After loading, confirm these IDs are available in state: `projectId`, `agentId`, `flowId`.
If any are missing, stop and tell the user: "Could not resolve [missing field] from MCP state — please check the project is initialised."

---

## Step 2: Gather raw data

Make these three calls in order. Capture all results — they are used across all assertion groups.

**A. Agent:**
```
cognigy_get(resource_type: "aiagents", resource_id: agentId)
```
Capture: `agent.llmId`, `agent.description`

**B. Endpoints:**
```
cognigy_list(resource_type: "endpoints", project_id: projectId)
```
Filter the results: keep only entries where `endpoint.flowId` matches the flow's hex `_id`. Note: `flowId` in MCP state is typically the hex `_id` — confirm by calling `cognigy_get(resource_type: "flows", resource_id: flowId)` and checking the `_id` field if the filter returns no results unexpectedly.
Capture: filtered list as `voiceEndpoints` (may be empty).

**C. Flow chart:**
```
get_flow_chart(flow_id: flowId, format: "raw")
```
Capture: raw chart object as `chart`.

---

## Step 3: Platform assertions (P1–P4)

Evaluate each assertion and record PASS / FAIL / WARN. Do not stop on failure — run all 15 before printing the report.

### P1 — LLM connected · FAIL if missing

**Check:** `agent.llmId` is non-null and non-empty.

Pass: `✅ P1  LLM connected`
Fail: `❌ P1  No LLM connected to AI Agent`
→ Wire the LLM in the Cognigy UI: Agent → LLM settings → select an LLM. Or call `cognigy_update(resource_type: "aiagents", resource_id: agentId, body: { llmId: "<llm-id>" })` if you prefer the API path.

### P2 — VoiceGateway2 endpoint bound · FAIL if missing

**Check:** `voiceEndpoints` contains at least one entry with `channel: "voiceGateway2"`.

Pass: `✅ P2  VoiceGateway2 endpoint bound to flow`
Fail: `❌ P2  No VoiceGateway2 endpoint bound to this flow`
→ Run `cognigy:build-orchestrator` S1.5(g), or call `provision_webrtc_endpoint` directly to create and bind a webRTC endpoint.

### P3 — Demo URL active · WARN if missing

**Precondition:** P2 passed (a VoiceGateway2 endpoint exists). If P2 failed, mark P3 as SKIP.

**Check:** The VoiceGateway2 endpoint has `webrtcWidgetConfig.active: true` AND a non-empty `urlToken`.

Pass: `✅ P3  Demo URL active (webRTC widget enabled)`
Warn: `⚠️  P3  Demo URL not active — webrtcWidgetConfig.active is false or urlToken is empty`
→ Enable the webRTC widget in the Cognigy UI: Endpoints → [endpoint name] → webRTC Widget → set Active to on. Re-run this checklist to confirm the `urlToken` is then present.

### P4 — Agent description ≤ 1000 chars · FAIL if over

**Check:** `agent.description.length <= 1000`.

Pass: `✅ P4  Agent description within 1000-char cap ([N] chars)`
Fail: `❌ P4  Agent description over 1000-char cap ([N] chars)`
→ Condense the `## Persona` block in the agent description. The cap is a hard platform limit — over-length silently fails on save. See build-orchestrator S1.1 pre-flight gate.

---

## Step 4: Flow structure assertions (F1–F9)

All checks use `chart` from Step 2C. Walk node types and relations — do not rely on node labels, which the user may have customised.

### F1 — Once gate present · FAIL if missing

**Check:** Walking from the `start` node via `next` links, a node of type `once` is reachable within the first 3 hops.

Pass: `✅ F1  Once gate present`
Fail: `❌ F1  No Once node found near start of flow`
→ Re-run `build-orchestrator` S1.5(a), or manually add a Once node after the Start node.

### F2 — Set Session Config present · FAIL if missing

**Check:** The `once` node's `onFirstExecution` branch contains a node of type `setSessionConfig`.

Pass: `✅ F2  Set Session Config present in OnFirstExecution branch`
Fail: `❌ F2  No Set Session Config node found in OnFirstExecution branch`
→ Re-run `build-orchestrator` S1.5(c), or manually add a Set Session Config node (extension: `@cognigy/voicegateway2`) in the OnFirstExecution branch.

### F3 — TTS/STT fields non-placeholder · FAIL if any empty or placeholder

**Precondition:** F2 passed. If F2 failed, mark F3 as SKIP.

**Check:** On the `setSessionConfig` node's config, all of these fields are non-empty and none equals the literal string `"<placeholder>"`:
- `ttsVendor`, `ttsVoice`, `sttVendor`, `sttLanguage`, `locale`

Pass: `✅ F3  TTS/STT fields configured (non-placeholder)`
Fail: `❌ F3  TTS/STT fields contain placeholder or empty values: [list the failing fields]`
→ Populate the flagged fields in the Set Session Config node. See `explain("voice-gateway")` for the expected field shapes.

### F4 — sttHints populated · FAIL if empty or contains blank entries

**Precondition:** F2 passed. If F2 failed, mark F4 as SKIP.

**Check:** `setSessionConfig.config.sttHints` is a non-empty array and contains no empty-string entries.

Pass: `✅ F4  sttHints populated ([N] hints)`
Fail: `❌ F4  sttHints empty or contains blank entries`
→ Populate `sttHints` with the customer brand name, the persona name, and ≥3 domain terms from the agent's tool set (e.g. tool names and their key nouns). See `build-orchestrator` S1.5(c).

### F5 — Silence handling wired · FAIL if neither condition met

**Check:** Either condition is true:
1. `setSessionConfig.config.userNoInputTimeoutEnable` is `true`, OR
2. A node in the flow handles the `noUserInput` system intent (look for an intent node or default reply referencing `noUserInput`, or an ifThenElse checking `input.data.event === "USER_INPUT_TIMEOUT"`).

Pass: `✅ F5  Silence handling wired`
Fail: `❌ F5  No silence/no-input handling detected`
→ Set `userNoInputTimeoutEnable: true` in Set Session Config, or wire a `noUserInput` system intent handler. See `explain("voice-silence-timeout")` for the reprompt-then-escalate pattern.

### F6 — Say Welcome with name interpolation · WARN if missing

**Check:** In the `onFirstExecution` branch, a node of type `say` exists whose `config.say.text` array contains at least one entry with the substring `{{context.customer.firstName}}`.

Pass: `✅ F6  Say Welcome contains firstName interpolation`
Warn: `⚠️  F6  Say Welcome missing firstName interpolation`
→ Add `{{context.customer.firstName}}` to at least one variant in the Say Welcome node's text array.

### F7 — End-call pair present · FAIL if neither; WARN if only one

**Check:** Scan all `aiAgentJobTool` children of the `aiAgentJob` node for tool branches named `end_call` and `end_call_resolved`. Each valid branch must contain a `hangup` node before the `aiAgentToolAnswer`.

- Both `end_call` and `end_call_resolved` present with Hangup → PASS
- Only one present with Hangup → WARN
- Neither present → FAIL

Pass: `✅ F7  End-call pair present (end_call + end_call_resolved with Hangup)`
Warn: `⚠️  F7  Only one end-call branch present ([name]) — add the missing counterpart`
→ Re-run `build-orchestrator` S5, or manually add the missing end-call branch with a Hangup node (extension: `@cognigy/voicegateway2`) before the aiAgentToolAnswer.
Fail: `❌ F7  No end-call branches found — both end_call and end_call_resolved are missing`
→ Re-run `build-orchestrator` S5.

### F8 — No unpopulated tool answers · FAIL if any empty

**Check:** Every node of type `aiAgentToolAnswer` in the flow has `config.answer` that is non-null and non-empty string.

Pass: `✅ F8  All tool answer nodes populated`
Fail: `❌ F8  [N] aiAgentToolAnswer node(s) have empty config.answer: [list node IDs or labels]`
→ Open each flagged node in the Cognigy Flow Editor and set the Answer field to `{{JSON.stringify(context.toolResponse)}}` with Max Loops set to `4`. Or call `cognigy_update(resource_type: "node", flow_id: flowId, resource_id: <nodeId>, merge_config: true, body: { config: { answer: "{{JSON.stringify(context.toolResponse)}}", maxLoops: 4 } })`. See `build-orchestrator` S1.4.

### F9 — AI Agent Job production flags · FAIL if any debug flag is on

**Check:** On the `aiAgentJob` node:
- `config.debugLogSystemPrompt` is `false` or absent (default is false)
- `config.debugResult` is `false` or absent (default is false)

Pass: `✅ F9  AI Agent Job production flags correct`
Fail: `❌ F9  AI Agent Job has debug flags enabled: [list flagged fields]`
→ Open the AI Agent Job node in the Cognigy Flow Editor and uncheck "Debug Log System Prompt" and "Debug Result" in the node config. Or call `cognigy_update(resource_type: "node", flow_id: flowId, resource_id: <aiAgentJobNodeId>, merge_config: true, body: { config: { debugLogSystemPrompt: false, debugResult: false } })`.

---

## Step 5: Advisory assertions (A1–A2)

These are warnings only — they do not block go-live. A1 fires when DTMF branching is absent; A2 fires when bargeIn is not explicitly configured.

### A1 — DTMF handling · WARN if no branching detected

**Check:** Scan the flow chart for any node that branches on `input.data.dtmf` (look for ifThenElse or lookup nodes referencing `dtmf` in their condition or data fields).

If DTMF branching is found: `✅ A1  DTMF branching present`
If not found: `⚠️  A1  No DTMF branching detected`
→ If this agent handles keypress input (e.g. IVR menu options), add an ifThenElse node branching on `input.data.dtmf`. See `explain("voice-gateway")` for the DTMF input path.

### A2 — bargeIn explicitly set · WARN if absent

**Precondition:** F2 passed. If F2 failed, mark A2 as SKIP.

**Check:** `setSessionConfig.config.bargeIn` exists and `bargeIn.enable` is explicitly set (to either `true` or `false`).

If explicitly set: `✅ A2  bargeIn explicitly configured (enable: [value])`
If absent: `⚠️  A2  bargeIn not explicitly set in Set Session Config — platform default applies`
→ Add `bargeIn: { enable: false, actionHook: "voice", dtmfBargein: false }` to the Set Session Config node config for an explicit no-barge-in setting. Adjust if barge-in is intentional for this use case.

---

## Step 6: Print the report

Collect all assertion results from Steps 3–5. Print the full report in this exact format — do not omit any assertion, even if it passed:

```
## Voice Go-Live Checklist — [project name] / [flow name]

### Platform
[P1 result line]
[P1 remediation line if FAIL or WARN, indented with →]
[P2 result line]
[P2 remediation line if FAIL or WARN]
[P3 result line or SKIP]
[P3 remediation line if WARN]
[P4 result line]
[P4 remediation line if FAIL]

### Flow Structure
[F1–F9 result lines, each with remediation line below if FAIL or WARN]

### Advisory
[A1 result line]
[A1 remediation line if WARN]
[A2 result line or SKIP]
[A2 remediation line if WARN]

---
[N] passed · [N] failed · [N] warnings
```

**Counts:** PASS → passed; FAIL → failed; WARN → warnings; SKIP → not counted.

**Emoji key:**
- `✅` — PASS
- `❌` — FAIL
- `⚠️ ` — WARN
- `—` — SKIP (precondition not met)

After printing the report, if any FAIL results exist, add this note:
> "Fix the FAIL items before going live. WARN items are advisory — address them if the scenario applies."

If all 15 assertions (excluding SKIPs) are PASS or WARN:
> "No blocking issues found. Review any warnings above before going live."
