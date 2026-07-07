# Cognigy Claude Plugin

Read `docs/architecture.md` at the start of every new session. **Note: architecture.md is significantly out of date — treat structural claims skeptically and prefer the live code.** See TODO item #1.

## Git Worktrees

Worktrees live at `.claude/worktrees/` (gitignored). This is the default Claude Code location — do not create worktrees under `.worktrees/`.

## Development Workflow

1. **Feature arrives** — if there is a GitHub issue, read it first: `gh issue view <number>`. Clarify scope if ambiguous before any code work.

2. **Sync from remote** — if working tree is clean, `git pull` is preferred. Use `git fetch origin dev` only if you have uncommitted changes and don't want to switch branches first. (If you are the maintainer cutting a release, sync from `main` instead.)

3. **Create branch or worktree from remote dev** (not local dev). When working from a GitHub issue, name the branch `feat/<number>-<slug>`:
   ```bash
   git checkout -b feat/98-my-feature origin/dev
   # or, using the using-git-worktrees skill (preferred — activates the worktree in-session):
   # EnterWorktree will create .claude/worktrees/feat/98-my-feature on a new branch
   ```

4. **Plan before code** — run `superpowers:brainstorming` then `superpowers:writing-plans`. Do not touch implementation files until the plan is written. The plan **must** include a task to find and fix related documentation (CLAUDE.md, runtime-reference, explain topics, contributor guides). See [§Documentation](#documentation) for content guidelines.

5. **Specs and plans are locally tracked only** — `docs/superpowers/` is intentionally gitignored. No commit is needed or possible. This is expected; do not ask or warn about it.

6. **Implement using `superpowers:subagent-driven-development`**
   - Read the plan; extract all tasks upfront; create a TodoWrite list.
   - Dispatch one fresh implementer subagent per task (never in parallel).
   - **Every implementer dispatch must include:** the absolute worktree path as working directory, and an explicit instruction to run `git branch --show-current` and confirm it matches the expected branch before making any commit. If it does not match, the subagent must stop and report BLOCKED — do not commit to the wrong branch.
   - After each task: spec-compliance review → code-quality review → mark complete.
   - After all tasks: dispatch a final code-quality reviewer, then proceed to step 7.

7. **Finish the branch using `superpowers:finishing-a-development-branch`**
   - The skill presents 4 options. **Always choose option 2 (Push and create PR).**
   - The skill will `git push -u origin <branch>` and run `gh pr create`.
   - **PRs target `dev`**, not `main`. The `dev → main` promotion (cutting a stable release) is the maintainer's responsibility and happens separately.
   - If the branch tracks a GitHub issue, include `Closes #<number>` in the PR body — GitHub will auto-close the issue on merge.

8. **Verify PR and check for conflicts**
   ```bash
   gh pr view --json url,mergeable,mergeStateStatus
   ```
   - If `mergeable` is `CONFLICTING`: rebase the branch on current remote dev, then force-push.
     ```bash
     git fetch origin dev
     git rebase origin/dev
     git push --force-with-lease
     ```

9. **Get merge Actions run IDs**
   ```bash
   gh run list --branch <branch> --json databaseId,name,status
   ```
   Note the `databaseId` values for the CI runs triggered by the PR.

10. **Poll until CI completes** (every 30 seconds)
    ```bash
    while true; do
      STATUS=$(gh run list --branch <branch> --json databaseId,status,conclusion \
        --jq '.[] | select(.databaseId == <run-id>) | .status + "/" + .conclusion')
      echo "$(date +%H:%M:%S) $STATUS"
      [[ "$STATUS" == "completed/"* ]] && break
      sleep 30
    done
    ```
    Alternatively: `gh run watch <run-id>` (streams live; exits on completion).

11. **Report to user** — final CI status (`success` / `failure`), PR URL, and any actions taken (rebases, force-pushes, re-runs).

12. **Close the issue** — once the PR is merged, verify the related GitHub issue is closed. If `Closes #<number>` was in the PR body it will have auto-closed; otherwise close it manually:
    ```bash
    gh issue close <number> --comment "Resolved in PR #<pr-number>"
    ```

## Hotfix Workflow

For critical bugs in the current stable release (crash-on-start, data loss, security), bypass the normal dev cycle:

1. Branch from `main`: `git checkout -b hotfix/<slug> main`
2. Implement the fix with TDD (write failing test first)
3. Bump the patch version in `pyproject.toml` and `plugin.json`
4. PR targets `main` — this is intentional and correct
5. After merge to `main`, cherry-pick the fix commit(s) back to `dev` — **do not** `git merge main`, as that pulls in the version bump and CI will reject it:
   ```bash
   git checkout dev
   git cherry-pick <hotfix-commit-sha>
   git push
   ```

The "PRs target `dev`" rule applies to feature work. Hotfixes go straight to `main` because routing through `dev` delays the fix for all users on the current stable version.

## Documentation

- **Runtime usage** (skills, MCP tools, hooks, code conventions) → document via the `cognigy:explain` skill and the MCP tool build structure (`runtime-reference/`). Do not duplicate this content in CLAUDE.md or docs/.
- **Modular architecture** — atomic pieces of knowledge are their own explain topic. Higher-order and orchestration skills reference those topics by name instead of duplicating their content. Design atomic topics with this in mind: one concern per topic, reusable across contexts.
- **Find-and-fix scope** — during any docs update, flag to the user any opportunities to restructure explain topics (especially extracting atomic topics from higher-order or orchestration skills) and ask whether restructuring is in scope before acting.

## Rules

- **Composite skills call atomic skills** (`cognigy:get`, `cognigy:create`, etc.) — never hardcode `npx tsx` CLI calls in a composite skill.
- **Do not bump versions in `dev` PRs.** CI will reject any PR to `dev` that changes the version in `cognigy-mcp/pyproject.toml` or `.claude-plugin/plugin.json`. Version bumps are pushed **directly to `dev`** (it is unprotected) as part of initiating a prerelease cycle — not via PR.
- **Shell commands:** if Claude is constructing the command, run each step as a separate Bash call. If a compound command is explicitly defined in a CLAUDE.md, run it as written.

## Code Review

- **`/review <N>` posts findings as a PR comment** — never just output to the terminal. Use `gh pr review <N> --comment -b "..."` after completing the review.
- **Byline**: `/review` signs as `*— Claude Reviewer*`. The implementer loop (applying fixes) signs as `*— claude implementer*`.
- Both bylines go at the bottom of the comment body.
- **After implementer fixes**: check the implementer's follow-up comment, then post `LGTM — all findings addressed.\n\n*— Claude Reviewer*` if satisfied.

## OpenAPI Spec

The Cognigy OpenAPI spec is available per environment (not vendored):
- AU1: `GET https://cognigy-api-au1.nicecxone.com/openapi/openapi-viewer.json`
- NA1: `GET https://cognigy-api-na1.nicecxone.com/openapi/openapi-viewer.json`
- JP1: `GET https://cognigy-api-jp1.nicecxone.com/openapi/openapi-viewer.json`
- Trial: `GET https://api-trial.cognigy.ai/openapi/openapi-viewer.json`

## Runtime Reference

The `runtime-reference/` directory contains usage documentation for the MCP server and skills (Cognigy API runtime objects, channel output formats, code conventions). These reference docs are consumed at runtime — skills instruct Claude to read them before writing code.

This content is distinct from the `docs/` directory, which covers plugin development (architecture, shared design patterns, design specs/plans).

## Required Plugins

This project uses two Claude Code plugins. `.claude/settings.json` enables them — Superpowers requires its marketplace; Cognigy can be installed directly from GitHub (see below).

**Superpowers** (`superpowers@superpowers-dev`) — workflow skills (brainstorming, planning, TDD, etc.):
```bash
claude plugin marketplace add superpowers-dev github:obra/superpowers
claude plugin install superpowers@superpowers-dev
```

**Cognigy** (`cognigy-vibe@cognigy-vibe`) — Cognigy-specific skills:
```bash
claude plugin marketplace add ben-elliot-nice/cognigy-claude-plugin
claude plugin install cognigy-vibe@cognigy-vibe
```

## Local Development Testing

First time in a new clone, trust the mise config:

```bash
mise trust
```

Copy `.env.example` to `.env` and fill in your Cognigy credentials — `mise` auto-sources it when you enter the directory. If you skip filling in `.env`, the server starts in degraded mode — all tools are visible but calls return setup guidance until credentials are in place.

`.mcp.json` is pre-configured for dev mode — `COGNIGY_VIBE_DEV=1` and `COGNIGY_VIBE_SOURCE_DIR=./cognigy-mcp` are baked in. Claude Code picks it up automatically on next start. The server runs from local source (`./cognigy-mcp`) with `reload_mcp` available. After editing source files, call `reload_mcp` — the server respawns from updated source and the tool list refreshes in the same session. No terminal restart needed.

If you are only using the skills (not developing the MCP server), you can opt out of dev mode by adding `COGNIGY_VIBE_DEV=` (empty value) to your `.env` — `load_dotenv` override takes effect on the next spawn.

### Plugin conflict (if you have the cognigy plugin installed)

If you have the cognigy plugin installed at user level, Claude Code loads both the plugin-defined server (`mcp__plugin_<marketplace>__cognigy-vibe__*`) and the `.mcp.json` dev server (`mcp__cognigy-vibe__*`) simultaneously. To avoid namespace ambiguity during MCP development, disable the plugin locally by adding to your `.claude/settings.local.json`:

```json
{
  "enabledPlugins": {
    "cognigy@nice": false
  }
}
```

## TODO

The following items are tracked but not currently in scope. If you ask Claude to work on this project, Claude may ask whether these TODOs are in scope for the current session before proceeding.

1. **CI documentation audit** (issue #102) — Find and update all documentation that still references the old auto-publish-on-dev-push CI flow.

## Prerelease flow

Prereleases are **not** published automatically on every `dev` push. To cut a prerelease:

1. Bump `cognigy-mcp/pyproject.toml` and `.claude-plugin/plugin.json` to the intended next version (e.g. `1.7.0`) — push directly to `dev` (not via PR).
2. Trigger one of:
   - **Dispatch:** GitHub Actions UI → "Release (prerelease)" → Run workflow on `dev`
   - **Tag:** `git tag v1.7.0rc1 && git push origin v1.7.0rc1`
3. CI validates that the base version in pyproject exceeds the current stable on PyPI, then publishes to PyPI.

Install a prerelease:
```bash
uvx cognigy-vibe-mcp==1.7.0rc1      # specific RC
uv tool install cognigy-vibe-mcp --prerelease allow  # latest prerelease
```

**Merge to `main`** (stable release only) — the stable version is published to PyPI. The marketplace submodule reference must be updated manually (see TODO item #1 — automation not yet implemented).