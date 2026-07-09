# cognigy-mcp/tests/test_setup.py
import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch
import pytest


def test_get_desktop_config_path_macos():
    with patch.object(sys, "platform", "darwin"):
        from importlib import reload
        import cognigy_mcp.setup as setup_mod
        reload(setup_mod)
        p = setup_mod.get_desktop_config_path()
    assert "Library" in str(p)
    assert "Claude" in str(p)
    assert p.name == "claude_desktop_config.json"


def test_get_desktop_config_path_linux():
    with patch.object(sys, "platform", "linux"):
        from importlib import reload
        import cognigy_mcp.setup as setup_mod
        reload(setup_mod)
        p = setup_mod.get_desktop_config_path()
    assert ".config" in str(p)
    assert "claude-desktop" in str(p)


def test_get_desktop_config_path_windows():
    fake_appdata = "/fake/AppData/Roaming"
    with patch.object(sys, "platform", "win32"), \
         patch.dict(os.environ, {"APPDATA": fake_appdata}):
        from importlib import reload
        import cognigy_mcp.setup as setup_mod
        reload(setup_mod)
        p = setup_mod.get_desktop_config_path()
    assert "AppData" in str(p) or "fake" in str(p)
    assert "Claude" in str(p)


def test_merge_desktop_config_creates_file(tmp_path):
    from cognigy_mcp.setup import merge_desktop_config
    config_path = tmp_path / "claude_desktop_config.json"
    entry = {"command": "uvx", "args": ["--from", "cognigy-vibe-mcp==1.7.0", "cognigy-vibe-launch"]}
    merge_desktop_config(config_path, "cognigy-vibe", entry)
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data["mcpServers"]["cognigy-vibe"] == entry


def test_merge_desktop_config_preserves_existing_entries(tmp_path):
    from cognigy_mcp.setup import merge_desktop_config
    config_path = tmp_path / "claude_desktop_config.json"
    config_path.write_text(json.dumps({
        "mcpServers": {"other-server": {"command": "node", "args": ["server.js"]}}
    }))
    entry = {"command": "uvx", "args": ["--from", "cognigy-vibe-mcp==1.7.0", "cognigy-vibe-launch"]}
    merge_desktop_config(config_path, "cognigy-vibe", entry)
    data = json.loads(config_path.read_text())
    assert "other-server" in data["mcpServers"]
    assert "cognigy-vibe" in data["mcpServers"]


def test_merge_desktop_config_overwrites_existing_cognigy_entry(tmp_path):
    from cognigy_mcp.setup import merge_desktop_config
    config_path = tmp_path / "claude_desktop_config.json"
    config_path.write_text(json.dumps({
        "mcpServers": {"cognigy-vibe": {"command": "uvx", "args": ["cognigy-vibe-mcp"]}}
    }))
    new_entry = {"command": "uvx", "args": ["--from", "cognigy-vibe-mcp==1.7.0", "cognigy-vibe-launch"]}
    merge_desktop_config(config_path, "cognigy-vibe", new_entry)
    data = json.loads(config_path.read_text())
    assert data["mcpServers"]["cognigy-vibe"] == new_entry


def test_write_credential_env_creates_file(tmp_path):
    from cognigy_mcp.setup import write_credential_env
    env_path = tmp_path / ".env"
    write_credential_env(env_path, "https://example.com", "my-key")
    content = env_path.read_text()
    assert "COGNIGY_BASE_URL=https://example.com" in content
    assert "COGNIGY_API_KEY=my-key" in content


def test_write_credential_env_preserves_existing_keys(tmp_path):
    from cognigy_mcp.setup import write_credential_env
    env_path = tmp_path / ".env"
    env_path.write_text("COGNIGY_PROJECT_ID=existing-project\nCOGNIGY_BASE_URL=https://old.example.com\n")
    write_credential_env(env_path, "https://new.example.com", "new-key")
    content = env_path.read_text()
    assert "COGNIGY_PROJECT_ID=existing-project" in content
    assert "COGNIGY_BASE_URL=https://new.example.com" in content
    assert "COGNIGY_API_KEY=new-key" in content
    assert "https://old.example.com" not in content


def test_write_credential_env_creates_parent_dirs(tmp_path):
    from cognigy_mcp.setup import write_credential_env
    env_path = tmp_path / ".config" / "cognigy-vibe" / ".env"
    write_credential_env(env_path, "https://example.com", "my-key")
    assert env_path.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="chmod not meaningful on Windows")
def test_write_credential_env_sets_permissions(tmp_path):
    from cognigy_mcp.setup import write_credential_env
    env_path = tmp_path / ".env"
    write_credential_env(env_path, "https://example.com", "my-key")
    mode = oct(stat.S_IMODE(env_path.stat().st_mode))
    assert mode == "0o600"


def test_get_installed_version():
    from cognigy_mcp.setup import get_installed_version
    ver = get_installed_version()
    assert isinstance(ver, str)
    assert "." in ver


def test_install_plugin_calls_claude_cli():
    from unittest.mock import patch
    from cognigy_mcp.setup import install_plugin
    with patch("cognigy_mcp.setup.get_installed_version", return_value="1.7.0"), \
         patch("subprocess.run") as mock_run:
        install_plugin("user")
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["claude", "plugin", "marketplace", "add", "ben-elliot-nice/cognigy-claude-plugin@v1.7.0"],
            check=True,
        )
        mock_run.assert_any_call(
            ["claude", "plugin", "install", "cognigy-vibe@cognigy-vibe", "--scope", "user"],
            check=True,
        )


def test_install_plugin_version_pins_prerelease():
    from unittest.mock import patch
    from cognigy_mcp.setup import install_plugin
    with patch("cognigy_mcp.setup.get_installed_version", return_value="1.7.0rc8"), \
         patch("subprocess.run") as mock_run:
        install_plugin("project")
        mock_run.assert_any_call(
            ["claude", "plugin", "marketplace", "add", "ben-elliot-nice/cognigy-claude-plugin@v1.7.0rc8"],
            check=True,
        )


def test_install_plugin_rejects_invalid_scope():
    import pytest
    from cognigy_mcp.setup import install_plugin
    with pytest.raises(ValueError, match="Invalid scope"):
        install_plugin("global")


def test_parse_args_defaults_to_install_with_no_argv(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup"])
    args = _parse_args()
    assert args.command == "install"


def test_parse_args_defaults_to_install_when_only_legacy_flags_given(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "--install-only", "--scope", "project"])
    args = _parse_args()
    assert args.command == "install"
    assert args.install_only is True
    assert args.scope == "project"


def test_parse_args_explicit_install_subcommand(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "install", "--client", "code"])
    args = _parse_args()
    assert args.command == "install"
    assert args.client == "code"


def test_parse_args_status(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "status"])
    args = _parse_args()
    assert args.command == "status"
    assert args.fix is False


def test_parse_args_status_fix(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "status", "--fix"])
    args = _parse_args()
    assert args.command == "status"
    assert args.fix is True


def test_parse_args_update(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "update"])
    args = _parse_args()
    assert args.command == "update"
    assert args.check is False


def test_parse_args_update_check(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "update", "--check"])
    args = _parse_args()
    assert args.command == "update"
    assert args.check is True


def test_parse_args_uninstall(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "uninstall"])
    args = _parse_args()
    assert args.command == "uninstall"
