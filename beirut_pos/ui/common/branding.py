"""Utility helpers for loading and caching brand assets (logo/icon/background)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt

from beirut_pos.core.db import setting_get

_FALLBACK_BG = "#20130B"
_FALLBACK_TEXT = "#F6EFE3"
_FALLBACK_ACCENT = "#C89A5B"


def _quote_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace("\"", r"\"")


@lru_cache(maxsize=1)
def _resolve_logo_path() -> Optional[Path]:
    path = setting_get("logo_path", "").strip()
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    return p


@lru_cache(maxsize=1)
def _resolve_background_path() -> Optional[Path]:
    path = setting_get("background_path", "").strip()
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    return p


@lru_cache(maxsize=1)
def _load_raw_logo() -> Optional[QPixmap]:
    p = _resolve_logo_path()
    if p is None:
        return None
    pix = QPixmap(str(p))
    if pix.isNull():
        return None
    return pix


@lru_cache(maxsize=1)
def _load_raw_background() -> Optional[QPixmap]:
    p = _resolve_background_path()
    if p is None:
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


def get_background_path() -> Optional[str]:
    p = _resolve_background_path()
    if p is None:
        return None
    # ensure the pixmap can be loaded at least once
    if _load_raw_background() is None:
        return None
    return _quote_path(p)


def _sanitize_color(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if len(value) in {4, 7} and value.startswith("#"):
        return value
    return fallback


def get_accent_color(default: str = _FALLBACK_ACCENT) -> str:
    raw = setting_get("accent_color", default).strip()
    return _sanitize_color(raw, default)


def build_login_stylesheet() -> str:
    accent = get_accent_color()
    bg_path = get_background_path()
    parts = [
        "#LoginDialog {",
        f"    background-color: {_FALLBACK_BG};",
    ]
    if bg_path:
        parts.append(f"    border-image: url(\"{bg_path}\") 0 0 0 0 stretch stretch;")
    else:
        parts.append("    border-image: none;")
        parts.append("    background-image: none;")
    parts.extend(
        [
            "}",
            "#LoginCard {",
            "    background-color: rgba(33, 21, 15, 0.86);",
            "    border-radius: 18px;",
            f"    color: {_FALLBACK_TEXT};",
            "    padding: 24px;",
            "}",
            f"#LoginCard QLabel {{ color: {_FALLBACK_TEXT}; font-size: 12pt; }}",
            f"#LoginDialog QPushButton {{ background-color: {accent}; color: #1B0F08; border-radius: 8px; padding: 10px 20px; font-weight: 600; }}",
            f"#LoginDialog QPushButton[class=\"link\"] {{ background-color: transparent; color: {_FALLBACK_TEXT}; border: none; padding: 0; font-weight: 500; text-decoration: underline; }}",
            "#LoginDialog QPushButton:disabled { background-color: rgba(110, 96, 80, 0.7); color: rgba(27, 15, 8, 0.4); }",
            "#LoginDialog QLineEdit { border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 6px; padding: 8px 12px; background-color: rgba(255,255,255,0.96); color: #1E130B; font-size: 11pt; }",
            f"#LoginDialog QLineEdit:focus {{ border: 2px solid {accent}; }}",
            "#LoginDialog QLabel#LoginHint { color: rgba(255,255,255,0.78); font-size: 10pt; }",
        ]
    )
    return "\n".join(parts)


def build_main_window_stylesheet() -> str:
    accent = get_accent_color()
    bg_path = get_background_path()
    parts = [
        "QMainWindow {",
        f"    background-color: {_FALLBACK_BG};",
    ]
    if bg_path:
        parts.append(f"    border-image: url(\"{bg_path}\") 0 0 0 0 stretch stretch;")
    else:
        parts.append("    border-image: none;")
    parts.append("}")
    parts.extend(
        [
            "QStackedWidget { background-color: rgba(30, 21, 15, 0.85); border: none; }",
            "QWidget#TablesPage, QWidget#OrderPage { background-color: rgba(24, 16, 11, 0.88); border-radius: 18px; margin: 12px; }",
            "QStatusBar { background-color: rgba(24, 16, 11, 0.9); color: #E9DAC4; }",
            "QToolBar { background-color: rgba(24, 16, 11, 0.92); spacing: 10px; padding: 6px; border: none; }",
            f"QToolBar QLabel#appLogo {{ color: {accent}; font-weight: 600; font-size: 18px; }}",
            f"QMainWindow QPushButton {{ background-color: {accent}; color: #1B0F08; border-radius: 10px; padding: 10px 18px; font-weight: 600; }}",
            "QMainWindow QPushButton:disabled { background-color: rgba(110, 96, 80, 0.6); color: rgba(27, 15, 8, 0.35); }",
            "QMainWindow QGroupBox { background-color: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.14); border-radius: 14px; margin-top: 18px; font-weight: 600; color: #F4E8D5; }",
            "QMainWindow QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top right; padding: 0 12px; font-size: 12pt; }",
            "QMainWindow QListWidget { background-color: rgba(255,255,255,0.94); border-radius: 12px; padding: 6px; }",
            "QMainWindow QLabel { color: #F6EFE3; font-size: 12pt; }",
            "QMainWindow QLineEdit, QMainWindow QSpinBox, QMainWindow QComboBox { background-color: rgba(255,255,255,0.92); border-radius: 8px; padding: 6px 10px; }",
        ]
    )
    return "\n".join(parts)


def clear_branding_cache() -> None:
    """Drop cached pixmaps so the next access reloads from disk."""
    _resolve_logo_path.cache_clear()
    _resolve_background_path.cache_clear()
    _load_raw_logo.cache_clear()
    _load_raw_background.cache_clear()
