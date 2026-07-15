# Cognigy Claude Plugin — Architecture

## Overview

This plugin gives Claude Code structured access to the Cognigy API for building AI agent demos. It is built in two layers: a Python MCP server and a set of composite skills.

```
Composite skills       design-agent-*, init-cognigy-vibe, scope-demo
      ↓ call MCP tools
cognigy-vibe MCP       cognigy_create, cognigy_update, get_flow_chart, push_code_node, explain ...
      ↓ calls
Cognigy REST API
```

---

## Layer 1: cognigy-vibe MCP Server

**Location:** `cognigy-vibe-mcp/`  
**Package:** `cognigy-vibe-mcp` (PyPI)  
**Install:** `uvx cognigy-vibe-mcp`  
**Server name (Claude sees):** `cognigy-vibe`

The MCP server is the only thing that talks to the Cognigy API. It handles authentication, per-project state management, filesystem cache, and conflict detection. Skills call MCP tools — they never make HTTP requests directly.

### Tools (20 total: 19 always registered + 1 dev-only)

| Group | Tools |
|---|---|
| State & sync | `sync_remote_state`, `get_build_state`, `resolve_resource`, `assign_org_llm` |
| Flow ops | `cognigy_get`, `cognigy_list`, `cognigy_create`, `cognigy_update`, `cognigy_delete`, `cognigy_invoke`, `get_flow_chart` |
| File push | `push_code_node`, `push_html_node`, `push_agent_tool`, `push_agent_avatar`, `export_package` |
| Voice | `provision_webrtc_endpoint` |
| Testing | `talk_to_agent` |
| Guidance | `explain` |
| Dev only | `reload_mcp` (gated on `COGNIGY_VIBE_DEV=1`) |

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
| `server.py` | MCP server wiring, degraded/full/dev mode selection, config cascade (`_find_config_file`), auto-resync middleware, tool dispatch |
| `api.py` | `CognigyClient` — thin httpx wrapper; derives endpoint URL from base URL |
| `state.py` | `ProjectState` — name→ID mappings, seed/runtime merge, interaction timestamp |
| `cache.py` | `Cache` — filesystem TTL cache for resource JSON + code node snapshots |
| `config.py` | Path constants — `CONFIG_BASE` (`~/.config/cognigy-vibe`), `USER_ENV_PATH` (`CONFIG_BASE/.env`), `SETUP_META_PATH` (`CONFIG_BASE/.setup-meta.json`); `CONFIG_SCHEMA_VERSION` for the on-disk layout version |
| `filters.py` | `strip_response` — removes internal fields (`__v`, `transpiled`) from API responses |
| `validation.py` | `validate()` / `make_schema()` — Pydantic-model argument validation shared across tool handlers |
| `launcher.py` | `cognigy-vibe-launch` console-script entry point — resolves installed package version, hands off to `orchestrator.main()` |
| `orchestrator.py` | Outer supervisor process — spawns/monitors the inner server subprocess, handles the dev-mode restart protocol (rc=42 sentinel), logs to `~/.config/cognigy-vibe/logs/` |
| `migrate.py` | `safe_move()` — best-effort, race-safe file move used by layout migrations |
| `setup.py` | `cognigy-vibe-setup` console-script entry point — `install`/`status`/`update`/`uninstall` subcommands |
| `reconcile.py` | `SetupState`/`DriftIssue` dataclasses, `gather_state()`/`diff_state()`/`apply_fixes()`, `check_pypi_latest()` — drift detection and reconciliation backing `status`/`update` |
| `wizard_ui.py` | `rich`-based terminal presentation helpers (`print_header`, `print_section`, `print_summary`, `print_drift_table`, `print_step`, `print_error_panel`) and `run_subprocess()`/`StepFailure` — shared UI layer for all `setup.py` subcommands |
| `tools/state_tools.py` | `sync_remote_state`, `get_build_state`, `resolve_resource`, `assign_org_llm` |
| `tools/flow_ops.py` | CRUD ops, normalisation logic, `get_flow_chart` hierarchy renderer, `cognigy_invoke` operation routing |
| `tools/file_push.py` | `push_code_node`/`push_html_node` (conflict detection), `push_agent_tool`, `push_agent_avatar`, `export_package` |
| `tools/voice_ops.py` | `provision_webrtc_endpoint` — VoiceGateway webRTC endpoint provisioning with real/dummy Azure Speech connection path |
| `tools/testing.py` | `talk_to_agent` — REST endpoint test harness |
| `tools/explain.py` | `explain` — 51-key tiered reference library (6 groups, 45 leaf topics) |
| `tools/dev_tools.py` | `reload_mcp` — dev-mode server respawn signal |

### State storage

`~/.config/cognigy-vibe/` holds config/credentials at its root and generated data under `logs/` and `cache/`:

