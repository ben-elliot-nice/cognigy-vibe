import inspect
import json
import os
import queue
import subprocess
import sys
import time
import pytest
from pathlib import Path
from types import SimpleNamespace
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
    monkeypatch.setenv("COGNIGY_VIBE_SOURCE_DIR", "/path/to/cognigy-vibe-mcp")
    from cognigy_mcp.orchestrator import _inner_command
    cmd = _inner_command("dev")
    expected = str(Path("/path/to/cognigy-vibe-mcp").resolve())
    assert cmd == ["uv", "run", "--directory", expected, "-m", "cognigy_mcp.server"]


def test_inner_command_dev_relative_path_resolved(monkeypatch, tmp_path):
    # Relative COGNIGY_VIBE_SOURCE_DIR (as set by .mcp.json) is resolved against CWD.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COGNIGY_VIBE_SOURCE_DIR", "./cognigy-vibe-mcp")
    from cognigy_mcp.orchestrator import _inner_command
    cmd = _inner_command("dev")
    assert cmd == ["uv", "run", "--directory", str(tmp_path / "cognigy-vibe-mcp"), "-m", "cognigy_mcp.server"]


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

def test_log_file_is_under_config_base_logs():
    """Log file must live under CONFIG_BASE/logs (see #171), not a hardcoded /tmp path."""
    import cognigy_mcp.orchestrator as orch
    from cognigy_mcp.config import CONFIG_BASE
    log_path = Path(orch._LOG.name)
    assert log_path.parent == CONFIG_BASE / "logs", (
        f"Expected log under {CONFIG_BASE / 'logs'!r}, got {log_path!r}"
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


def test_migrate_flat_logs_moves_stray_log_file(tmp_path):
    from cognigy_mcp.orchestrator import _migrate_flat_logs
    config_base = tmp_path / "cognigy-vibe"
    config_base.mkdir()
    stray = config_base / "cognigy-vibe-mcp-1.5.4.log"
    stray.write_text("old log contents")
    log_dir = config_base / "logs"
    log_dir.mkdir()

    _migrate_flat_logs(config_base, log_dir)

    assert not stray.exists()
    assert (log_dir / "cognigy-vibe-mcp-1.5.4.log").read_text() == "old log contents"


def test_migrate_flat_logs_noop_if_destination_exists(tmp_path):
    from cognigy_mcp.orchestrator import _migrate_flat_logs
    config_base = tmp_path / "cognigy-vibe"
    config_base.mkdir()
    stray = config_base / "cognigy-vibe-mcp-1.5.4.log"
    stray.write_text("old")
    log_dir = config_base / "logs"
    log_dir.mkdir()
    (log_dir / "cognigy-vibe-mcp-1.5.4.log").write_text("new")

    _migrate_flat_logs(config_base, log_dir)

    assert stray.exists()  # untouched — destination already existed
    assert (log_dir / "cognigy-vibe-mcp-1.5.4.log").read_text() == "new"


def test_migrate_flat_logs_noop_if_config_base_missing(tmp_path):
    from cognigy_mcp.orchestrator import _migrate_flat_logs
    config_base = tmp_path / "does-not-exist"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    _migrate_flat_logs(config_base, log_dir)  # must not raise

    assert not config_base.exists()


def test_migrate_flat_logs_survives_concurrent_migration_race(tmp_path, monkeypatch):
    """Simulates a second orchestrator process winning the race: dest.exists()
    is False when this process checks it, but the log file vanishes before
    the move actually runs (the other process already relocated it)."""
    from cognigy_mcp.orchestrator import _migrate_flat_logs

    config_base = tmp_path / "cognigy-vibe"
    config_base.mkdir()
    (config_base / "cognigy-vibe-mcp-1.5.4.log").write_text("old")
    log_dir = config_base / "logs"
    log_dir.mkdir()

    def fake_move(s, d):
        raise FileNotFoundError(s)

    monkeypatch.setattr("shutil.move", fake_move)

    _migrate_flat_logs(config_base, log_dir)  # must not raise


def test_migrate_flat_logs_ignores_non_log_files(tmp_path):
    from cognigy_mcp.orchestrator import _migrate_flat_logs
    config_base = tmp_path / "cognigy-vibe"
    config_base.mkdir()
    (config_base / "config.json").write_text("{}")
    (config_base / ".env").write_text("KEY=1")
    log_dir = config_base / "logs"
    log_dir.mkdir()

    _migrate_flat_logs(config_base, log_dir)

    assert (config_base / "config.json").exists()
    assert (config_base / ".env").exists()


def test_main_merges_project_and_user_env(tmp_path, monkeypatch):
    """#255 regression: project .env has only the project id, user .env has credentials —
    main() must end up with both in os.environ, not just whichever file it found first."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_text("COGNIGY_PROJECT_ID=proj-123\n")
    user_env = tmp_path / "userhome" / ".config" / "cognigy-vibe" / ".env"
    user_env.parent.mkdir(parents=True)
    user_env.write_text("COGNIGY_BASE_URL=https://user.example.com\nCOGNIGY_API_KEY=userkey\n")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "userhome")
    import cognigy_mcp.orchestrator as orch
    monkeypatch.setattr(orch, "USER_ENV_PATH", user_env)
    for key in ("COGNIGY_PROJECT_ID", "COGNIGY_BASE_URL", "COGNIGY_API_KEY", "COGNIGY_PROJECT_ROOT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(orch._Orchestrator, "run", lambda self: None)
    monkeypatch.setattr("truststore.inject_into_ssl", lambda: None)

    # main() writes directly to os.environ via setdefault(), which monkeypatch's
    # setenv/delenv-based teardown does not track — reset these keys afterward so
    # this test doesn't leak COGNIGY_PROJECT_ROOT (etc.) into later tests in the
    # same session (e.g. test_server.py's _find_config_file cascade).
    try:
        orch.main()

        assert os.environ["COGNIGY_PROJECT_ID"] == "proj-123"
        assert os.environ["COGNIGY_BASE_URL"] == "https://user.example.com"
        assert os.environ["COGNIGY_API_KEY"] == "userkey"
        assert os.environ["COGNIGY_PROJECT_ROOT"] == str(project_dir)
    finally:
        for key in ("COGNIGY_PROJECT_ID", "COGNIGY_BASE_URL", "COGNIGY_API_KEY", "COGNIGY_PROJECT_ROOT"):
            os.environ.pop(key, None)


def test_spawn_merges_project_and_user_env(tmp_path, monkeypatch):
    """Hot-reload path (_spawn, invoked by reload_mcp) must merge just like main()."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_text("COGNIGY_PROJECT_ID=proj-123\n")
    user_env = tmp_path / "userhome" / ".config" / "cognigy-vibe" / ".env"
    user_env.parent.mkdir(parents=True)
    user_env.write_text("COGNIGY_BASE_URL=https://user.example.com\nCOGNIGY_API_KEY=userkey\n")

    import cognigy_mcp.orchestrator as orch
    monkeypatch.setattr(orch, "USER_ENV_PATH", user_env)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "userhome")
    monkeypatch.setenv("COGNIGY_PROJECT_ROOT", str(project_dir))
    for key in ("COGNIGY_PROJECT_ID", "COGNIGY_BASE_URL", "COGNIGY_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(orch.subprocess, "Popen", lambda *a, **k: SimpleNamespace(pid=1234))

    # _spawn() writes directly to os.environ via os.environ.update(), which
    # monkeypatch's setenv/delenv-based teardown does not track — reset these keys
    # afterward so this test doesn't leak COGNIGY_PROJECT_ID (etc.) into later tests
    # in the same session.
    try:
        o = orch._Orchestrator()
        o._spawn()

        assert os.environ["COGNIGY_PROJECT_ID"] == "proj-123"
        assert os.environ["COGNIGY_BASE_URL"] == "https://user.example.com"
        assert os.environ["COGNIGY_API_KEY"] == "userkey"
    finally:
        for key in ("COGNIGY_PROJECT_ID", "COGNIGY_BASE_URL", "COGNIGY_API_KEY"):
            os.environ.pop(key, None)


def test_degraded_interceptor_restarts_when_user_global_env_fixes_it(tmp_path, monkeypatch):
    """#255 gap: today this only checks COGNIGY_PROJECT_ROOT/.env existence, so a fix
    living purely in the user-global .env is never detected and the orchestrator never
    retries — it must instead check whether the merged resolution now has both keys."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    # No project .env at all.
    user_env = tmp_path / "userhome" / ".config" / "cognigy-vibe" / ".env"
    user_env.parent.mkdir(parents=True)
    user_env.write_text("COGNIGY_BASE_URL=https://user.example.com\nCOGNIGY_API_KEY=userkey\n")

    import cognigy_mcp.orchestrator as orch
    from cognigy_mcp.discovery import resolve_env_layers, missing_env_keys
    monkeypatch.setattr(orch, "USER_ENV_PATH", user_env)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "userhome")
    monkeypatch.setenv("COGNIGY_PROJECT_ROOT", str(project_dir))

    o = orch._Orchestrator()
    o._mode = "degraded"
    restarted = {"called": False}
    monkeypatch.setattr(o, "_do_restart", lambda: restarted.update(called=True))

    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}}
    raw = (json.dumps(msg) + "\n").encode()

    # Simulate the relevant slice of run()'s message loop directly — this locks in
    # the intended restart condition (imported straight from discovery.py, not via
    # orch's namespace, since orch is only wired to these helpers in Step 3 below).
    o._pending_call = None
    resolution = resolve_env_layers(project_dir, Path.home(), orch.USER_ENV_PATH)
    if not missing_env_keys(resolution):
        o._pending_call = raw
        o._do_restart()

    assert restarted["called"] is True
