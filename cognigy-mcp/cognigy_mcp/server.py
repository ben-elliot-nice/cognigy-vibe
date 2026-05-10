from __future__ import annotations
import asyncio
import json
import os
from typing import Any
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.tools import state_tools, flow_ops, file_push, testing, explain


def create_server() -> tuple[Server, list[types.Tool]]:
    client = CognigyClient(
        base_url=os.environ["COGNIGY_BASE_URL"],
        api_key=os.environ["COGNIGY_API_KEY"],
    )
    project_id = os.environ["COGNIGY_PROJECT_ID"]
    state = ProjectState(
        project_id=project_id,
        resync_hours=float(os.getenv("COGNIGY_VIBE_RESYNC_HOURS", "4")),
    )
    cache = Cache(
        cache_dir=state.config_dir / "cache",
        ttl=int(os.getenv("COGNIGY_VIBE_CACHE_TTL", "300")),
    )

    all_tools = (
        state_tools.TOOLS
        + flow_ops.TOOLS
        + file_push.TOOLS
        + testing.TOOLS
        + explain.TOOLS
    )

    all_handlers: dict[str, Any] = {
        **state_tools.make_handlers(client, state, cache),
        **flow_ops.make_handlers(client, state, cache),
        **file_push.make_handlers(client, state, cache),
        **testing.make_handlers(client, state, cache),
        **explain.make_handlers(client, state, cache),
    }

    server = Server("cognigy-vibe")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return all_tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        # Auto-resync check (skip for sync_remote_state itself)
        auto_synced = False
        if name != "sync_remote_state" and state.needs_resync():
            sync_handler = all_handlers["sync_remote_state"]
            sync_handler({"project_id": project_id})
            auto_synced = True

        state.touch_interaction()

        handler = all_handlers.get(name)
        if not handler:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"})
            )]

        result = handler(arguments or {})

        if auto_synced and result:
            # Inject flag into first response object if it's JSON
            try:
                first = json.loads(result[0].text)
                first["auto_synced"] = True
                result[0] = types.TextContent(type="text", text=json.dumps(first, indent=2))
            except Exception:
                pass

        return result

    return server, all_tools


async def _run() -> None:
    server, _ = create_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    load_dotenv()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
