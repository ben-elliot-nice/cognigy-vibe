#!/usr/bin/env bash
set -euo pipefail

if ! command -v uvx >/dev/null 2>&1; then
    echo "uv not found — installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Reload PATH for common uv install locations
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uvx >/dev/null 2>&1; then
        echo "ERROR: uv installed but uvx not on PATH. Open a new terminal and re-run this script." >&2
        exit 1
    fi
fi

uvx --from cognigy-vibe-mcp cognigy-vibe-setup "$@"
