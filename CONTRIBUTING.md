# Contributing to cognigy-vibe

## Branching

Branch from `origin/dev` (not local `dev`):

```bash
git checkout -b feat/<name> origin/dev
```

If the work tracks a GitHub issue, name the branch `feat/<number>-<slug>` — e.g. `feat/98-my-feature`.

## Rules

- **Do not bump versions in dev PRs.** CI rejects any PR to `dev` that changes the version in `cognigy-vibe-mcp/pyproject.toml` or `plugin/.claude-plugin/plugin.json`. Version bumps are pushed directly to `dev` by the maintainer to initiate a prerelease cycle — not via PR.
- **Composite skills call atomic MCP tools** (`cognigy_get`, `cognigy_create`, etc.) — never hardcode `npx tsx` CLI calls in a skill.

## Pull requests

PRs target `dev`. Prereleases are not published automatically on merge — the maintainer cuts them explicitly, either via `workflow_dispatch` (GitHub Actions → "Release (prerelease)" → Run workflow on `dev`) or by pushing an RC tag:

```bash
git tag v1.7.0rc1 && git push origin v1.7.0rc1
```

Both paths gate on the base version in `pyproject.toml` exceeding the current stable release on PyPI. To install a specific prerelease for testing:

```bash
uvx cognigy-vibe-mcp==1.7.0rc1                        # specific RC
uv tool install cognigy-vibe-mcp --prerelease allow   # latest RC prerelease
```

Stable releases are published when the maintainer merges `dev` into `main`.

See [CLAUDE.md](CLAUDE.md) for the full development workflow — planning, subagent-driven implementation, PR and CI flow.
