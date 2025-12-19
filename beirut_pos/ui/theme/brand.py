"""Brand assets (logo lockup, iconography, imagery hints) for Beirut POS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from PyQt6.QtWidgets import QStyle


@dataclass(frozen=True)
class LogoLockupSpec:
    title: str = "Beirut POS"
    subtitle: str = "Café Edition"
    clear_space_px: int = 8
    preferred_height_px: int = 40
    description: str = (
        "Stacked Arabic/English lockup with generous padding and the accent color applied to the icon silhouette."
    )


@dataclass(frozen=True)
class IconSpec:
    key: str
    glyph: QStyle.StandardPixmap
    description: str


ICON_SET: Dict[str, IconSpec] = {
    "tables": IconSpec("tables", QStyle.StandardPixmap.SP_FileDialogDetailedView, "Two-column layout for tables"),
    "reservations": IconSpec("reservations", QStyle.StandardPixmap.SP_DialogYesButton, "Checkmark for confirmed seats"),
    "inventory": IconSpec("inventory", QStyle.StandardPixmap.SP_DriveHDIcon, "Storage drive for stock"),
    "reports": IconSpec("reports", QStyle.StandardPixmap.SP_FileDialogInfoView, "Info pane for reports"),
    "purchases": IconSpec("purchases", QStyle.StandardPixmap.SP_FileDialogListView, "List icon for supplier runs"),
    "tables_admin": IconSpec("tables_admin", QStyle.StandardPixmap.SP_DesktopIcon, "Grid for layout admin"),
    "settings": IconSpec("settings", QStyle.StandardPixmap.SP_FileDialogDetailedView, "Columns for configuration"),
    "recovery": IconSpec("recovery", QStyle.StandardPixmap.SP_DialogResetButton, "Reset arrow for restore"),
}


ILLUSTRATION_STYLE = {
    "treatment": "Muted grain overlays with soft glow, pairing dark walnut surfaces with brass accent strokes.",
    "subjects": "Coffee craft moments, table service, and ticket-like cards framed with rounded corners.",
    "usage": "Prefer full-bleed backgrounds at login and small accent spots on empty states instead of busy collages.",
}


def resolve_icon(style, key: str):
    """Return a standard icon matching the requested brand key."""

    spec = ICON_SET.get(key)
    if not spec:
        return None
    return style.standardIcon(spec.glyph)
