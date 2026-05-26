from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cognigy_mcp.api import CognigyClient
from cognigy_mcp.cache import Cache
from cognigy_mcp.state import ProjectState


@dataclass
class SessionContext:
    client: CognigyClient
    state: ProjectState
    cache: Cache
    workspace_dir: Path
    handlers: dict[str, Any]
