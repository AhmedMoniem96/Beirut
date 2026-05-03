"""Design tokens for Beirut POS UI components.

The tokens are intentionally structured as plain dictionaries/NamedTuples so they
can be imported from Python or referenced when generating Qt StyleSheets.  Keep
values centralized here to ensure consistent spacing, typography, radii, and
colors across dialogs and widgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ColorTokens:
    primary: str = "#D4A05E"
    primary_dark: str = "#9C6B31"
    on_primary: str = "#1B0F08"
    surface: str = "#23140C"
    surface_muted: str = "#160D08"
    surface_alt: str = "#2F1A11"
    text: str = "#F8EFE4"
    text_muted: str = "#D9C7B5"
    border: str = "rgba(255,255,255,0.12)"
    success: str = "#2E7D54"
    warning: str = "#C47F1D"
    danger: str = "#B24646"
    info: str = "#2D6DB6"


@dataclass(frozen=True)
class TypographyScale:
    display: Dict[str, int] = None
    title: Dict[str, int] = None
    body: Dict[str, int] = None
    caption: Dict[str, int] = None

    def __init__(self):
        object.__setattr__(self, "display", {"size": 28, "weight": 800})
        object.__setattr__(self, "title", {"size": 16, "weight": 700})
        object.__setattr__(self, "body", {"size": 13, "weight": 600})
        object.__setattr__(self, "caption", {"size": 11, "weight": 600})


@dataclass(frozen=True)
class SpacingTokens:
    xxs: int = 4
    xs: int = 8
    sm: int = 12
    md: int = 16
    lg: int = 24
    xl: int = 32
    xxl: int = 48




@dataclass(frozen=True)
class ControlTokens:
    field_height: int = 38
    compact_field_width: int = 92
    date_field_width: int = 148


@dataclass(frozen=True)
class TableTokens:
    row_height: int = 36
    header_height: int = 42
    empty_state_text: str = "لا توجد بيانات لعرضها"

@dataclass(frozen=True)
class RadiusTokens:
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 22
    pill: int = 999


@dataclass(frozen=True)
class ShadowTokens:
    soft: str = "0 10px 30px rgba(0,0,0,0.28)"
    raised: str = "0 18px 48px rgba(0,0,0,0.35)"
    inset: str = "inset 0 1px 0 rgba(255,255,255,0.08)"


COLORS = ColorTokens()
TYPOGRAPHY = TypographyScale()
SPACING = SpacingTokens()
CONTROLS = ControlTokens()
TABLE = TableTokens()
RADII = RadiusTokens()
SHADOWS = ShadowTokens()


def typography_rule(role: str) -> str:
    """Return a small CSS snippet for a typography role using the tokens."""
    mapping = {
        "display": TYPOGRAPHY.display,
        "title": TYPOGRAPHY.title,
        "body": TYPOGRAPHY.body,
        "caption": TYPOGRAPHY.caption,
    }
    cfg = mapping.get(role, TYPOGRAPHY.body)
    return f"font-size: {cfg['size']}px; font-weight: {cfg['weight']};"
