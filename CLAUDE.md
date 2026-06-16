# Cognigy Claude Plugin

Read `docs/architecture.md` at the start of every new session. **Note: architecture.md is significantly out of date — treat structural claims skeptically and prefer the live code.** See TODO item #1.

## Rules

- **Composite skills call atomic skills** (`cognigy:get`, `cognigy:create`, etc.) — never hardcode `npx tsx` CLI calls in a composite skill.
- **After any change to `cognigy-mcp/` or `skills/`**, increment both `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json` versions. Always patch increment unless directed otherwise (e.g. `1.1.9` → `1.1.10`). CI enforces this on PRs to main.
- **Shell commands:** if Claude is constructing the command, run each step as a separate Bash call. If a compound command is explicitly defined in a CLAUDE.md, run it as written.

## OpenAPI Spec

The Cognigy OpenAPI spec is available per environment (not vendored):
- AU1: `GET https://cognigy-api-au1.nicecxone.com/openapi/openapi-viewer.json`
- NA1: `GET https://cognigy-api-na1.nicecxone.com/openapi/openapi-viewer.json`
- JP1: `GET https://cognigy-api-jp1.nicecxone.com/openapi/openapi-viewer.json`
- Trial: `GET https://api-trial.cognigy.ai/openapi/openapi-viewer.json`

## Runtime Reference

The `runtime-reference/` directory contains usage documentation for the MCP server and skills (Cognigy API runtime objects, channel output formats, code conventions). These reference docs are consumed at runtime — skills instruct Claude to read them before writing code.

This content is distinct from the `docs/` directory, which covers plugin development (architecture, shared design patterns, design specs/plans).

## Local Development Testing

`.mcp.json` is configured to run `cognigy-vibe-mcp` from the local `cognigy-mcp/` source tree via `uv run`. To pick up code changes in-session:

```bash
bash scripts/restart-mcp.sh   # kill server so Claude Code respawns with updated code
```

No install step required. Credentials must be in the shell environment before starting Claude. Copy `.env.example` to `.env`, fill in your values, and `mise` will auto-source it when you enter the directory.

## TODO

The following items are tracked but not currently in scope. If you ask Claude to work on this project, Claude may ask whether these TODOs are in scope for the current session before proceeding.

1. **Update `docs/architecture.md`** — Significantly out of date. Reflect current MCP tools, skills, and project structure.
2. **Integrate 3x docs into MCP explain topics** — Move `cognigy-api-reference.md`, `cognigy-output-formats.md`, `cognigy-code-conventions.md` content into the MCP server's `explain` tool topics so they're accessible at runtime.
3. **Extricate explain topics to markdown + build-time process** — All MCP explain topic content should live as markdown files in the repo, with a build step that generates the in-server topic registry. Makes topics reviewable, versionable, and editable without redeploying the server.
4. **GitHub Actions: auto-update marketplace parent repo** — When this plugin is committed and pushed, the parent repo (`nice-claude-marketplace`) should automatically pull the submodule update via CI instead of manual command above.

## After every commit + push

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```