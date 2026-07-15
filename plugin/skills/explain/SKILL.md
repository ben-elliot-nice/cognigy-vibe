---
name: explain
description: Retrieve implementation guidance for Cognigy topics before brute-forcing or web-searching
---

# Explain

## When to Use

Call `explain` before brute-forcing or web-searching for Cognigy implementation guidance. It returns authoritative reference for the topics below — faster and more accurate than inference.

## Available Topics

Topics and what they cover. File paths are relative to `plugin/skills/explain/resources/` — read a topic's file directly if the `explain` MCP tool isn't available in this session.

| Topic | Description | File |
| --- | --- | --- |
| `aiagent` | AI Agent Job node configuration, persona authoring, tool design, turn structure, and multi-agent architecture patterns | `aiagent/index.md` |
| `code` | Code node runtime objects, CognigyScript interpolation, async function execution, output formatting, and profile editing | `code/index.md` |
| `nodes` | Flow chart structure, node type strings, node wiring/positioning, and the full node-type reference | `nodes/index.md` |
| `platform` | Project-level platform resources — connections, endpoints, extensions, LLMs, locales, playbooks, knowledge store, and resource_type discovery recipes | `platform/index.md` |
| `voice` | Voice Gateway session configuration and silence-timeout handling | `voice/index.md` |
| `xapp` | xApp architecture overview, variant selection, and channel differences | `xapp/index.md` |

### aiagent

AI Agent Job node configuration, persona authoring, tool design, turn structure, and multi-agent architecture patterns

| Topic | Description | File |
| --- | --- | --- |
| `agent-avatar-image` | Custom avatar image on AI Agent — data URI pattern, imageOptimizedFormat, file spec, push_agent_avatar usage | `aiagent/agent-avatar-image.md` |
| `agent-behavioral-rules` | Silent tool execution, outcome-based framing, compliance rules in tool descriptions | `aiagent/agent-behavioral-rules.md` |
| `agent-handover` | Escalation to human pattern and handover context artefact design (two-consumer model) | `aiagent/agent-handover.md` |
| `agent-job-node` | aiAgentJob node — assumptions, resolution/insertion procedure, config schema, tool-node creation | `aiagent/agent-job-node.md` |
| `agent-persona-authoring` | AI Agent description and instructions field authoring — structure, constraints, speaking style | `aiagent/agent-persona-authoring.md` |
| `agent-tool-branch` | aiAgentJobTool + code + toolAnswer assembly, tool args access | `aiagent/agent-tool-branch.md` |
| `agent-tool-json` | .tool.json convention — field reference, toolType selection, toolId uniqueness rule | `aiagent/agent-tool-json.md` |
| `agent-tool-patterns` | Tool granularity options (granular/consolidated/action-parameterized) and context.toolResponse channel | `aiagent/agent-tool-patterns.md` |
| `agent-tool-scaffold` | Cognigy auto-scaffolds a default placeholder tool node when an AI Agent Job node is created — detect and delete it before authoring real tools | `aiagent/agent-tool-scaffold.md` |
| `multi-agent-architecture` | Concierge + Specialists pattern, specialist job types, routing, context schema, stub agent | `aiagent/multi-agent-architecture.md` |
| `tool-conditions` | CognigyScript condition field, hiding tools from LLM | `aiagent/tool-conditions.md` |
| `tool-selection` | when to use push_agent_tool vs push_code_node vs cognigy_create vs cognigy_update | `aiagent/tool-selection.md` |
| `turn-structure` | Once/OnFirstTime/Afterwards, input.execution, context reset prevention, child branch API patterns | `aiagent/turn-structure.md` |
| `two-pass-confirm` | inter-turn flag management, STOP gate wording | `aiagent/two-pass-confirm.md` |

### code

Code node runtime objects, CognigyScript interpolation, async function execution, output formatting, and profile editing

| Topic | Description | File |
| --- | --- | --- |
| `code-node-patterns` | api.* functions, execution model, runtime objects (input/context/profile/analyticsdata), utility functions (getVar/setVar/mergeVar), as const bug, httpRequest response shape and storage config | `code/code-node-patterns.md` |
| `cognigyScript` | interpolation contexts, what works where | `code/cognigyScript.md` |
| `function-execution` | async pattern, inject-back via sessions API, create-body-shape gap | `code/function-execution.md` |
| `output-formats` | api.say() channel output shapes — quick replies, buttons, gallery, image, audio, adaptive card | `code/output-formats.md` |
| `profile-editing` | Writing to the Cognigy contact profile — why direct mutation doesn't persist, api.updateProfile behaviour, and getProfileVar/setProfileVar/mergeProfileVar utility functions | `code/profile-editing.md` |
| `session-injection` | context/state inject for in-session testing | `code/session-injection.md` |

