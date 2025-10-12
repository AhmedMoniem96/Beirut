"""Utility helpers for loading and caching brand assets (logo/icon)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt

from beirut_pos.core.db import setting_get


@lru_cache(maxsize=1)
def _load_raw_logo() -> Optional[QPixmap]:
    path = setting_get("logo_path", "").strip()
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    pix = QPixmap(str(p))
    if pix.isNull():
        return None
    return pix


def get_logo_pixmap(max_height: int | None = None) -> Optional[QPixmap]:
    """Return the configured logo pixmap, optionally scaled to `max_height`."""
    pix = _load_raw_logo()
    if pix is None:
        return None
    if max_height is None or pix.height() <= max_height:
        return QPixmap(pix)
    return pix.scaledToHeight(max_height, Qt.TransformationMode.SmoothTransformation)


def get_logo_icon(size: int = 64) -> Optional[QIcon]:
    pix = get_logo_pixmap(size)
    if pix is None:
        return None
    return QIcon(pix)


def clear_logo_cache() -> None:
    """Drop cached pixmaps so the next access reloads from disk."""
    _load_raw_logo.cache_clear()
