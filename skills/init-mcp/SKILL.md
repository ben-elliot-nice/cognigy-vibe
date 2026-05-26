---
name: init-mcp
description: Set up cognigy-vibe-mcp for a new demo project. Run once per project from the project root.
---

# cognigy:init-mcp

Set up cognigy-vibe-mcp for a new demo project. Run once per project from the project root.

## Prerequisites

- `COGNIGY_PROJECT_ID` known (get from Cognigy UI: Project Settings)
- `COGNIGY_BASE_URL` known (e.g. `https://cognigy-api-au1.nicecxone.com`)
- `COGNIGY_API_KEY` known (get from Cognigy UI: My Profile → API Keys)
- `uv` installed
- `cognigy-vibe-mcp` installed: `uv tool install cognigy-vibe-mcp`

## Steps

### 1. Read COGNIGY_PROJECT_ID from user or .env if present

If a `.env` file exists in CWD, read `COGNIGY_PROJECT_ID` from it.
Otherwise, ask the user for it.

### 2. Create config directory

```bash
mkdir -p ~/.config/cognigy-mcp/<COGNIGY_PROJECT_ID>
```

### 3. Create or copy .state-seed.json

If `.state-seed.json` exists in CWD, copy it:
```bash
cp .state-seed.json ~/.config/cognigy-mcp/<COGNIGY_PROJECT_ID>/.state-seed.json
```

Otherwise, create an empty seed:
```bash
echo '{}' > ~/.config/cognigy-mcp/<COGNIGY_PROJECT_ID>/.state-seed.json
```

### 4. Create symlink

```bash
ln -sf ~/.config/cognigy-mcp/<COGNIGY_PROJECT_ID> .cognigy-mcp
```

### 5. Add to .gitignore

Check if `.cognigy-mcp` is already in `.gitignore`. If not:
```bash
echo '.cognigy-mcp' >> .gitignore
```

### 6. Write MCP server entry to .claude/mcp.json

Create `.claude/` if needed:
```bash
mkdir -p .claude
```

Write or merge this entry into `.claude/mcp.json`:
```json
{
  "mcpServers": {
    "cognigy-vibe": {
      "command": "uvx",
      "args": ["cognigy-vibe-mcp"],
      "env": {
        "COGNIGY_BASE_URL": "<COGNIGY_BASE_URL>",
        "COGNIGY_API_KEY": "<COGNIGY_API_KEY>",
        "COGNIGY_PROJECT_ID": "<COGNIGY_PROJECT_ID>"
      }
    }
  }
}
```

If `.claude/mcp.json` already exists, merge the `cognigy-vibe` key into the existing `mcpServers` object — do not overwrite other entries.

### 7. Confirm to user

Report:
- Config dir created at: `~/.config/cognigy-mcp/<projectId>/`
- Symlink created: `.cognigy-mcp → ~/.config/cognigy-mcp/<projectId>/`
- `.gitignore` updated
- MCP server entry written to `.claude/mcp.json`

Remind user to:
1. Restart Claude Code to load the new MCP server
2. Run `sync_remote_state(project_id="<projectId>")` as the first tool call in the new session
