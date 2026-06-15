---
topic: endpoint-config
description: referenceId vs _id gotcha, urlToken caching
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
