"""Theme utilities for Jewelry UI."""

from __future__ import annotations


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
        font-size: 13px;
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
        padding: 4px 6px;
    }}
    QPushButton {{
        background-color: {palette["card"]};
        border: 1px solid {palette["border"]};
        border-radius: 8px;
        padding: 6px 12px;
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
        padding: 6px;
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
