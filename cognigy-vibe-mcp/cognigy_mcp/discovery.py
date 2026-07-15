# cognigy-vibe-mcp/cognigy_mcp/discovery.py
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from dotenv import dotenv_values


def _safe_dotenv_values(path: Path) -> dict:
    """dotenv_values(), but a file in an unreadable encoding (e.g. UTF-16 saved by
    Notepad) contributes zero values instead of crashing the whole process."""
    try:
        return dotenv_values(path)
    except (UnicodeDecodeError, OSError) as e:
        print(f"cognigy-vibe: skipping unreadable .env {path}: {e}", file=sys.stderr)
        return {}


def _ancestor_boundary(project_root: Path, home: Path) -> Path:
    """Only climb toward home when it's actually an ancestor of project_root — otherwise
    (CI checkout, /tmp, a mounted volume) don't escape project_root onto unrelated
    ancestors looking for a stray .env/config file."""
    home = home.resolve()
    current = project_root.resolve()
    return home if (home == current or home in current.parents) else current


def find_nearest_ancestor(filename: str, start: Path, stop: Path) -> "Path | None":
    """Walk up from start toward stop looking for filename. Checks stop itself, but never ascends past it."""
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
    project_env_path = find_nearest_ancestor(".env", project_root, _ancestor_boundary(project_root, home))
    values: dict[str, str] = {}
    sources: dict[str, Path] = {}

    if user_env_path.exists():
        for key, val in _safe_dotenv_values(user_env_path).items():
            if val is not None:
                values[key] = val
                sources[key] = user_env_path

    if project_env_path is not None:
        for key, val in _safe_dotenv_values(project_env_path).items():
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


def _find_nearest_valid_ancestor(
    filename: str, start: Path, stop: Path, loader: "Callable[[Path], dict | None]"
) -> "tuple[Path | None, dict | None]":
    """Like find_nearest_ancestor, but a candidate the loader rejects (returns falsy
    for — e.g. malformed JSON) doesn't stop the walk; climbing continues toward stop
    looking for a valid ancestor, matching the pre-#255 behavior of the original
    server.py loop."""
    current = start.resolve()
    stop = stop.resolve()
    while True:
        candidate = current / filename
        if candidate.exists():
            data = loader(candidate)
            if data:  # intentionally truthy, not `is not None` — a real config always
                return candidate, data  # sets $schemaVersion, so an empty {} is as unusable as None
        if current == stop or current == current.parent:
            return None, None
        current = current.parent


def resolve_config_layers(
    filename: str,
    project_root: Path,
    home: Path,
    user_config_path: Path,
    loader: "Callable[[Path], dict | None]",
) -> ConfigResolution:
    """Merge project-nearest-valid-ancestor config with user-global config. Shallow, project wins per top-level key."""
    project_config_path, project_data = _find_nearest_valid_ancestor(
        filename, project_root, _ancestor_boundary(project_root, home), loader
    )
    values: dict = {}
    sources: dict[str, Path] = {}

    if user_config_path.exists():
        data = loader(user_config_path)
        if data:  # same intentional truthy check as above — an empty {} contributes nothing
            for key, val in data.items():
                values[key] = val
                sources[key] = user_config_path

    if project_data:
        for key, val in project_data.items():
            values[key] = val
            sources[key] = project_config_path

    return ConfigResolution(
        values=values,
        sources=sources,
        project_config_path=project_config_path,
        user_config_path=user_config_path,
    )


REQUIRED_ENV_KEYS: tuple[str, ...] = ("COGNIGY_BASE_URL", "COGNIGY_API_KEY")


def missing_env_keys(resolution: EnvResolution) -> list[str]:
    return [key for key in REQUIRED_ENV_KEYS if not resolution.values.get(key)]


def _layer_line(label: str, path: Path, resolution: EnvResolution) -> str:
    keys_from_here = sorted(k for k, src in resolution.sources.items() if src == path)
    if path.exists():
        detail = f"(found — sets: {', '.join(keys_from_here)})" if keys_from_here else "(found — sets nothing usable)"
    else:
        detail = "(not found)"
    return f"  {label}. {path}  {detail}"


def build_env_guidance(resolution: EnvResolution, project_root: Path) -> str:
    missing = missing_env_keys(resolution)
    missing_str = ", ".join(missing) if missing else "(nothing — this guidance should not be shown when fully configured)"
    project_path = resolution.project_env_path or (project_root / ".env")

    lines = [
        "cognigy-vibe-mcp is not configured.",
        "",
        f"Still missing: {missing_str}",
        "",
        "Checked (nearest wins):",
        _layer_line("1", project_path, resolution),
        _layer_line("2", resolution.user_env_path, resolution),
        "",
        f"Add {missing_str} to either file (#1 takes precedence if both set it).",
        "",
        "COGNIGY_BASE_URL is the API endpoint for your deployment — not the UI URL.",
        "  CXone: https://cognigy-api-au1.nicecxone.com  (note: cognigy-api-*, not cognigy-*)",
        "  Trial: https://api-trial.cognigy.ai  (note: api-trial.*, not trial.*)",
        "",
        "Get your API key in Cognigy: My Profile → API Keys → +",
        "",
        "Once saved, retry this tool call — credentials will load automatically.",
    ]
    return "\n".join(lines)
