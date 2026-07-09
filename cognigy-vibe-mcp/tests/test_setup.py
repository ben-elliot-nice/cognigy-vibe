# cognigy-vibe-mcp/tests/test_setup.py
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
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        mock_run.return_value = None
        install_plugin("user")
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["claude", "plugin", "marketplace", "add", "ben-elliot-nice/cognigy-vibe@v1.7.0"],
            "Adding marketplace",
            verbose=False,
        )
        mock_run.assert_any_call(
            ["claude", "plugin", "install", "cognigy-vibe@cognigy-vibe", "--scope", "user"],
            "Installing plugin",
            verbose=False,
        )


def test_install_plugin_version_pins_prerelease():
    from unittest.mock import patch
    from cognigy_mcp.setup import install_plugin
    with patch("cognigy_mcp.setup.get_installed_version", return_value="1.7.0rc8"), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        install_plugin("project")
        mock_run.assert_any_call(
            ["claude", "plugin", "marketplace", "add", "ben-elliot-nice/cognigy-vibe@v1.7.0rc8"],
            "Adding marketplace",
            verbose=False,
        )


def test_install_plugin_passes_verbose_through():
    from unittest.mock import patch
    from cognigy_mcp.setup import install_plugin
    with patch("cognigy_mcp.setup.get_installed_version", return_value="1.7.0"), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        install_plugin("user", verbose=True)
        mock_run.assert_any_call(
            ["claude", "plugin", "marketplace", "add", "ben-elliot-nice/cognigy-vibe@v1.7.0"],
            "Adding marketplace",
            verbose=True,
        )


def test_install_plugin_rejects_invalid_scope():
    import pytest
    from cognigy_mcp.setup import install_plugin
    with pytest.raises(ValueError, match="Invalid scope"):
        install_plugin("global")


def test_install_plugin_raises_step_failure_on_cli_error():
    from unittest.mock import patch
    from cognigy_mcp.setup import install_plugin
    from cognigy_mcp.wizard_ui import StepFailure, SubprocessResult
    import pytest
    failure = StepFailure("Adding marketplace", SubprocessResult(returncode=1, stdout="", stderr="denied"))
    with patch("cognigy_mcp.setup.get_installed_version", return_value="1.7.0"), \
         patch("cognigy_mcp.setup.run_subprocess", side_effect=failure):
        with pytest.raises(StepFailure):
            install_plugin("user")


def test_parse_args_verbose_flag_defaults_false():
    from unittest.mock import patch
    from cognigy_mcp.setup import _parse_args
    with patch("sys.argv", ["cognigy-vibe-setup"]):
        args = _parse_args()
    assert args.verbose is False


def test_parse_args_verbose_flag_can_be_set():
    from unittest.mock import patch
    from cognigy_mcp.setup import _parse_args
    with patch("sys.argv", ["cognigy-vibe-setup", "--verbose"]):
        args = _parse_args()
    assert args.verbose is True


def test_main_renders_error_panel_on_unhandled_exception():
    from unittest.mock import patch
    from cognigy_mcp.setup import main
    with patch("sys.argv", ["cognigy-vibe-setup", "--install-only", "--client", "code", "--scope", "user"]), \
         patch("cognigy_mcp.setup.install_plugin", side_effect=RuntimeError("network down")), \
         patch("cognigy_mcp.setup.print_error_panel") as mock_panel, \
         patch("cognigy_mcp.setup.print_summary"), \
         patch("cognigy_mcp.setup.print_header"), \
         patch("cognigy_mcp.setup.print_section"), \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert mock_panel.call_count == 1
    call_args = mock_panel.call_args
    assert call_args.args[0] == "Setup failed."
    assert isinstance(call_args.args[1], RuntimeError)
    assert call_args.kwargs["debug"] is False


