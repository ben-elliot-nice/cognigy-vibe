from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version


def _get_version() -> str:
    try:
        return version("cognigy-vibe-mcp")
    except PackageNotFoundError:
        return "dev"


def main() -> None:
    ver = _get_version()
    print(f"cognigy-vibe-launch {ver}", file=sys.stderr, flush=True)
    from cognigy_mcp import orchestrator
    orchestrator.main()
