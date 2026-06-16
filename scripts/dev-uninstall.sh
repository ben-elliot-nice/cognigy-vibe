#!/usr/bin/env bash
# Uninstall the local editable cognigy-vibe-mcp tool, reverting to the published uvx version.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Uninstalling local cognigy-vibe-mcp..."
uv tool uninstall cognigy-vibe-mcp

echo "Restarting MCP server (will fetch published version on next call)..."
bash "$REPO_ROOT/scripts/restart-mcp.sh"

echo "Reverted to published uvx version."
