from pathlib import Path
from unittest.mock import MagicMock
from cognigy_mcp.session import SessionContext


def test_session_context_creation(tmp_path):
    client = MagicMock()
    state = MagicMock()
    cache = MagicMock()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    handlers = {"some_tool": lambda args: []}

    ctx = SessionContext(
        client=client,
        state=state,
        cache=cache,
        workspace_dir=workspace,
        handlers=handlers,
    )

    assert ctx.client is client
    assert ctx.state is state
    assert ctx.cache is cache
    assert ctx.workspace_dir == workspace
    assert ctx.handlers is handlers
