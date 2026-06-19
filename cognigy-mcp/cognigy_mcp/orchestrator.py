# cognigy-mcp/cognigy_mcp/orchestrator.py
from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import threading
import time
from pathlib import Path
from dotenv import load_dotenv

_LOG = open("/tmp/cognigy-mcp.log", "a", buffering=1)


def _log(msg: str) -> None:
    _LOG.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


_ENV_KEYS = frozenset([
    "COGNIGY_BASE_URL",
    "COGNIGY_API_KEY",
    "COGNIGY_PROJECT_ID",
    "COGNIGY_VIBE_DEV",
    "COGNIGY_VIBE_SOURCE_DIR",
])


def _detect_mode() -> str:
    if not os.environ.get("COGNIGY_BASE_URL") or not os.environ.get("COGNIGY_API_KEY"):
        return "degraded"
    if os.environ.get("COGNIGY_VIBE_DEV") == "1":
        return "dev"
    return "prod"


def _inner_command(mode: str) -> list[str]:
    if mode == "dev":
        source_dir = os.environ.get("COGNIGY_VIBE_SOURCE_DIR", "")
        if not source_dir:
            sys.stderr.write("[orchestrator] COGNIGY_VIBE_SOURCE_DIR must be set for dev mode\n")
            sys.exit(1)
        return ["uv", "run", "--directory", source_dir, "-m", "cognigy_mcp.server"]
    return [sys.executable, "-m", "cognigy_mcp.server"]


