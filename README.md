# cognigy-claude-plugin

[![PyPI version](https://img.shields.io/pypi/v/cognigy-vibe-mcp?label=cognigy-vibe-mcp)](https://pypi.org/project/cognigy-vibe-mcp/)
[![Check version bump](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-version-bump.yml/badge.svg)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-version-bump.yml)
[![Check explain topics](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-explain-topics.yml/badge.svg)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-explain-topics.yml)
[![Release (production)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/on-push-main.yml/badge.svg)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/on-push-main.yml)

Cognigy AI agent development skills for [Claude Code](https://docs.claude.com/en/docs/claude-code) — scope, design, build, and smoke-test Cognigy.AI agent demos end-to-end.

> **Active development** — capabilities expand regularly and releases ship frequently.

---

## Installation

### Recommended — all users

Run the setup wizard. It installs `uv` if needed, installs the plugin, and optionally configures your Cognigy credentials for Claude Code and/or Claude Desktop.

**Mac / Linux:**
```bash
bash <(curl -LsSf https://raw.githubusercontent.com/ben-elliot-nice/cognigy-claude-plugin/dev/plugin/bin/cognigy-setup.sh)
```

Or, if you have already cloned the repo:
```bash
bash plugin/bin/cognigy-setup.sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File plugin\bin\cognigy-setup.ps1
```

**Wizard defaults:** installs + configures, both Claude Code and Desktop (if Desktop is detected), user scope.

**Wizard options (pass as flags):**
- `--install-only` — skip credential collection
- `--client code|desktop|both`
- `--scope user|project|local`

After setup, open Claude Code or restart Claude Desktop. On the first tool call you will be prompted through onboarding.

---

### Advanced — uv already installed, Code only

Prerequisites: [install uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
claude plugin marketplace add ben-elliot-nice/cognigy-claude-plugin
claude plugin install cognigy-vibe@cognigy-vibe
```

Create a `.env` in your project root:
```
COGNIGY_BASE_URL=https://cognigy-api-au1.nicecxone.com
COGNIGY_API_KEY=<your-api-key>
COGNIGY_PROJECT_ID=<your-project-id>   # optional — set later via sync_remote_state
```

Run `claude` from the project directory. The server finds `.env` automatically.

---

## What it does

The plugin pairs two layers: **skills** provide the workflow knowledge — how to interview, scope, design a persona, lay out an init chain, shape tool branches, and verify the result. **`cognigy-vibe-mcp`** is the execution layer: an MCP server wrapping the Cognigy REST API for node creation, flow inspection, code push with conflict detection, and live session testing. A skill decides *what* to build; the MCP server *does* it against your Cognigy project.

The entry point is `cognigy-vibe:build-orchestrator` — a single-batch interview that drives scoping, design, build, and an automated smoke test, handing back only when structural and runtime checks are green.

---

## Skills

| Skill | Purpose |
|---|---|
| [`build-orchestrator`](plugin/skills/build-orchestrator/SKILL.md) | **End-to-end demo builder.** Interview → scope → design → build → smoke-test, driving the full plugin stack. |
| [`scope-demo`](plugin/skills/scope-demo/SKILL.md) | Four-phase conversational workflow — discovery, design, structured demo-plan generation (12 facts). |
| [`design-agent`](plugin/skills/design-agent/SKILL.md) | Orchestrates the four design sub-skills below. |
| [`design-agent-persona`](plugin/skills/design-agent-persona/SKILL.md) | Identity & standing orders — brand voice, compliance framing, channel formatting, auth scope. |
| [`design-agent-jobs`](plugin/skills/design-agent-jobs/SKILL.md) | Specialist jobs, routing architecture, and context schema. |
| [`design-agent-interfaces`](plugin/skills/design-agent-interfaces/SKILL.md) | Touchpoints outside the chat window — xApp scenes, webchat patterns, live-agent handover. |
| [`design-agent-contracts`](plugin/skills/design-agent-contracts/SKILL.md) | Deterministic enforcement layer — guard sub-flows, obligation state, structured refusals. |
| [`add-aiagent-job`](plugin/skills/add-aiagent-job/SKILL.md) | Add an AI Agent Job node (+ optional tool nodes) to an existing flow. |
| [`init-cognigy-vibe`](plugin/skills/init-cognigy-vibe/SKILL.md) | **First-time setup wizard.** Captures every build variable once (API URL + key, LLM refs, TTS, STT, voice channel, voice preview, naming) → `.env` + `default-demo-config.json` at the `Demo Builds` workspace root. Run before your first build; `build-orchestrator` S0.0 loads it and binds projects with no restart. |
| [`explain`](plugin/skills/explain/SKILL.md) | Retrieve implementation guidance for Cognigy topics before brute-forcing or web-searching. |
| [`submit-issue`](plugin/skills/submit-issue/SKILL.md) | File a bug against this plugin (MCP server or a skill). |

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

> The `cognigy-vibe-mcp` PyPI package is the MCP server only — narrower in scope than this repository, which also contains the Claude Code skills, hooks, and marketplace manifest that pair with it. See [cognigy-mcp/README.md](cognigy-mcp/README.md) for the server's own docs.

---

## Development

### Dev setup

1. `mise trust` (once per clone).
2. `cp .env.example .env` and fill in your Cognigy credentials.
3. [`.mcp.json`](.mcp.json) is pre-configured for dev mode — `COGNIGY_VIBE_DEV=1` and `COGNIGY_VIBE_SOURCE_DIR=./cognigy-mcp` are baked in. Start Claude Code and it picks up local source automatically. See [Local Development Testing](CLAUDE.md#local-development-testing) for details.

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

### Repository layout

```
.claude-plugin/marketplace.json   marketplace definition (self-referential)
plugin/                           plugin content installed by Claude Code
  .claude-plugin/plugin.json        plugin manifest (name, version)
  bin/                              setup wizard bootstrap scripts (cognigy-setup.sh / .ps1)
  skills/                           one directory per skill, each a SKILL.md
cognigy-mcp/                      the cognigy-vibe-mcp Python server (+ tests, own README)
docs/                             plugin-development docs (architecture, rename-impact, design specs)
scripts/                          explain-topic build tooling
.githooks/                        pre-commit hook (GitGuardian)
.github/workflows/                CI: version-bump check, explain-topic check, prerelease + production release
```

### Maintainers

Ben Elliot — [ben.elliot@nice.com](mailto:ben.elliot@nice.com)
Ben Hancock — [ben.hancock@nice.com](mailto:ben.hancock@nice.com)
