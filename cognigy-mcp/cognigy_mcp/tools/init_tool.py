# cognigy-mcp/cognigy_mcp/tools/init_tool.py
from __future__ import annotations

import os
import threading
from pathlib import Path

import mcp.types as types

TOOLS = [
    types.Tool(
        name="init",
        description=(
            "Configure the Cognigy MCP server. Writes credentials to the project .env file "
            "and reloads the server with full tool access. Run this once per project.\n\n"
            "Required:\n"
            "- cognigy_base_url: API base URL (e.g. https://cognigy-api-au1.nicecxone.com)\n"
            "- cognigy_api_key: Your Cognigy API key (Settings → API Keys)\n\n"
            "Optional:\n"
            "- cognigy_project_id: Your project ID (can be set later via sync_remote_state)"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cognigy_base_url": {
                    "type": "string",
                    "description": "Cognigy API base URL for your region",
                },
                "cognigy_api_key": {
                    "type": "string",
                    "description": "Cognigy API key",
                },
                "cognigy_project_id": {
                    "type": "string",
                    "description": "Cognigy project ID (optional)",
                },
            },
            "required": ["cognigy_base_url", "cognigy_api_key"],
        },
    )
]


def make_handlers() -> dict:
    def _init(args: dict) -> list[types.TextContent]:
        base_url = args["cognigy_base_url"].rstrip("/")
        api_key = args["cognigy_api_key"]
        project_id = args.get("cognigy_project_id", "")

        lines = [
            f"COGNIGY_BASE_URL={base_url}",
            f"COGNIGY_API_KEY={api_key}",
        ]
        if project_id:
            lines.append(f"COGNIGY_PROJECT_ID={project_id}")

        env_path = Path.cwd() / ".env"
        env_path.write_text("\n".join(lines) + "\n")

        threading.Timer(0.5, lambda: os._exit(42)).start()

        return [
            types.TextContent(
                type="text",
                text=(
                    f"Configuration written to {env_path}.\n"
                    "The MCP server is reloading — full tools will be available momentarily."
                ),
            )
        ]

    return {"init": _init}
