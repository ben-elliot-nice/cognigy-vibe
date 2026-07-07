---
topic: voice-gateway
description: VG endpoint routing, Set Session Config, SIP headers, DTMF
group: voice
---

## voice-gateway — Voice Channel Patterns

### VG Entrypoint + Channel Settings — required pairing
VG Entrypoint and Channel Settings are paired in the Cognigy UI.
Channel Settings holds the TTS/STT config and instructions (NOT the VG Entrypoint).
Both must exist.

### Set Session Config node
- Required for all voice flows (TTS engine, STT engine, barge-in, silence timeout)
- Place in OnFirstTime branch (not main chain — avoid re-init every turn)
- Copy-paste identical across demos: create once, copy to other flows

### VG endpoint creation — automatable via `provision_webrtc_endpoint`
Creating a VoiceGateway webRTC endpoint and binding it to a flow is fully
API-automatable. `provision_webrtc_endpoint` handles the Microsoft Azure Speech
Services connection prerequisite, endpoint creation (`channel: "voiceGateway2"`,
`webrtcWidgetConfig: { active: true }`), and flow binding (`flowId` +
`flowReferenceId`) in one call.

Demo calls work regardless of credential path. The in-browser voice-preview
widget requires `COGNIGY_VOICE_PREVIEW_API_KEY` in `.env` (captured by
`init-cognigy-vibe`).

The webRTC demo URL is `{COGNIGY_ENDPOINT_BASE}/demo/{URLToken}`.
See `build-orchestrator S1.5(g)` for build-context usage.

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
