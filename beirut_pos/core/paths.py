"""Centralised storage paths for Beirut POS on Windows and fallbacks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "CONFIG_DIR",
    "BACKUP_DIR",
    "LICENSE_DIR",
    "LOG_DIR",
    "DB_PATH",
    "SETTINGS_FILE",
    "LICENSE_CACHE_FILE",
    "ensure_storage_dirs",
    "get_app_data_dir",
    "resolve_seed_db_path",
]


def get_app_data_dir(app_name: str = "BeirutPOS") -> Path:
    if os.name == "nt":
        base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
        if base:
            return Path(base) / app_name
        return Path.home() / "AppData" / "Roaming" / app_name
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    return Path.home() / ".local" / "share" / "beirut_pos"


def resolve_seed_db_path(filename: str = "beirut_pos.db") -> Path | None:
    candidates = [filename, "beirut_pos_seed.db"]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base_dir = Path(__file__).resolve().parents[2]
    for candidate in candidates:
        for parent in (base_dir, base_dir / "assets"):
            path = parent / candidate
            if path.exists():
                return path
    return None


def _detect_base_dir() -> Path:
    env_override = os.getenv("BEIRUTPOS_DATA_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()

    if os.name == "nt":
        return get_app_data_dir()

    return get_app_data_dir()


BASE_DIR = _detect_base_dir()
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"
BACKUP_DIR = BASE_DIR / "backup"
LICENSE_DIR = BASE_DIR / "license"
LOG_DIR = BASE_DIR / "logs"

DB_PATH = DATA_DIR / "beirut_pos.db"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
LICENSE_CACHE_FILE = LICENSE_DIR / "license.sig.json"


def ensure_storage_dirs() -> None:
    """Create the directory tree required for persistent storage."""
    for path in (DATA_DIR, CONFIG_DIR, BACKUP_DIR, LICENSE_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
