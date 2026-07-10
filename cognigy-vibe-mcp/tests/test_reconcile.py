# cognigy-vibe-mcp/tests/test_reconcile.py
import json
from unittest.mock import patch, MagicMock

import httpx
import pytest
import respx

from cognigy_mcp.reconcile import (
    SetupState,
    DriftIssue,
    gather_state,
    diff_state,
    apply_fixes,
    check_pypi_latest,
)


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


def test_read_marketplace_ref_returns_none_when_cli_returns_json_null():
    """gather_state()'s marketplace read must degrade gracefully, not raise,
    when the CLI returns valid-but-unexpected JSON (null instead of a list).
    Regression guard for PR #186 review finding 1.
    """
    from cognigy_mcp.reconcile import _read_marketplace_ref

    def _run(cmd, **kwargs):
        result = MagicMock()
        result.stdout = "null"
        return result

    with patch("subprocess.run", side_effect=_run):
        assert _read_marketplace_ref() is None


def test_read_plugin_install_returns_none_tuple_when_entry_is_not_a_dict():
    """gather_state()'s plugin read must degrade gracefully, not raise,
    when the CLI returns a JSON list containing a non-dict item.
    Regression guard for PR #186 review finding 1.
    """
    from cognigy_mcp.reconcile import _read_plugin_install

    def _run(cmd, **kwargs):
        result = MagicMock()
        result.stdout = json.dumps(["not-a-dict"])
        return result

    with patch("subprocess.run", side_effect=_run):
        assert _read_plugin_install() == (None, None)


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


def _aligned_state(**overrides):
    base = dict(
        package_version="1.7.0",
        marketplace_ref="v1.7.0",
        plugin_version="1.7.0",
        plugin_scope="user",
        desktop_pin="1.7.0",
        layout_schema_version=1,
    )
    base.update(overrides)
    return SetupState(**base)


def test_diff_state_empty_when_everything_aligned():
    assert diff_state(_aligned_state()) == []


def test_diff_state_flags_marketplace_ref_drift():
    issues = diff_state(_aligned_state(marketplace_ref="v1.6.0"))
    assert len(issues) == 1
    assert issues[0].surface == "marketplace_ref"
    assert issues[0].current == "v1.6.0"
    assert issues[0].expected == "v1.7.0"
    assert issues[0].kind == "drift"


def test_diff_state_flags_plugin_version_drift():
    issues = diff_state(_aligned_state(plugin_version="1.6.0"))
    assert issues == [DriftIssue(surface="plugin_version", current="1.6.0", expected="1.7.0", kind="drift")]


def test_diff_state_flags_desktop_pin_drift():
    issues = diff_state(_aligned_state(desktop_pin="1.6.0"))
    assert issues == [DriftIssue(surface="desktop_pin", current="1.6.0", expected="1.7.0", kind="drift")]


def test_diff_state_flags_layout_schema_drift():
    issues = diff_state(_aligned_state(layout_schema_version=0))
    assert issues == [DriftIssue(surface="layout_schema_version", current="0", expected="1", kind="drift")]


def test_diff_state_flags_missing_surfaces_not_drift():
    issues = diff_state(_aligned_state(marketplace_ref=None, plugin_version=None, plugin_scope=None))
    surfaces = {i.surface: i.kind for i in issues}
    assert surfaces["marketplace_ref"] == "missing"
    assert surfaces["plugin_version"] == "missing"


def test_apply_fixes_reinstalls_plugin_on_marketplace_or_version_drift(tmp_path):
    state = _aligned_state()
    issues = [DriftIssue("marketplace_ref", "v1.6.0", "v1.7.0", "drift")]
    with patch("cognigy_mcp.setup.install_plugin") as mock_install:
        apply_fixes(issues, state)
    mock_install.assert_called_once_with("user")


def test_apply_fixes_propagates_subprocess_failure_during_plugin_repair():
    import subprocess
    state = _aligned_state()
    issues = [DriftIssue("plugin_version", "1.6.0", "1.7.0", "drift")]
    with patch("cognigy_mcp.setup.get_installed_version", return_value="1.7.0"), \
         patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["claude"])):
        with pytest.raises(subprocess.CalledProcessError):
            apply_fixes(issues, state)