def test_main_passes_verbose_to_error_panel_debug():
    from unittest.mock import patch
    from cognigy_mcp.setup import main
    with patch("sys.argv", ["cognigy-vibe-setup", "--install-only", "--client", "code", "--scope", "user", "--verbose"]), \
         patch("cognigy_mcp.setup.install_plugin", side_effect=RuntimeError("network down")), \
         patch("cognigy_mcp.setup.print_error_panel") as mock_panel, \
         patch("cognigy_mcp.setup.print_summary"), \
         patch("cognigy_mcp.setup.print_header"), \
         patch("cognigy_mcp.setup.print_section"), \
         pytest.raises(SystemExit):
        main()
    assert mock_panel.call_args.kwargs["debug"] is True


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


def test_parse_args_bare_help_shows_top_level_subcommands(monkeypatch, capsys):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "--help"])
    with pytest.raises(SystemExit):
        _parse_args()
    output = capsys.readouterr().out
    assert "status" in output
    assert "update" in output


def test_parse_args_typo_subcommand_reports_invalid_choice(monkeypatch, capsys):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "satus"])
    with pytest.raises(SystemExit):
        _parse_args()
    err = capsys.readouterr().err
    assert "invalid choice" in err
    assert "'satus'" in err
    assert "install" in err
    assert "status" in err
    assert "update" in err
    assert "uninstall" in err


from cognigy_mcp.reconcile import SetupState, DriftIssue


def _state(**overrides):
    base = dict(
        package_version="1.7.0", marketplace_ref="v1.7.0", plugin_version="1.7.0",
        plugin_scope="user", desktop_pin="1.7.0", layout_schema_version=1,
    )
    base.update(overrides)
    return SetupState(**base)


def test_run_status_exits_zero_when_aligned(capsys):
    from cognigy_mcp.setup import _run_status
    args = type("Args", (), {"fix": False})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state()):
        with pytest.raises(SystemExit) as exc:
            _run_status(args)
    assert exc.value.code == 0
    assert "marketplace_ref" in capsys.readouterr().out


def test_run_status_exits_nonzero_when_drift_found_without_fix():
    from cognigy_mcp.setup import _run_status
    args = type("Args", (), {"fix": False})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_version="1.6.0")):
        with pytest.raises(SystemExit) as exc:
            _run_status(args)
    assert exc.value.code == 1


def test_run_status_fix_applies_fixes_and_exits_zero():
    from cognigy_mcp.setup import _run_status
    args = type("Args", (), {"fix": True})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_version="1.6.0")), \
         patch("cognigy_mcp.reconcile.apply_fixes") as mock_apply:
        with pytest.raises(SystemExit) as exc:
            _run_status(args)
    assert exc.value.code == 0
    mock_apply.assert_called_once()
    called_issues = mock_apply.call_args[0][0]
    assert all(issue.kind == "drift" for issue in called_issues)


def test_run_status_fix_does_not_call_apply_fixes_when_nothing_drifted():
    from cognigy_mcp.setup import _run_status
    args = type("Args", (), {"fix": True})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state()), \
         patch("cognigy_mcp.reconcile.apply_fixes") as mock_apply:
        with pytest.raises(SystemExit) as exc:
            _run_status(args)
    assert exc.value.code == 0
    mock_apply.assert_not_called()


def test_run_update_hard_fails_when_pypi_unreachable(capsys):
    from cognigy_mcp.setup import _run_update
    args = type("Args", (), {"check": False, "verbose": False})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state()), \
         patch("cognigy_mcp.reconcile.check_pypi_latest", side_effect=Exception("network down")), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        with pytest.raises(SystemExit) as exc:
            _run_update(args)
    assert exc.value.code == 1
    assert "status --fix" in capsys.readouterr().err
    mock_run.assert_not_called()


def test_run_update_short_circuits_when_already_latest():
    from cognigy_mcp.setup import _run_update
    args = type("Args", (), {"check": False, "verbose": False})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state()), \
         patch("cognigy_mcp.reconcile.check_pypi_latest", return_value="1.7.0"), \
         patch("cognigy_mcp.reconcile.apply_fixes") as mock_apply, \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        with pytest.raises(SystemExit) as exc:
            _run_update(args)
    assert exc.value.code == 0
    mock_run.assert_not_called()  # no `uv tool upgrade` call
    mock_apply.assert_not_called()  # aligned state, nothing to fix


