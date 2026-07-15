# cognigy-vibe-mcp/cognigy_mcp/discovery.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


def find_nearest_ancestor(filename: str, start: Path, stop: Path) -> "Path | None":
    """Walk up from start toward stop looking for filename. Stop is the boundary (inclusive)."""
    current = start.resolve()
    stop = stop.resolve()
    while True:
        candidate = current / filename
        if candidate.exists():
            return candidate
        if current == stop or current == current.parent:
            return None
        current = current.parent


@dataclass
class EnvResolution:
    values: dict[str, str] = field(default_factory=dict)
    sources: dict[str, Path] = field(default_factory=dict)
    project_env_path: "Path | None" = None
    user_env_path: "Path | None" = None


def resolve_env_layers(project_root: Path, home: Path, user_env_path: Path) -> EnvResolution:
    """Merge project-nearest-ancestor .env with user-global .env. Project wins per-key."""
    project_env_path = find_nearest_ancestor(".env", project_root, home)
    values: dict[str, str] = {}
    sources: dict[str, Path] = {}

    if user_env_path.exists():
        for key, val in dotenv_values(user_env_path).items():
            if val is not None:
                values[key] = val
                sources[key] = user_env_path

    if project_env_path is not None:
        for key, val in dotenv_values(project_env_path).items():
            if val is not None:
                values[key] = val
                sources[key] = project_env_path

    return EnvResolution(
        values=values,
        sources=sources,
        project_env_path=project_env_path,
        user_env_path=user_env_path,
    )
