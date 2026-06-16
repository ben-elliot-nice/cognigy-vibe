#!/usr/bin/env python3
"""
Hot-reload proxy for cognigy-vibe-mcp.

Sits between Claude Code (stdio) and the actual server subprocess. The proxy
process stays alive indefinitely, so Claude Code never sees a disconnect.

To reload the server after source changes, send SIGUSR1:
    pkill -USR1 -f mcp-proxy.py
    # or: bash scripts/restart-mcp.sh

On SIGUSR1 the proxy:
1. Kills the current inner server
2. Spawns a fresh one (picks up updated source via uv run --directory)
3. Replays the MCP initialize handshake internally
4. Resumes forwarding messages — Claude Code session continues uninterrupted
"""

from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = REPO_ROOT / "cognigy-mcp"
SERVER_CMD = ["uv", "run", "--directory", str(SERVER_DIR), "cognigy-vibe-mcp"]


class HotReloadProxy:
    def __init__(self) -> None:
        self._child: subprocess.Popen | None = None
        self._init_params: dict | None = None  # params from Claude Code's initialize
        self._reload_flag = threading.Event()
        self._write_lock = threading.Lock()

    # ------------------------------------------------------------------ child lifecycle

    def _spawn(self) -> subprocess.Popen:
        return subprocess.Popen(
            SERVER_CMD,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            env=os.environ.copy(),
        )

    def _handshake(self, child: subprocess.Popen) -> None:
        """Replay MCP initialize to a freshly spawned child and consume its response."""
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
        child.stdout.readline()  # consume response — Claude Code already has capabilities
        notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        child.stdin.write((notif + "\n").encode())
        child.stdin.flush()

    def _start_reader(self, child: subprocess.Popen) -> None:
        """Spawn a daemon thread forwarding this child's stdout to Claude Code."""
        def _read(c: subprocess.Popen) -> None:
            while True:
                line = c.stdout.readline()
                if not line:
                    break
                with self._write_lock:
                    sys.stdout.buffer.write(line)
                    sys.stdout.buffer.flush()

        threading.Thread(target=_read, args=(child,), daemon=True).start()

    def _do_reload(self) -> None:
        print("[mcp-proxy] reloading inner server...", file=sys.stderr)
        if self._child:
            self._child.kill()
        try:
            child = self._spawn()
            self._handshake(child)
            self._child = child
            self._start_reader(child)
            print("[mcp-proxy] reload complete.", file=sys.stderr)
        except Exception as exc:
            print(f"[mcp-proxy] reload failed: {exc}", file=sys.stderr)

    # ------------------------------------------------------------------ run

    def run(self) -> None:
        signal.signal(signal.SIGUSR1, lambda _s, _f: self._reload_flag.set())

        self._child = self._spawn()
        self._start_reader(self._child)

        for raw_line in sys.stdin.buffer:
            if self._reload_flag.is_set():
                self._reload_flag.clear()
                self._do_reload()

            # Cache initialize params for replay on future reloads
            try:
                msg = json.loads(raw_line)
                if isinstance(msg, dict) and msg.get("method") == "initialize":
                    self._init_params = msg.get("params")
            except (json.JSONDecodeError, AttributeError):
                pass

            child = self._child
            child.stdin.write(raw_line)
            child.stdin.flush()


if __name__ == "__main__":
    HotReloadProxy().run()
