#!/usr/bin/env bash
# Kill the cognigy-vibe-mcp server process so Claude Code restarts it on the next MCP call.
# Use after making and saving changes to cognigy-mcp/ — requires dev-install first (see below).
#
# Full dev loop:
#   bash scripts/dev-install.sh   # one-time: install local source as editable uv tool
#   <make code changes>
#   bash scripts/restart-mcp.sh   # reload: kill server so Claude Code picks up changes
#   bash scripts/dev-uninstall.sh # revert: restore published uvx version

set -e

SERVER="cognigy-vibe-mcp"

if pgrep -f "$SERVER" > /dev/null 2>&1; then
    pkill -f "$SERVER"
    echo "Killed $SERVER — Claude Code will restart it on the next MCP call."
else
    echo "$SERVER is not currently running."
fi
