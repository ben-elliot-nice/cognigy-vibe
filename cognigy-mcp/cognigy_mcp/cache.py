from __future__ import annotations
import json
import time
from pathlib import Path


class Cache:
    def __init__(self, cache_dir: Path, ttl: int = 300):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl

    def _resource_path(self, resource_type: str, resource_id: str) -> Path:
        return self.cache_dir / resource_type / f"{resource_id}.json"

    def _snapshot_path(self, node_id: str) -> Path:
        return self.cache_dir / "nodes" / node_id / "code.js"

    def get(self, resource_type: str, resource_id: str) -> tuple[dict | None, bool]:
        path = self._resource_path(resource_type, resource_id)
        if not path.exists():
            return None, False
        entry = json.loads(path.read_text())
        fresh = (time.time() - entry["_cached_at"]) < self.ttl
        return entry["data"], fresh

    def set(self, resource_type: str, resource_id: str, data: dict) -> None:
        path = self._resource_path(resource_type, resource_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"_cached_at": time.time(), "data": data}))

    def invalidate(self, resource_type: str, resource_id: str) -> None:
        path = self._resource_path(resource_type, resource_id)
        if path.exists():
            path.unlink()

    def invalidate_all(self) -> None:
        for f in self.cache_dir.rglob("*.json"):
            f.unlink()
        for f in self.cache_dir.rglob("*.js"):
            f.unlink()

    def get_node_snapshot(self, node_id: str) -> str | None:
        path = self._snapshot_path(node_id)
        return path.read_text() if path.exists() else None

    def set_node_snapshot(self, node_id: str, content: str) -> None:
        path = self._snapshot_path(node_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
