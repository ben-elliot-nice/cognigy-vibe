# cognigy-claude-plugin

[![PyPI version](https://img.shields.io/pypi/v/cognigy-vibe-mcp?label=cognigy-vibe-mcp)](https://pypi.org/project/cognigy-vibe-mcp/)
[![Check version bump](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-version-bump.yml/badge.svg)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-version-bump.yml)
[![Check explain topics](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-explain-topics.yml/badge.svg)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/check-explain-topics.yml)
[![Publish to PyPI](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/publish.yml/badge.svg)](https://github.com/ben-elliot-nice/cognigy-claude-plugin/actions/workflows/publish.yml)

Cognigy AI agent development skills for [Claude Code](https://docs.claude.com/en/docs/claude-code) — scope, design, build, and smoke-test Cognigy.AI agent demos end-to-end.

> **Active development** — capabilities expand regularly and releases ship frequently.

---

## Install

**Prerequisite:** [`uv`](https://docs.astral.sh/uv/getting-started/installation/) must be installed — the plugin uses `uvx` to run the MCP server.

### Direct from GitHub (recommended)

Install with a single command — no marketplace required:

```bash
claude plugin install github:ben-elliot-nice/cognigy-claude-plugin
```

After install:

1. Add your Cognigy credentials to `.env` in your working directory:
   ```
   COGNIGY_BASE_URL=https://cognigy-api-au1.nicecxone.com
   COGNIGY_API_KEY=your-api-key-here
   ```
2. Add the MCP server to your project's `.mcp.json` (or copy it from [`.mcp.json`](.mcp.json)):
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
3. Restart Claude Code to pick up the new credentials.
4. Run `cognigy:init-cognigy-vibe` to capture your build defaults (one-time per workstation).
5. Ask: *"Build me a Cognigy demo for \<customer\>."*

### Marketplace (NICE internal)

If you have access to the NICE Claude Marketplace:

```bash
claude plugin marketplace add ben-elliot-nice/nice-claude-marketplace
claude plugin install cognigy@nice
```

Then follow steps 1–5 above.

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
4. [`.mcp.json`](.mcp.json) is pre-configured — Claude Code will pick it up on next start. If you skip filling in `.env`, the server starts in degraded mode — all tools are visible but calls return setup guidance until credentials are in place.

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
| [`init-cognigy-vibe`](skills/init-cognigy-vibe/SKILL.md) | **First-time setup wizard.** Captures every build variable once (API URL + key, LLM refs, TTS, STT, voice channel, voice preview, naming) → `.env` + `default-demo-config.json` at the `Demo Builds` workspace root. Run before your first build; `build-orchestrator` S0.0 loads it and binds projects with no restart. |
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

1. `mise trust` (once per clone).
2. `cp .env.example .env` and fill in your Cognigy credentials.
3. [`.mcp.json`](.mcp.json) uses `uvx cognigy-vibe-mcp` (same as installed users). To develop against local source with hot-reload, see the [Dev mode](CLAUDE.md#dev-mode-server-contributors-only) section in CLAUDE.md.

### Contributing

- Branch from `origin/dev` (not local dev):
  ```bash
  git checkout -b feat/<name> origin/dev
  ```
- **Do not bump versions.** CI will reject any PR to `dev` that changes the version. Version bumps are pushed directly to `dev` by the maintainer to initiate a prerelease cycle — not via PR.
- **Composite skills call atomic MCP tools** (`cognigy_get`, `cognigy_create`, …) — never hardcode `npx tsx` CLI calls in a skill.
- PR to `dev`. Prereleases are **not** published automatically on merge — the maintainer cuts them explicitly via `workflow_dispatch` (GitHub Actions → "Release (prerelease)" → Run workflow on `dev`) or RC tag (`git tag v1.7.0rc1 && git push origin v1.7.0rc1`). Both paths gate on the base version in `pyproject.toml` exceeding the current stable on PyPI. To install a specific prerelease for testing:
  ```bash
  uvx cognigy-vibe-mcp==1.7.0rc1            # specific RC
  uv tool install cognigy-vibe-mcp --prerelease allow  # latest RC prerelease
  ```
  Stable releases are published when the maintainer merges `dev → main`. The marketplace submodule reference must be updated manually after a stable release (see TODO item #1 in CLAUDE.md).
- See [CLAUDE.md](CLAUDE.md) for the full development workflow (planning, subagent-driven implementation, PR + CI flow).

### Repository layout

```
.claude-plugin/plugin.json   plugin manifest (name, version)
skills/                      one directory per skill, each a SKILL.md
cognigy-mcp/                 the cognigy-vibe-mcp Python server (+ tests, own README)
runtime-reference/           runtime docs skills read before writing code
                             (API reference, code conventions, output formats)
docs/                        plugin-development docs (architecture, patterns, design specs)
scripts/                     explain-topic build tooling
hooks/ .githooks/            onboarding gate + pre-commit hook
.github/workflows/           CI: version-bump check, explain-topic check, publish, release
```

### Maintainers

Ben Elliot — [ben.elliot@nice.com](mailto:ben.elliot@nice.com)