def test_run_update_exits_nonzero_when_uv_missing_and_upgrade_never_happened(monkeypatch):
    from cognigy_mcp.setup import _run_update
    args = type("Args", (), {"check": False, "verbose": False})()
    monkeypatch.setattr("shutil.which", lambda name: None)
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(package_version="1.6.0")), \
         patch("cognigy_mcp.reconcile.check_pypi_latest", return_value="1.7.0"), \
         patch("cognigy_mcp.reconcile.apply_fixes") as mock_apply, \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        with pytest.raises(SystemExit) as exc:
            _run_update(args)
    assert exc.value.code == 1
    mock_run.assert_not_called()  # no `uv tool upgrade` call, uv not on PATH


def test_run_update_upgrades_package_when_stale(monkeypatch):
    from cognigy_mcp.setup import _run_update
    args = type("Args", (), {"check": False, "verbose": False})()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/uv")
    states = iter([_state(package_version="1.6.0"), _state(package_version="1.7.0")])
    with patch("cognigy_mcp.reconcile.gather_state", side_effect=lambda: next(states)), \
         patch("cognigy_mcp.reconcile.check_pypi_latest", return_value="1.7.0"), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        with pytest.raises(SystemExit) as exc:
            _run_update(args)
    assert exc.value.code == 0
    mock_run.assert_called_once_with(
        ["uv", "tool", "upgrade", "cognigy-vibe-mcp"],
        "Upgrading cognigy-vibe-mcp",
        verbose=False,
    )


def test_run_update_prints_version_transition(monkeypatch, capsys):
    """The upgrade step must show the old -> new version, not just
    run_subprocess's bare description. Regression guard for PR #189
    review finding 1.
    """
    from cognigy_mcp.setup import _run_update
    args = type("Args", (), {"check": False, "verbose": False})()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/uv")
    states = iter([_state(package_version="1.6.0"), _state(package_version="1.7.0")])
    with patch("cognigy_mcp.reconcile.gather_state", side_effect=lambda: next(states)), \
         patch("cognigy_mcp.reconcile.check_pypi_latest", return_value="1.7.0"), \
         patch("cognigy_mcp.setup.run_subprocess"):
        with pytest.raises(SystemExit):
            _run_update(args)
    out = capsys.readouterr().out
    assert "1.6.0" in out
    assert "1.7.0" in out
    assert "->" in out


def test_run_update_upgrade_failure_raises_step_failure(monkeypatch):
    from cognigy_mcp.setup import _run_update
    from cognigy_mcp.wizard_ui import StepFailure, SubprocessResult
    args = type("Args", (), {"check": False, "verbose": False})()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/uv")
    failure = StepFailure("Upgrading cognigy-vibe-mcp", SubprocessResult(returncode=1, stdout="", stderr="locked"))
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(package_version="1.6.0")), \
         patch("cognigy_mcp.reconcile.check_pypi_latest", return_value="1.7.0"), \
         patch("cognigy_mcp.setup.run_subprocess", side_effect=failure):
        with pytest.raises(StepFailure):
            _run_update(args)


def test_run_update_check_reports_without_mutating():
    from cognigy_mcp.setup import _run_update
    args = type("Args", (), {"check": True, "verbose": False})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(package_version="1.6.0")), \
         patch("cognigy_mcp.reconcile.check_pypi_latest", return_value="1.7.0"), \
         patch("cognigy_mcp.reconcile.apply_fixes") as mock_apply, \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        with pytest.raises(SystemExit) as exc:
            _run_update(args)
    assert exc.value.code == 1
    mock_run.assert_not_called()
    mock_apply.assert_not_called()


def test_run_update_applies_fixes_when_drift_found_and_not_check():
    from cognigy_mcp.setup import _run_update
    args = type("Args", (), {"check": False})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(desktop_pin="1.6.0")), \
         patch("cognigy_mcp.reconcile.check_pypi_latest", return_value="1.7.0"), \
         patch("cognigy_mcp.reconcile.apply_fixes") as mock_apply:
        with pytest.raises(SystemExit) as exc:
            _run_update(args)
    assert exc.value.code == 0
    mock_apply.assert_called_once()


