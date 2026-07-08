# cognigy-mcp/cognigy_mcp/setup.py
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path


def get_desktop_config_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "claude-desktop" / "claude_desktop_config.json"


def detect_desktop_installed() -> bool:
    return get_desktop_config_path().parent.exists()


def get_installed_version() -> str:
    return version("cognigy-vibe-mcp")


def merge_desktop_config(path: Path, server_name: str, entry: dict) -> None:
    config: dict = {}
    if path.exists():
        config = json.loads(path.read_text())
    config.setdefault("mcpServers", {})[server_name] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    if sys.platform != "win32":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def write_credential_env(path: Path, base_url: str, api_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"COGNIGY_BASE_URL={base_url}\n"
        f"COGNIGY_API_KEY={api_key}\n"
    )
    if sys.platform != "win32":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def install_plugin(scope: str) -> None:
    scope_map = {"user": "user", "project": "project", "local": "local"}
    cmd = ["claude", "plugin", "install", "cognigy-vibe@cognigy-vibe", "--scope", scope_map[scope]]
    subprocess.run(cmd, check=True)


def main() -> None:
    pass  # wizard CLI — implemented in Task 6
