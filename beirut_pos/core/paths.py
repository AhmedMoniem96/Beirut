"""Centralised storage paths for Beirut POS on Windows and fallbacks."""
from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "CONFIG_DIR",
    "BACKUP_DIR",
    "LICENSE_DIR",
    "DB_PATH",
    "SETTINGS_FILE",
    "LICENSE_CACHE_FILE",
    "ensure_storage_dirs",
]


def _detect_base_dir() -> Path:
    env_override = os.getenv("BEIRUT_DATA_ROOT")
    if env_override:
        return Path(env_override).expanduser().resolve()

    if os.name == "nt":
        program_data = os.environ.get("PROGRAMDATA") or r"C:\\ProgramData"
        return Path(program_data) / "BeirutPOS"

    # POS runs primarily on Windows; on other platforms keep data in project dir.
    return Path.home() / ".beirut_pos"


BASE_DIR = _detect_base_dir()
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"
BACKUP_DIR = BASE_DIR / "backup"
LICENSE_DIR = BASE_DIR / "license"

DB_PATH = DATA_DIR / "beirut_pos.db"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
LICENSE_CACHE_FILE = LICENSE_DIR / "license.sig.json"


def ensure_storage_dirs() -> None:
    """Create the directory tree required for persistent storage."""
    for path in (DATA_DIR, CONFIG_DIR, BACKUP_DIR, LICENSE_DIR):
        path.mkdir(parents=True, exist_ok=True)