def test_run_uninstall_noop_when_not_installed(tmp_path, capsys):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"  # does not exist
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope=None)), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        _run_uninstall(args)
    mock_run.assert_not_called()
    assert "not installed" in capsys.readouterr().out.lower()


def test_run_uninstall_removes_plugin_and_desktop_entry(tmp_path):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"
    desktop_path.write_text(json.dumps({"mcpServers": {"cognigy-vibe": {"command": "uvx"}}}))
    env_path = tmp_path / ".env"  # does not exist -> no credential prompt

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="user")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="n"), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        _run_uninstall(args)

    mock_run.assert_any_call(
        ["claude", "plugin", "uninstall", "cognigy-vibe@cognigy-vibe", "--scope", "user"],
        "Uninstalling plugin",
        verbose=False,
    )
    data = json.loads(desktop_path.read_text())
    assert "cognigy-vibe" not in data.get("mcpServers", {})


@pytest.mark.skipif(sys.platform == "win32", reason="chmod not meaningful on Windows")
def test_run_uninstall_retightens_desktop_config_permissions(tmp_path):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"
    desktop_path.write_text(json.dumps({"mcpServers": {"cognigy-vibe": {"command": "uvx"}}}))
    desktop_path.chmod(0o644)
    env_path = tmp_path / ".env"  # does not exist -> no credential prompt

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="user")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="n"), \
         patch("cognigy_mcp.setup.run_subprocess"):
        _run_uninstall(args)

    mode = oct(stat.S_IMODE(desktop_path.stat().st_mode))
    assert mode == "0o600"


def test_run_uninstall_prompts_before_deleting_credentials(tmp_path):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    env_path = tmp_path / ".env"
    env_path.write_text("COGNIGY_API_KEY=secret\n")
    desktop_path = tmp_path / "claude_desktop_config.json"  # does not exist

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="user")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="n"), \
         patch("cognigy_mcp.setup.run_subprocess"):
        _run_uninstall(args)

    assert env_path.exists()  # user said no, credentials survive


def test_run_uninstall_deletes_credentials_on_confirmation(tmp_path):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    env_path = tmp_path / ".env"
    env_path.write_text("COGNIGY_API_KEY=secret\n")
    desktop_path = tmp_path / "claude_desktop_config.json"

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="user")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="y"), \
         patch("cognigy_mcp.setup.run_subprocess"):
        _run_uninstall(args)

    assert not env_path.exists()


def test_run_uninstall_prints_credential_confirmation_before_later_step_failure(tmp_path, capsys):
    """The credentials branch must print its own confirmation immediately,
    not only via the final print_summary — a later step (e.g. marketplace
    removal) raising StepFailure must not swallow it. Regression guard for
    PR #189 review finding 1.
    """
    from cognigy_mcp.setup import _run_uninstall
    from cognigy_mcp.wizard_ui import StepFailure, SubprocessResult
    args = type("Args", (), {"verbose": False})()
    env_path = tmp_path / ".env"
    env_path.write_text("COGNIGY_API_KEY=secret\n")
    desktop_path = tmp_path / "claude_desktop_config.json"

    failure = StepFailure("Removing marketplace entry", SubprocessResult(returncode=1, stdout="", stderr="boom"))

    def fake_run_subprocess(cmd, description, verbose=False):
        if cmd[:3] == ["claude", "plugin", "marketplace"]:
            raise failure
        return None

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="user")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="y"), \
         patch("cognigy_mcp.setup.run_subprocess", side_effect=fake_run_subprocess):
        with pytest.raises(StepFailure):
            _run_uninstall(args)

    assert not env_path.exists()
    out = capsys.readouterr().out
    assert "Removed credentials" in out
    assert ".env" in out


def test_run_uninstall_prints_header(tmp_path, capsys):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"  # does not exist

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope=None)), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        _run_uninstall(args)

    assert "cognigy-vibe uninstall" in capsys.readouterr().out


def test_run_uninstall_does_not_remove_marketplace_by_default(tmp_path):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"
    env_path = tmp_path / ".env"

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="user")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="n"), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        _run_uninstall(args)

    marketplace_calls = [
        call for call in mock_run.call_args_list
        if call.args[0][:3] == ["claude", "plugin", "marketplace"]
    ]
    assert marketplace_calls == []


