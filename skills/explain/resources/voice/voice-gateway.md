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
