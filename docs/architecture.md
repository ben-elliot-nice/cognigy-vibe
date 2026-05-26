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
**Install:** `uvx cognigy-vibe-mcp`  
**Server name (Claude sees):** `cognigy-vibe`

The MCP server is the only thing that talks to the Cognigy API. It handles authentication, per-project state management, filesystem cache, and conflict detection. Skills call MCP tools — they never make HTTP requests directly.

### Tools (15 total)

| Group | Tools |
|---|---|
| State & sync | `sync_remote_state`, `get_build_state`, `resolve_resource` |
| Flow ops | `cognigy_get`, `cognigy_list`, `cognigy_create`, `cognigy_update`, `cognigy_delete`, `cognigy_invoke`, `get_flow_chart` |
| File push | `push_code_node`, `push_html_node`, `push_tool_from_file` |
| Testing | `talk_to_agent` |
| Guidance | `explain` |

### Key behaviours

- **Extension auto-injection:** `cognigy_create` injects the correct `extension` field for all known node types (e.g. `@cognigy/voicegateway2` for `setSessionConfig`, `cognigy-ai-agent` for `aiAgentJob`)
- **Say node normalisation:** `config.text: "Hello"` is automatically lifted into the full `config.say.text` envelope
- **Plural/singular normalisation:** `resource_type: "flow"` or `"flows"` both work
- **Cache-first reads:** `cognigy_get` serves from a 5-min TTL filesystem cache; writes are always fresh
- **Conflict detection:** `push_code_node` compares the remote node against a local snapshot and blocks if the Cognigy UI has been edited since the last push
- **Auto-resync:** If a session has been idle > 4 hours, the server silently re-syncs state before the next tool call

### State storage

Per-project state lives in `~/.config/cognigy-mcp/<project-id>/` — outside the demo repo. The `cognigy:init-mcp` skill creates this directory, a `.cognigy-mcp` symlink in the project root, and the `.claude/mcp.json` entry.

### Reference docs

The `explain` tool carries a 20-topic in-server reference library (node creation patterns, xApp delivery, extension map, voice gateway setup, CXone outbound trigger, etc.). Access via `explain("topic")`. The full topic list is front-loaded in the tool description — no tool call needed to see what's available.

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

## Reference Docs

**Location:** `docs/`

Reference docs contain domain knowledge used by skills and the MCP server's `explain` tool:

| File | Purpose |
|---|---|
| `docs/cognigy-api-reference.md` | Runtime objects (`input`, `context`, `profile`), all `api.*` functions, available libraries |
| `docs/cognigy-output-formats.md` | Channel output structures and code examples |
| `docs/cognigy-code-conventions.md` | Code node structural conventions |
| `docs/cognigy-agent-patterns.md` | Tool design patterns, two-pass confirmation, context schema |
| `docs/cognigy-capabilities.md` | Platform reference for demo scoping |
| `docs/agent-prompting-guide.md` | Persona field purposes, outcome-based framing, tool descriptions as contracts |

Skills read these files before generating content:
> "Before writing any code, read `<plugin-root>/docs/cognigy-api-reference.md` ..."

The plugin root is derived from the `Base directory for this skill:` path injected at skill load time — two directories up from the skill file.

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
