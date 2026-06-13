# Cognigy Claude Plugin — Architecture

## Overview

This plugin gives Claude Code structured access to the Cognigy API for building AI agent demos. It is built in two layers: a Python MCP server and a set of composite skills.

```
Composite skills       add-aiagent-job, design-agent-*, scope-demo, init-mcp
      ↓ call MCP tools
cognigy-vibe MCP       cognigy_create, cognigy_update, get_flow_chart, push_code_node, explain ...
      ↓ calls
Cognigy REST API
```

---

## Layer 1: cognigy-vibe MCP Server

**Location:** `cognigy-mcp/`  
**Package:** `cognigy-vibe-mcp` (PyPI)  
**Install:** `uvx cognigy-vibe-mcp`  
**Server name (Claude sees):** `cognigy-vibe`

The MCP server is the only thing that talks to the Cognigy API. It handles authentication, per-project state management, filesystem cache, and conflict detection. Skills call MCP tools — they never make HTTP requests directly.

### Tools (14 total)

| Group | Tools |
|---|---|
| State & sync | `sync_remote_state`, `get_build_state`, `resolve_resource` |
| Flow ops | `cognigy_get`, `cognigy_list`, `cognigy_create`, `cognigy_update`, `cognigy_delete`, `cognigy_invoke`, `get_flow_chart` |
| File push | `push_code_node`, `push_html_node` |
| Testing | `talk_to_agent` |
| Guidance | `explain` |

### Key behaviours

- **Extension auto-injection:** `cognigy_create` injects the correct `extension` field for all known node types (e.g. `@cognigy/voicegateway2` for `setSessionConfig`, `@cognigy/basic-nodes` for `aiAgentJob`)
- **Say node normalisation:** `config.text: "Hello"` is automatically lifted into the full `config.say.text` envelope
- **Plural/singular normalisation:** `resource_type: "flow"` or `"flows"` both work
- **Cache-first reads:** `cognigy_get` serves from a configurable TTL filesystem cache (default 5 min); writes are always fresh
- **Conflict detection:** `push_code_node` compares the remote node against a local snapshot and blocks if the Cognigy UI has been edited since the last push
- **Auto-resync:** If a session has been idle > threshold (default 4 hours), the server silently re-syncs state before the next tool call
- **Code node protection:** `cognigy_create` and `cognigy_update` block code node operations and redirect to `push_code_node` (which provides file-backed conflict detection)
- **Mode validation:** `cognigy_create` validates the `mode` field and returns a clear error for invalid values; `insertAfter` / `insertBefore` are marked BROKEN on AU1
- **Token-efficient defaults:** `cognigy_list` returns simplified `{id, name}` pairs by default (~95% savings); `cognigy_create`/`cognigy_update` return minimal objects by default (~90% savings); both support optional `fields` filtering

### `cognigy_invoke` operations

| Operation | Path |
|---|---|
| `node/move` | `POST /v2.0/flows/{flowId}/chart/nodes/{id}/move` |
| `flow/clone` | `POST /v2.0/flows/{id}/clone` |
| `aiagent/train` | `POST /v2.0/aiagents/{id}/train` |
| `sessions/inject-context` | `POST /v2.0/sessions/{id}/context/inject` |
| `sessions/inject-state` | `POST /v2.0/sessions/{id}/state/inject` |
| `sessions/reset-context` | `POST /v2.0/sessions/{id}/context/reset` |
| `sessions/reset-state` | `POST /v2.0/sessions/{id}/state/reset` |
| `knowledgestore/run` | `POST /v2.0/knowledgestores/{id}/connectors/{connectorId}/run` |

### Internal modules

| Module | Responsibility |
|---|---|
| `server.py` | MCP server wiring, auto-resync middleware, tool dispatch |
| `api.py` | `CognigyClient` — thin httpx wrapper; derives endpoint URL from base URL |
| `state.py` | `ProjectState` — name→ID mappings, seed/runtime merge, interaction timestamp |
| `cache.py` | `Cache` — filesystem TTL cache for resource JSON + code node snapshots |
| `tools/state_tools.py` | `sync_remote_state`, `get_build_state`, `resolve_resource` |
| `tools/flow_ops.py` | CRUD ops, normalisation logic, `get_flow_chart` hierarchy renderer |
| `tools/file_push.py` | `push_code_node` (conflict detection), `push_html_node` |
| `tools/testing.py` | `talk_to_agent` — REST endpoint test harness |
| `tools/explain.py` | `explain` — 21-topic in-server reference library |

### State storage

Per-project state lives in `~/.config/cognigy-mcp/<project-id>/`:

```
~/.config/cognigy-mcp/<project-id>/
├── .state.json          # runtime name→ID mappings (written by sync_remote_state)
├── .state-seed.json     # optional seed defaults (merged under runtime state)
├── last-interaction     # epoch timestamp — drives auto-resync threshold
└── cache/               # filesystem TTL cache
    ├── flows/           # resource JSON by ID
    ├── nodes/           # resource JSON + code snapshots (code.js per node)
    └── ...
```

