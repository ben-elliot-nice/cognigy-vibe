#!/usr/bin/env bash
# Kill the cognigy-vibe-mcp server process so Claude Code restarts it on the next MCP call.
# Use after saving changes to cognigy-mcp/ to pick up updated code in-session.
# .mcp.json runs the server from local source — no install step needed.

set -e

SERVER="cognigy-vibe-mcp"

if pgrep -f "$SERVER" > /dev/null 2>&1; then
    pkill -f "$SERVER"
    echo "Killed $SERVER — Claude Code will restart it on the next MCP call."
else
    echo "$SERVER is not currently running."
fi
