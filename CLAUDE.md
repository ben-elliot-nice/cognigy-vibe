# Cognigy Claude Plugin

Read `docs/architecture.md` at the start of every new session. **Note: architecture.md is significantly out of date — treat structural claims skeptically and prefer the live code.** See TODO item #1.

## Git Worktrees

Worktrees live at `.claude/worktrees/` (gitignored). This is the default Claude Code location — do not create worktrees under `.worktrees/`.

## Development Workflow

1. **Feature arrives** — clarify scope if ambiguous before any code work.

2. **Sync from remote** — if working tree is clean, `git pull` is preferred. Use `git fetch origin main` only if you have uncommitted changes and don't want to switch branches first.

3. **Create branch or worktree from remote main** (not local main)
   ```bash
   git checkout -b feat/<name> origin/main
   # or, using the using-git-worktrees skill:
   git worktree add .claude/worktrees/<name> -b feat/<name> origin/main
   ```

4. **Plan before code** — run `superpowers:brainstorming` then `superpowers:writing-plans`. Do not touch implementation files until the plan is written.

5. **Commit the spec/plan** after user approval. The plan file lives in the repo; commit it as a standalone commit before any implementation.

6. **Implement using `superpowers:subagent-driven-development`**
   - Read the plan; extract all tasks upfront; create a TodoWrite list.
   - Dispatch one fresh implementer subagent per task (never in parallel).
   - After each task: spec-compliance review → code-quality review → mark complete.
   - After all tasks: dispatch a final code-quality reviewer, then proceed to step 7.

7. **Finish the branch using `superpowers:finishing-a-development-branch`**
   - The skill presents 4 options. **Always choose option 2 (Push and create PR).**
   - The skill will `git push -u origin <branch>` and run `gh pr create`.

8. **Verify PR and check for conflicts**
   ```bash
   gh pr view --json url,mergeable,mergeStateStatus
   ```
   - If `mergeable` is `CONFLICTING`: rebase the branch on current remote main, then force-push.
     ```bash
     git fetch origin main
     git rebase origin/main
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

## Required Plugins

This project uses two Claude Code plugins. `.claude/settings.json` enables them — you need both marketplaces installed locally.

**Superpowers** (`superpowers@superpowers-dev`) — workflow skills (brainstorming, planning, TDD, etc.):
```bash
claude marketplace add superpowers-dev github:obra/superpowers
claude plugin install superpowers@superpowers-dev
```

**Cognigy** (`cognigy@nice`) — Cognigy-specific skills. Installed from the NICE Claude Marketplace, which is the parent repo of this plugin. If you have `nice-claude-marketplace` checked out:
```bash
claude marketplace add nice directory:/path/to/nice-claude-marketplace
claude plugin install cognigy@nice
```

## Local Development Testing

First time in a new clone, trust the mise config:

```bash
mise trust
```

`.mcp.json` uses `uvx cognigy-vibe-mcp` (the published package) — same as an installed user. Credentials must be in the shell environment before starting Claude. Copy `.env.example` to `.env`, fill in your values, and `mise` will auto-source it when you enter the directory.

### Hot-reload loop (server contributors only)

If you are modifying the MCP server source in `cognigy-mcp/`, switch to the hot-reload proxy so changes take effect without restarting Claude Code:

1. Add an entry to `~/.claude/settings.json` under `mcpServers` — this overrides the plugin's `uvx` config for your local session:
   ```json
   {
     "mcpServers": {
       "cognigy-vibe": {
         "command": "python3",
         "args": ["/absolute/path/to/cognigy-claude-plugin/scripts/mcp-proxy.py"]
       }
     }
   }
   ```
2. Restart Claude Code. The proxy spawns the inner server via `uv run --directory cognigy-mcp`.
3. After source changes, reload the inner server without disconnecting:
   ```bash
   bash scripts/restart-mcp.sh
   ```
   The script sends `SIGUSR1` to the proxy, which kills the inner server, respawns it, replays the MCP handshake, and resumes forwarding — the Claude Code session continues uninterrupted.

Remove the `~/.claude/settings.json` override when you are done to return to the published package.

## TODO

The following items are tracked but not currently in scope. If you ask Claude to work on this project, Claude may ask whether these TODOs are in scope for the current session before proceeding.

1. **GitHub Actions: auto-update marketplace parent repo** — When this plugin is committed and pushed, the parent repo (`nice-claude-marketplace`) should automatically pull the submodule update via CI instead of manual command above.

## After every commit + push

On merge to main, the release pipeline automatically notifies `nice-claude-marketplace` to update its submodule reference. No manual step required.