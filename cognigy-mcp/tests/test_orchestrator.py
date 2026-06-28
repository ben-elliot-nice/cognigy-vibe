import os
import sys
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