class _Orchestrator:
    def __init__(self) -> None:
        self._child: subprocess.Popen | None = None
        self._init_params: dict | None = None
        self._mode: str = "unknown"
        self._pending_call: bytes | None = None
        self._wake_w: int = -1
        self._write_lock = threading.Lock()

    def _spawn(self) -> subprocess.Popen:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        load_dotenv(override=True)
        mode = _detect_mode()
        self._mode = mode
        cmd = _inner_command(mode)
        _log(f"spawn mode={mode} cmd={cmd}")
        sys.stderr.write(f"[orchestrator] starting in {mode} mode\n")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            env=os.environ.copy(),
        )
        _log(f"spawn pid={proc.pid}")
        return proc

    def _replay_handshake(self, child: subprocess.Popen) -> None:
        if self._init_params is None:
            _log("replay_handshake: no init_params, skipping")
            return
        _log("replay_handshake: sending initialize")
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": self._init_params,
        })
        child.stdin.write((req + "\n").encode())
        child.stdin.flush()
        resp = child.stdout.readline()  # consume initialize response
        _log(f"replay_handshake: initialize response={resp[:120]}")
        notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        child.stdin.write((notif + "\n").encode())
        child.stdin.flush()
        _log("replay_handshake: done")

    def _guidance_response(self, request_id: object, env_path: Path) -> bytes:
        text = (
            f"cognigy-vibe-mcp is not configured.\n\n"
            f"Create a .env file at:\n  {env_path}\n\n"
            f"  COGNIGY_BASE_URL=<your-api-base-url>\n"
            f"  COGNIGY_API_KEY=<your-api-key>\n"
            f"  COGNIGY_PROJECT_ID=<your-project-id>  # optional\n\n"
            f"COGNIGY_BASE_URL is the API endpoint for your deployment — not the UI URL.\n"
            f"  CXone: https://cognigy-api-au1.nicecxone.com  (note: cognigy-api-*, not cognigy-*)\n"
            f"  Trial: https://api-trial.cognigy.ai  (note: api-trial.*, not trial.*)\n\n"
            f"Get your API key in Cognigy: My Profile → API Keys → +\n\n"
            f"Once the file is saved, retry this tool call — credentials will load automatically."
        )
        resp = json.dumps({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": text}]},
        })
        return (resp + "\n").encode()

    def _notify_tools_changed(self) -> None:
        msg = json.dumps({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
        _log("notify_tools_changed: sending")
        with self._write_lock:
            sys.stdout.buffer.write((msg + "\n").encode())
            sys.stdout.buffer.flush()
        _log("notify_tools_changed: sent")

    def _start_reader(self, child: subprocess.Popen) -> None:
        def _read(c: subprocess.Popen) -> None:
            while True:
                line = c.stdout.readline()
                if not line:
                    break
                with self._write_lock:
                    sys.stdout.buffer.write(line)
                    sys.stdout.buffer.flush()

        threading.Thread(target=_read, args=(child,), daemon=True).start()

    def _monitor_child(self, child: subprocess.Popen) -> None:
        def _watch(c: subprocess.Popen) -> None:
            c.wait()
            _log(f"child pid={c.pid} exited rc={c.returncode}")
            if c.returncode == 42:
                sys.stderr.write("[orchestrator] inner server requested restart\n")
                _log("writing wakeup byte")
                os.write(self._wake_w, b"\x00")

        threading.Thread(target=_watch, args=(child,), daemon=True).start()

    def _do_restart(self) -> None:
        _log("do_restart: begin")
        sys.stderr.write("[orchestrator] restarting inner server\n")
        if self._child:
            self._child.kill()
            self._child.wait()
        child = self._spawn()
        self._replay_handshake(child)

        pending = self._pending_call
        self._pending_call = None
        if pending:
            # Degraded→full transition: replay the tool call that triggered the restart.
            # Tool surface is identical so no tools/list_changed needed.
            _log("replaying pending tool call to new child")
            child.stdin.write(pending)
            child.stdin.flush()
        else:
            # reload_mcp or other restart: notify Claude the tool list may have changed.
            self._notify_tools_changed()

        self._start_reader(child)
        self._monitor_child(child)
        self._child = child
        _log("do_restart: complete")
        sys.stderr.write("[orchestrator] restart complete\n")

    def run(self) -> None:
        self._child = self._spawn()
        self._start_reader(self._child)
        self._monitor_child(self._child)

        # Wakeup pipe: monitor thread writes a byte here when rc=42 fires,
        # unblocking select() without waiting for the next stdin message.
        wake_r, wake_w = os.pipe()
        self._wake_w = wake_w

        stdin_fd = sys.stdin.fileno()

        buf = b""
        while True:
            ready, _, _ = select.select([stdin_fd, wake_r], [], [])

            if wake_r in ready:
                os.read(wake_r, 1)  # drain
                _log("wakeup received — restarting")
                self._do_restart()

            if stdin_fd not in ready:
                continue

            chunk = os.read(stdin_fd, 65536)
            if not chunk:
                break
            buf += chunk

            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                raw_line = line + b"\n"
                msg = None
                try:
                    msg = json.loads(raw_line)
                    if isinstance(msg, dict) and msg.get("method") == "initialize":
                        self._init_params = msg.get("params")
                        _log("initialize received")
                except (json.JSONDecodeError, AttributeError):
                    pass

                # In degraded mode, intercept tool calls before forwarding to child.
                if (
                    self._mode == "degraded"
                    and isinstance(msg, dict)
                    and msg.get("method") == "tools/call"
                ):
                    env_path = Path(os.environ.get("COGNIGY_PROJECT_ROOT", ".")) / ".env"
                    if env_path.exists():
                        _log(f"tools/call in degraded mode: .env found, restarting")
                        self._pending_call = raw_line
                        self._do_restart()
                    else:
                        _log("tools/call in degraded mode: no .env, returning guidance")
                        resp = self._guidance_response(msg.get("id"), env_path)
                        with self._write_lock:
                            sys.stdout.buffer.write(resp)
                            sys.stdout.buffer.flush()
                    continue

                child = self._child
                try:
                    child.stdin.write(raw_line)
                    child.stdin.flush()
                except BrokenPipeError:
                    _log("BrokenPipeError writing to child — restart pending")


def main() -> None:
    import truststore
    truststore.inject_into_ssl()
    os.environ.setdefault("COGNIGY_PROJECT_ROOT", str(Path.cwd()))
    _log(f"main: start cwd={Path.cwd()} project_root={os.environ.get('COGNIGY_PROJECT_ROOT')}")
    load_dotenv()
    _log(f"main: after load_dotenv mode={_detect_mode()}")
    _Orchestrator().run()
