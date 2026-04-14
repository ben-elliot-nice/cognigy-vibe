# Cognigy Claude Plugin

Read `docs/architecture.md` at the start of every new session.

## Rules

- **Composite skills call atomic skills** (`cognigy:get`, `cognigy:create`, etc.) — never hardcode `npx tsx` CLI calls in a composite skill.
- **After any change to `cli/` or `skills/`**, increment both `cli/package.json` and `.claude-plugin/plugin.json` versions. Always patch increment unless directed otherwise (e.g. `1.1.9` → `1.1.10`).
- **Shell commands:** if Claude is constructing the command, run each step as a separate Bash call. If a compound command is explicitly defined in a CLAUDE.md, run it as written.

## After every commit + push

```bash
cd /Users/Ben.Elliot/repos/claude-marketplace/nice-claude-marketplace && git submodule update --remote && git add plugins && git commit -m "Further cognigy plugins revisions" && git push
```
