# cognigy-vibe-mcp/cognigy_mcp/tools/dev_tools.py
from __future__ import annotations

import os
import threading

import mcp.types as types

TOOLS = [
    types.Tool(
        name="reload_mcp",
        description=(
            "Reload the MCP server from local source. "
            "Call this after editing source files in dev mode — "
            "the server respawns from COGNIGY_VIBE_SOURCE_DIR and tool list refreshes."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    )
]


def make_handlers() -> dict:
    def _reload_mcp(args: dict) -> list[types.TextContent]:
        threading.Timer(0.5, lambda: os._exit(42)).start()
        return [
            types.TextContent(
                type="text",
                text="Reloading MCP server from local source. Tool list will refresh momentarily.",
            )
        ]

    return {"reload_mcp": _reload_mcp}
