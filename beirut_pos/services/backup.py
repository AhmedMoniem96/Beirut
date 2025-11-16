"""Automated backup and restore helpers for the durable SQLite database."""

from __future__ import annotations

import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from ..core import db as db_module
from ..core.config_store import get_config_value, set_config_value
from ..core.paths import BACKUP_DIR, DB_PATH, ensure_storage_dirs

_BACKUP_NAME = "beirut_pos.db"


def _today_dir() -> Path:
    return BACKUP_DIR / date.today().isoformat()


def prune_old_backups(retention_days: int = 14) -> None:
    ensure_storage_dirs()
    if not BACKUP_DIR.exists():
        return
    dated_dirs = []
    for entry in BACKUP_DIR.iterdir():
        if not entry.is_dir():
            continue
        try:
            entry_date = datetime.strptime(entry.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        dated_dirs.append((entry_date, entry))
    dated_dirs.sort()
    while len(dated_dirs) > retention_days:
        _, path = dated_dirs.pop(0)
        shutil.rmtree(path, ignore_errors=True)


def backup_now() -> Path:
    """Create (or replace) today's backup and return its path."""
    ensure_storage_dirs()
    today_dir = _today_dir()
    today_dir.mkdir(parents=True, exist_ok=True)
    target = today_dir / _BACKUP_NAME
    tmp_target = target.with_suffix(".tmp")

    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(tmp_target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    os.replace(tmp_target, target)
    set_config_value("last_backup_date", date.today().isoformat())
    prune_old_backups()
    return target


def ensure_daily_backup(retention_days: int = 14) -> Optional[Path]:
    """Guarantee there's a backup for today (used on startup)."""
    ensure_storage_dirs()
    today = date.today().isoformat()
    recorded = str(get_config_value("last_backup_date", ""))
    candidate = _today_dir() / _BACKUP_NAME
    if recorded == today and candidate.exists():
        prune_old_backups(retention_days)
        return candidate
    path = backup_now()
    prune_old_backups(retention_days)
    return path


def latest_backup_path() -> Optional[Path]:
    ensure_storage_dirs()
    if not BACKUP_DIR.exists():
        return None
    best: tuple[date, Path] | None = None
    for entry in BACKUP_DIR.iterdir():
        if not entry.is_dir():
            continue
        candidate = entry / _BACKUP_NAME
        if not candidate.exists():
            continue
        try:
            entry_date = datetime.strptime(entry.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if not best or entry_date > best[0]:
            best = (entry_date, candidate)
    return None if best is None else best[1]


@dataclass(frozen=True)
class BackupMetadata:
    """Summary information for a backup file on disk."""

    path: Path
    created_at: datetime
    size_bytes: int

    @property
    def human_size(self) -> str:
        size = float(self.size_bytes)
        units = ["B", "KB", "MB", "GB", "TB"]
        for unit in units:
            if size < 1024.0:
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


def list_backup_metadata(limit: int = 10) -> List[BackupMetadata]:
    """Return metadata objects for the newest *limit* backups."""

    ensure_storage_dirs()
    if not BACKUP_DIR.exists():
        return []
    entries: List[BackupMetadata] = []
    for day_dir in sorted(BACKUP_DIR.iterdir(), reverse=True):
        if not day_dir.is_dir():
            continue
        candidate = day_dir / _BACKUP_NAME
        if not candidate.exists():
            continue
        try:
            stat = candidate.stat()
        except OSError:
            continue
        created = datetime.fromtimestamp(stat.st_mtime)
        entries.append(BackupMetadata(candidate, created, stat.st_size))
        if len(entries) >= max(1, limit):
            break
    return entries


def restore_backup(source: Path) -> Path:
    """Replace the live database with a backup file."""
    ensure_storage_dirs()
    resolved = source.resolve()
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    if not resolved.is_file():
        raise ValueError("ملف النسخة الاحتياطية غير صالح")

    db_module.close_engine()
    tmp_path = DB_PATH.with_suffix(".restore.tmp")
    shutil.copy2(resolved, tmp_path)
    os.replace(tmp_path, DB_PATH)
    return DB_PATH
