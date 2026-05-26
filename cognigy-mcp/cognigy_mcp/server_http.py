from __future__ import annotations
import contextlib
import json
import os
from http import HTTPStatus
from pathlib import Path
from uuid import uuid4

import anyio
from anyio.abc import TaskStatus
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.types import INVALID_REQUEST, ErrorData, JSONRPCError

from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.session import SessionContext
from cognigy_mcp.state import ProjectState
from cognigy_mcp.tools import explain, file_push, flow_ops, state_tools, testing

_CONFIGURE_TOOL = types.Tool(
    name="configure",
    description=(
        "Initialize this MCP session with Cognigy credentials. "
        "Must be called before any other tool. "
        "base_url example: https://cognigy-api-au1.nicecxone.com"
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "base_url": {"type": "string"},
            "api_key": {"type": "string"},
            "project_id": {"type": "string"},
        },
        "required": ["base_url", "api_key", "project_id"],
    },
)

_ALL_TOOLS = (
    [_CONFIGURE_TOOL]
    + state_tools.TOOLS
    + flow_ops.TOOLS
    + file_push.TOOLS
    + testing.TOOLS
    + explain.TOOLS
)


def _ok(data: dict) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


def _data_base() -> Path:
    return Path(os.getenv("COGNIGY_VIBE_DATA_DIR", str(Path.home() / ".config" / "cognigy-mcp")))


def _make_session_server(session_ref: list[SessionContext | None]) -> Server:
    """Create one MCP Server for one HTTP session. session_ref is filled by configure."""
    server = Server("cognigy-vibe")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return _ALL_TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name == "configure":
            base_url = (arguments.get("base_url") or "").strip()
            api_key = (arguments.get("api_key") or "").strip()
            project_id = (arguments.get("project_id") or "").strip()

            if not all([base_url, api_key, project_id]):
                return _ok({"error": "base_url, api_key, and project_id are all required"})

            data_base = _data_base()
            workspace_dir = data_base / "workspaces" / project_id
            workspace_dir.mkdir(parents=True, exist_ok=True)

            client = CognigyClient(base_url=base_url, api_key=api_key)
            state = ProjectState(
                project_id=project_id,
                resync_hours=float(os.getenv("COGNIGY_VIBE_RESYNC_HOURS", "4")),
                config_base=data_base,
            )
            cache = Cache(
                cache_dir=state.config_dir / "cache",
                ttl=int(os.getenv("COGNIGY_VIBE_CACHE_TTL", "300")),
            )
            handlers = {
                **state_tools.make_handlers(client, state, cache),
                **flow_ops.make_handlers(client, state, cache),
                **file_push.make_handlers(client, state, cache, workspace_dir=workspace_dir),
                **testing.make_handlers(client, state, cache),
                **explain.make_handlers(client, state, cache),
            }
            session_ref[0] = SessionContext(
                client=client,
                state=state,
                cache=cache,
                workspace_dir=workspace_dir,
                handlers=handlers,
            )
            return _ok({"configured": True, "project_id": project_id})

        ctx = session_ref[0]
        if ctx is None:
            return _ok({"error": "session not configured", "hint": "Call configure first"})

        if name != "sync_remote_state" and ctx.state.needs_resync():
            try:
                ctx.handlers["sync_remote_state"]({"project_id": ctx.state.project_id})
            except Exception:
                pass

        handler = ctx.handlers.get(name)
        if not handler:
            return _ok({"error": f"Unknown tool: {name}"})

        ctx.state.touch_interaction()
        return handler(arguments or {})

    return server


class PerSessionMCPManager:
    """Manages one MCP Server per HTTP session for isolated Cognigy credentials."""

    def __init__(self) -> None:
        self._transports: dict[str, StreamableHTTPServerTransport] = {}
        self._task_group: anyio.abc.TaskGroup | None = None

    @contextlib.asynccontextmanager
    async def run(self):
        async with anyio.create_task_group() as tg:
            self._task_group = tg
            try:
                yield
            finally:
                tg.cancel_scope.cancel()
                self._task_group = None
                self._transports.clear()

    async def handle_request(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive)
        mcp_sid = request.headers.get("mcp-session-id")

        if mcp_sid is not None:
            transport = self._transports.get(mcp_sid)
            if transport is None:
                err = JSONRPCError(
                    jsonrpc="2.0",
                    id="server-error",
                    error=ErrorData(code=INVALID_REQUEST, message="Session not found"),
                )
                resp = Response(
                    content=err.model_dump_json(by_alias=True, exclude_none=True),
                    status_code=HTTPStatus.NOT_FOUND,
                    media_type="application/json",
                )
                await resp(scope, receive, send)
                return
            await transport.handle_request(scope, receive, send)
            return

        # New session
        if self._task_group is None:
            resp = Response("Service unavailable", status_code=503)
            await resp(scope, receive, send)
            return
        new_sid = uuid4().hex
        session_ref: list[SessionContext | None] = [None]
        server = _make_session_server(session_ref)
        transport = StreamableHTTPServerTransport(mcp_session_id=new_sid)
        self._transports[new_sid] = transport

        async def run_server(*, task_status: TaskStatus[None] = anyio.TASK_STATUS_IGNORED) -> None:
            async with transport.connect() as (read, write):
                task_status.started()
                try:
                    await server.run(read, write, server.create_initialization_options())
                except Exception:
                    pass
                finally:
                    self._transports.pop(new_sid, None)

        await self._task_group.start(run_server)
        await transport.handle_request(scope, receive, send)


def _check_bearer(request: Request) -> bool:
    token = os.getenv("COGNIGY_VIBE_TOKEN", "")
    if not token:
        return True
    # == is not timing-safe, but this token protects only demo infrastructure.
    return request.headers.get("authorization", "") == f"Bearer {token}"


def create_app() -> Starlette:
    manager = PerSessionMCPManager()

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with manager.run():
            yield

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def upload_file(request: Request) -> Response:
        if not _check_bearer(request):
            return Response("Unauthorized", status_code=401)
        project_id = request.path_params["project_id"]
        file_path = request.path_params["path"]
        dest = _data_base() / "workspaces" / project_id / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(await request.body())
        return JSONResponse({"stored": str(dest)})

    async def get_state(request: Request) -> Response:
        if not _check_bearer(request):
            return Response("Unauthorized", status_code=401)
        project_id = request.path_params["project_id"]
        state_path = _data_base() / project_id / ".state.json"
        if not state_path.exists():
            return Response("Not Found", status_code=404)
        return Response(state_path.read_text(), media_type="application/json")

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await manager.handle_request(scope, receive, send)

    return Starlette(
        lifespan=lifespan,
        routes=[
            Route("/health", health),
            Route("/workspace/{project_id}/{path:path}", upload_file, methods=["PUT"]),
            Route("/state/{project_id}", get_state, methods=["GET"]),
            # MCP endpoint: auth is handled at the session/tool level via configure credentials.
            # Bearer token protects only the out-of-band upload and state endpoints.
            Mount("/mcp", handle_mcp),
        ],
    )


def main() -> None:
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(create_app(), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
