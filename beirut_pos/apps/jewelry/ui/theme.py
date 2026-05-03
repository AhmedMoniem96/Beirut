"""Theme utilities for Jewelry UI."""

from __future__ import annotations


from dataclasses import dataclass


@dataclass(frozen=True)
class JewelrySpacingTokens:
    xxs: int = 4
    xs: int = 8
    sm: int = 12
    md: int = 16
    lg: int = 24


@dataclass(frozen=True)
class JewelryTypographyTokens:
    body_size: int = 13
    helper_size: int = 12
    title_weight: int = 700


@dataclass(frozen=True)
class JewelryControlTokens:
    field_min_height: int = 34
    button_min_height: int = 34
    icon_button_size: int = 32


@dataclass(frozen=True)
class JewelryTableTokens:
    row_height: int = 34
    header_height: int = 40
    empty_state: str = "لا توجد بيانات للعرض"


JEWELRY_SPACING = JewelrySpacingTokens()
JEWELRY_TYPOGRAPHY = JewelryTypographyTokens()
JEWELRY_CONTROLS = JewelryControlTokens()
JEWELRY_TABLE = JewelryTableTokens()


def gallery_stylesheet() -> str:
    palette = {
        "bg": "#f7f4f0",
        "card": "#ffffff",
        "accent": "#a67c52",
        "accent_dark": "#8c6745",
        "text": "#2b2b2b",
        "muted": "#6e6a64",
        "border": "#ddd6cf",
        "header": "#efe8e1",
        "row_alt": "#faf7f2",
    }
    return f"""
    QWidget {{
        background-color: {palette["bg"]};
        color: {palette["text"]};
        font-size: {JEWELRY_TYPOGRAPHY.body_size}px;
    }}
    QLabel {{
        color: {palette["text"]};
    }}
    QGroupBox {{
        background-color: {palette["card"]};
        border: 1px solid {palette["border"]};
        border-radius: 10px;
        margin-top: 12px;
        padding: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        top: 4px;
        color: {palette["muted"]};
        font-weight: bold;
    }}
    QLineEdit, QTextEdit, QComboBox, QDateEdit, QDateTimeEdit, QSpinBox, QDoubleSpinBox {{
        background: {palette["card"]};
        border: 1px solid {palette["border"]};
        border-radius: 6px;
        padding: {JEWELRY_SPACING.xxs}px {JEWELRY_SPACING.xs}px;
        min-height: {JEWELRY_CONTROLS.field_min_height}px;
    }}
    QPushButton {{
        background-color: {palette["card"]};
        border: 1px solid {palette["border"]};
        border-radius: 8px;
        padding: {JEWELRY_SPACING.xs}px {JEWELRY_SPACING.sm}px;
        min-height: {JEWELRY_CONTROLS.button_min_height}px;
    }}
    QPushButton:hover {{
        border-color: {palette["accent"]};
    }}
    QPushButton#primaryButton {{
        background-color: {palette["accent"]};
        color: white;
        font-weight: bold;
        border: none;
        padding: 10px 16px;
    }}
    QPushButton#primaryButton:hover {{
        background-color: {palette["accent_dark"]};
    }}
    QTabBar::tab {{
        background: {palette["header"]};
        padding: 8px 16px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        margin-right: 4px;
    }}
    QTabBar::tab:selected {{
        background: {palette["card"]};
        border: 1px solid {palette["border"]};
        border-bottom-color: {palette["card"]};
    }}
    QTableWidget {{
        background: {palette["card"]};
        border: 1px solid {palette["border"]};
        border-radius: 8px;
    }}
    QHeaderView::section {{
        background: {palette["header"]};
        padding: {JEWELRY_SPACING.xs}px;
        border: none;
        font-weight: bold;
    }}
    QTableWidget::item:selected {{
        background: {palette["accent"]};
        color: white;
    }}
    QTableView {{
        alternate-background-color: {palette["row_alt"]};
    }}
    QStatusBar {{
        background: {palette["header"]};
        color: {palette["muted"]};
    }}
    """
