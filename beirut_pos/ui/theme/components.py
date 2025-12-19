from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette

from .tokens import COLORS, RADII, SPACING, SHADOWS, typography_rule


class DSButton(QPushButton):
    """Token-driven push button with variants and sizes."""

    def __init__(self, text: str = "", *, variant: str = "primary", size: str = "md", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("DSButton")
        self.setProperty("data-variant", variant)
        self.setProperty("data-size", size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class DSLinkButton(DSButton):
    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, variant="link", size="sm", parent=parent)
        self.setFlat(True)


class DSTextField(QLineEdit):
    def __init__(self, placeholder: str = "", *, width: Optional[int] = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DSTextField")
        self.setPlaceholderText(placeholder)
        if width:
            self.setMinimumWidth(width)


class DSSelect(QComboBox):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DSSelect")
        self.setEditable(False)


class DSTable(QTableWidget):
    def __init__(self, rows: int = 0, columns: int = 0, parent: QWidget | None = None):
        super().__init__(rows, columns, parent)
        self.setObjectName("DSTable")
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setHighlightSections(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSortingEnabled(True)
        self._column_alignments: list[Qt.AlignmentFlag | None] = []

    def set_headers(self, labels: list[str]):
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)

    def set_column_alignments(self, alignments: list[Qt.AlignmentFlag | None]):
        self._column_alignments = alignments

    def add_row(self, values: list[str]):
        row = self.rowCount()
        self.insertRow(row)
        for col, value in enumerate(values):
            self.setItem(row, col, QTableWidgetItem(value))

    def setItem(self, row: int, column: int, item: QTableWidgetItem) -> None:  # noqa: N802 (Qt override)
        if self._column_alignments and column < len(self._column_alignments):
            alignment = self._column_alignments[column]
            if alignment:
                item.setTextAlignment(alignment)
        super().setItem(row, column, item)


class DSAlert(QFrame):
    def __init__(self, text: str, *, severity: str = "info", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DSAlert")
        self.setProperty("data-severity", severity)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.md, SPACING.sm, SPACING.md, SPACING.sm)
        layout.setSpacing(SPACING.xs)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setProperty("data-typo", "body")
        layout.addWidget(self.label)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt compatibility)
        self.label.setText(text)

    def set_severity(self, severity: str) -> None:
        self.setProperty("data-severity", severity)
        self.style().unpolish(self)
        self.style().polish(self)


class DSTabWidget(QTabWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DSTabWidget")
        self.setDocumentMode(True)


class DSModal(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DSModal")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(COLORS.surface_muted))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(COLORS.text))
        self.setPalette(pal)


class TokenDocBlock(QFrame):
    """Small helper used on the style guide page to highlight token usage."""

    def __init__(self, title: str, body: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("TokenDocBlock")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        layout.setSpacing(SPACING.sm)

        title_label = QLabel(title)
        title_label.setProperty("data-typo", "title")
        layout.addWidget(title_label)

        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setProperty("data-typo", "body")
        layout.addWidget(body_label)


class KpiCard(QFrame):
    """Small pill-like summary card used for KPIs and totals."""

    def __init__(self, icon: str, title: str, value: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("KpiCard")
        root = QHBoxLayout(self)
        root.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        root.setSpacing(SPACING.sm)

        self.icon_label = QLabel(icon)
        self.icon_label.setFixedWidth(28)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setProperty("data-typo", "title")

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setProperty("data-typo", "caption")
        self.title_label.setStyleSheet(f"color: {COLORS.text_muted};")

        self.value_label = QLabel(value)
        self.value_label.setProperty("data-typo", "title")

        text_box.addWidget(self.title_label)
        text_box.addWidget(self.value_label)

        root.addWidget(self.icon_label)
        root.addLayout(text_box, 1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


# Utility helpers -----------------------------------------------------------

def apply_typography(widget: QWidget, role: str = "body") -> None:
    widget.setProperty("data-typo", role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def design_system_stylesheet(accent_color: str | None = None) -> str:
    """Centralized QSS for the design system components."""

    accent = accent_color or COLORS.primary
    accent_dark = COLORS.primary_dark
    return f"""
QPushButton#DSButton {{
    border: none;
    border-radius: {RADII.lg}px;
    padding: {SPACING.sm}px {SPACING.lg}px;
    {typography_rule("body")}
}}
QPushButton#DSButton[data-size="sm"] {{ padding: {SPACING.xs}px {SPACING.md}px; {typography_rule("caption")}; }}
QPushButton#DSButton[data-size="lg"] {{ padding: {SPACING.md}px {SPACING.xl}px; {typography_rule("title")}; }}
QPushButton#DSButton[data-variant="primary"] {{ background-color: {accent}; color: {COLORS.on_primary}; }}
QPushButton#DSButton[data-variant="primary"]:hover {{ background-color: {accent_dark}; }}
QPushButton#DSButton[data-variant="secondary"] {{ background-color: transparent; color: {COLORS.text}; border: 1px solid {COLORS.border}; }}
QPushButton#DSButton[data-variant="secondary"]:hover {{ background-color: rgba(255,255,255,0.08); }}
QPushButton#DSButton[data-variant="link"] {{ background-color: transparent; color: {accent}; text-decoration: none; padding: {SPACING.xs}px {SPACING.sm}px; }}
QPushButton#DSButton[data-variant="link"]:hover {{ color: {COLORS.text}; text-decoration: underline; }}
QPushButton#DSButton:disabled {{ background-color: rgba(110,96,80,0.55); color: rgba(27,15,8,0.45); }}

QLineEdit#DSTextField {{
    background-color: rgba(255,255,255,0.94);
    color: #2A170C;
    border-radius: {RADII.md}px;
    padding: {SPACING.sm}px {SPACING.md}px;
    border: 1px solid rgba(255,255,255,0.16);
    {typography_rule("body")}
}}
QLineEdit#DSTextField:focus {{ border: 2px solid {accent}; }}

QComboBox#DSSelect {{
    background-color: rgba(255,255,255,0.94);
    color: #2A170C;
    border-radius: {RADII.md}px;
    padding: {SPACING.sm}px {SPACING.md}px;
    border: 1px solid rgba(255,255,255,0.16);
    {typography_rule("body")}
}}
QComboBox#DSSelect:focus {{ border: 2px solid {accent}; }}
QComboBox#DSSelect::drop-down {{ border: none; width: 28px; }}
QComboBox#DSSelect::down-arrow {{ width: 12px; height: 12px; margin: 6px; }}

QFrame#DSAlert {{
    border-radius: {RADII.md}px;
    border: 1px solid {COLORS.border};
    background-color: {COLORS.surface_alt};
}}
QFrame#DSAlert[data-severity="success"] {{ border-color: rgba(46,125,84,0.5); background-color: rgba(46,125,84,0.18); }}
QFrame#DSAlert[data-severity="warning"] {{ border-color: rgba(196,127,29,0.5); background-color: rgba(196,127,29,0.18); }}
QFrame#DSAlert[data-severity="danger"] {{ border-color: rgba(178,70,70,0.5); background-color: rgba(178,70,70,0.18); }}

QTabWidget#DSTabWidget::pane {{
    border: 1px solid {COLORS.border};
    border-radius: {RADII.md}px;
    padding: {SPACING.sm}px;
    background: {COLORS.surface_alt};
}}
QTabBar::tab {{
    {typography_rule("body")}
    padding: {SPACING.xs}px {SPACING.md}px;
    border: 1px solid transparent;
    border-radius: {RADII.md}px;
    background: transparent;
    color: {COLORS.text_muted};
    margin: 2px;
}}
QTabBar::tab:selected {{ background: {accent}; color: {COLORS.on_primary}; border-color: {accent}; }}
QTabBar::tab:hover {{ background: rgba(255,255,255,0.06); color: {COLORS.text}; }}

QTableWidget#DSTable {{
    background: rgba(255,255,255,0.92);
    border-radius: {RADII.md}px;
    gridline-color: rgba(0,0,0,0.08);
    {typography_rule("body")}
}}
QTableWidget#DSTable::item {{
    padding: {SPACING.xs}px;
}}
QTableWidget#DSTable::item:selected {{
    background: rgba(212,160,94,0.35);
    color: #2A170C;
}}
QTableWidget#DSTable::item:hover:!active {{
    background: rgba(212,160,94,0.14);
}}
QTableCornerButton::section {{
    background-color: rgba(0,0,0,0.08);
    border: none;
}}
QHeaderView::section {{
    background-color: rgba(0,0,0,0.08);
    color: #2A170C;
    padding: {SPACING.xs}px;
    border: none;
    {typography_rule("caption")}
}}
QHeaderView::section:horizontal {{
    border-bottom: 2px solid rgba(0,0,0,0.12);
}}
QHeaderView::section:pressed {{
    background-color: rgba(0,0,0,0.14);
}}

QDialog#DSModal {{
    background-color: {COLORS.surface_muted};
    color: {COLORS.text};
    border-radius: {RADII.xl}px;
}}
QFrame#TokenDocBlock {{
    border-radius: {RADII.lg}px;
    border: 1px solid {COLORS.border};
    background-color: {COLORS.surface_alt};
}}
QFrame#KpiCard {{
    border-radius: {RADII.lg}px;
    border: 1px solid rgba(255,255,255,0.14);
    background-color: rgba(255,255,255,0.06);
    box-shadow: {SHADOWS.soft};
}}
QFrame#SectionCard {{
    border-radius: {RADII.lg}px;
    border: 1px solid {COLORS.border};
    background-color: {COLORS.surface_alt};
    padding: {SPACING.md}px;
}}

*[data-typo="display"] {{ {typography_rule("display")} }}
*[data-typo="title"] {{ {typography_rule("title")} }}
*[data-typo="body"] {{ {typography_rule("body")} }}
*[data-typo="caption"] {{ {typography_rule("caption")} }}
"""
