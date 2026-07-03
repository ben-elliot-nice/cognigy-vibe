import inspect
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch


def test_detect_mode_degraded_no_url(monkeypatch):
    monkeypatch.delenv("COGNIGY_BASE_URL", raising=False)
    monkeypatch.delenv("COGNIGY_API_KEY", raising=False)
    from cognigy_mcp.orchestrator import _detect_mode
    assert _detect_mode() == "degraded"


def test_detect_mode_degraded_missing_key(monkeypatch):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://example.com")
    monkeypatch.delenv("COGNIGY_API_KEY", raising=False)
    from cognigy_mcp.orchestrator import _detect_mode
    assert _detect_mode() == "degraded"


def test_detect_mode_prod(monkeypatch):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://example.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "key123")
    monkeypatch.delenv("COGNIGY_VIBE_DEV", raising=False)
    from cognigy_mcp.orchestrator import _detect_mode
    assert _detect_mode() == "prod"


def test_detect_mode_dev_requires_credentials(monkeypatch):
    monkeypatch.setenv("COGNIGY_VIBE_DEV", "1")
    monkeypatch.delenv("COGNIGY_BASE_URL", raising=False)
    monkeypatch.delenv("COGNIGY_API_KEY", raising=False)
    from cognigy_mcp.orchestrator import _detect_mode
    assert _detect_mode() == "degraded"  # dev flag ignored without credentials


def test_detect_mode_dev(monkeypatch):
    monkeypatch.setenv("COGNIGY_BASE_URL", "https://example.com")
    monkeypatch.setenv("COGNIGY_API_KEY", "key123")
    monkeypatch.setenv("COGNIGY_VIBE_DEV", "1")
    from cognigy_mcp.orchestrator import _detect_mode
    assert _detect_mode() == "dev"


def test_inner_command_prod():
    from cognigy_mcp.orchestrator import _inner_command
    cmd = _inner_command("prod")
    assert cmd == [sys.executable, "-m", "cognigy_mcp.server"]


def test_inner_command_degraded():
    from cognigy_mcp.orchestrator import _inner_command
    cmd = _inner_command("degraded")
    assert cmd == [sys.executable, "-m", "cognigy_mcp.server"]


def test_inner_command_dev(monkeypatch):
    monkeypatch.setenv("COGNIGY_VIBE_SOURCE_DIR", "/path/to/cognigy-mcp")
    from cognigy_mcp.orchestrator import _inner_command
    cmd = _inner_command("dev")
    assert cmd == ["uv", "run", "--directory", "/path/to/cognigy-mcp", "-m", "cognigy_mcp.server"]


def test_inner_command_dev_missing_source_dir(monkeypatch):
    monkeypatch.delenv("COGNIGY_VIBE_SOURCE_DIR", raising=False)
    from cognigy_mcp.orchestrator import _inner_command
    with pytest.raises(SystemExit):
        _inner_command("dev")


# ---------------------------------------------------------------------------
# Windows compatibility fixes
# ---------------------------------------------------------------------------

def test_log_file_is_in_system_tempdir():
    """Log file must use tempfile.gettempdir(), not a hardcoded /tmp path."""
    import cognigy_mcp.orchestrator as orch
    log_path = Path(orch._LOG.name)
    assert log_path.parent == Path(tempfile.gettempdir()), (
        f"Expected log in {tempfile.gettempdir()!r}, got {log_path!r} — "
        "use tempfile.gettempdir() instead of a hardcoded /tmp path"
    )


def test_orchestrator_run_does_not_use_select_on_stdin():
    """run() must not call select.select() — it only accepts sockets on Windows."""
    import cognigy_mcp.orchestrator as orch
    source = inspect.getsource(orch._Orchestrator.run)
    assert "select.select" not in source, (
        "select.select() found in _Orchestrator.run — replace with a "
        "threading.Event / queue.Queue approach that works on all platforms"
    )