def test_run_uninstall_prompts_for_project_scope_credentials(tmp_path, monkeypatch):
    """A project/local-scope install writes credentials to Path.cwd()/.env,
    not USER_ENV_PATH. Uninstall must detect and prompt for that path too.
    Regression guard for PR #186 review finding 2.
    """
    from cognigy_mcp.setup import _run_uninstall

    monkeypatch.chdir(tmp_path)
    project_env_path = tmp_path / ".env"
    project_env_path.write_text("COGNIGY_API_KEY=secret\n")

    user_env_path = tmp_path / "user-home" / ".env"  # does not exist
    desktop_path = tmp_path / "claude_desktop_config.json"  # does not exist

    args = type("Args", (), {"verbose": False})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="project")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", user_env_path), \
         patch("builtins.input", return_value="n") as mock_input, \
         patch("cognigy_mcp.setup.run_subprocess"):
        _run_uninstall(args)

    prompted_paths = [str(call.args[0]) for call in mock_input.call_args_list]
    assert any(str(project_env_path) in p for p in prompted_paths)
    assert project_env_path.exists()  # user said no, credentials survive


def test_run_uninstall_desktop_only_removes_entry_without_plugin_call(tmp_path):
    """Desktop-only installs (plugin_scope=None) must still be detected and cleaned up.

    A user who ran `install --client desktop` never registers a Code plugin,
    so plugin_scope is None even though a live Desktop config entry exists.
    Regression guard for issue #185 fix 1.
    """
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"
    desktop_path.write_text(json.dumps({"mcpServers": {"cognigy-vibe": {"command": "uvx"}}}))
    env_path = tmp_path / ".env"  # does not exist -> no credential prompt

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope=None)), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="n"), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        _run_uninstall(args)

    plugin_uninstall_calls = [
        call for call in mock_run.call_args_list
        if call.args[0][:3] == ["claude", "plugin", "uninstall"]
    ]
    assert plugin_uninstall_calls == []
    data = json.loads(desktop_path.read_text())
    assert "cognigy-vibe" not in data.get("mcpServers", {})


def test_run_uninstall_degrades_gracefully_on_malformed_desktop_config(tmp_path, capsys):
    """A malformed/hand-edited Desktop config must not crash uninstall.
    Matches how reconcile._read_desktop_pin() already degrades gracefully
    on the same file. Regression guard for PR #186 review finding 3.
    """
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"
    desktop_path.write_text("not json")
    env_path = tmp_path / ".env"  # does not exist -> no credential prompt

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="user")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="n"), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        _run_uninstall(args)

    out = capsys.readouterr().out
    assert "warning" in out.lower()
    assert str(desktop_path) in out
    mock_run.assert_any_call(
        ["claude", "plugin", "uninstall", "cognigy-vibe@cognigy-vibe", "--scope", "user"],
        "Uninstalling plugin",
        verbose=False,
    )


def test_run_uninstall_noop_when_no_plugin_and_no_desktop_entry(tmp_path, capsys):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"  # does not exist

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope=None)), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        _run_uninstall(args)

    mock_run.assert_not_called()
    assert "not installed" in capsys.readouterr().out.lower()


def test_run_uninstall_removes_marketplace_with_run_subprocess(tmp_path):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"
    env_path = tmp_path / ".env"

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="user")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="y"), \
         patch("cognigy_mcp.setup.run_subprocess") as mock_run:
        _run_uninstall(args)

    mock_run.assert_any_call(
        ["claude", "plugin", "marketplace", "remove", "cognigy-vibe"],
        "Removing marketplace entry",
        verbose=False,
    )


