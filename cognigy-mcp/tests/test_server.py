import pytest
from cognigy_mcp.server import create_server


def test_server_creates_without_error(monkeypatch, tmp_path):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://cognigy-api-au1.nicecxone.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "test-key")
    monkeypatch.setenv("COGNIGY_PROJECT_ID", "proj-123")
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    server, all_tools = create_server()
    tool_names = [t.name for t in all_tools]
    assert "cognigy_get" in tool_names
    assert "explain" in tool_names
    assert "explain_dev" not in tool_names
    assert "push_code_node" in tool_names
    assert "talk_to_agent" in tool_names
    assert "sync_remote_state" in tool_names
    assert len(all_tools) == 15


def test_server_boots_without_project_id(monkeypatch, tmp_path):
    """Server must start successfully when COGNIGY_PROJECT_ID is not set."""
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://cognigy-api-au1.nicecxone.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "test-key")
    monkeypatch.delenv("COGNIGY_PROJECT_ID", raising=False)
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    server, all_tools = create_server()
    assert len(all_tools) == 15


# --- degraded / dev mode tests (append below existing tests) ---

def test_create_server_degraded_when_no_env(monkeypatch):
    monkeypatch.delenv("COGNIGY_BASE_URL", raising=False)
    monkeypatch.delenv("COGNIGY_API_KEY", raising=False)
    from cognigy_mcp import server
    import importlib
    importlib.reload(server)
    s, tools = server.create_server()
    tool_names = [t.name for t in tools]
    assert tool_names == ["init"]


def test_create_server_degraded_when_missing_key(monkeypatch):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://example.com")
    monkeypatch.delenv("COGNIGY_API_KEY", raising=False)
    from cognigy_mcp import server
    import importlib
    importlib.reload(server)
    s, tools = server.create_server()
    assert tools[0].name == "init"


def test_create_server_full_when_env_set(monkeypatch, tmp_path, respx_mock):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://example.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "key")
    monkeypatch.delenv("COGNIGY_VIBE_DEV", raising=False)
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    from cognigy_mcp import server
    import importlib
    importlib.reload(server)
    s, tools = server.create_server()
    tool_names = [t.name for t in tools]
    assert "init" not in tool_names
    assert "sync_remote_state" in tool_names
    assert "reload_mcp" not in tool_names


def test_create_server_dev_mode_includes_reload_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://example.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "key")
    monkeypatch.setenv("COGNIGY_VIBE_DEV", "1")
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    from cognigy_mcp import server
    import importlib
    importlib.reload(server)
    s, tools = server.create_server()
    tool_names = [t.name for t in tools]
    assert "reload_mcp" in tool_names
    assert "sync_remote_state" in tool_names


def test_create_server_dev_flag_ignored_without_credentials(monkeypatch):
    monkeypatch.setenv("COGNIGY_VIBE_DEV", "1")
    monkeypatch.delenv("COGNIGY_BASE_URL", raising=False)
    monkeypatch.delenv("COGNIGY_API_KEY", raising=False)
    from cognigy_mcp import server
    import importlib
    importlib.reload(server)
    s, tools = server.create_server()
    tool_names = [t.name for t in tools]
    assert tool_names == ["init"]
    assert "reload_mcp" not in tool_names
