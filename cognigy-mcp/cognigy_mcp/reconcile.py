# cognigy-mcp/cognigy_mcp/reconcile.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


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
