---
topic: llm-resources
description: org-level vs project-level LLMs, assign_org_llm tool, discovery pattern, referenceId resolution, manage_packages fallback
group: platform
---

## llm-resources — LLM Discovery and Project Assignment

### resourceLevel: organisation vs project

Every LLM on a Cognigy tenant has a `resourceLevel` field:

- `"organisation"` — tenant-wide model managed by an admin. Visible to all projects that have been granted access via `assignedToProjects`. This is the standard model for shared demo builds.
- `"project"` — lives only inside one project. Not accessible from other projects without a `manage_packages` export/import.

### Discovering available LLMs

Call `cognigy_list` **without** a `project_id` to get all LLMs on the tenant (both org-level and project-level):

```
cognigy_list {
  resource_type: "largelanguagemodels",
  full_objects: true,
  fields: ["_id", "name", "referenceId", "resourceLevel", "modelType", "provider"]
}
```

Filter for org-level generation models:
- Keep: `resourceLevel == "organisation"`
- Exclude: `modelType` contains `"embedding"` (case-insensitive)

This gives the list to present to users during setup — real names, not hardcoded UUIDs.

To list LLMs scoped to a specific project (e.g. to verify before generation):

```
cognigy_list { resource_type: "largelanguagemodels", project_id: "<projectId>", full_objects: true,
               fields: ["_id", "name", "referenceId", "modelType", "provider"] }
```

### referenceId resolution

Builders configure LLMs by **label** (readable, stable across people); the build needs the **`referenceId`**. Resolve label → referenceId by listing with `full_objects: true` and matching on `name`. Never hardcode a referenceId — confirm it exists in the **target** project first.

### Assigning an org-level LLM to a new project

Use `assign_org_llm` after `create_ai_agent`. It appends the project to the LLM's `assignedToProjects` list safely:

```
assign_org_llm {
  project_id: "<new project _id>",
  llm_id: "<org-level LLM _id — NOT referenceId>"
}
```

Returns:
- `{ already_assigned: true, llm_name: "..." }` — no write made (idempotent, safe to call twice)
- `{ assigned: true, llm_name: "...", project_id: "..." }` — project added
- `{ error: "not_org_level", hint: "..." }` — LLM is project-scoped; use `manage_packages` instead
- `{ error: "llm_not_found", llm_id: "..." }` — bad `llm_id`

**Always use `assign_org_llm`, never hand-write the GET+PATCH.** The raw PATCH requires sending the full `assignedToProjects` array — a hand-written PATCH that omits an entry drops it. `assign_org_llm` prevents this by reading the current array before writing.

> **Concurrency note.** `assign_org_llm` prevents duplicate entries (if the project is already in the array, it skips the PATCH) but does not protect against two simultaneous *first*-assignment calls targeting the same LLM. In that race, both calls read the same pre-write array, and each writes a version without the other's entry — one assignment is lost. In practice this is harmless for demo builds (sequential per-build usage), but do not rely on it for concurrent automated provisioning.

### When `manage_packages` is still appropriate

If the user's chosen LLM is `resourceLevel: "project"` (e.g. a custom connection not promoted to org level), `assign_org_llm` will refuse. Export the LLM from its source project and import it into the new project:

```
manage_packages { operation: "list_exportable", projectId: "<source project id>" }
# → find the llm_model resource id

manage_packages {
  operation: "export",
  projectId: "<source project id>",
  resourceIds: ["<llm_model id>"],
  includeDependencies: true,
  outputPath: "<absolute path>/llm-backup.zip",
  waitForCompletion: true
}

manage_packages {
  operation: "import",
  projectId: "<new project id>",
  packagePath: "<absolute path>/llm-backup.zip",
  waitForCompletion: true
}
```

### `_id` vs `referenceId`

- `_id` — MongoDB ObjectId hex string. Required by `assign_org_llm` and for direct API calls (`GET /v2.0/largelanguagemodels/<_id>`).
- `referenceId` — UUID. Required by `update_ai_agent.jobConfig.llmProviderReferenceId`.

Both are returned by `cognigy_list`. Store both in `buildConfig.llm.options[]` (`id` for assignment, `referenceId` for the job config patch).

### Confirming the resource path per region

`largelanguagemodels` is the standard path across regions. If a `cognigy_list` returns unexpected results on a non-AU1 tenant, confirm the exact collection name against that environment's OpenAPI spec (`GET https://cognigy-api-<region>.nicecxone.com/openapi/openapi-viewer.json`) — the spec is the source of truth for resource paths.
