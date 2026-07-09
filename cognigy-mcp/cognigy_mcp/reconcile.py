# cognigy-mcp/cognigy_mcp/reconcile.py
from __future__ import annotations
import json
import re
import subprocess
from dataclasses import dataclass
from typing import Literal

from cognigy_mcp.config import CONFIG_SCHEMA_VERSION, SETUP_META_PATH


@dataclass
class SetupState:
    package_version: str
    marketplace_ref: str | None
    plugin_version: str | None
    plugin_scope: str | None
    desktop_pin: str | None
    layout_schema_version: int | None


@dataclass
class DriftIssue:
    surface: str
    current: str | None
    expected: str
    kind: Literal["drift", "missing"]


PLUGIN_ID = "cognigy-vibe@cognigy-vibe"
MARKETPLACE_NAME = "cognigy-vibe"
_VERSION_PIN_RE = re.compile(r"cognigy-vibe-mcp==([^\s]+)")


def _read_marketplace_ref() -> str | None:
    try:
        result = subprocess.run(
            ["claude", "plugin", "marketplace", "list", "--json"],
            check=True, capture_output=True, text=True,
        )
        entries = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError, TypeError):
        return None
    for entry in entries:
        if entry.get("name") == MARKETPLACE_NAME:
            return entry.get("ref")
    return None


def _read_plugin_install() -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["claude", "plugin", "list", "--json"],
            check=True, capture_output=True, text=True,
        )
        entries = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError, TypeError):
        return None, None
    for entry in entries:
        if entry.get("id") == PLUGIN_ID:
            return entry.get("version"), entry.get("scope")
    return None, None


def _read_desktop_pin() -> str | None:
    from cognigy_mcp.setup import get_desktop_config_path
    path = get_desktop_config_path()
    if not path.exists():
        return None
    try:
        config = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    entry = config.get("mcpServers", {}).get(MARKETPLACE_NAME)
    if not entry:
        return None
    for arg in entry.get("args", []):
        match = _VERSION_PIN_RE.search(arg)
        if match:
            return match.group(1)
    return None


def _read_layout_schema_version() -> int | None:
    if not SETUP_META_PATH.exists():
        return None
    try:
        data = json.loads(SETUP_META_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return data.get("schema_version")


def gather_state() -> SetupState:
    from cognigy_mcp.setup import get_installed_version
    plugin_version, plugin_scope = _read_plugin_install()
    return SetupState(
        package_version=get_installed_version(),
        marketplace_ref=_read_marketplace_ref(),
        plugin_version=plugin_version,
        plugin_scope=plugin_scope,
        desktop_pin=_read_desktop_pin(),
        layout_schema_version=_read_layout_schema_version(),
    )


def diff_state(state: SetupState) -> list[DriftIssue]:
    issues: list[DriftIssue] = []
    target = state.package_version
    expected_ref = f"v{target}"

    if state.marketplace_ref is None:
        issues.append(DriftIssue("marketplace_ref", None, expected_ref, "missing"))
    elif state.marketplace_ref != expected_ref:
        issues.append(DriftIssue("marketplace_ref", state.marketplace_ref, expected_ref, "drift"))

    if state.plugin_version is None:
        issues.append(DriftIssue("plugin_version", None, target, "missing"))
    elif state.plugin_version != target:
        issues.append(DriftIssue("plugin_version", state.plugin_version, target, "drift"))

    if state.desktop_pin is None:
        issues.append(DriftIssue("desktop_pin", None, target, "missing"))
    elif state.desktop_pin != target:
        issues.append(DriftIssue("desktop_pin", state.desktop_pin, target, "drift"))

    expected_schema = str(CONFIG_SCHEMA_VERSION)
    if state.layout_schema_version is None:
        issues.append(DriftIssue("layout_schema_version", None, expected_schema, "missing"))
    elif str(state.layout_schema_version) != expected_schema:
        issues.append(DriftIssue("layout_schema_version", str(state.layout_schema_version), expected_schema, "drift"))

    return issues
