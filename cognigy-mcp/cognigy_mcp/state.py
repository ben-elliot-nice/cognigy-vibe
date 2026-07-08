from __future__ import annotations
import copy
import json
import time
from pathlib import Path
from typing import Any

CONFIG_BASE = Path.home() / ".config" / "cognigy-vibe"

# Migrate state from old locations on first access
def _migrate_old_state() -> None:
    import shutil
    for old in [
        Path.home() / ".config" / "cognigy-mcp",
        Path.home() / ".config" / "cognigy-vibe-mcp",
    ]:
        if old.exists() and not CONFIG_BASE.exists():
            shutil.copytree(old, CONFIG_BASE)
            return

_migrate_old_state()


def _deep_get(d: dict, *keys: str) -> Any:
    for key in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
        if d is None:
            return None
    return d


def _deep_set(d: dict, *keys: str, value: Any) -> None:
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class ProjectState:
    def __init__(self, project_id: str | None, resync_hours: float = 4.0):
        self.resync_hours = resync_hours
        self._state: dict = {}
        self._bind(project_id)

    def _bind(self, project_id: str | None) -> None:
        self.project_id = project_id
        self.config_dir = CONFIG_BASE / (project_id or ".unscoped")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self.config_dir / ".state.json"
        self._seed_path = self.config_dir / ".state-seed.json"
        self._interaction_path = self.config_dir / "last-interaction"
        self._state = {}
        self._load()

    def bind_project(self, project_id: str) -> None:
        """Re-scope this state instance to a specific project. Safe to call mid-session."""
        if self.project_id == project_id:
            return
        self._bind(project_id)

    def _load(self) -> None:
        try:
            seed = json.loads(self._seed_path.read_text()) if self._seed_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            seed = {}
        try:
            runtime = json.loads(self._state_path.read_text()) if self._state_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            runtime = {}
        self._state = _deep_merge(seed, runtime)

    def save(self) -> None:
        payload = json.dumps(self._state, indent=2)
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(payload)
        tmp.replace(self._state_path)

    def get(self, *keys: str) -> Any:
        return _deep_get(self._state, *keys)

    def set(self, *keys: str, value: Any) -> None:
        _deep_set(self._state, *keys, value=value)
        self.save()

    def needs_resync(self) -> bool:
        if not self._interaction_path.exists():
            return True
        try:
            last = float(self._interaction_path.read_text())
            return (time.time() - last) > (self.resync_hours * 3600)
        except (ValueError, OSError):
            return True

    def touch_interaction(self) -> None:
        tmp = self._interaction_path.with_suffix(".tmp")
        tmp.write_text(str(time.time()))
        tmp.replace(self._interaction_path)

    def as_dict(self) -> dict:
        return copy.deepcopy(self._state)
