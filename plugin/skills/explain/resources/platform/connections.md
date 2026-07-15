---
topic: connections
description: create/update body shape for the connections resource_type, verified via provision_webrtc_endpoint
---

## connections — Creating and Updating Connections

### What a Connection is
A project-level (or agent-level) credential/config object that other resources
(endpoints, extensions) reference by ID. Distinct from an "endpoint" — a
connection holds a provider credential; an endpoint is a channel binding.

### Verified create body shape
This shape is drawn from working production code in this repo
(`provision_webrtc_endpoint` in `cognigy_mcp/tools/voice_ops.py`), not guessed:

  cognigy_create(resource_type="connections", body={
    "name": "My Speech Connection",
    "extension": "@cognigy/audio-preview-provider",
    "type": "MicrosoftSpeechProvider",
    "resourceLevel": "project",
    "projectId": "<projectId>",
    "fields": {"apiKey": "<key>", "region": "australiaeast"},
  })

Required fields confirmed by this working example: `name`, `extension`, `type`,
`resourceLevel`, `projectId`, `fields` (a nested object whose keys depend on
`type` — for `MicrosoftSpeechProvider` it's `apiKey` + `region`).

### Other connection `type`/`extension` pairs
Only the `MicrosoftSpeechProvider` / `@cognigy/audio-preview-provider` pair has
been verified in this codebase. For any other provider (e.g. a different LLM
or speech vendor), the `type` string and the shape of `fields` are unverified —
use the discovery recipe: `cognigy_list(resource_type="connections", project_id=..., full_objects=true)`
against a project with an existing working connection of the type you need, to
read the real shape back rather than guessing it.

### Deleting a connection
  cognigy_delete(resource_type="connections", resource_id="<connectionId>")

### Cross-reference
See `explain("endpoint-config")` for how a connection interacts with endpoint
provisioning (the speech connection is a prerequisite for VoiceGateway webRTC
endpoints).
