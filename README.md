# cognigy-claude-plugin

[![PyPI version](https://img.shields.io/pypi/v/cognigy-vibe-mcp?label=cognigy-vibe-mcp)](https://pypi.org/project/cognigy-vibe-mcp/)
[![Check version bump](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-version-bump.yml/badge.svg)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-version-bump.yml)
[![Check explain topics](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-explain-topics.yml/badge.svg)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-explain-topics.yml)
[![Publish to PyPI](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/publish.yml/badge.svg)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/publish.yml)

Cognigy AI agent development skills for [Claude Code](https://docs.claude.com/en/docs/claude-code) — scope, design, build, and smoke-test Cognigy.AI agent demos end-to-end.

> **Active development** — capabilities expand regularly and releases ship frequently.

---

## Install

### Marketplace (recommended)

1. Add the NiCE marketplace and install the plugin:
   ```bash
   claude marketplace add ben-elliot-nice/nice-claude-marketplace
   claude plugin install cognigy@nice
   ```
3. Install the MCP server:
   ```bash
   uv tool install cognigy-vibe-mcp
   ```
4. In your demo project directory, run the `cognigy:init-mcp` skill to wire up state, cache, and the MCP entry.
5. Restart Claude Code, then ask: *"Build me a Cognigy demo for \<customer\>."*

### Clone + local dev

For contributors running from source — the repo is configured to run the MCP server directly, no install step required.

1. Clone this repo.
2. `mise trust` (once per clone) so `mise` auto-sources `.env`.
3. Copy `.env.example` to `.env` and fill in your Cognigy credentials:
   ```
   COGNIGY_BASE_URL=https://cognigy-api-au1.nicecxone.com
   COGNIGY_API_KEY=your-api-key-here
   COGNIGY_PROJECT_ID=your-project-id-here
   ```
4. [`.mcp.json`](.mcp.json) is pre-configured — Claude Code will pick it up on next start.

See the [Development](#development) section for the full contributor workflow.

### MCP server only

If you want the Cognigy API tools without the skills workflow:

1. Install the server:
   ```bash
   uv tool install cognigy-vibe-mcp
   ```
2. Add an entry to your project's `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "cognigy-vibe": {
         "command": "uvx",
         "args": ["cognigy-vibe-mcp"],
         "env": {
           "COGNIGY_BASE_URL": "https://cognigy-api-au1.nicecxone.com",
           "COGNIGY_API_KEY": "your-api-key-here",
           "COGNIGY_PROJECT_ID": "your-project-id-here"
         }
       }
     }
   }
   ```

---

## What it does

The plugin pairs two layers: **skills** provide the workflow knowledge — how to interview, scope, design a persona, lay out an init chain, shape tool branches, and verify the result. **`cognigy-vibe-mcp`** is the execution layer: an MCP server wrapping the Cognigy REST API for node creation, flow inspection, code push with conflict detection, and live session testing. A skill decides *what* to build; the MCP server *does* it against your Cognigy project.

The entry point is `cognigy:build-orchestrator` — a single-batch interview that drives scoping, design, build, and an automated smoke test, handing back only when structural and runtime checks are green.

---

## Skills

| Skill | Purpose |
|---|---|
| [`build-orchestrator`](skills/build-orchestrator/SKILL.md) | **End-to-end demo builder.** Interview → scope → design → build → smoke-test, driving the full plugin stack. |
| [`scope-demo`](skills/scope-demo/SKILL.md) | Four-phase conversational workflow — discovery, design, structured demo-plan generation (12 facts). |
| [`design-agent`](skills/design-agent/SKILL.md) | Orchestrates the four design sub-skills below. |
| [`design-agent-persona`](skills/design-agent-persona/SKILL.md) | Identity & standing orders — brand voice, compliance framing, channel formatting, auth scope. |
| [`design-agent-jobs`](skills/design-agent-jobs/SKILL.md) | Specialist jobs, routing architecture, and context schema. |
| [`design-agent-interfaces`](skills/design-agent-interfaces/SKILL.md) | Touchpoints outside the chat window — xApp scenes, webchat patterns, live-agent handover. |
| [`design-agent-contracts`](skills/design-agent-contracts/SKILL.md) | Deterministic enforcement layer — guard sub-flows, obligation state, structured refusals. |
| [`add-aiagent-job`](skills/add-aiagent-job/SKILL.md) | Add an AI Agent Job node (+ optional tool nodes) to an existing flow. |
| [`init-mcp`](skills/init-mcp/SKILL.md) | Set up `cognigy-vibe-mcp` for a new demo project. Run once per project. |
| [`explain`](skills/explain/SKILL.md) | Retrieve implementation guidance for Cognigy topics before brute-forcing or web-searching. |
| [`submit-issue`](skills/submit-issue/SKILL.md) | File a bug against this plugin (MCP server or a skill). |

---

## MCP server — `cognigy-vibe-mcp`

A local Python MCP server (full docs: [cognigy-mcp/README.md](cognigy-mcp/README.md)) exposing the Cognigy REST API surface plus a reference library. Install with `uv tool install cognigy-vibe-mcp`.

| Tool | Role |
|---|---|
| `cognigy_list` / `cognigy_get` / `cognigy_create` / `cognigy_update` / `cognigy_delete` | Generic CRUD over Cognigy resources. |
| `cognigy_invoke` | Named non-CRUD operations (clone, inject, etc.). |
| `resolve_resource` | Resolve a name/reference to a canonical resource. |
| `push_code_node` | Create + position + push a Code node in one call. |
| `push_agent_tool` | File-backed `aiAgentJobTool` create/update (author `.tool.json`, then push). |
| `push_html_node` | Push xApp HTML moments. |
| `get_flow_chart` | Read the live flow as a node hierarchy (used for as-built docs + verification). |
| `get_build_state` | Inspect tracked build state. |
| `sync_remote_state` | Bind a project and populate local state from Cognigy. |
| `talk_to_agent` | Drive a live session for smoke testing. |
| `explain` | Topic reference library (node positioning, say-node schema, xApp events, knowledge store, …). |

---

## Development

### Dev setup

The repo runs `cognigy-vibe-mcp` from source via a hot-reload proxy — no install step needed.

1. `mise trust` (once per clone).
2. `cp .env.example .env` and fill in your Cognigy credentials.
3. [`.mcp.json`](.mcp.json) is pre-configured to run the server via `uv run`.
4. After source changes to `cognigy-mcp/`, reload the inner server without disconnecting Claude Code:
   ```bash
   bash scripts/restart-mcp.sh
   ```

### Contributing

- Branch from `origin/main` (not local main):
  ```bash
  git checkout -b feat/<name> origin/main
  ```
- After any change to `cognigy-mcp/` or `skills/`, bump the version in **both** [`cognigy-mcp/pyproject.toml`](cognigy-mcp/pyproject.toml) and [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) — patch increment by default (e.g. `1.4.2` → `1.4.3`). CI enforces this on PRs to `main`.
- **Composite skills call atomic MCP tools** (`cognigy_get`, `cognigy_create`, …) — never hardcode `npx tsx` CLI calls in a skill.
- PR to `main`. On merge, the release pipeline notifies `nice-claude-marketplace` to update its submodule reference automatically.
- See [CLAUDE.md](CLAUDE.md) for the full development workflow (planning, subagent-driven implementation, PR + CI flow).

### Repository layout

```
.claude-plugin/plugin.json   plugin manifest (name, version)
skills/                      one directory per skill, each a SKILL.md
cognigy-mcp/                 the cognigy-vibe-mcp Python server (+ tests, own README)
runtime-reference/           runtime docs skills read before writing code
                             (API reference, code conventions, output formats)
docs/                        plugin-development docs (architecture, patterns, design specs)
scripts/                     mcp-proxy.py, restart-mcp.sh, explain-topic build tooling
hooks/ .githooks/            onboarding gate + pre-commit hook
.github/workflows/           CI: version-bump check, explain-topic check, publish, release
```

### Maintainers

Ben Elliot — [ben.elliot@nice.com](mailto:ben.elliot@nice.com)
