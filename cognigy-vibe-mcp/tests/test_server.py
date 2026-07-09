import json
from pathlib import Path
import pytest
from cognigy_mcp.server import create_server, _find_config_file


def test_server_creates_without_error(monkeypatch, tmp_path):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://cognigy-api-au1.nicecxone.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "test-key")
    monkeypatch.setenv("COGNIGY_PROJECT_ID", "proj-123")
    monkeypatch.delenv("COGNIGY_VIBE_DEV", raising=False)
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    server, all_tools = create_server()
    tool_names = [t.name for t in all_tools]
    assert "cognigy_get" in tool_names
    assert "explain" in tool_names
    assert "explain_dev" not in tool_names
    assert "push_code_node" in tool_names
    assert "push_agent_avatar" in tool_names
    assert "talk_to_agent" in tool_names
    assert "sync_remote_state" in tool_names
    assert len(all_tools) == 19


def test_server_boots_without_project_id(monkeypatch, tmp_path):
    """Server must start successfully when COGNIGY_PROJECT_ID is not set."""
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://cognigy-api-au1.nicecxone.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "test-key")
    monkeypatch.delenv("COGNIGY_PROJECT_ID", raising=False)
    monkeypatch.delenv("COGNIGY_VIBE_DEV", raising=False)
    monkeypatch.setattr("cognigy_mcp.state.CONFIG_BASE", tmp_path / "config")
    server, all_tools = create_server()
    assert len(all_tools) == 19


# --- degraded / dev mode tests (append below existing tests) ---

def test_create_server_degraded_when_no_env(monkeypatch):
    monkeypatch.delenv("COGNIGY_BASE_URL", raising=False)
    monkeypatch.delenv("COGNIGY_API_KEY", raising=False)
    from cognigy_mcp import server
    import importlib
    importlib.reload(server)
    s, tools = server.create_server()
    tool_names = [t.name for t in tools]
    # Degraded mode exposes the full tool surface so the session list is identical to full mode.
    assert "cognigy_get" in tool_names
    assert "explain" in tool_names
    assert "sync_remote_state" in tool_names
    assert "init" not in tool_names
    assert "reload_mcp" not in tool_names
    assert len(tools) == 19


def test_create_server_degraded_when_missing_key(monkeypatch):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://example.com")
    monkeypatch.delenv("COGNIGY_API_KEY", raising=False)
    from cognigy_mcp import server
    import importlib
    importlib.reload(server)
    s, tools = server.create_server()
    tool_names = [t.name for t in tools]
    assert "cognigy_get" in tool_names
    assert "init" not in tool_names


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
    assert "cognigy_get" in tool_names
    assert "reload_mcp" not in tool_names
    assert "init" not in tool_names


# --- _find_config_file tests ---

def test_find_config_file_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {"$schemaVersion": 2, "connection": {"region": "au1"}}
    (tmp_path / "default-demo-config.json").write_text(json.dumps(cfg))
    result, source = _find_config_file()
    assert result is not None
    assert result["connection"]["region"] == "au1"
    assert "default-demo-config.json" in source


def test_find_config_file_in_ancestor(tmp_path, monkeypatch):
    child = tmp_path / "acme-demo"
    child.mkdir()
    monkeypatch.chdir(child)
    cfg = {"$schemaVersion": 2, "connection": {"region": "na1"}}
    (tmp_path / "default-demo-config.json").write_text(json.dumps(cfg))
    result, source = _find_config_file()
    assert result is not None
    assert result["connection"]["region"] == "na1"


def test_find_config_file_global_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    global_dir = tmp_path / ".config" / "cognigy-vibe"
    global_dir.mkdir(parents=True)
    cfg = {"$schemaVersion": 2, "connection": {"region": "jp1"}}
    (global_dir / "config.json").write_text(json.dumps(cfg))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result, source = _find_config_file()
    assert result is not None
    assert result["connection"]["region"] == "jp1"
    assert "config.json" in source


def test_find_config_file_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result, source = _find_config_file()
    assert result is None
    assert source is None


def test_find_config_file_cwd_wins_over_ancestor(tmp_path, monkeypatch):
    child = tmp_path / "acme-demo"
    child.mkdir()
    monkeypatch.chdir(child)
    parent_cfg = {"$schemaVersion": 2, "connection": {"region": "au1"}}
    child_cfg = {"$schemaVersion": 2, "connection": {"region": "na1"}}
    (tmp_path / "default-demo-config.json").write_text(json.dumps(parent_cfg))
    (child / "default-demo-config.json").write_text(json.dumps(child_cfg))
    result, source = _find_config_file()
    assert result["connection"]["region"] == "na1"  # child wins
