import inspect
import json
import os
import queue
import subprocess
import sys
import tempfile
import time
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


# ---------------------------------------------------------------------------
# Single-queue sentinel design (findings 3 + 6)
# ---------------------------------------------------------------------------

def test_monitor_child_puts_restart_sentinel_on_rc42(monkeypatch):
    """Child exit with rc=42 must enqueue _RESTART into self._stdin_q — not set a threading.Event."""
    import cognigy_mcp.orchestrator as orch
    monkeypatch.setattr(orch, "_log", lambda msg: None)

    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(42)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    o = orch._Orchestrator()
    o._monitor_child(proc)
    proc.wait(timeout=3)
    time.sleep(0.1)

    item = o._stdin_q.get(timeout=1)
    assert item is orch._RESTART, f"Expected _RESTART sentinel, got {item!r}"


def test_monitor_child_no_sentinel_on_normal_exit(monkeypatch):
    """Child exit with rc=0 must NOT enqueue a restart sentinel."""
    import cognigy_mcp.orchestrator as orch
    monkeypatch.setattr(orch, "_log", lambda msg: None)

    proc = subprocess.Popen(
        [sys.executable, "-c", "pass"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    o = orch._Orchestrator()
    o._monitor_child(proc)
    proc.wait(timeout=3)
    time.sleep(0.1)

    with pytest.raises(queue.Empty):
        o._stdin_q.get(timeout=0.2)


def test_run_loop_does_not_poll(monkeypatch):
    """run() must block indefinitely on stdin_q.get() — no timeout= polling."""
    import cognigy_mcp.orchestrator as orch
    source = inspect.getsource(orch._Orchestrator.run)
    assert "timeout=" not in source, (
        "timeout= found in _Orchestrator.run — use self._stdin_q.get() without "
        "a timeout; route restart signals as sentinels through the queue instead"
    )


# ---------------------------------------------------------------------------
# BrokenPipeError error response (finding 2)
# ---------------------------------------------------------------------------

def test_write_to_child_broken_pipe_sends_jsonrpc_error(monkeypatch):
    """BrokenPipeError writing to dead child must send a JSON-RPC error to the client."""
    import cognigy_mcp.orchestrator as orch

    forwarded = []

    class FakeBuffer:
        def write(self, data): forwarded.append(data)
        def flush(self): pass

    class FakeStdout:
        buffer = FakeBuffer()

    class FakeChildStdin:
        def write(self, data): raise BrokenPipeError
        def flush(self): pass

    class FakeChild:
        stdin = FakeChildStdin()

    monkeypatch.setattr(sys, "stdout", FakeStdout())
    monkeypatch.setattr(orch, "_log", lambda msg: None)

    o = orch._Orchestrator()
    o._child = FakeChild()

    raw = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {}})
    o._write_to_child((raw + "\n").encode(), json.loads(raw))

    combined = b"".join(forwarded).decode().strip()
    resp = json.loads(combined)
    assert resp["id"] == 7
    assert "error" in resp, "Expected a JSON-RPC error response, not a result"


def test_write_to_child_broken_pipe_notification_no_response(monkeypatch):
    """BrokenPipeError on a notification (no id) must not send any response."""
    import cognigy_mcp.orchestrator as orch

    forwarded = []

    class FakeBuffer:
        def write(self, data): forwarded.append(data)
        def flush(self): pass

    class FakeStdout:
        buffer = FakeBuffer()

    class FakeChildStdin:
        def write(self, data): raise BrokenPipeError
        def flush(self): pass

    class FakeChild:
        stdin = FakeChildStdin()

    monkeypatch.setattr(sys, "stdout", FakeStdout())
    monkeypatch.setattr(orch, "_log", lambda msg: None)

    o = orch._Orchestrator()
    o._child = FakeChild()

    raw = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
    o._write_to_child((raw + "\n").encode(), json.loads(raw))

    assert not forwarded, "Notifications have no id — must not send a response"
