"""JSON configuration stored under ProgramData with atomic writes."""
from __future__ import annotations

import json
import os
from threading import RLock
from typing import Any, Dict

from .paths import SETTINGS_FILE, ensure_storage_dirs

_LOCK = RLock()
_DEFAULT_CONFIG: Dict[str, Any] = {
    "sqlite_synchronous": "FULL",
    "last_backup_date": "",
    "last_integrity_check": "",
}


def _ensure_file_exists() -> None:
    ensure_storage_dirs()
    if not SETTINGS_FILE.exists():
        _atomic_write_json(_DEFAULT_CONFIG)


def _atomic_write_json(payload: Dict[str, Any]) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SETTINGS_FILE.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp_path, SETTINGS_FILE)


def load_config() -> Dict[str, Any]:
    with _LOCK:
        _ensure_file_exists()
        try:
            with SETTINGS_FILE.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        merged = {**_DEFAULT_CONFIG, **data}
        if merged != data:
            _atomic_write_json(merged)
        return merged


def save_config(data: Dict[str, Any]) -> None:
    with _LOCK:
        merged = {**_DEFAULT_CONFIG, **data}
        _atomic_write_json(merged)


def get_config_value(key: str, default: Any = None) -> Any:
    config = load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    config = load_config()
    if config.get(key) == value:
        return
    config[key] = value
    save_config(config)
