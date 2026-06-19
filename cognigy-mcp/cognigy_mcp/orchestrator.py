# cognigy-mcp/cognigy_mcp/orchestrator.py
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dotenv import load_dotenv


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
        self._restart_flag = threading.Event()
        self._write_lock = threading.Lock()

    def _spawn(self) -> subprocess.Popen:
        load_dotenv(override=True)
        mode = _detect_mode()
        sys.stderr.write(f"[orchestrator] starting in {mode} mode\n")
        return subprocess.Popen(
            _inner_command(mode),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            env=os.environ.copy(),
        )

    def _replay_handshake(self, child: subprocess.Popen) -> None:
        if self._init_params is None:
            return
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": self._init_params,
        })
        child.stdin.write((req + "\n").encode())
        child.stdin.flush()
        child.stdout.readline()  # consume initialize response
        notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        child.stdin.write((notif + "\n").encode())
        child.stdin.flush()

    def _notify_tools_changed(self) -> None:
        msg = json.dumps({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
        with self._write_lock:
            sys.stdout.buffer.write((msg + "\n").encode())
            sys.stdout.buffer.flush()

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
            if c.returncode == 42:
                sys.stderr.write("[orchestrator] inner server requested restart\n")
                self._restart_flag.set()

        threading.Thread(target=_watch, args=(child,), daemon=True).start()

    def _do_restart(self) -> None:
        sys.stderr.write("[orchestrator] restarting inner server\n")
        if self._child:
            self._child.kill()
            self._child.wait()
        child = self._spawn()
        self._replay_handshake(child)
        self._notify_tools_changed()
        self._start_reader(child)
        self._monitor_child(child)
        self._child = child
        sys.stderr.write("[orchestrator] restart complete\n")

    def run(self) -> None:
        self._child = self._spawn()
        self._start_reader(self._child)
        self._monitor_child(self._child)

        for raw_line in sys.stdin.buffer:
            # Two paths trigger restart: the flag is set here when the child has already
            # exited cleanly before this line arrived; the BrokenPipeError handler below
            # covers the case where the child exits mid-write (race between exit and write).
            if self._restart_flag.is_set():
                self._restart_flag.clear()
                self._do_restart()

            try:
                msg = json.loads(raw_line)
                if isinstance(msg, dict) and msg.get("method") == "initialize":
                    self._init_params = msg.get("params")
            except (json.JSONDecodeError, AttributeError):
                pass

            child = self._child
            try:
                child.stdin.write(raw_line)
                child.stdin.flush()
            except BrokenPipeError:
                # Child exited (exit 42) between the flag check and this write.
                # If a restart was requested, handle it now and replay this line.
                if self._restart_flag.is_set():
                    self._restart_flag.clear()
                    self._do_restart()
                    try:
                        self._child.stdin.write(raw_line)
                        self._child.stdin.flush()
                    except BrokenPipeError:
                        pass  # new child also died — nothing more to do


def main() -> None:
    import truststore
    truststore.inject_into_ssl()
    load_dotenv()
    _Orchestrator().run()
