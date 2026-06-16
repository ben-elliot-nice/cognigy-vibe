#!/usr/bin/env bash
# Hot-reload the cognigy-vibe-mcp server without disconnecting Claude Code.
# Sends SIGUSR1 to mcp-proxy.py, which respawns the inner server and replays
# the MCP handshake internally. The Claude Code session continues uninterrupted.

set -e

PROXY="mcp-proxy.py"

if pgrep -f "$PROXY" > /dev/null 2>&1; then
    pkill -USR1 -f "$PROXY"
    echo "Reload signal sent — next MCP call will use updated source."
else
    echo "Proxy not running. Start Claude Code to launch it."
fi
