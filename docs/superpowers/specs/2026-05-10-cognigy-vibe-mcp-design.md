# cognigy-vibe-mcp — Design Spec

**Date:** 2026-05-10  
**Status:** Approved for implementation planning  
**Branch:** `cognigy-vibe-mcp-design`

---

## Background

Five demo builds (IAG/Allianz, Bunnings, Virgin, CBA, RHCNZ) produced an incrementally evolved local Python MCP server for building Cognigy AI agent demos. Each build copy-pasted the previous `server.py` and added tools ad-hoc:

| Build | Location | Server lines |
|---|---|---|
| IAG + Allianz | `~/repos/insurance-demo-site/cognigy-mcp/` | 1,141 |
| Bunnings | No local MCP (CLI-only) | — |
| Virgin | `~/working/virgin/virgin-cognigy-demo/cognigy-mcp/` | 1,422 |
| CBA | `~/working/cba/cognigy-on-the-tools/cognigy-mcp/` | 1,423 |
| RHCNZ | `~/working/rhcnz/cognigy-mcp/` | 1,430 |

Core patterns (cache-first, file-first, state.json as source-of-truth, escalation protocol) were present from day one and remained stable. Growth was purely additive. This spec designs the canonical, distributable version that replaces the copy-paste cycle.

The existing `cognigy-claude-plugin` CLI + atomic skills architecture is **not** the primary interface for demo builds. The MCP server is. This spec is MCP-first.

---

## Goals

1. Single canonical `cognigy-vibe-mcp` that ships with this repo and is installable standalone via `uvx`
2. Token efficiency: reduce per-session API call overhead, smarter caching, server-side conflict detection
3. Clean project directories: no MCP infrastructure files committed to demo repos
4. Extensible without interface churn: new resource types and explain topics don't require tool interface changes

---

## Non-Goals

- Exhaustive implementation of all Cognigy API endpoints (the generic `cognigy_get`/`cognigy_list`/`cognigy_invoke` tools cover the long tail; specific tooling is added as needed)
- Replacing the official `@cognigy/mcp-server` (read-only, different purpose)
- Supporting non-stdio transports in v1

---

## Package Identity

| | Value |
|---|---|
| PyPI package name | `cognigy-vibe-mcp` |
| MCP server name (Claude sees) | `cognigy-vibe` |
| Entry point | `uvx cognigy-vibe-mcp` |
| Repo location | `cognigy-mcp/` in this repo |
| Python minimum | 3.11 |
| Runtime manager | `uv` exclusively |

---

## Architecture

### Package Structure

```
cognigy-mcp/
├── pyproject.toml
├── cognigy_mcp/
│   ├── __init__.py
│   ├── server.py          # ~200 lines — MCP server init + tool registration
│   ├── api.py             # httpx client, auth, retry, AU1 domain derivation
│   ├── cache.py           # TTL cache, stale detection, code-node snapshots
│   ├── state.py           # config-dir management, seed merge, interaction timestamp
│   └── tools/
│       ├── __init__.py
│       ├── flow_ops.py    # cognigy_get/list/create/update/delete/invoke, get_flow_chart
│       ├── file_push.py   # push_code_node, push_html_node, push_tool_from_file
│       ├── testing.py     # talk_to_agent
│       ├── state_tools.py # sync_remote_state, get_build_state, resolve_resource
│       └── explain.py     # explain() with front-loaded topic library
```

`server.py` imports tool registrations from each `tools/` module and wires them to the MCP `Server` instance. It is the only entry point.

---

## State & Config Directory

### Per-Project Config Dir

All MCP runtime state lives outside the demo project repo:

```
~/.config/cognigy-mcp/<cognigy-project-id>/
├── .state-seed.json       # committed baseline copied in by init skill
├── .state.json            # runtime name→ID map (never committed)
├── last-interaction       # timestamp touched on every tool call
└── cache/
    ├── flows/<id>.json
    ├── aiagents/<id>.json
    ├── endpoints/<id>.json
    └── nodes/<node-id>/
        └── code.js        # snapshot of last successfully pushed content
```