def test_apply_fixes_rewrites_desktop_pin(tmp_path):
    desktop_path = tmp_path / "claude_desktop_config.json"
    desktop_path.write_text(json.dumps({
        "mcpServers": {"cognigy-vibe": {"command": "uvx", "args": ["--from", "cognigy-vibe-mcp==1.6.0", "cognigy-vibe-launch"]}}
    }))
    state = _aligned_state()
    issues = [DriftIssue("desktop_pin", "1.6.0", "1.7.0", "drift")]
    with patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path):
        apply_fixes(issues, state)
    data = json.loads(desktop_path.read_text())
    assert data["mcpServers"]["cognigy-vibe"]["args"] == ["--from", "cognigy-vibe-mcp==1.7.0", "cognigy-vibe-launch"]


def test_apply_fixes_migrates_layout_schema_marker(tmp_path):
    meta_path = tmp_path / ".setup-meta.json"
    state = _aligned_state()
    issues = [DriftIssue("layout_schema_version", "0", "1", "drift")]
    with patch("cognigy_mcp.reconcile.SETUP_META_PATH", meta_path):
        apply_fixes(issues, state)
    assert json.loads(meta_path.read_text()) == {"schema_version": 1}


def test_apply_fixes_never_touches_missing_surfaces(tmp_path):
    state = _aligned_state()
    issues = [DriftIssue("desktop_pin", None, "1.7.0", "missing")]
    with patch("cognigy_mcp.setup.get_desktop_config_path") as mock_path, \
         patch("cognigy_mcp.setup.merge_desktop_config") as mock_merge, \
         patch("cognigy_mcp.setup.install_plugin") as mock_install:
        apply_fixes(issues, state)
    mock_path.assert_not_called()
    mock_merge.assert_not_called()
    mock_install.assert_not_called()


def test_apply_fixes_asserts_when_plugin_version_drift_has_no_scope():
    """gather_state() should never produce plugin_version/marketplace_ref drift
    paired with plugin_scope=None, since _read_plugin_install() reads both
    from the same claude plugin list entry. If this invariant is ever
    violated, fail loudly instead of silently defaulting to scope "user".
    Regression guard for issue #185 fix 3.
    """
    state = _aligned_state(plugin_scope=None)
    issues = [DriftIssue("plugin_version", "1.6.0", "1.7.0", "drift")]
    with pytest.raises(AssertionError):
        apply_fixes(issues, state)


def test_apply_fixes_asserts_when_marketplace_ref_drift_has_no_scope():
    state = _aligned_state(plugin_scope=None)
    issues = [DriftIssue("marketplace_ref", "v1.6.0", "v1.7.0", "drift")]
    with pytest.raises(AssertionError):
        apply_fixes(issues, state)


def test_check_pypi_latest_returns_version_string():
    with respx.mock:
        respx.get("https://pypi.org/pypi/cognigy-vibe-mcp/json").mock(
            return_value=httpx.Response(200, json={"info": {"version": "1.8.0"}})
        )
        assert check_pypi_latest("cognigy-vibe-mcp") == "1.8.0"


def test_check_pypi_latest_raises_on_404():
    with respx.mock:
        respx.get("https://pypi.org/pypi/cognigy-vibe-mcp/json").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(httpx.HTTPStatusError):
            check_pypi_latest("cognigy-vibe-mcp")


def test_check_pypi_latest_raises_on_network_error():
    with respx.mock:
        respx.get("https://pypi.org/pypi/cognigy-vibe-mcp/json").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        with pytest.raises(httpx.ConnectError):
            check_pypi_latest("cognigy-vibe-mcp")


def test_check_pypi_latest_raises_on_malformed_response():
    with respx.mock:
        respx.get("https://pypi.org/pypi/cognigy-vibe-mcp/json").mock(
            return_value=httpx.Response(200, json={"unexpected": "shape"})
        )
        with pytest.raises(KeyError):
            check_pypi_latest("cognigy-vibe-mcp")
