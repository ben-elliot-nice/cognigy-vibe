#!/usr/bin/env bash
# Install the local cognigy-mcp source as an editable uv tool.
# After this, cognigy-vibe-mcp runs from local source — restart-mcp.sh picks up code changes.
# Revert with: bash scripts/dev-uninstall.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing cognigy-vibe-mcp from local source (editable)..."
uv tool install --editable "$REPO_ROOT/cognigy-mcp"

echo "Restarting MCP server..."
bash "$REPO_ROOT/scripts/restart-mcp.sh"

echo ""
echo "Dev mode active. Edit cognigy-mcp/ freely; run restart-mcp.sh after each change."
echo "Revert to published version: bash scripts/dev-uninstall.sh"
