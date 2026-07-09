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