```
~/.config/cognigy-vibe/
├── config.json           # user config (root)
├── .env                   # credentials (root)
├── logs/
│   └── cognigy-vibe-mcp-{version}.log
└── cache/
    └── <project-id>/
        ├── .state.json          # runtime name→ID mappings (written by sync_remote_state)
        ├── .state-seed.json     # optional seed defaults (merged under runtime state)
        ├── last-interaction     # epoch timestamp — drives auto-resync threshold
        └── cache/               # filesystem TTL cache
            ├── flows/           # resource JSON by ID
            ├── nodes/           # resource JSON + code snapshots (code.js per node)
            └── ...
```

State is loaded at startup by deep-merging seed into runtime. `sync_remote_state` populates `flows`, `agents`, `endpoints`, and `tools` categories. `resolve_resource` and `get_build_state` read from this without making API calls. The `~/.config/cognigy-vibe/cache/<project-id>/` directory is auto-created by the MCP server on first use of any stateful tool for that project. Existing installs on the pre-#171 flat layout are migrated automatically on first run.

### Config file cascade

`server.py`'s `_find_config_file()` resolves the active `default-demo-config.json` at startup by walking from `cwd` up through ancestor directories, then falling back to `~/.config/cognigy-vibe/config.json`. The first file found wins — there is no merging across levels. A malformed or unreadable candidate is skipped with a stderr message (distinguishing `JSONDecodeError` from `OSError`) rather than aborting the walk. `COGNIGY_PROJECT_ROOT` is a separate mechanism: it controls where `.env` is read from and does not participate in this cascade.

### Reference docs (runtime guidance)

The `explain` tool carries a 51-key tiered reference library — 6 top-level groups (aiagent, code, nodes, platform, voice, xapp), each expanding to its own set of leaf topics, 45 leaf topics in total (node creation patterns, xApp delivery, extension map, voice gateway setup, CXone outbound trigger, etc.). Access via `explain("group")` to see a group's primer plus its child topic list, then `explain("topic")` to drill into a specific leaf. The tool description still enumerates every key up front, but the no-arg `explain()` response itself only surfaces the 6 group names — a drill-down call is required to see any group's topics.

Topic source files live at `plugin/skills/explain/resources/` and are compiled into the MCP server by `scripts/build_explain_topics.py`. Edit the resource markdown files and re-run the script to update both the skill and the in-server library.

---

## Layer 2: Composite Skills

**Location:** `plugin/skills/`

Skills orchestrate MCP tool calls and user interaction to accomplish higher-level goals. They call MCP tools by name — never make API calls directly.

| Skill | Purpose |
|---|---|
| `cognigy-vibe:scope-demo` | Four-phase discovery → demo plan document |
| `cognigy-vibe:design-agent` | Orchestrate full agent design workflow |
| `cognigy-vibe:design-agent-persona` | Agent identity, brand voice, compliance framing |
| `cognigy-vibe:design-agent-jobs` | Job definitions, routing architecture, context schema |
| `cognigy-vibe:design-agent-interfaces` | xApp scenes, webchat patterns, handover context |
| `cognigy-vibe:design-agent-contracts` | Guard sub-flows, obligation state, structured refusals |

`cognigy-vibe:scope-demo` has a `references/` subdirectory (`plugin/skills/scope-demo/references/`) containing `cognigy-capabilities.md`, `scope-demo-discovery-questions.md`, and `scope-demo-output-template.md` — referenced at runtime by the skill.

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

## Design docs and specs

**Location:** `docs/`

| File | Purpose |
|---|---|
| `docs/architecture.md` | System architecture overview |

---

## Plugin registration

**Marketplace manifest:** `.claude-plugin/marketplace.json` — defines the `cognigy-vibe` marketplace, pointing to `./plugin`.

**Plugin manifest:** `plugin/.claude-plugin/plugin.json` — declares the plugin name (`cognigy-vibe`), description, version, and author. Version must be bumped (patch) on every change to `plugin/`.

---

## Adding a New MCP Tool

1. Add a `Tool` definition to the relevant module in `cognigy-vibe-mcp/cognigy_mcp/tools/`
2. Add a handler function and register it in `make_handlers()`
3. Add tests in `cognigy-vibe-mcp/tests/tools/`
4. If it covers new Cognigy API patterns, add an `explain` topic: a markdown file under `plugin/skills/explain/resources/<group>/` (with `topic:`+`description:` frontmatter), then re-run `scripts/build_explain_topics.py` to recompile it into both `SKILL.md` and `explain.py`'s in-server library
5. Bump the patch version in `cognigy-vibe-mcp/pyproject.toml` and `plugin/.claude-plugin/plugin.json`

For new node types, add the type → extension mapping to `_NODE_EXTENSION_MAP` in `flow_ops.py` — no other changes needed.

---

## Adding a New Composite Skill

1. Identify which MCP tools it will call
2. Write `plugin/skills/<skill-name>/SKILL.md` — call MCP tools by name, never construct HTTP requests
3. Register it in `plugin/.claude-plugin/plugin.json`
4. Bump the patch version in `plugin/.claude-plugin/plugin.json`
