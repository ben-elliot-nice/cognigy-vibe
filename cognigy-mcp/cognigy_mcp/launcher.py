from __future__ import annotations

import sys
from importlib.metadata import version


def _get_version() -> str:
    return version("cognigy-vibe-mcp")


def main() -> None:
    import truststore
    truststore.inject_into_ssl()
    ver = _get_version()
    print(f"cognigy-vibe-launch {ver}", file=sys.stderr, flush=True)
    from cognigy_mcp import orchestrator
    orchestrator.main()