State is loaded at startup by deep-merging seed into runtime. `sync_remote_state` populates `flows`, `agents`, `endpoints`, and `tools` categories. `resolve_resource` and `get_build_state` read from this without making API calls.

The `cognigy:init-mcp` skill creates this directory, a `.cognigy-mcp` symlink in the project root, and the `.claude/mcp.json` entry.

### Reference docs (runtime guidance)

**Location:** `runtime-reference/`

These files contain domain knowledge read by skills before generating code or content. Skills read them via the `Base directory for this skill:` path injected at skill load time.

| File | Purpose |
|---|---|
| `runtime-reference/cognigy-api-reference.md` | Runtime objects (`input`, `context`, `profile`), all `api.*` functions, available libraries |
| `runtime-reference/cognigy-output-formats.md` | Channel output structures and code examples |
| `runtime-reference/cognigy-code-conventions.md` | Code node structural conventions |

The `explain` tool carries a 21-topic in-server reference library (node creation patterns, xApp delivery, extension map, voice gateway setup, CXone outbound trigger, etc.). Access via `explain("topic")`. The full topic list is front-loaded in the tool description — no tool call needed to see what's available.

---

## Layer 2: Composite Skills

**Location:** `skills/`

Skills orchestrate MCP tool calls and user interaction to accomplish higher-level goals. They call MCP tools by name — never make API calls directly.

| Skill | Purpose |
|---|---|
| `cognigy:init-mcp` | First-time project setup — config dir, symlink, `.claude/mcp.json` |
| `cognigy:add-aiagent-job` | Add an AI Agent Job node + tool nodes to an existing flow |
| `cognigy:scope-demo` | Four-phase discovery → demo plan document |
| `cognigy:design-agent` | Orchestrate full agent design workflow |
| `cognigy:design-agent-persona` | Agent identity, brand voice, compliance framing |
| `cognigy:design-agent-jobs` | Job definitions, routing architecture, context schema |
| `cognigy:design-agent-interfaces` | xApp scenes, webchat patterns, handover context |
| `cognigy:design-agent-contracts` | Guard sub-flows, obligation state, structured refusals |

`cognigy:scope-demo` has a `references/` subdirectory (`skills/scope-demo/references/`) containing `cognigy-capabilities.md`, `scope-demo-discovery-questions.md`, and `scope-demo-output-template.md` — referenced at runtime by the skill.

### The key rule: skills call MCP tools, not the API

**Wrong:**
```
cognigy_create(resource_type="node", body={...})  ← direct HTTP, bypasses cache/conflict detection
```

**Right:**
```
Call the cognigy-vibe MCP tool cognigy_create with resource_type="node" and body={...}
```

---

## Hooks

**Location:** `hooks/`

| File | Purpose |
|---|---|
| `hooks/hooks.json` | Hook registration — `PreToolUse` on `mcp__cognigy-vibe__.*` |
| `hooks/onboarding-gate.sh` | Injects architectural primer on the first Cognigy MCP call per session |

The onboarding gate fires before any `cognigy-vibe` tool call. On the first call in a session it denies the tool call and injects a primer (project/flow/node/agent hierarchy, key tool guidance) as `additionalContext`. On all subsequent calls it exits immediately. `explain` calls bypass the gate unconditionally.

---

## Design docs and specs

**Location:** `docs/`

| File | Purpose |
|---|---|
| `docs/cognigy-agent-patterns.md` | Tool design patterns, two-pass confirmation, context schema |
| `docs/agent-prompting-guide.md` | Persona field purposes, outcome-based framing, tool descriptions as contracts |
| `docs/superpowers/specs/` | Brainstorming design specs |
| `docs/superpowers/plans/` | Implementation plans |
| `docs/test-reports/` | Exploratory testing reports |

---

## Plugin registration

**Location:** `.claude-plugin/plugin.json`

Declares the plugin name, description, version, and author. Version must be bumped (patch) on every change to `cli/` or `skills/`.

---

## Adding a New MCP Tool

1. Add a `Tool` definition to the relevant module in `cognigy-mcp/cognigy_mcp/tools/`
2. Add a handler function and register it in `make_handlers()`
3. Add tests in `cognigy-mcp/tests/tools/`
4. If it covers new Cognigy API patterns, add an `explain` topic in `explain.py`
5. Bump the patch version in `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json`

For new node types, add the type → extension mapping to `_NODE_EXTENSION_MAP` in `flow_ops.py` — no other changes needed.

---

## Adding a New Composite Skill

1. Identify which MCP tools it will call
2. Write `skills/<skill-name>/SKILL.md` — call MCP tools by name, never construct HTTP requests
3. Register it in `.claude-plugin/plugin.json`
4. Bump the patch version in `.claude-plugin/plugin.json`
