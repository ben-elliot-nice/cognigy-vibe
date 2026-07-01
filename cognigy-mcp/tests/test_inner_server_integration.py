"""Integration tests: spawn the inner server as a subprocess in degraded mode and
drive it through the full MCP protocol handshake.

These tests fail if the inner server crashes (rc=1) or hangs — the exact regression
reported in issue #95. They run without Cognigy credentials so the server is in
degraded mode, exercising the same code path that was broken.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rpc(method: str, id: int | None = None, params: dict | None = None) -> bytes:
    msg: dict = {"jsonrpc": "2.0", "method": method}
    if id is not None:
        msg["id"] = id
    if params is not None:
        msg["params"] = params
    return (json.dumps(msg) + "\n").encode()


def _read_response(proc: subprocess.Popen, timeout: float = 8.0) -> dict:
    """Read the next JSON-RPC response from the inner server's stdout.

    Skips blank lines and non-JSON lines (startup noise from truststore etc.);
    raises TimeoutError if no valid response arrives within `timeout` seconds.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            rc = proc.poll()
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            raise RuntimeError(
                f"inner server stdout closed unexpectedly. rc={rc}\nstderr:\n{stderr}"
            )
        stripped = line.strip()
        if not stripped:
            continue
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            continue  # skip non-JSON startup lines
    rc = proc.poll()
    stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    raise TimeoutError(
        f"timed out waiting for inner server response after {timeout}s. "
        f"rc={rc}\nstderr:\n{stderr}"
    )


def _spawn_degraded_inner_server() -> subprocess.Popen:
    """Spawn the inner server subprocess with no Cognigy credentials (degraded mode).

    Sets COGNIGY_BASE_URL and COGNIGY_API_KEY to empty strings rather than removing
    them. server.main() calls load_dotenv(override=False); dotenv only sets vars that
    are absent from the environment, so an empty-string value prevents it from loading
    real credentials from a local .env file. bool("") is False, so _env_configured()
    returns False and the server starts in degraded mode.
    """
    env = dict(os.environ)
    env["COGNIGY_BASE_URL"] = ""
    env["COGNIGY_API_KEY"] = ""
    env.pop("COGNIGY_PROJECT_ID", None)
    env.pop("COGNIGY_VIBE_DEV", None)
    return subprocess.Popen(
        [sys.executable, "-m", "cognigy_mcp.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def _teardown(proc: subprocess.Popen) -> tuple[int | None, str]:
    """Close stdin, wait for exit, return (returncode, stderr_text)."""
    try:
        proc.stdin.close()
    except OSError:
        pass
    try:
        proc.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    stderr_text = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    return proc.returncode, stderr_text


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_degraded_server_handles_initialize():
    """Inner server in degraded mode must respond to 'initialize' without crashing."""
    proc = _spawn_degraded_inner_server()
    try:
        proc.stdin.write(_rpc("initialize", id=1, params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0.0.1"},
        }))
        proc.stdin.flush()

        resp = _read_response(proc)
        assert resp.get("id") == 1, f"wrong id in response: {resp}"
        assert "result" in resp, f"initialize must return a result, got: {resp}"
        assert "error" not in resp, f"initialize returned an error: {resp}"
    finally:
        rc, stderr_text = _teardown(proc)
        assert rc in (0, None, -15), (
            f"inner server exited with rc={rc} (expected 0 or SIGTERM)\n"
            f"stderr:\n{stderr_text}"
        )


def test_degraded_server_tools_list_returns_expected_tools():
    """Inner server in degraded mode must return the complete tool list without crashing."""
    proc = _spawn_degraded_inner_server()
    try:
        # Initialize
        proc.stdin.write(_rpc("initialize", id=1, params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "0.0.1"},
        }))
        proc.stdin.flush()
        resp = _read_response(proc)
        assert resp.get("id") == 1 and "result" in resp, f"initialize failed: {resp}"

        # Notify initialized
        proc.stdin.write(_rpc("notifications/initialized"))
        proc.stdin.flush()

        # Request tool list
        proc.stdin.write(_rpc("tools/list", id=2))
        proc.stdin.flush()
        resp = _read_response(proc)
        assert resp.get("id") == 2, f"wrong id: {resp}"
        assert "result" in resp, f"tools/list failed: {resp}"

        tools = resp["result"].get("tools", [])
        tool_names = sorted(t["name"] for t in tools)

        expected = sorted([
            "cognigy_get", "cognigy_list", "cognigy_create", "cognigy_update",
            "cognigy_delete", "cognigy_invoke", "sync_remote_state", "get_build_state",
            "resolve_resource", "get_flow_chart", "push_code_node", "push_html_node",
            "push_agent_tool", "push_agent_avatar", "talk_to_agent", "explain",
            "provision_webrtc_endpoint",
        ])
        assert tool_names == expected, (
            f"tool list mismatch.\nGot:      {tool_names}\nExpected: {expected}"
        )
    finally:
        rc, stderr_text = _teardown(proc)
        assert rc in (0, None, -15), (
            f"inner server exited with rc={rc}\nstderr:\n{stderr_text}"
        )
