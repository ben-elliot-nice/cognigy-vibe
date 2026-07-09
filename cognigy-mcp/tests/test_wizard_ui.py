# cognigy-mcp/tests/test_wizard_ui.py
from unittest.mock import patch, MagicMock
import pytest


def _mock_completed_process(returncode=0, stdout="", stderr=""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def test_run_subprocess_returns_result_on_success():
    from cognigy_mcp.wizard_ui import run_subprocess
    with patch("subprocess.run", return_value=_mock_completed_process(0, "ok", "")):
        result = run_subprocess(["echo", "hi"], "Running echo")
    assert result.returncode == 0
    assert result.stdout == "ok"
    assert result.stderr == ""


def test_run_subprocess_passes_cmd_through():
    from cognigy_mcp.wizard_ui import run_subprocess
    with patch("subprocess.run", return_value=_mock_completed_process(0)) as mock_run:
        run_subprocess(["claude", "plugin", "install", "x"], "Installing x")
    called_cmd = mock_run.call_args.args[0]
    assert called_cmd == ["claude", "plugin", "install", "x"]


def test_run_subprocess_raises_step_failure_on_nonzero_exit():
    from cognigy_mcp.wizard_ui import run_subprocess, StepFailure
    with patch("subprocess.run", return_value=_mock_completed_process(1, "", "boom")):
        with pytest.raises(StepFailure) as exc_info:
            run_subprocess(["claude", "plugin", "install", "x"], "Installing x")
    assert exc_info.value.description == "Installing x"
    assert exc_info.value.result.returncode == 1
    assert exc_info.value.result.stderr == "boom"


def test_run_subprocess_verbose_does_not_raise_on_success():
    from cognigy_mcp.wizard_ui import run_subprocess
    with patch("subprocess.run", return_value=_mock_completed_process(0, "line1\nline2", "")):
        result = run_subprocess(["echo", "hi"], "Running echo", verbose=True)
    assert result.stdout == "line1\nline2"


def test_print_header_renders_without_raising():
    from rich.console import Console
    from cognigy_mcp import wizard_ui
    test_console = Console(record=True)
    with patch.object(wizard_ui, "console", test_console):
        wizard_ui.print_header("cognigy-vibe setup wizard")
    output = test_console.export_text()
    assert "cognigy-vibe setup wizard" in output


def test_print_section_renders_without_raising():
    from rich.console import Console
    from cognigy_mcp import wizard_ui
    test_console = Console(record=True)
    with patch.object(wizard_ui, "console", test_console):
        wizard_ui.print_section(1, "Mode")
    output = test_console.export_text()
    assert "Mode" in output


def test_print_summary_renders_rows():
    from rich.console import Console
    from cognigy_mcp import wizard_ui
    test_console = Console(record=True)
    with patch.object(wizard_ui, "console", test_console):
        wizard_ui.print_summary([("Credentials", "/home/user/.config/cognigy-vibe/.env")])
    output = test_console.export_text()
    assert "Credentials" in output
    assert "cognigy-vibe" in output


def test_print_error_panel_hides_traceback_by_default():
    from rich.console import Console
    from cognigy_mcp import wizard_ui
    test_console = Console(record=True)
    with patch.object(wizard_ui, "console", test_console):
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            wizard_ui.print_error_panel("Setup failed.", exc, debug=False)
    output = test_console.export_text()
    assert "Setup failed." in output
    assert "Traceback" not in output


def test_print_error_panel_shows_traceback_when_debug():
    from rich.console import Console
    from cognigy_mcp import wizard_ui
    test_console = Console(record=True)
    with patch.object(wizard_ui, "console", test_console):
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            wizard_ui.print_error_panel("Setup failed.", exc, debug=True)
    output = test_console.export_text()
    assert "Traceback" in output
    assert "boom" in output


def test_print_error_panel_surfaces_step_failure_output_without_debug():
    from rich.console import Console
    from cognigy_mcp import wizard_ui
    from cognigy_mcp.wizard_ui import StepFailure, SubprocessResult
    test_console = Console(record=True)
    failure = StepFailure(
        "Installing plugin",
        SubprocessResult(returncode=1, stdout="", stderr="marketplace conflict: already registered"),
    )
    with patch.object(wizard_ui, "console", test_console):
        wizard_ui.print_error_panel("Setup failed.", failure, debug=False)
    output = test_console.export_text()
    assert "Setup failed." in output
    assert "marketplace conflict: already registered" in output
    assert "Traceback" not in output


def test_print_error_panel_plain_exception_unaffected():
    from rich.console import Console
    from cognigy_mcp import wizard_ui
    test_console = Console(record=True)
    with patch.object(wizard_ui, "console", test_console):
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            wizard_ui.print_error_panel("Setup failed.", exc, debug=False)
    output = test_console.export_text()
    assert "Setup failed." in output
    assert "Traceback" not in output


def test_print_drift_table_renders_all_rows():
    from rich.console import Console
    from cognigy_mcp import wizard_ui
    test_console = Console(record=True)
    with patch.object(wizard_ui, "console", test_console):
        wizard_ui.print_drift_table([
            ("package_version", "1.6.0", "1.6.0", "ok"),
            ("plugin_version", "1.5.0", "1.6.0", "drift"),
            ("desktop_pin", "None", "1.6.0", "missing"),
        ])
    output = test_console.export_text()
    assert "package_version" in output
    assert "plugin_version" in output
    assert "desktop_pin" in output
    assert "ok" in output
    assert "drift" in output
    assert "missing" in output


def test_print_drift_table_rejects_unknown_status():
    from cognigy_mcp import wizard_ui
    with pytest.raises(KeyError):
        wizard_ui.print_drift_table([("surface", "a", "b", "not-a-real-status")])


def test_print_step_renders_text():
    from rich.console import Console
    from cognigy_mcp import wizard_ui
    test_console = Console(record=True)
    with patch.object(wizard_ui, "console", test_console):
        wizard_ui.print_step("Uninstalling cognigy-vibe plugin (scope: user)")
    output = test_console.export_text()
    assert "Uninstalling cognigy-vibe plugin (scope: user)" in output
