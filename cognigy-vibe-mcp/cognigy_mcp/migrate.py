from __future__ import annotations
from pathlib import Path


def safe_move(src: Path, dest: Path) -> None:
    """Best-effort move: no-op if dest already exists, or if src vanished
    because another process racing the same migration already moved it."""
    import shutil
    if dest.exists():
        return
    try:
        shutil.move(str(src), str(dest))
    except FileNotFoundError:
        pass
