# cognigy-claude-plugin

Cognigy AI agent development skills for [Claude Code](https://docs.claude.com/en/docs/claude-code). This is the **`cognigy@nice`** plugin: a set of skills plus a local [`cognigy-vibe-mcp`](cognigy-mcp/README.md) server that together let you scope, design, build, and test Cognigy.AI agent demos end-to-end from inside Claude Code.

> **Status:** v1.4.3 — the [`build-orchestrator`](skills/build-orchestrator/SKILL.md) skill landed in [PR #55](https://github.com/ben-elliot-nice/cognigy-claude-plugin/pull/55), making the plugin a complete **scope → design → build → smoke-test** pipeline.

---

## What it does

The plugin turns "build me a Cognigy demo for *\<customer\>*" into a finished, tested AI Agent build. It pairs two layers:

- **Skills** — the workflow knowledge: how to interview, scope, design a persona, lay out an init chain, shape tool branches, and verify the result.
- **`cognigy-vibe-mcp`** — the hands: an MCP server wrapping the Cognigy REST API for node creation, flow inspection, code push with conflict detection, and live session testing.

A skill decides *what* to build; the MCP server *does* it against your Cognigy project.

---

## The build pipeline

```
build-orchestrator  ──┬─►  scope-demo        →  <Customer>-demo-plan.md
 (single-batch        │
  interview)          ├─►  design-agent       →  persona / jobs / interfaces / contracts docs
                      │      ├─ design-agent-persona
                      │      ├─ design-agent-jobs
                      │      ├─ design-agent-interfaces
                      │      └─ design-agent-contracts
                      │
                      └─►  build (via cognigy-vibe-mcp)
                             project + AI Agent + Job Node patch
                             init chain  (Once → Initialize Session → Set Session Config → Say Welcome → Wait)
                             tool branches  (Say filler → Code mock → Resolve)
                             end-call pair + as-built doc + drift baseline + package zip
                             smoke test  (structural assertions + 3-turn talk_to_agent run)
```

[`build-orchestrator`](skills/build-orchestrator/SKILL.md) is the entry point. It keeps a single-batch interview, then delegates scoping and design to the purpose-built sub-skills before running the build sequence and an automated smoke test — it only hands back when both structural and runtime checks are green.

---

## Skills

| Skill | Purpose |
|---|---|
| [`build-orchestrator`](skills/build-orchestrator/SKILL.md) | **End-to-end demo builder.** Interview → scope → design → build → smoke-test, driving the full plugin stack. *(Added in PR #55.)* |
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

## The MCP server — `cognigy-vibe-mcp`

A local Python MCP server (full docs: [cognigy-mcp/README.md](cognigy-mcp/README.md)) exposing the Cognigy REST API surface plus a reference library. Tools:

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

### Install the server

```bash
uv tool install cognigy-vibe-mcp     # first time
uv tool upgrade cognigy-vibe-mcp     # thereafter
```

The `build-orchestrator` skill requires **≥ 1.4.2** (file-backed tool authoring, `push_code_node` CREATE mode, AU1 stability fixes, project-binding refactor). Newer is always preferred.

---

## Getting started

### As a user (consuming the published plugin)

1. Install the server: `uv tool install cognigy-vibe-mcp`.
2. Install the plugin from the NiCE Claude Marketplace:
   ```bash
   claude marketplace add nice directory:/path/to/nice-claude-marketplace
   claude plugin install cognigy@nice
   ```
3. In a demo project directory, run the `cognigy:init-mcp` skill to wire up state, cache, and the MCP entry.
4. Restart Claude Code, then ask: *"Build me a Cognigy demo for \<customer\>."*

### As a contributor (local development)

The repo is configured to run the server from source — no install step.

1. `mise trust` (once per clone) so `mise` auto-sources `.env`.
2. `cp .env.example .env` and fill in your Cognigy credentials:
   ```
   COGNIGY_BASE_URL=https://cognigy-api-au1.nicecxone.com
   COGNIGY_API_KEY=your-api-key-here
   COGNIGY_PROJECT_ID=your-project-id-here
   ```
3. [`.mcp.json`](.mcp.json) runs `cognigy-vibe-mcp` from `cognigy-mcp/` via a hot-reload proxy. After source changes:
   ```bash
   bash scripts/restart-mcp.sh
   ```
   The proxy stays alive across reloads, so the Claude Code session is never disconnected.

See [CLAUDE.md](CLAUDE.md) for the full development workflow (branching, planning, subagent-driven implementation, PR + CI flow).

---

## Repository layout

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

---

## Conventions

- **Composite skills call atomic skills** (`cognigy:get`, `cognigy:create`, …) — never hardcode CLI calls.
- **Bump both versions** in [`cognigy-mcp/pyproject.toml`](cognigy-mcp/pyproject.toml) and [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) after any change to `cognigy-mcp/` or `skills/` (patch increment by default). CI enforces this on PRs to `main`.
- On merge to `main`, the release pipeline notifies `nice-claude-marketplace` to update its submodule reference automatically.

---

## Required plugins

This plugin builds on:

- **Superpowers** (`superpowers@superpowers-dev`) — workflow skills (brainstorming, planning, TDD).
- **Cognigy** (`cognigy@nice`) — this plugin, installed from the NiCE Claude Marketplace.

---

*Author: Ben Elliot ([ben.elliot@nice.com](mailto:ben.elliot@nice.com))*
