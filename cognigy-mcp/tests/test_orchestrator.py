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
    expected = str(Path("/path/to/cognigy-mcp").resolve())
    assert cmd == ["uv", "run", "--directory", expected, "-m", "cognigy_mcp.server"]


def test_inner_command_dev_relative_path_resolved(monkeypatch, tmp_path):
    # Relative COGNIGY_VIBE_SOURCE_DIR (as set by .mcp.json) is resolved against CWD.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COGNIGY_VIBE_SOURCE_DIR", "./cognigy-mcp")
    from cognigy_mcp.orchestrator import _inner_command
    cmd = _inner_command("dev")
    assert cmd == ["uv", "run", "--directory", str(tmp_path / "cognigy-mcp"), "-m", "cognigy_mcp.server"]


def test_inner_command_dev_missing_source_dir(monkeypatch):
    monkeypatch.delenv("COGNIGY_VIBE_SOURCE_DIR", raising=False)
    from cognigy_mcp.orchestrator import _inner_command
    with pytest.raises(SystemExit):
        _inner_command("dev")


def test_env_keys_excludes_dev_vars():
    # COGNIGY_VIBE_DEV and COGNIGY_VIBE_SOURCE_DIR must NOT be in _ENV_KEYS —
    # they are injected by .mcp.json and must survive the _spawn() pop cycle.
    from cognigy_mcp.orchestrator import _ENV_KEYS
    assert "COGNIGY_VIBE_DEV" not in _ENV_KEYS
    assert "COGNIGY_VIBE_SOURCE_DIR" not in _ENV_KEYS


from cognigy_mcp.orchestrator import _find_env_file


def test_find_env_file_in_start_dir(tmp_path):
    env = tmp_path / ".env"
    env.write_text("COGNIGY_BASE_URL=https://example.com\n")
    result = _find_env_file(tmp_path, tmp_path.parent)
    assert result == env


def test_find_env_file_in_parent(tmp_path):
    child = tmp_path / "project"
    child.mkdir()
    env = tmp_path / ".env"
    env.write_text("COGNIGY_BASE_URL=https://example.com\n")
    result = _find_env_file(child, tmp_path.parent)
    assert result == env


def test_find_env_file_stops_at_boundary(tmp_path):
    # boundary is tmp_path itself — .env is above it (in tmp_path.parent), should not be found
    child = tmp_path / "project"
    child.mkdir()
    env = tmp_path.parent / ".env"
    env.write_text("COGNIGY_BASE_URL=https://example.com\n")
    result = _find_env_file(child, tmp_path)  # stop at tmp_path, not tmp_path.parent
    assert result is None
    env.unlink()  # cleanup — tmp_path.parent is shared


def test_find_env_file_not_found(tmp_path):
    child = tmp_path / "deep" / "project"
    child.mkdir(parents=True)
    result = _find_env_file(child, tmp_path)
    assert result is None


def test_find_env_file_grandparent(tmp_path):
    grandchild = tmp_path / "a" / "b"
    grandchild.mkdir(parents=True)
    env = tmp_path / ".env"
    env.write_text("COGNIGY_API_KEY=key\n")
    result = _find_env_file(grandchild, tmp_path.parent)
    assert result == env


# ---------------------------------------------------------------------------
# Task 1 — stderr capture
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Task 2 — JSON-RPC guard in _start_reader
# ---------------------------------------------------------------------------

def test_start_reader_filters_non_json(monkeypatch):
    """Non-JSON lines from inner server stdout must be logged, not forwarded to Claude."""
    import cognigy_mcp.orchestrator as orch

    log_lines = []
    forwarded = []
    monkeypatch.setattr(orch, "_log", lambda msg: log_lines.append(msg))

    class FakeBuffer:
        def write(self, data):
            forwarded.append(data)
        def flush(self):
            pass

    class FakeStdout:
        buffer = FakeBuffer()

    monkeypatch.setattr(sys, "stdout", FakeStdout())

    script = (
        "import sys\n"
        "sys.stdout.write('this is not json\\n'); sys.stdout.flush()\n"
        'sys.stdout.write(\'{"jsonrpc":"2.0","id":1,"result":{}}\' + "\\n"); sys.stdout.flush()\n'
        "sys.stdout.write('also not json\\n'); sys.stdout.flush()\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    orchestrator = orch._Orchestrator()
    orchestrator._start_reader(proc)
    proc.wait(timeout=3)
    time.sleep(0.1)

    forwarded_text = b"".join(forwarded).decode()
    assert '{"jsonrpc":"2.0"' in forwarded_text, "valid JSON-RPC must be forwarded"
    assert "this is not json" not in forwarded_text, "garbage must NOT be forwarded"
    assert "also not json" not in forwarded_text, "garbage must NOT be forwarded"
    assert any("this is not json" in line for line in log_lines), "garbage must be logged"
    assert any("also not json" in line for line in log_lines), "garbage must be logged"


def test_inner_server_stderr_appears_in_log(monkeypatch):
    """Inner server stderr must reach the orchestrator log, not be discarded."""
    import cognigy_mcp.orchestrator as orch
    log_lines = []
    monkeypatch.setattr(orch, "_log", lambda msg: log_lines.append(msg))

    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.stderr.write('inner-err: crash trace\\n'); sys.exit(1)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    orchestrator = orch._Orchestrator()
    orchestrator._start_stderr_logger(proc)
    proc.wait(timeout=3)
    time.sleep(0.1)  # let reader thread drain

    assert any("inner-err: crash trace" in line for line in log_lines), (
        f"stderr not captured in log. Got: {log_lines}"
    )


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


# ---------------------------------------------------------------------------
# Task 4 — user-scope .env fallback
# ---------------------------------------------------------------------------

def test_resolve_env_file_finds_project_env(tmp_path):
    """Project .env takes priority over user-scope fallback."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_env = project_dir / ".env"
    project_env.write_text("COGNIGY_BASE_URL=https://project.example.com\n")

    user_config = tmp_path / ".config" / "cognigy-vibe"
    user_config.mkdir(parents=True)
    (user_config / ".env").write_text("COGNIGY_BASE_URL=https://user.example.com\n")

    from cognigy_mcp.orchestrator import _resolve_env_file
    result = _resolve_env_file(project_dir, tmp_path)
    assert result == project_env


def test_resolve_env_file_falls_back_to_user_scope(tmp_path, monkeypatch):
    """With no project .env, falls back to ~/.config/cognigy-vibe/.env."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    user_env = tmp_path / ".config" / "cognigy-vibe" / ".env"
    user_env.parent.mkdir(parents=True)
    user_env.write_text("COGNIGY_BASE_URL=https://user.example.com\n")

    import cognigy_mcp.orchestrator as orch
    monkeypatch.setattr(orch, "USER_ENV_PATH", user_env)
    result = orch._resolve_env_file(project_dir, tmp_path)
    assert result == user_env


def test_resolve_env_file_returns_none_when_neither_exists(tmp_path):
    """Returns None when no .env found anywhere."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    from cognigy_mcp.orchestrator import _resolve_env_file
    result = _resolve_env_file(project_dir, tmp_path)
    assert result is None
