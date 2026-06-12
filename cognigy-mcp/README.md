# cognigy-vibe-mcp

A local Python MCP server for building Cognigy AI agent demos with Claude Code. Provides 15 tools covering the full Cognigy REST API surface — node creation, flow inspection, code push with conflict detection, session testing, and a 20-topic reference library.

Part of the [cognigy-claude-plugin](https://github.com/ben-elliot-nice/cognigy-claude-plugin).

## Installation

```bash
uvx cognigy-vibe-mcp
```

Or install permanently:

```bash
uv tool install cognigy-vibe-mcp
```

## Quick start

In your demo project directory, run the `cognigy:init-mcp` skill in Claude Code. It will:

1. Create `~/.config/cognigy-mcp/<project-id>/` for state and cache
2. Create a `.cognigy-mcp` symlink in your project root
3. Write the MCP server entry to `.claude/mcp.json`

Then restart Claude Code and call `sync_remote_state` to populate state from your Cognigy project.

## Manual configuration

Add to `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "cognigy-vibe": {
      "command": "uvx",
      "args": ["cognigy-vibe-mcp"],
      "env": {
        "COGNIGY_BASE_URL": "https://cognigy-api-au1.nicecxone.com",
        "COGNIGY_API_KEY": "<your-api-key>",
        "COGNIGY_PROJECT_ID": "<your-project-id>"
      }
    }
  }
}
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `COGNIGY_BASE_URL` | Yes | — | Cognigy API base URL |
| `COGNIGY_API_KEY` | Yes | — | API key from Cognigy UI → My Profile → API Keys |
| `COGNIGY_PROJECT_ID` | No | — | Default project; prompted if omitted |
| `COGNIGY_VIBE_RESYNC_HOURS` | No | `4` | Hours of idle before auto-resync |
| `COGNIGY_VIBE_CACHE_TTL` | No | `300` | Resource cache TTL in seconds |

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

### Testing
| Tool | Description |
|---|---|
| `talk_to_agent` | Send a message to a flow via REST endpoint |

### Guidance
| Tool | Description |
|---|---|
| `explain` | 20-topic reference library (see below) |

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

## Development

```bash
git clone https://github.com/ben-elliot-nice/cognigy-claude-plugin
cd cognigy-claude-plugin/cognigy-mcp
uv sync --extra dev
uv run pytest tests/ -v
```
