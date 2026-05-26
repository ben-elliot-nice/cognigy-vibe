import json
import os
import pytest
from pathlib import Path
from starlette.testclient import TestClient


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("COGNIGY_VIBE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("COGNIGY_VIBE_TOKEN", "test-token")
    return tmp_path / "data"


@pytest.fixture
def app(data_dir):
    from cognigy_mcp.server_http import create_app
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_requires_auth(client, data_dir):
    resp = client.put(
        "/workspace/proj-1/code.js",
        content=b"api.say('hello');",
    )
    assert resp.status_code == 401


def test_upload_creates_file(client, data_dir):
    resp = client.put(
        "/workspace/proj-1/subdir/code.js",
        content=b"api.say('hello');",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    dest = data_dir / "workspaces" / "proj-1" / "subdir" / "code.js"
    assert dest.exists()
    assert dest.read_bytes() == b"api.say('hello');"


def test_upload_nested_path(client, data_dir):
    resp = client.put(
        "/workspace/proj-2/a/b/c/script.js",
        content=b"// deep",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    dest = data_dir / "workspaces" / "proj-2" / "a" / "b" / "c" / "script.js"
    assert dest.exists()


def test_state_endpoint_missing_project(client):
    resp = client.get(
        "/state/nonexistent-proj",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 404


def test_state_endpoint_requires_auth(client):
    resp = client.get("/state/proj-1")
    assert resp.status_code == 401


def test_state_endpoint_returns_state_json(client, data_dir):
    state_dir = data_dir / "proj-1"
    state_dir.mkdir(parents=True)
    (state_dir / ".state.json").write_text('{"flows": {}}')
    resp = client.get(
        "/state/proj-1",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"flows": {}}


# Access the registered call_tool handler via the MCP Server's request_handlers dict.
# This is an SDK implementation detail — if the SDK restructures request_handlers,
# update these tests to match.
def test_configure_tool_creates_session(tmp_path, monkeypatch):
    monkeypatch.setenv("COGNIGY_VIBE_DATA_DIR", str(tmp_path / "data"))
    import asyncio
    import mcp.types as types
    from cognigy_mcp.session import SessionContext
    from cognigy_mcp.server_http import _make_session_server

    session_ref: list[SessionContext | None] = [None]
    server = _make_session_server(session_ref)

    handler = server.request_handlers[types.CallToolRequest]

    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(
            name="configure",
            arguments={
                "base_url": "https://cognigy-api-au1.example.com",
                "api_key": "test-key",
                "project_id": "proj-99",
            },
        ),
    )
    result = asyncio.run(handler(req))
    content = result.root.content
    data = json.loads(content[0].text)
    assert data["configured"] is True
    assert session_ref[0] is not None
    assert session_ref[0].state.project_id == "proj-99"
    assert (tmp_path / "data" / "workspaces" / "proj-99").exists()


def test_tool_call_before_configure_returns_error(tmp_path, monkeypatch):
    monkeypatch.setenv("COGNIGY_VIBE_DATA_DIR", str(tmp_path / "data"))
    import asyncio
    import mcp.types as types
    from cognigy_mcp.server_http import _make_session_server

    session_ref: list[None] = [None]
    server = _make_session_server(session_ref)

    handler = server.request_handlers[types.CallToolRequest]

    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(
            name="cognigy_get",
            arguments={"resource_type": "flows", "resource_id": "abc"},
        ),
    )
    result = asyncio.run(handler(req))
    content = result.root.content
    data = json.loads(content[0].text)
    assert "error" in data
    assert "configure" in data.get("hint", "")
