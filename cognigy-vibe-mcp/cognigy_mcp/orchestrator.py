# cognigy-vibe-mcp/cognigy_mcp/orchestrator.py
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from dotenv import load_dotenv
from cognigy_mcp.config import CONFIG_BASE, USER_ENV_PATH
from cognigy_mcp.discovery import resolve_env_layers
from cognigy_mcp.migrate import safe_move

def _migrate_flat_logs(config_base: Path, log_dir: Path) -> None:
    """Move stray log files from the pre-#171 flat layout into logs/."""
    if not config_base.exists():
        return
    for entry in config_base.glob("cognigy-vibe-mcp-*.log"):
        safe_move(entry, log_dir / entry.name)


def _log_path() -> str:
    try:
        from importlib.metadata import version
        ver = version("cognigy-vibe-mcp")
    except Exception:
        ver = "unknown"
    log_dir = CONFIG_BASE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _migrate_flat_logs(CONFIG_BASE, log_dir)
    return str(log_dir / f"cognigy-vibe-mcp-{ver}.log")

_LOG = open(_log_path(), "a", buffering=1)

# Sentinel enqueued by _monitor_child when the inner server exits with rc=42.
# Routing through the same queue as stdin bytes makes restart delivery FIFO,
# eliminates the threading.Event TOCTOU race, and removes the 100ms poll timeout.
_RESTART = object()


def _log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
    _LOG.write(line)
    sys.stderr.write(line)
    sys.stderr.flush()


# Only credential keys are popped on each _spawn() so they reload from .env on restart.
# COGNIGY_VIBE_DEV and COGNIGY_VIBE_SOURCE_DIR are structural config injected by .mcp.json
# and must NOT be popped — they survive in os.environ across restarts. A contributor who
# wants to opt out of dev mode can set COGNIGY_VIBE_DEV= in their .env (load_dotenv
# override=True will clear it).
_ENV_KEYS = frozenset([
    "COGNIGY_BASE_URL",
    "COGNIGY_API_KEY",
    "COGNIGY_PROJECT_ID",
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
        # Resolve relative paths (e.g. ./cognigy-vibe-mcp from .mcp.json) against CWD.
        return ["uv", "run", "--directory", str(Path(source_dir).resolve()), "-m", "cognigy_mcp.server"]
    return [sys.executable, "-m", "cognigy_mcp.server"]


class _Orchestrator:
    def __init__(self) -> None:
        self._child: subprocess.Popen | None = None
        self._init_params: dict | None = None
        self._mode: str = "unknown"
        self._pending_call: bytes | None = None
        self._stdin_q: queue.Queue = queue.Queue()
        self._write_lock = threading.Lock()

    def _spawn(self) -> subprocess.Popen:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        project_env = Path(os.environ.get("COGNIGY_PROJECT_ROOT", ".")) / ".env"
        if project_env.exists():
            load_dotenv(dotenv_path=project_env, override=True)
            _log(f"_spawn: loaded project env {project_env} | project_id={'set' if os.environ.get('COGNIGY_PROJECT_ID') else 'NOT SET'}")
        elif USER_ENV_PATH.exists():
            load_dotenv(dotenv_path=USER_ENV_PATH, override=True)
            _log(f"_spawn: loaded user-scope env {USER_ENV_PATH} | project_id={'set' if os.environ.get('COGNIGY_PROJECT_ID') else 'NOT SET'}")
        else:
            _log("_spawn: no .env found — starting in degraded mode")
        mode = _detect_mode()
        self._mode = mode
        cmd = _inner_command(mode)
        _log(f"spawn mode={mode} cmd={cmd}")
        sys.stderr.write(f"[orchestrator] starting in {mode} mode\n")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
                stripped = line.rstrip()
                if stripped:
                    try:
                        json.loads(stripped)
                    except (json.JSONDecodeError, ValueError):
                        _log(f"[inner-stdout-rejected] {stripped[:200]!r}")
                        continue
                with self._write_lock:
                    sys.stdout.buffer.write(line)
                    sys.stdout.buffer.flush()

        threading.Thread(target=_read, args=(child,), daemon=True).start()

    def _start_stderr_logger(self, child: subprocess.Popen) -> None:
        def _read(c: subprocess.Popen) -> None:
            while True:
                line = c.stderr.readline()
                if not line:
                    break
                _log(f"[inner-stderr] {line.decode(errors='replace').rstrip()}")

        threading.Thread(target=_read, args=(child,), daemon=True).start()

    def _monitor_child(self, child: subprocess.Popen) -> None:
        def _watch(c: subprocess.Popen) -> None:
            c.wait()
            _log(f"child pid={c.pid} exited rc={c.returncode}")
            if c.returncode == 42:
                sys.stderr.write("[orchestrator] inner server requested restart\n")
                _log("enqueuing _RESTART sentinel")
                self._stdin_q.put(_RESTART)

        threading.Thread(target=_watch, args=(child,), daemon=True).start()

    def _do_restart(self) -> None:
        _log("do_restart: begin")
        sys.stderr.write("[orchestrator] restarting inner server\n")
        if self._child:
            self._child.kill()
            self._child.wait()
        child = self._spawn()
        # Drain stderr before any blocking stdout read — a verbose child can fill
        # the 64KB stderr pipe and deadlock on the handshake response otherwise.
        self._start_stderr_logger(child)
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

    def _write_to_child(self, raw_line: bytes, msg: object) -> None:
        child = self._child
        try:
            child.stdin.write(raw_line)
            child.stdin.flush()
        except BrokenPipeError:
            _log("BrokenPipeError writing to child")
            rid = msg.get("id") if isinstance(msg, dict) else None
            if rid is not None:
                err = json.dumps({
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32603, "message": "Server restarting, please retry"},
                })
                with self._write_lock:
                    sys.stdout.buffer.write((err + "\n").encode())
                    sys.stdout.buffer.flush()

    def run(self) -> None:
        self._child = self._spawn()
        self._start_reader(self._child)
        self._start_stderr_logger(self._child)
        self._monitor_child(self._child)

        # stdin is read on a dedicated thread so we never call select() on a pipe fd,
        # which is unsupported on Windows. Restart signals arrive as _RESTART sentinels
        # in the same queue, so get() blocks indefinitely — no polling required.
        def _stdin_reader() -> None:
            while True:
                chunk = sys.stdin.buffer.read1(65536)
                if not chunk:
                    self._stdin_q.put(b"")
                    return
                self._stdin_q.put(chunk)

        threading.Thread(target=_stdin_reader, daemon=True).start()

        buf = b""
        while True:
            item = self._stdin_q.get()

            if item is _RESTART:
                _log("wakeup received — restarting")
                self._do_restart()
                continue

            chunk = item
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

                self._write_to_child(raw_line, msg)


def main() -> None:
    import truststore
    truststore.inject_into_ssl()
    home = Path.home()
    cwd = Path.cwd()
    resolution = resolve_env_layers(cwd, home, USER_ENV_PATH)
    project_root = cwd if resolution.project_env_path is None else resolution.project_env_path.parent
    os.environ.setdefault("COGNIGY_PROJECT_ROOT", str(project_root))
    _log(
        f"main: start cwd={cwd} project_root={project_root} "
        f"project_env_found={resolution.project_env_path is not None} "
        f"user_env_found={resolution.user_env_path.exists()}"
    )
    for key, val in resolution.values.items():
        os.environ.setdefault(key, val)
    _log(f"main: after merge mode={_detect_mode()}")
    try:
        _Orchestrator().run()
    except KeyboardInterrupt:
        sys.exit(0)
