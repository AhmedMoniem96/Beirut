"""Centralised, user-writable storage paths for Beirut POS."""

from __future__ import annotations

import os
import shutil
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
]


def _detect_base_dir() -> Path:
    env_override = os.getenv("BEIRUTPOS_DATA_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()

    if os.name == "nt":
        # A normal desktop user can read %PROGRAMDATA% but cannot reliably
        # write there. Keep mutable application data under the user's profile
        # so schema migrations and settings saves do not require elevation.
        app_data = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if app_data:
            return Path(app_data) / "BeirutPOS"
        return Path.home() / "AppData" / "Roaming" / "BeirutPOS"

    # POS runs primarily on Windows; on other platforms keep data in project dir.
    return Path.home() / ".beirut_pos"


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
    _migrate_legacy_windows_data()


def _migrate_legacy_windows_data() -> None:
    """Copy legacy ProgramData files into the writable per-user location once."""
    if os.name != "nt":
        return

    program_data = os.environ.get("PROGRAMDATA") or r"C:\\ProgramData"
    legacy_dir = Path(program_data) / "BeirutPOS"
    if legacy_dir == BASE_DIR or not legacy_dir.exists():
        return

    # Copy only the live data/configuration files.  Existing user data in the
    # new location always wins, and backup archives remain in the old location
    # so a first launch cannot overwrite anything.
    relative_files = (
        Path("data") / "beirut_pos.db",
        Path("data") / "beirut_pos.db-wal",
        Path("data") / "beirut_pos.db-shm",
        Path("config") / "settings.json",
        Path("license") / "license.sig.json",
    )
    for relative in relative_files:
        source = legacy_dir / relative
        target = BASE_DIR / relative
        if not source.is_file() or target.exists():
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        except OSError:
            # Migration is best effort; the app can still initialize a fresh
            # database when the old installation directory is inaccessible.
            continue