The Cognigy project ID is the key — one config dir per Cognigy project, shared across any Claude session or CWD that targets the same project.

### Project Dir

The demo repo stays clean:

```
my-demo-project/
├── code-nodes/            # editable source, committed to git
│   └── payment.js
├── .cognigy-mcp           # symlink → ~/.config/cognigy-mcp/<project-id>/
└── .gitignore             # includes .cognigy-mcp
```

`code-nodes/` is user-editable source code, version-controlled. The symlink provides convenient access to state and cache without polluting the repo.

### Init Skill (`cognigy:init-mcp`)

First-time setup per project:

1. Creates `~/.config/cognigy-mcp/<project-id>/`
2. Copies `.state-seed.json` from CWD into config dir if present; otherwise creates an empty one (user populates stable IDs after first `sync_remote_state`)
3. Creates `.cognigy-mcp` symlink in CWD
4. Appends `.cognigy-mcp` to `.gitignore`
5. Writes `cognigy-vibe` MCP server entry to `.claude/mcp.json`

---

## Caching & Staleness

### General Resource Cache

- 5-minute TTL on all fetched resources
- Cache stored at `~/.config/cognigy-mcp/<project-id>/cache/<type>/<id>.json`
- Transparent to caller: responses include `"_source": "cache"` or `"api"`
- Write-through: every successful API response updates cache
- `cognigy_update` pre-fetches fresh state if cache is stale before writing; blocks on conflict

### Code-Node Snapshot Cache

The config dir maintains a snapshot of the last successfully pushed content for each code node. This enables server-side conflict detection without LLM involvement:

```
push_code_node("code-nodes/payment.js", node_id, flow_id)
  1. Read local file content
  2. Fetch remote node (cache-first, 5-min TTL)
  3. Compare remote config.code vs cache/nodes/<id>/code.js
     → match:    remote unchanged since last push → safe to write
     → mismatch: edited in Cognigy UI → show diff, block, return warning
  4. PATCH remote with file content
  5. Update cache/nodes/<id>/code.js with new content
  6. Return success + character diff summary
```

No hash parameter. No LLM involvement in the integrity check.

### Auto-Resync on Stale Session

On every tool call, `state.py` reads `last-interaction` and compares to now. If delta exceeds threshold (default: 4 hours, configurable via `COGNIGY_VIBE_RESYNC_HOURS`), `sync_remote_state()` runs silently before the tool executes. The LLM sees `"auto_synced": true` in the response — no extra tool call required.

---

## Tool Set (15 tools)

### State & Sync
| Tool | Purpose |
|---|---|
| `sync_remote_state` | Hard reset: wipe cache, repopulate all flows/agents/endpoints/tools from remote |
| `get_build_state` | Return `.state.json` — current name→ID mappings |
| `resolve_resource` | Fast lookup by name from `.state.json` (no API call) |

### Flow Operations
| Tool | Purpose |
|---|---|
| `cognigy_get` | GET any resource, cache-first |
| `cognigy_list` | List resources; supports agent-scoped queries |
| `cognigy_create` | POST any resource; auto-saves to `.state.json` |
| `cognigy_update` | PATCH with pre-validation and optional `merge_config` deep-merge |
| `cognigy_delete` | DELETE any resource including nodes (sub-resources pass parent ID as param) |
| `cognigy_invoke` | Named operations: move, clone, train, restore, inject, search, etc. |
| `get_flow_chart` | Full chart with relations array + human-readable hierarchy |

`cognigy_delete_node` and `cognigy_move_node` from earlier builds are absorbed into `cognigy_delete` and `cognigy_invoke` respectively. Node-specific routing is handled internally by `api.py`.

### File Push
| Tool | Purpose |
|---|---|
| `push_code_node` | Read local `.js`/`.ts`, conflict-check, PATCH node `config.code` |
| `push_html_node` | Read local `.html`, PATCH node `config.html`, set `mode="full"` |
| `push_tool_from_file` | Read local JSON tool definition, create or update |

### Testing
| Tool | Purpose |
|---|---|
| `talk_to_agent` | Send message to flow via REST endpoint; supports multi-turn |

