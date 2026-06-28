---
topic: llm-resources
description: LLM listing by project, referenceId resolution, project-scope vs global, and the largelanguagemodels API path
group: platform
---

## llm-resources — Finding and resolving LLMs

LLM models are a Cognigy resource. List them with `cognigy_list` — `resource_type` passes straight through to the REST path, so no NiCE MCP dependency is needed for LLM discovery.

### List the LLMs in a project

```
cognigy_list { resource_type: "largelanguagemodels", project_id: "<projectId>" }
# → GET /v2.0/largelanguagemodels?projectId=<projectId>
```

Returns one entry per LLM. With `full_objects: true` (or `fields: ["_id","name","referenceId","modelType","provider"]`) each entry includes:

| Field | Meaning |
|---|---|
| `name` | Human label (e.g. `Azure GPT 4.1`, `global-gpt-4.1-mini`) |
| `referenceId` | The UUID you pass as `llmProviderReferenceId` in `update_ai_agent.jobConfig` |
| `modelType` | Underlying model (e.g. `gpt-4.1`) |
| `provider` | e.g. `azureOpenAI` |

The default `cognigy_list` (no `full_objects`) returns `{id, name}` pairs — enough to let a user pick by label; fetch `referenceId` when you need to wire the agent.

### referenceId resolution

Builders configure LLMs by **label** (readable, stable across people); the build needs the **`referenceId`**. Resolve label → referenceId by listing with `full_objects: true` and matching on `name`. Never hardcode a referenceId blind — confirm it exists in the **target** project first (see project-scope below).

### Project-scope vs global

LLM connections are **project-scoped**: a `referenceId` valid in one project is not automatically usable in another. A freshly created project may have **no** LLM, in which case generation returns empty output with no error. Two ways to get an LLM into a target project:

- **Reuse via packages** — export the `largelanguagemodels` resource (+ its connection) from a project that has it and import into the target (`manage_packages`).
- **Global models** — some tenants expose a shared/global LLM available across projects; it still surfaces in the project-scoped list when usable.

Always verify the chosen LLM exists in the target project (list it) before relying on `talk_to_agent` output.

### Confirming the resource_type per region

`largelanguagemodels` is the AU1 path. If a `cognigy_list` for it returns nothing unexpected on another region/tenant, confirm the exact collection name against that environment's OpenAPI spec (`GET https://cognigy-api-<region>.nicecxone.com/openapi/openapi-viewer.json`) — the spec is the source of truth for resource paths.