def test_run_uninstall_prints_summary_of_actions(tmp_path, capsys):
    from cognigy_mcp.setup import _run_uninstall
    args = type("Args", (), {"verbose": False})()
    desktop_path = tmp_path / "claude_desktop_config.json"
    desktop_path.write_text(json.dumps({"mcpServers": {"cognigy-vibe": {"command": "uvx"}}}))
    env_path = tmp_path / ".env"
    env_path.write_text("COGNIGY_API_KEY=secret\n")

    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state(plugin_scope="user")), \
         patch("cognigy_mcp.setup.get_desktop_config_path", return_value=desktop_path), \
         patch("cognigy_mcp.setup.USER_ENV_PATH", env_path), \
         patch("builtins.input", return_value="y"), \
         patch("cognigy_mcp.setup.run_subprocess"):
        _run_uninstall(args)

    out = capsys.readouterr().out
    assert "Summary" in out
    assert "removed" in out.lower()


def test_parse_args_status_verbose_flag(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "status", "--verbose"])
    args = _parse_args()
    assert args.command == "status"
    assert args.verbose is True


def test_parse_args_update_verbose_flag(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "update", "--verbose"])
    args = _parse_args()
    assert args.command == "update"
    assert args.verbose is True


def test_parse_args_uninstall_verbose_flag(monkeypatch):
    from cognigy_mcp.setup import _parse_args
    monkeypatch.setattr("sys.argv", ["cognigy-vibe-setup", "uninstall", "--verbose"])
    args = _parse_args()
    assert args.command == "uninstall"
    assert args.verbose is True


def test_main_renders_error_panel_for_status_command():
    from unittest.mock import patch
    from cognigy_mcp.setup import main
    with patch("sys.argv", ["cognigy-vibe-setup", "status"]), \
         patch("cognigy_mcp.setup._run_status", side_effect=RuntimeError("disk full")), \
         patch("cognigy_mcp.setup.print_error_panel") as mock_panel, \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    mock_panel.assert_called_once()
    assert mock_panel.call_args.args[0] == "Status failed."
    assert isinstance(mock_panel.call_args.args[1], RuntimeError)


def test_main_renders_error_panel_for_update_command():
    from unittest.mock import patch
    from cognigy_mcp.setup import main
    with patch("sys.argv", ["cognigy-vibe-setup", "update"]), \
         patch("cognigy_mcp.setup._run_update", side_effect=RuntimeError("disk full")), \
         patch("cognigy_mcp.setup.print_error_panel") as mock_panel, \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert mock_panel.call_args.args[0] == "Update failed."


def test_main_renders_error_panel_for_uninstall_command():
    from unittest.mock import patch
    from cognigy_mcp.setup import main
    with patch("sys.argv", ["cognigy-vibe-setup", "uninstall"]), \
         patch("cognigy_mcp.setup._run_uninstall", side_effect=RuntimeError("disk full")), \
         patch("cognigy_mcp.setup.print_error_panel") as mock_panel, \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    assert mock_panel.call_args.args[0] == "Uninstall failed."


def test_main_status_command_propagates_system_exit_unchanged():
    """sys.exit(0) from a successful _run_status must NOT be intercepted
    by the new error wrapper and turned into exit code 1."""
    from unittest.mock import patch
    from cognigy_mcp.setup import main
    with patch("sys.argv", ["cognigy-vibe-setup", "status"]), \
         patch("cognigy_mcp.setup._run_status", side_effect=SystemExit(0)), \
         patch("cognigy_mcp.setup.print_error_panel") as mock_panel, \
         pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    mock_panel.assert_not_called()


def test_run_status_prints_header(capsys):
    from cognigy_mcp.setup import _run_status
    args = type("Args", (), {"fix": False, "verbose": False})()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state()):
        with pytest.raises(SystemExit):
            _run_status(args)
    assert "cognigy-vibe status" in capsys.readouterr().out


def test_run_update_prints_header(monkeypatch):
    from cognigy_mcp.setup import _run_update
    import io, contextlib
    args = type("Args", (), {"check": False, "verbose": False})()
    buf = io.StringIO()
    with patch("cognigy_mcp.reconcile.gather_state", return_value=_state()), \
         patch("cognigy_mcp.reconcile.check_pypi_latest", return_value="1.7.0"):
        with contextlib.redirect_stdout(buf):
            with pytest.raises(SystemExit):
                _run_update(args)
    assert "cognigy-vibe update" in buf.getvalue()