### nodes

Flow chart structure, node type strings, node wiring/positioning, and the full node-type reference

| Topic | Description | File |
| --- | --- | --- |
| `flow-chart-reading` | reading chart output, node type strings, extension field | `nodes/flow-chart-reading.md` |
| `node-config-update` | full-replace semantics, merge_config pattern, silent field deletion | `nodes/node-config-update.md` |
| `node-positioning` | append vs appendChild modes, moving an existing node via cognigy_update, child branch population for Once, IF, ifThenElse nodes, lookup default branch | `nodes/node-positioning.md` |
| `node-types` | quick reference for all node type strings | `nodes/node-types.md` |
| `node-wiring` | chart structure, relations array, sequential vs child chains | `nodes/node-wiring.md` |

### platform

Project-level platform resources — connections, endpoints, extensions, LLMs, locales, playbooks, knowledge store, and resource_type discovery recipes

| Topic | Description | File |
| --- | --- | --- |
| `connections` | create/update body shape for the connections resource_type, verified via provision_webrtc_endpoint | `platform/connections.md` |
| `endpoint-config` | referenceId vs _id gotcha, urlToken caching, VoiceGateway webRTC endpoint, per-channel field differences | `platform/endpoint-config.md` |
| `env-config-discovery` | how .env credentials and default-demo-config.json are discovered and merged across project and user-global scope | `platform/env-config-discovery.md` |
| `extension-map` | complete type → extension lookup table | `platform/extension-map.md` |
| `extensions-resource` | no verified create/update body shape yet — discovery recipe for resource_type=extensions (installed extension config, distinct from explain("extension-map")'s node-type lookup table) | `platform/extensions-resource.md` |
| `flow-resource` | no verified create/update body shape yet — discovery recipe for resource_type=flows (raw flow creation, distinct from flow/clone via cognigy_invoke) | `platform/flow-resource.md` |
| `knowledge-store` | chunking, connector run, source management | `platform/knowledge-store.md` |
| `lexicons` | no verified create/update body shape yet — discovery recipe for resource_type=lexicons | `platform/lexicons.md` |
| `llm-resources` | org-level vs project-level LLMs, assign_org_llm tool, discovery pattern, referenceId resolution, manage_packages fallback | `platform/llm-resources.md` |
| `locales` | no verified create/update body shape yet — discovery recipe for resource_type=locales | `platform/locales.md` |
| `mcp-comparison` | when to use cognigy-vibe vs NiCE official MCP | `platform/mcp-comparison.md` |
| `outbound-trigger` | 6-step CXone trigger, Accept-Encoding: identity requirement | `platform/outbound-trigger.md` |
| `playbooks` | no verified create/update body shape yet — discovery recipe for resource_type=playbooks | `platform/playbooks.md` |
| `project-resource` | no verified create/update body shape yet — discovery recipe for resource_type=project | `platform/project-resource.md` |
| `project-snapshots` | create project snapshots for versioning (flow-level versioning does not exist in the API) | `platform/project-snapshots.md` |
| `say-node` | say node config schema: correct text field, required _cognigy/_data fields, generativeAI_customInputs | `platform/say-node.md` |
| `session-workspace` | session workspace directory model — cwd vs Demo Builds/, .env scope, sync_remote_state project binding | `platform/session-workspace.md` |

### voice

Voice Gateway session configuration and silence-timeout handling

| Topic | Description | File |
| --- | --- | --- |
| `voice-gateway` | VG endpoint routing, Set Session Config, SIP headers, DTMF | `voice/voice-gateway.md` |
| `voice-silence-timeout` | Voice Gateway silence detection — three modes, noUserInput intent wiring, reprompt-then-escalate counter | `voice/voice-silence-timeout.md` |

### xapp

xApp architecture overview, variant selection, and channel differences

| Topic | Description | File |
| --- | --- | --- |
| `xapp-delivery` | session init, postMessage bridge, SDK.submit, dual xApp moments | `xapp/delivery.md` |
| `xapp-event-handling` | non-blocking xApp pattern: flow structure, ephemeral data capture, SDK.submit vs webhook inject variants | `xapp/event-handling.md` |

## How to Use

- **Orientation:** `explain()` with no args — returns the list of topic groups with one-line descriptions
- **Group primer:** `explain("group-name")` — returns that group's primer plus an index of the topics inside it
- **Full reference:** `explain("topic-name")` — returns complete guidance for that specific topic
