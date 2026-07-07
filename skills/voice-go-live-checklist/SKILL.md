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
→ `cognigy_update(resource_type: "aiagents", resource_id: agentId, body: { llmId: "<llm-id>" })` — or wire the LLM in the Cognigy UI under Agent → LLM settings.

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
→ `cognigy_update` the endpoint: `body: { webrtcWidgetConfig: { active: true } }`. Then retrieve the `urlToken` via `cognigy_get` on the endpoint and confirm it is non-empty.

### P4 — Agent description ≤ 1000 chars · FAIL if over

**Check:** `agent.description.length <= 1000`.

Pass: `✅ P4  Agent description within 1000-char cap ([N] chars)`
Fail: `❌ P4  Agent description over 1000-char cap ([N] chars)`
→ Condense the `## Persona` block in the agent description. The cap is a hard platform limit — over-length silently fails on save. See build-orchestrator S1.1 pre-flight gate.
