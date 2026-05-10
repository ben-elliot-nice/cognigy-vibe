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
    assert "push_code_node" in tool_names
    assert "talk_to_agent" in tool_names
    assert "sync_remote_state" in tool_names
    assert len(all_tools) == 15
