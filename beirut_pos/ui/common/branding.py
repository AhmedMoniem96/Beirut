"""Utility helpers for loading and caching brand assets (logo/icon/background)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt

from beirut_pos.core.db import setting_get
from beirut_pos.utils.paths import resource_path


_FALLBACK_BG = "#160D08"
_FALLBACK_SURFACE = "#23140C"
_FALLBACK_TEXT = "#F8EFE4"
_FALLBACK_MUTED_TEXT = "#D9C7B5"
_FALLBACK_ACCENT = "#D4A05E"
_FALLBACK_ACCENT_DARK = "#9C6B31"
_FALLBACK_MENU_CARD = "#28160F"
_FALLBACK_MENU_HEADER = "#F1C58F"
_FALLBACK_MENU_BUTTON = "#F5E1C8"
_FALLBACK_MENU_BUTTON_TEXT = "#2B130B"
_FALLBACK_MENU_BUTTON_HOVER = "#E3C69F"
_FALLBACK_TOOLBAR = "#000000"
_FALLBACK_TOOLBAR_TEXT = "#FFFFFF"


def _quote_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace("\"", r"\"")


def _first_existing(*candidates: str) -> Optional[Path]:
    """Return the first candidate path that exists (supports PyInstaller via resource_path)."""
    for rel in candidates:
        p = Path(resource_path(rel))
        if p.exists() and p.is_file():
            return p
    return None


@lru_cache(maxsize=1)
def _resolve_logo_path() -> Optional[Path]:
    # 1) user-configured (DB setting)
    cfg = setting_get("logo_path", "").strip()
    if cfg:
        p = Path(cfg)
        if p.exists() and p.is_file():
            return p

    # 2) bundled fallbacks (inside the EXE via --add-data "assets;assets")
    # try .ico first (best for Windows), then png/jpg
    return _first_existing(
        "assets/app.ico",
        "assets/logo.ico",
        "assets/app.png",
        "assets/logo.png",
        "assets/app.jpg",
        "assets/logo.jpg",
    )
@lru_cache(maxsize=1)
def _resolve_background_path() -> Optional[Path]:
    # 1) user-configured
    cfg = setting_get("background_path", "").strip()
    if cfg:
        p = Path(cfg)
        if p.exists() and p.is_file():
            return p

    # 2) bundled fallbacks
    return _first_existing(
        "assets/login_bg.jpg",
        "assets/login_bg.png",
        "assets/bg.jpg",
        "assets/bg.png",
        "assets/background.jpg",
        "assets/background.png",
    )

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


def get_surface_color(default: str = _FALLBACK_SURFACE) -> str:
    raw = setting_get("surface_color", default).strip()
    return _sanitize_color(raw, default)


def get_text_color(default: str = _FALLBACK_TEXT) -> str:
    raw = setting_get("text_color", default).strip()
    return _sanitize_color(raw, default)


def get_muted_text_color(default: str = _FALLBACK_MUTED_TEXT) -> str:
    raw = setting_get("muted_text_color", default).strip()
    return _sanitize_color(raw, default)


def get_menu_card_color(default: str = _FALLBACK_MENU_CARD) -> str:
    raw = setting_get("menu_card_color", default).strip()
    return _sanitize_color(raw, default)


def get_menu_header_color(default: str = _FALLBACK_MENU_HEADER) -> str:
    raw = setting_get("menu_header_color", default).strip()
    return _sanitize_color(raw, default)


def get_menu_button_color(default: str = _FALLBACK_MENU_BUTTON) -> str:
    raw = setting_get("menu_button_color", default).strip()
    return _sanitize_color(raw, default)


def get_menu_button_text_color(default: str = _FALLBACK_MENU_BUTTON_TEXT) -> str:
    raw = setting_get("menu_button_text_color", default).strip()
    return _sanitize_color(raw, default)


def get_menu_button_hover_color(default: str = _FALLBACK_MENU_BUTTON_HOVER) -> str:
    raw = setting_get("menu_button_hover_color", default).strip()
    return _sanitize_color(raw, default)


def get_toolbar_color(default: str = _FALLBACK_TOOLBAR) -> str:
    raw = setting_get("toolbar_color", default).strip()
    return _sanitize_color(raw, default)


def get_toolbar_text_color(default: str = _FALLBACK_TOOLBAR_TEXT) -> str:
    raw = setting_get("toolbar_text_color", default).strip()
    return _sanitize_color(raw, default)


def default_palette() -> dict[str, str]:
    """Return the default color palette used when resetting branding options."""

    return {
        "accent_color": _FALLBACK_ACCENT,
        "surface_color": _FALLBACK_SURFACE,
        "text_color": _FALLBACK_TEXT,
        "muted_text_color": _FALLBACK_MUTED_TEXT,
        "menu_card_color": _FALLBACK_MENU_CARD,
        "menu_header_color": _FALLBACK_MENU_HEADER,
        "menu_button_color": _FALLBACK_MENU_BUTTON,
        "menu_button_text_color": _FALLBACK_MENU_BUTTON_TEXT,
        "menu_button_hover_color": _FALLBACK_MENU_BUTTON_HOVER,
        "toolbar_color": _FALLBACK_TOOLBAR,
        "toolbar_text_color": _FALLBACK_TOOLBAR_TEXT,
    }


def build_login_stylesheet() -> str:
    accent = get_accent_color()
    text = get_text_color()
    muted = get_muted_text_color()
    bg_path = get_background_path()

    parts = [
        "#LoginDialog {",
        f"    background-color: {_FALLBACK_BG};",
    ]
    if bg_path:
        parts.append(f"    border-image: url(\"{bg_path}\") 0 0 0 0 stretch stretch;")
        parts.append("    background-position: center;")
    else:
        parts.append("    border-image: none;")
        parts.append("    background-image: none;")

    parts.extend([
        "}",
        "#LoginCard {",
        "    background-color: rgba(19, 12, 8, 0.88);",
        "    border-radius: 32px;",
        f"    color: {text};",
        "    border: 1px solid rgba(255,255,255,0.1);",
        "}",
        f"#LoginCard QLabel {{ color: {text}; font-size: 12.5pt; font-weight: 600; }}",
        f"#LoginCard QLabel#BrandTitle {{ font-size: 22pt; font-weight: 800; letter-spacing: 1.2px; color: {accent}; }}",
        f"#LoginCard QLabel#LoginHero {{ font-size: 14pt; font-weight: 700; color: {text}; }}",
        f"#LoginCard QLabel#HeroHint {{ color: {muted}; font-size: 11.5pt; }}",
        f"#LoginCard QLabel#FormTitle {{ font-size: 16pt; font-weight: 800; margin-bottom: 8px; }}",
        f"#LoginCard QLabel#LoginHint {{ color: {muted}; font-size: 11.5pt; letter-spacing: 0.4px; }}",
        "#LoginCard QFrame#BrandColumn { background: transparent; }",
        "#LoginCard QFrame#LoginForm { background-color: rgba(12, 7, 4, 0.72); border-radius: 26px; border: 1px solid rgba(255,255,255,0.08); }",
        f"#LoginDialog QPushButton {{ background-color: {accent}; color: #1B0F08; border-radius: 18px; padding: 14px 28px; font-weight: 700; letter-spacing: 0.5px; min-height: 48px; }}",
        f"#LoginDialog QPushButton:disabled {{ background-color: rgba(110, 96, 80, 0.7); color: rgba(27, 15, 8, 0.4); }}",
        f"#LoginDialog QPushButton[class=\"link\"] {{ background-color: transparent; color: {accent}; border:none; padding: 4px 8px; font-weight: 600; text-decoration: none; }}",
        f"#LoginDialog QPushButton[class=\"link\"]:hover {{ color: {text}; text-decoration: underline; }}",
        f"#LoginDialog QLineEdit {{ border: 1px solid rgba(255, 255, 255, 0.16); border-radius: 14px; padding: 14px 18px; background-color: rgba(255,255,255,0.96); color: #2A170C; font-size: 12.5pt; }}",
        f"#LoginDialog QLineEdit:focus {{ border: 2px solid {accent}; background-color: rgba(255,255,255,0.99); }}",
        f"#LoginDialog QLabel#LoginHero, #LoginDialog QLabel#HeroHint {{ max-width: 320px; }}",
        "#LoginDialog QPushButton[class=\"link\"] { border-radius: 12px; }",
    ])

    return "\n".join(parts)


def build_main_window_stylesheet() -> str:
    accent = get_accent_color()
    text = get_text_color()
    muted = get_muted_text_color()
    surface = get_surface_color()
    menu_card = get_menu_card_color()
    menu_header = get_menu_header_color()
    menu_button = get_menu_button_color()
    menu_button_text = get_menu_button_text_color()
    menu_button_hover = get_menu_button_hover_color()
    bg_path = get_background_path()
    toolbar_color = get_toolbar_color()
    toolbar_text = get_toolbar_text_color()

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
            "QWidget#MainContainer { background-color: transparent; }",
            f"QStackedWidget {{ background-color: rgba(22, 13, 8, 0.84); border: 1px solid rgba(255,255,255,0.08); border-radius: 28px; margin: 0 6px; }}",
            f"QWidget#TablesPage, QWidget#OrderPage {{ background-color: {surface}; border-radius: 28px; margin: 18px; padding: 12px; }}",
            f"QStatusBar {{ background-color: rgba(22, 13, 8, 0.9); color: {muted}; border-top: 1px solid rgba(255,255,255,0.1); }}",
            f"QToolBar {{ background-color: {toolbar_color}; spacing: 16px; padding: 12px 18px; border: none; }}",
            f"QToolBar QLabel#appLogo {{ color: {toolbar_text}; font-weight: 700; font-size: 22px; letter-spacing: 1px; }}",
            f"QToolBar QToolButton {{ color: {toolbar_text}; font-weight: 700; font-size: 12pt; padding: 8px 14px; border-radius: 12px; background-color: transparent; }}",
            f"QToolBar QToolButton:hover {{ background-color: {accent}; color: #1B0F08; border-radius: 12px; }}",
            f"QToolBar QToolButton:pressed {{ background-color: {accent}; color: #1B0F08; border-radius: 12px; }}",
            f"QToolBar QToolButton:disabled {{ color: rgba(255,255,255,0.35); background: transparent; }}",
            f"QMainWindow QPushButton {{ background-color: {accent}; color: #1B0F08; border-radius: 16px; padding: 12px 22px; font-weight: 700; letter-spacing: 0.4px; }}",
            "QMainWindow QPushButton:disabled { background-color: rgba(110, 96, 80, 0.6); color: rgba(27, 15, 8, 0.35); }",
            f"QMainWindow QGroupBox {{ background-color: {menu_card}; border: 1px solid rgba(255,255,255,0.12); border-radius: 20px; margin-top: 24px; font-weight: 700; color: {menu_header}; padding-top: 24px; }}",
            f"QMainWindow QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top right; padding: 0 16px; font-size: 13pt; color: {menu_header}; }}",
            "QMainWindow QListWidget { background-color: rgba(255,255,255,0.94); border-radius: 18px; padding: 10px; font-size: 12pt; }",
            "QMainWindow QListWidget#OrderItems { padding: 16px; }",
            f"QMainWindow QLabel {{ color: {text}; font-size: 12pt; font-weight: 600; }}",
            "QMainWindow QLineEdit, QMainWindow QSpinBox, QMainWindow QComboBox { background-color: rgba(255,255,255,0.92); border-radius: 12px; padding: 8px 12px; }",
            "QMainWindow QListWidget::item { margin: 6px; padding: 10px 14px; border-radius: 12px; }",
            f"QMainWindow QListWidget::item:selected {{ background-color: {accent}; color: #20130B; font-weight: 700; }}",
            "QScrollArea { border: none; background: transparent; }",
            "QScrollArea > QWidget > QWidget { background: transparent; }",
            "QGroupBox QPushButton { font-size: 12pt; font-weight: 600; min-height: 72px; }",
            f"QGroupBox QPushButton {{ background-color: {menu_button}; color: {menu_button_text}; border-radius: 18px; padding: 12px; }}",
            f"QGroupBox QPushButton:hover {{ background-color: {menu_button_hover}; color: {menu_button_text}; }}",
            "QFrame#ToastBanner { border-radius: 18px; padding: 14px 20px; border: 1px solid rgba(255,255,255,0.18); background-color: rgba(255,255,255,0.90); color: #1B0F08; font-weight: 600; }",
            f"QFrame#ToastBanner[kind=\"success\"] {{ background-color: rgba(72, 160, 132, 0.9); color: {text}; border: 1px solid rgba(72,160,132,0.4); }}",
            "QFrame#ToastBanner[kind=\"warn\"] { background-color: rgba(214, 161, 80, 0.92); color: #2B130B; border: 1px solid rgba(43,19,11,0.2); }",
            "QFrame#ToastBanner[kind=\"error\"] { background-color: rgba(178, 70, 70, 0.92); color: #1B0F08; border: 1px solid rgba(80,0,0,0.3); }",
            "QFrame#ToastBanner QLabel { font-size: 12pt; font-weight: 600; }",
            "QFrame#ToastBanner QPushButton { background-color: transparent; color: #1B0F08; border: none; padding: 4px 8px; font-weight: 700; }",
        ]
    )
    return "\n".join(parts)


def clear_branding_cache() -> None:
    """Drop cached pixmaps so the next access reloads from disk."""
    _resolve_logo_path.cache_clear()
    _resolve_background_path.cache_clear()
    _load_raw_logo.cache_clear()
    _load_raw_background.cache_clear()
