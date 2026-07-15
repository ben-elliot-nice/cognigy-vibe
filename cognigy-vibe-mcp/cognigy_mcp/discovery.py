# cognigy-vibe-mcp/cognigy_mcp/discovery.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

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


@dataclass
class ConfigResolution:
    values: dict = field(default_factory=dict)
    sources: dict[str, Path] = field(default_factory=dict)
    project_config_path: "Path | None" = None
    user_config_path: "Path | None" = None


def resolve_config_layers(
    filename: str,
    project_root: Path,
    home: Path,
    user_config_path: Path,
    loader: "Callable[[Path], dict | None]",
) -> ConfigResolution:
    """Merge project-nearest-ancestor config with user-global config. Shallow, project wins per top-level key."""
    project_config_path = find_nearest_ancestor(filename, project_root, home)
    values: dict = {}
    sources: dict[str, Path] = {}

    if user_config_path.exists():
        data = loader(user_config_path)
        if data:
            for key, val in data.items():
                values[key] = val
                sources[key] = user_config_path

    if project_config_path is not None:
        data = loader(project_config_path)
        if data:
            for key, val in data.items():
                values[key] = val
                sources[key] = project_config_path

    return ConfigResolution(
        values=values,
        sources=sources,
        project_config_path=project_config_path,
        user_config_path=user_config_path,
    )
