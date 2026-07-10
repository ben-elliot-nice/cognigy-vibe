from __future__ import annotations
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState
from cognigy_mcp.tools import state_tools, flow_ops, file_push, testing, explain, dev_tools, voice_ops


_CONFIG_SCHEMA_VERSION = 2


def _load_config_candidate(candidate: Path) -> "dict | None":
    try:
        data = json.loads(candidate.read_text())
    except json.JSONDecodeError as e:
        print(f"cognigy-vibe: skipping malformed config {candidate}: {e}", file=sys.stderr)
        return None
    except OSError as e:
        print(f"cognigy-vibe: cannot read config {candidate}: {e}", file=sys.stderr)
        return None
    if data.get("$schemaVersion") != _CONFIG_SCHEMA_VERSION:
        print(
            f"cognigy-vibe: {candidate} has $schemaVersion={data.get('$schemaVersion')!r}, "
            f"expected {_CONFIG_SCHEMA_VERSION} — fields may be missing or misread",
            file=sys.stderr,
        )
    return data


def _find_config_file() -> "tuple[dict | None, str | None]":
    """Cascade: COGNIGY_PROJECT_ROOT (or cwd) → ancestors (bounded by $HOME, if an ancestor)
    → ~/.config/cognigy-vibe/config.json. First wins, no merging."""
    home = Path.home().resolve()
    current = Path(os.environ.get("COGNIGY_PROJECT_ROOT", str(Path.cwd()))).resolve()
    # Only climb toward $HOME when it's actually an ancestor — otherwise (CI checkout,
    # /tmp, a mounted volume) don't escape the starting directory onto unrelated ancestors.
    stop = home if (home == current or home in current.parents) else current

    while True:
        candidate = current / "default-demo-config.json"
        if candidate.exists():
            data = _load_config_candidate(candidate)
            if data is not None:
                return data, str(candidate)
        if current == stop or current == current.parent:
            break
        current = current.parent

    global_config = home / ".config" / "cognigy-vibe" / "config.json"
    if global_config.exists():
        data = _load_config_candidate(global_config)
        if data is not None:
            return data, str(global_config)

    return None, None


def _env_configured() -> bool:
    return bool(os.environ.get("COGNIGY_BASE_URL")) and bool(os.environ.get("COGNIGY_API_KEY"))


def create_server() -> tuple[Server, list[types.Tool]]:
    if not _env_configured():
        return _create_degraded_server()
    return _create_full_server()


def _create_degraded_server() -> tuple[Server, list[types.Tool]]:
    # Expose the full tool surface so the session tool list is identical to full mode.
    # Tool calls are intercepted by the orchestrator before reaching here; this fallback
    # handler covers any edge case where a call slips through.
    all_tools = (
        state_tools.TOOLS
        + flow_ops.TOOLS
        + file_push.TOOLS
        + testing.TOOLS
        + explain.TOOLS
        + voice_ops.TOOLS
    )
    env_path = Path(os.environ.get("COGNIGY_PROJECT_ROOT", str(Path.cwd()))) / ".env"
    server = Server("cognigy-vibe")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return all_tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=(
            f"cognigy-vibe-mcp is not configured.\n\n"
            f"Create a .env file at:\n  {env_path}\n\n"
            f"  COGNIGY_BASE_URL=<your-api-base-url>\n"
            f"  COGNIGY_API_KEY=<your-api-key>\n"
            f"  COGNIGY_PROJECT_ID=<your-project-id>  # optional\n\n"
            f"COGNIGY_BASE_URL is the API endpoint — not the UI URL.\n"
            f"  CXone: https://cognigy-api-au1.nicecxone.com  (cognigy-api-*, not cognigy-*)\n"
            f"  Trial: https://api-trial.cognigy.ai  (api-trial.*, not trial.*)\n\n"
            f"Get your API key in Cognigy: My Profile → API Keys → +\n\n"
            f"Once saved, retry this tool call — credentials will load automatically."
        ))]

    return server, all_tools


def _create_full_server() -> tuple[Server, list[types.Tool]]:
    client = CognigyClient(
        base_url=os.environ["COGNIGY_BASE_URL"],
        api_key=os.environ["COGNIGY_API_KEY"],
    )
    state = ProjectState(
        project_id=os.getenv("COGNIGY_PROJECT_ID"),
        resync_hours=float(os.getenv("COGNIGY_VIBE_RESYNC_HOURS", "4")),
    )
    cache = Cache(
        cache_dir=state.config_dir / "cache",
        ttl=int(os.getenv("COGNIGY_VIBE_CACHE_TTL", "300")),
    )

    build_config, config_source = _find_config_file()

    all_tools = (
        state_tools.TOOLS
        + flow_ops.TOOLS
        + file_push.TOOLS
        + testing.TOOLS
        + explain.TOOLS
        + voice_ops.TOOLS
    )
    all_handlers: dict[str, Any] = {
        **state_tools.make_handlers(client, state, cache, build_config=build_config, config_source=config_source),
        **flow_ops.make_handlers(client, state, cache),
        **file_push.make_handlers(client, state, cache),
        **testing.make_handlers(client, state, cache),
        **explain.make_handlers(client, state, cache),
        **voice_ops.make_handlers(client, state, cache),
    }

    if os.environ.get("COGNIGY_VIBE_DEV") == "1":
        all_tools = all_tools + dev_tools.TOOLS
        all_handlers.update(dev_tools.make_handlers())

    server = Server("cognigy-vibe")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return all_tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        auto_synced = False
        if name != "sync_remote_state" and state.project_id and state.needs_resync():
            sync_handler = all_handlers["sync_remote_state"]
            try:
                sync_handler({"project_id": state.project_id})
                auto_synced = True
            except Exception:
                pass

        handler = all_handlers.get(name)
        if not handler:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"})
            )]

        state.touch_interaction()
        result = handler(arguments or {})

        if auto_synced and isinstance(result, list) and result:
            try:
                first = json.loads(result[0].text)
                if "error" not in first:
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
    import truststore
    truststore.inject_into_ssl()
    load_dotenv()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