### Guidance
| Tool | Purpose |
|---|---|
| `explain` | Progressive disclosure reference library (see below) |

---

## `explain` Tool — Progressive Disclosure

The tool's **description field** (read by Claude at session start, zero tool calls) carries the full topic index:

```
Retrieve implementation guidance before brute-forcing or web-searching.

Topics: node-positioning | node-wiring | agent-tool-branch | node-config-update |
        flow-chart-reading | tool-conditions | two-pass-confirm | turn-structure |
        xapp-delivery | cognigyScript | code-node-patterns | voice-gateway |
        outbound-trigger | knowledge-store | endpoint-config | function-execution |
        session-injection

Call explain() for orientation and topic descriptions.
Call explain("topic") for full reference on that topic.
```

### Topic Coverage (v1)

| Topic | Covers |
|---|---|
| `node-positioning` | move, append vs appendChild, insertAfter 500 bug on AU1 |
| `node-wiring` | chart structure, insertion modes, relations array, node ordering |
| `agent-tool-branch` | aiAgentJobTool + code + toolAnswer three-node assembly, appendChild pattern, conditions field, toolResponse.summary |
| `node-config-update` | full-replace semantics, merge pattern, silent field deletion (preview field bug) |
| `flow-chart-reading` | interpreting chart + relations output, node type strings, extension field |
| `tool-conditions` | CognigyScript on condition field, hiding tools from LLM, re-auth pattern |
| `two-pass-confirm` | inter-turn flag management, STOP gate wording, toolResponse.summary placement |
| `turn-structure` | Once/OnFirstTime/Afterwards, context reset prevention, flow close pattern |
| `xapp-delivery` | session init, postMessage bridge, SDK.submit, data paths, session guard pattern |
| `cognigyScript` | interpolation contexts — confirmed vs unconfirmed, payloadJSON behaviour |
| `code-node-patterns` | api.* functions, no fetch/import/require, api.log, bare return bug, deep copy |
| `voice-gateway` | voice config, DTMF, REST vs voice streaming differences |
| `outbound-trigger` | 6-step CXone trigger, Accept-Encoding: identity, script lookup by path |
| `knowledge-store` | chunking, connector run, source management |
| `endpoint-config` | referenceId vs _id gotcha, token lookup, urlToken caching |
| `function-execution` | async pattern, inject-back via sessions API |
| `session-injection` | context/state inject for in-session testing without talk_to_agent |

New topics are added by appending to `explain.py` — no tool interface change required.

---

## Token Efficiency Summary

| Mechanism | Saving |
|---|---|
| Config-dir state eliminates UUID handling | LLM never asks "what's the ID for X" |
| 5-min TTL cache + write-through | Eliminates repeat fetches within session |
| Auto-resync on stale session | Eliminates explicit sync call at session start |
| Code-node snapshot + server-side diff | Eliminates LLM hash computation + retry loops |
| `explain` topics front-loaded in description | Zero tool calls to discover available guidance |
| `cognigy_delete`/`cognigy_invoke` absorb node-specific tools | Reduces tool count LLM must reason about |
| `get_flow_chart` returns readable hierarchy | Eliminates secondary node lookups for structure |

---

## Future Expansion (Not in Scope for v1)

The generic tool set (`cognigy_get`, `cognigy_list`, `cognigy_invoke`) already covers these — they just lack guided explain topics:

- `flows/{flowId}/chart/nodes/search` — node search by type/label
- `flows/{flowId}/chart/nodes/aiagents` — AI agent nodes only
- `sessions/{id}/context/inject` and `state/inject` — direct session manipulation
- `playbooks` — automated test assertions
- `functions` lifecycle management
- `locales` and NLU intent management
- `connections` management

---

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `COGNIGY_API_KEY` | API authentication | required |
| `COGNIGY_BASE_URL` | API base URL | required |
| `COGNIGY_PROJECT_ID` | Target project | required |
| `COGNIGY_VIBE_RESYNC_HOURS` | Auto-resync threshold | `4` |
| `COGNIGY_VIBE_CACHE_TTL` | Cache TTL in seconds | `300` |

Read from `.env` in project CWD or from environment. `state.py` handles discovery.
