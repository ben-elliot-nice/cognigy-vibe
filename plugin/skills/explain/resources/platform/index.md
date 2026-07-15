---
description: Project-level platform resources — connections, endpoints, extensions, LLMs, locales, playbooks, knowledge store, and resource_type discovery recipes
---

## platform — Platform Resources Overview

Everything in this group is a project-level resource reached through `cognigy_get`/`cognigy_create`/
`cognigy_update`/`cognigy_list` with a specific `resource_type`, rather than through the flow chart
itself: connections, endpoints, extensions, LLM resources, locales, playbooks, the project resource,
project snapshots, session workspace, and the knowledge store.

Several `resource_type`s here (`extensions-resource`, `flow-resource`, `lexicons`, `locales`,
`playbooks`, `project-resource`) have no verified create/update body shape yet — their topics are
honest discovery recipes (via `cognigy_list(full_objects=true)` and `describe_resource_schema`)
rather than confirmed examples. Reach for this group whenever you're about to call a resource-type
API you haven't used before.
