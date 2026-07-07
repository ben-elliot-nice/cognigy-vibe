---
topic: knowledge-store
description: chunking, connector run, source management
group: platform
---

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
