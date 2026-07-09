from pathlib import Path

CONFIG_BASE: Path = Path.home() / ".config" / "cognigy-vibe"
USER_ENV_PATH: Path = CONFIG_BASE / ".env"
CONFIG_SCHEMA_VERSION: int = 1
SETUP_META_PATH: Path = CONFIG_BASE / ".setup-meta.json"
