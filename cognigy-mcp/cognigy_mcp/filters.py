from __future__ import annotations

BLOCKED_TOP_LEVEL: frozenset[str] = frozenset({"__v"})
BLOCKED_IN_CONFIG: frozenset[str] = frozenset({"transpiled"})


def strip_response(data: dict) -> dict:
    out = {k: v for k, v in data.items() if k not in BLOCKED_TOP_LEVEL}
    if "config" in out:
        config = {k: v for k, v in out["config"].items() if k not in BLOCKED_IN_CONFIG}
        if "mock" in config and isinstance(config["mock"], dict):
            config = {**config, "mock": {k: v for k, v in config["mock"].items() if k not in BLOCKED_IN_CONFIG}}
        out = {**out, "config": config}
    return out
