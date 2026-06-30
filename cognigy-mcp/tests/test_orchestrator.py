import os
import subprocess
import sys
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
