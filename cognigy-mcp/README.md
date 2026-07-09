# cognigy-vibe-mcp

A local Python MCP server for building Cognigy AI agent demos with Claude Code. Covers the full Cognigy REST API surface — node creation, flow inspection, code push with conflict detection, session testing, and a 20-topic reference library.

Part of the [cognigy-claude-plugin](https://github.com/ben-elliot-nice/cognigy-claude-plugin) — this package is the MCP server; the plugin repo also ships the Claude Code skills that drive it.

## Installation

```bash
uv tool install cognigy-vibe-mcp                        # stable
uv tool install cognigy-vibe-mcp --prerelease allow     # latest RC prerelease
uvx cognigy-vibe-mcp==1.7.0rc1                          # specific RC (check PyPI for latest)
```

## Setup CLI (`cognigy-vibe-setup`)

Installing this package also installs `cognigy-vibe-setup`, a CLI that manages the companion Claude Code plugin — marketplace entry, plugin install/uninstall, and the Claude Desktop config version pin. It's separate from the MCP server process itself.

```bash
cognigy-vibe-setup                 # install — default when no subcommand is given
cognigy-vibe-setup install         # explicit alias for the default
cognigy-vibe-setup status          # report drift across marketplace/plugin/Desktop pins; no changes
cognigy-vibe-setup status --fix    # same check, applies fixes; never touches PyPI or upgrades the package
cognigy-vibe-setup update          # check PyPI for a newer cognigy-vibe-mcp, upgrade if stale, then reconcile
cognigy-vibe-setup update --check  # dry-run of update — reports drift, changes nothing
cognigy-vibe-setup uninstall       # reverse install: plugin, Desktop config entry, optionally credentials
```

| Flag | Applies to | Description |
|---|---|---|
| `--install-only` | `install` | Skip credential collection; install the plugin only. |
| `--client code\|desktop\|both` | `install` | Which client(s) to configure (default: both if Desktop is detected, else code). |
| `--scope user\|project\|local` | `install` | Plugin install scope for Claude Code (default: user). |
| `--verbose` | all subcommands | Stream subprocess output instead of hiding it behind a status line; show a full traceback instead of a short message on failure. |

`uninstall` always prompts before deleting `~/.config/cognigy-vibe/.env` — credentials are the one step that is never non-interactive, regardless of flags.

## Quick start

Run `cognigy:init-cognigy-vibe` in Claude Code to capture your Cognigy credentials and build defaults. It writes `.env` at your workspace root and `~/.config/cognigy-vibe/config.json` globally. No restart required.

If credentials aren't configured yet, the server starts in degraded mode — all tools are visible but every call returns setup guidance until you create a `.env`. Once the file exists, retry the same tool call and it executes immediately without restarting.

Once connected, call `sync_remote_state` to populate state from your Cognigy project.

## Manual configuration

Add to `.mcp.json` at your project root:

```json
{
  "mcpServers": {
    "cognigy-vibe": {
      "command": "uvx",
      "args": ["cognigy-vibe-mcp"]
    }
  }
}
```

Credentials are read from a `.env` file in the project root (see Environment variables below). If no `.env` exists, the server starts in degraded mode — all tools are visible but calls return setup guidance until credentials are configured.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `COGNIGY_BASE_URL` | Yes | — | Cognigy API base URL (e.g. `https://cognigy-api-au1.nicecxone.com`) |
| `COGNIGY_API_KEY` | Yes | — | API key from Cognigy UI → My Profile → API Keys |
| `COGNIGY_PROJECT_ID` | No | — | Default project; can be set later via `sync_remote_state` |
| `COGNIGY_VIBE_RESYNC_HOURS` | No | `4` | Hours of idle before auto-resync |
| `COGNIGY_VIBE_CACHE_TTL` | No | `300` | Resource cache TTL in seconds |
| `COGNIGY_VIBE_DEV` | No | — | Set to `1` to enable dev mode (requires credentials configured) |
| `COGNIGY_VIBE_SOURCE_DIR` | No | — | Path to `cognigy-mcp/` source tree; required when `COGNIGY_VIBE_DEV=1`. Relative paths are resolved from CWD (e.g. `./cognigy-mcp` works when Claude Code opens the repo root). |

## Startup modes

The server selects a mode at startup based on the `.env` file in the project root:

| Condition | Mode | Tools available |
|---|---|---|
| `COGNIGY_BASE_URL` or `COGNIGY_API_KEY` missing | Degraded | Full tool set (calls return setup guidance) |
| Both present, `COGNIGY_VIBE_DEV` absent | Production | Full tool set |
| Both present, `COGNIGY_VIBE_DEV=1` | Dev | Full tool set + `reload_mcp` |

In degraded mode every tool call returns guidance on creating `.env` with the correct credentials. Once the file exists, retry the same call — the server restarts to production mode and returns the real response immediately.

Dev mode spawns the inner server from `COGNIGY_VIBE_SOURCE_DIR` via `uv run`. After editing source files, call `reload_mcp` to respawn from updated code in the same Claude session.

## Tools

### State & sync
| Tool | Description |
|---|---|
| `sync_remote_state` | Wipe cache and repopulate from Cognigy remote |
| `get_build_state` | Return name→ID mappings (filterable by resource_type) |
| `resolve_resource` | Fast name→ID lookup from local state (no API call) |

### Flow operations
| Tool | Description |
|---|---|
| `cognigy_get` | GET any resource, cache-first |
| `cognigy_list` | List resources; singular/plural resource_type both accepted |
| `cognigy_create` | POST resource; extension auto-injected, Say config auto-normalised |
| `cognigy_update` | PATCH with always-fresh GET + optional deep merge |
| `cognigy_delete` | DELETE any resource including nodes |
| `cognigy_invoke` | Named operations: move, clone, train, inject, search |
| `get_flow_chart` | Chart with relations array + readable hierarchy string |

### File push
| Tool | Description |
|---|---|
| `push_code_node` | Push local `.js`/`.ts` to a code node with conflict detection |
| `push_html_node` | Push local `.html` to a `setHTMLAppState` node |
| `push_agent_tool` | Create or update a file-backed `aiAgentJobTool` from a `.tool.json` |

### Testing
| Tool | Description |
|---|---|
| `talk_to_agent` | Send a message to a flow via REST endpoint |

### Guidance
| Tool | Description |
|---|---|
| `explain` | 20-topic reference library (see below) |

### Dev
| Tool | Mode | Description |
|---|---|---|
| `reload_mcp` | Dev only | Respawn the inner server from local source after file edits |

## explain topics

Call `explain()` for an overview. Call `explain("topic")` for full details.

`node-positioning` · `node-wiring` · `agent-tool-branch` · `node-config-update` · `flow-chart-reading` · `tool-conditions` · `two-pass-confirm` · `turn-structure` · `xapp-delivery` · `cognigyScript` · `code-node-patterns` · `voice-gateway` · `outbound-trigger` · `knowledge-store` · `endpoint-config` · `function-execution` · `session-injection` · `extension-map` · `node-types` · `mcp-comparison`

Topics are front-loaded in the tool description — no tool call needed to see what's available.

## Key behaviours

- **Extension auto-injection** — `cognigy_create` injects `extension` for all known node types: `@cognigy/voicegateway2` for `setSessionConfig`/`hangup`, `cognigy-ai-agent` for AI agent nodes, `cxone-utils` for xApp nodes
- **Say node normalisation** — `config: { text: "Hello" }` is automatically wrapped into the full `config.say.text` envelope
- **Conflict detection** — `push_code_node` snapshots the last-pushed content and blocks if the Cognigy UI has been edited since
- **Auto-resync** — sessions idle longer than the threshold are silently re-synced before the next tool call
- **Atomic writes** — state and cache files use write-to-tmp-then-replace to survive process interrupts
- **Graceful degraded mode** — server always starts; missing credentials surface the `init` tool instead of crashing

## Development

```bash
git clone https://github.com/ben-elliot-nice/cognigy-claude-plugin
cd cognigy-claude-plugin/cognigy-mcp
uv sync --extra dev
uv run pytest tests/ -v
```

To develop against local source with hot-reload, the repo's `.mcp.json` already sets `COGNIGY_VIBE_DEV=1` and `COGNIGY_VIBE_SOURCE_DIR=./cognigy-mcp` — no `.env` additions needed. Ask Claude to call `reload_mcp` after editing source files — the server respawns from updated code without a terminal restart.
