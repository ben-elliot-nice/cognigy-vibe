# cognigy-mcp/tests/test_reconcile.py
import json
from unittest.mock import patch, MagicMock

from cognigy_mcp.reconcile import SetupState, DriftIssue, gather_state


def test_setup_state_holds_all_five_surfaces():
    state = SetupState(
        package_version="1.7.0",
        marketplace_ref="v1.7.0",
        plugin_version="1.7.0",
        plugin_scope="user",
        desktop_pin="1.7.0",
        layout_schema_version=1,
    )
    assert state.package_version == "1.7.0"
    assert state.layout_schema_version == 1


def test_drift_issue_has_surface_current_expected_kind():
    issue = DriftIssue(surface="plugin_version", current="1.6.0", expected="1.7.0", kind="drift")
    assert issue.kind == "drift"
    assert issue.current == "1.6.0"


def _run_side_effect(marketplace_json, plugin_json):
    def _run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        if cmd[:3] == ["claude", "plugin", "marketplace"]:
            result.stdout = json.dumps(marketplace_json)
        elif cmd[:3] == ["claude", "plugin", "list"]:
            result.stdout = json.dumps(plugin_json)
        else:
            raise AssertionError(f"unexpected subprocess call: {cmd}")
        return result
    return _run


def test_gather_state_reads_all_present_surfaces(tmp_path, monkeypatch):
    desktop_path = tmp_path / "claude_desktop_config.json"
    desktop_path.write_text(json.dumps({
        "mcpServers": {"cognigy-vibe": {"command": "uvx", "args": ["--from", "cognigy-vibe-mcp==1.7.0", "cognigy-vibe-launch"]}}
    }))
    meta_path = tmp_path / ".setup-meta.json"
    meta_path.write_text(json.dumps({"schema_version": 1}))

    marketplace_json = [{"name": "cognigy-vibe", "ref": "v1.7.0"}]
    plugin_json = [{"id": "cognigy-vibe@cognigy-vibe", "version": "1.7.0", "scope": "user"}]

    with patch("cognigy_mcp.setup.get_installed_version", return_value="1.7.0"), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.reconcile.SETUP_META_PATH", meta_path), \
         patch("subprocess.run", side_effect=_run_side_effect(marketplace_json, plugin_json)):
        state = gather_state()

    assert state.package_version == "1.7.0"
    assert state.marketplace_ref == "v1.7.0"
    assert state.plugin_version == "1.7.0"
    assert state.plugin_scope == "user"
    assert state.desktop_pin == "1.7.0"
    assert state.layout_schema_version == 1


def test_gather_state_soft_fails_absent_surfaces(tmp_path):
    desktop_path = tmp_path / "claude_desktop_config.json"  # does not exist
    meta_path = tmp_path / ".setup-meta.json"  # does not exist

    with patch("cognigy_mcp.setup.get_installed_version", return_value="1.7.0"), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.reconcile.SETUP_META_PATH", meta_path), \
         patch("subprocess.run", side_effect=FileNotFoundError("claude not on PATH")):
        state = gather_state()

    assert state.package_version == "1.7.0"
    assert state.marketplace_ref is None
    assert state.plugin_version is None
    assert state.plugin_scope is None
    assert state.desktop_pin is None
    assert state.layout_schema_version is None


def test_gather_state_handles_malformed_json_from_claude_cli(tmp_path):
    desktop_path = tmp_path / "claude_desktop_config.json"
    meta_path = tmp_path / ".setup-meta.json"

    def _bad_run(cmd, **kwargs):
        result = MagicMock()
        result.stdout = "not json"
        return result

    with patch("cognigy_mcp.setup.get_installed_version", return_value="1.7.0"), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.reconcile.SETUP_META_PATH", meta_path), \
         patch("subprocess.run", side_effect=_bad_run):
        state = gather_state()

    assert state.marketplace_ref is None
    assert state.plugin_version is None
