# cognigy-mcp/cognigy_mcp/setup.py
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from cognigy_mcp.config import USER_ENV_PATH


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
    try:
        return version("cognigy-vibe-mcp")
    except PackageNotFoundError:
        raise RuntimeError(
            "Cannot determine cognigy-vibe-mcp version. "
            "Run the wizard via: uvx --from cognigy-vibe-mcp cognigy-vibe-setup"
        ) from None


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
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
    existing["COGNIGY_BASE_URL"] = base_url
    existing["COGNIGY_API_KEY"] = api_key
    content = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
    path.write_text(content)
    if sys.platform != "win32":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def install_plugin(scope: str) -> None:
    if scope not in ("user", "project", "local"):
        raise ValueError(f"Invalid scope: {scope!r}. Must be one of: user, project, local")
    subprocess.run(
        ["claude", "plugin", "marketplace", "add", "ben-elliot-nice/cognigy-claude-plugin"],
        check=True,
    )
    subprocess.run(
        ["claude", "plugin", "install", "cognigy-vibe@cognigy-vibe", "--scope", scope],
        check=True,
    )


def _prompt(msg: str, default: str = "", secret: bool = False) -> str:
    import getpass
    display = f"{msg} [{default}]: " if default else f"{msg}: "
    if secret:
        value = getpass.getpass(display)
    else:
        value = input(display).strip()
    return value or default


def _parse_args() -> "argparse.Namespace":
    import argparse
    parser = argparse.ArgumentParser(
        prog="cognigy-vibe-setup",
        description="Install and configure the cognigy-vibe plugin.",
    )
    parser.add_argument(
        "--install-only",
        action="store_true",
        help="Skip credential collection; install plugin only.",
    )
    parser.add_argument(
        "--client",
        choices=["code", "desktop", "both"],
        default=None,
        help="Which client(s) to configure (default: both if Desktop detected, else code).",
    )
    parser.add_argument(
        "--scope",
        choices=["user", "project", "local"],
        default=None,
        help="Plugin install scope for Claude Code (default: user).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print("\ncognigy-vibe setup wizard\n")

    # 1. Mode (flag or prompt)
    if args.install_only:
        mode = "install"
    else:
        mode_raw = _prompt("Mode — install+configure or install only? (configure/install)", default="configure")
        mode = "install" if mode_raw == "install" else "configure"

    # 2. Client (flag or detect+prompt)
    if args.client:
        clients = ["code", "desktop"] if args.client == "both" else [args.client]
    else:
        desktop_detected = detect_desktop_installed()
        default_client = "both" if desktop_detected else "code"
        while True:
            client_raw = _prompt("Install for which client? (code/desktop/both)", default=default_client)
            if client_raw in ("both", "b"):
                clients = ["code", "desktop"]
                break
            elif client_raw in ("desktop", "d"):
                clients = ["desktop"]
                break
            elif client_raw in ("code", "c"):
                clients = ["code"]
                break
            else:
                print(f"  Invalid choice '{client_raw}'. Enter: code, desktop, or both.")

    # 3. Scope (flag or prompt, Code only)
    scope = "user"
    if "code" in clients:
        if args.scope:
            scope = args.scope
        else:
            scope_raw = _prompt("Plugin scope for Claude Code? (user/project/local)", default="user")
            scope = scope_raw if scope_raw in ("user", "project", "local") else "user"

    # 4. Credentials (configure mode only)
    base_url = ""
    api_key = ""
    if mode == "configure":
        print("\nCredentials (project ID can be set later via the sync_remote_state tool)")
        base_url = _prompt("COGNIGY_BASE_URL (e.g. https://cognigy-api-au1.nicecxone.com)")
        while not base_url:
            print("  Base URL is required.")
            base_url = _prompt("COGNIGY_BASE_URL")
        base_url = base_url.rstrip("/")
        api_key = _prompt("COGNIGY_API_KEY", secret=True)
        while not api_key:
            print("  API key is required.")
            api_key = _prompt("COGNIGY_API_KEY", secret=True)

    # 5. Install + write
    print()

    if "code" in clients:
        if scope != "local":
            print(f"Installing plugin at {scope} scope...")
            install_plugin(scope)
        else:
            print("Local scope: plugin install skipped.")
            print("  Run manually: claude plugin marketplace add ben-elliot-nice/cognigy-claude-plugin")
            print("  Then:         claude plugin install cognigy-vibe@cognigy-vibe --scope local")
        if mode == "configure":
            cred_path = USER_ENV_PATH if scope == "user" else Path.cwd() / ".env"
            print(f"Writing credentials to {cred_path}")
            write_credential_env(cred_path, base_url, api_key)

    if "desktop" in clients:
        ver = get_installed_version()
        desktop_path = get_desktop_config_path()
        skip_desktop = False
        if desktop_path.exists():
            try:
                import json as _json
                existing_config = _json.loads(desktop_path.read_text())
                if "cognigy-vibe" in existing_config.get("mcpServers", {}):
                    print(f"  An existing 'cognigy-vibe' Desktop entry was found.")
                    resp = _prompt("  Overwrite it?", default="y")
                    if resp.lower() not in ("y", "yes"):
                        print("  Skipping Desktop config update.")
                        skip_desktop = True
            except Exception:
                pass
        if not skip_desktop:
            entry: dict = {
                "command": "uvx",
                "args": ["--from", f"cognigy-vibe-mcp=={ver}", "cognigy-vibe-launch"],
            }
            if mode == "configure":
                entry["env"] = {
                    "COGNIGY_BASE_URL": base_url,
                    "COGNIGY_API_KEY": api_key,
                }
            print(f"Writing Desktop config to {desktop_path}")
            merge_desktop_config(desktop_path, "cognigy-vibe", entry)

    # 6. Success
    print("\nDone!")
    if "code" in clients:
        print("  Claude Code: restart Claude if it is already running.")
    if "desktop" in clients:
        print("  Claude Desktop: restart the application to pick up the new config.")
        print("  Note: the Desktop entry is pinned to the version installed today.")
        print("  After a cognigy-vibe-mcp upgrade, re-run this wizard to update the pin.")
    print()
