---
topic: endpoint-config
description: referenceId vs _id gotcha, urlToken caching, VoiceGateway webRTC endpoint
group: platform
---

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

### VoiceGateway webRTC endpoint
`channel: "voiceGateway2"` with `webrtcWidgetConfig: { active: true }` enables
the in-browser demo widget. Flow binding via `flowId` (hex `_id`) +
`flowReferenceId` (UUID) at creation time — no UI routing step required.

Demo URL format: `{COGNIGY_ENDPOINT_BASE}/demo/{URLToken}`

For the full e2e provisioning (including speech connection prerequisite),
use `provision_webrtc_endpoint` rather than `cognigy_create` directly.
`provision_webrtc_endpoint` handles credential detection, dummy-connection
cleanup, and URL derivation in one call.
