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
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, pyqtProperty, QParallelAnimationGroup
from PyQt6.QtGui import QColor, QPalette, QPixmap

from .tokens import COLORS, RADII, SPACING, SHADOWS, typography_rule


class DSButton(QPushButton):
    """Token-driven push button with variants and sizes."""

    def __init__(self, text: str = "", *, variant: str = "primary", size: str = "md", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("DSButton")
        self.setProperty("data-variant", variant)
        self.setProperty("data-size", size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if not self.accessibleName():
            self.setAccessibleName(text or "زر")

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(8)
        self._shadow.setOffset(0, 2)
        self._shadow.setColor(QColor(0, 0, 0, 70))
        self.setGraphicsEffect(self._shadow)

        self._elevation = 0.0
        self._elevation_anim = QPropertyAnimation(self, b"elevation", self)
        self._elevation_anim.setDuration(160)
        self._elevation_anim.setEasingCurve(QEasingCurve.Type.OutQuad)

    # Qt property used for micro-interaction shadow animation
    def get_elevation(self) -> float:  # noqa: N802 (Qt property)
        return self._elevation

    def set_elevation(self, value: float) -> None:  # noqa: N802 (Qt property)
        self._elevation = value
        self._shadow.setBlurRadius(8 + 6 * value)
        self._shadow.setOffset(0, 2 + 2 * value)

    elevation = pyqtProperty(float, fget=get_elevation, fset=set_elevation)

    def enterEvent(self, event):  # noqa: N802 (Qt override)
        self._animate_elevation(1.0)
        return super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802 (Qt override)
        self._animate_elevation(0.0)
        return super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        self._animate_elevation(0.35)
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 (Qt override)
        target = 1.0 if self.underMouse() else 0.0
        self._animate_elevation(target)
        return super().mouseReleaseEvent(event)

    def _animate_elevation(self, target: float) -> None:
        self._elevation_anim.stop()
        self._elevation_anim.setEndValue(target)
        self._elevation_anim.start()


class DSLinkButton(DSButton):
    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, variant="link", size="sm", parent=parent)
        self.setFlat(True)


class DSTextField(QLineEdit):
    def __init__(self, placeholder: str = "", *, width: Optional[int] = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DSTextField")
        self.setPlaceholderText(placeholder)
        self.setMinimumWidth(width or 320)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if not self.accessibleName():
            self.setAccessibleName(placeholder or "حقل إدخال")


class DSSelect(QComboBox):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DSSelect")
        self.setEditable(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if not self.accessibleName():
            self.setAccessibleName("قائمة اختيار")


class DSFormField(QFrame):
    """Labeled form wrapper with helper/error text and focus states."""

    def __init__(
        self,
        label: str,
        field: QWidget,
        *,
        helper: str = "",
        required: bool = False,
        width: int = 360,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("DSFormField")
        self.setProperty("data-status", "neutral")
        self.setProperty("data-focused", False)
        self._field = field
        self._default_helper = helper
        self._required = required
        self.setMinimumWidth(width)
        self._field.setParent(self)
        self._field.setMinimumWidth(width)
        self._field.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.sm, SPACING.sm, SPACING.sm, SPACING.sm)
        layout.setSpacing(SPACING.xs)

        self.label = QLabel(f"{label}{' *' if required else ''}")
        self.label.setProperty("data-role", "label")
        apply_typography(self.label, "caption")
        layout.addWidget(self.label)

        layout.addWidget(self._field)

        self.helper = QLabel(helper)
        self.helper.setWordWrap(True)
        self.helper.setProperty("data-role", "helper")
        self.helper.setProperty("data-status", "neutral")
        apply_typography(self.helper, "caption")
        layout.addWidget(self.helper)

    # ------------------------------------------------------------------ api
    @property
    def field(self) -> QWidget:
        return self._field

    def set_helper_text(self, text: str) -> None:
        self._default_helper = text
        self.helper.setText(text)
        self.helper.setProperty("data-status", "neutral")
        self._refresh_styles()

    def set_status(self, status: str = "neutral", message: Optional[str] = None) -> None:
        self.setProperty("data-status", status)
        self._field.setProperty("data-status", status)
        self.helper.setProperty("data-status", status)
        self.helper.setText(message if message is not None else self._default_helper)
        self._refresh_styles()

    def mark_error(self, message: str) -> None:
        self.set_status("error", message)

    def mark_success(self, message: Optional[str] = None) -> None:
        self.set_status("success", message or self._default_helper)

    def clear_status(self) -> None:
        self.set_status("neutral", self._default_helper)

    def eventFilter(self, source, event):  # noqa: N802 (Qt override)
        if source is self._field:
            if event.type() == QEvent.Type.FocusIn:
                self.setProperty("data-focused", True)
                self._refresh_styles()
            elif event.type() == QEvent.Type.FocusOut:
                self.setProperty("data-focused", False)
                self._refresh_styles()
        return super().eventFilter(source, event)

    # ------------------------------------------------------------------ utils
    def _refresh_styles(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        self._field.style().unpolish(self._field)
        self._field.style().polish(self._field)


class ProgressStepper(QFrame):
    """Horizontal stepper used for wizard-like flows."""

    def __init__(self, steps: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ProgressStepper")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING.sm, SPACING.sm, SPACING.sm, SPACING.sm)
        layout.setSpacing(SPACING.md)
        self._badges: list[QLabel] = []
        self._labels: list[QLabel] = []

        for idx, title in enumerate(steps):
            wrapper = QVBoxLayout()
            wrapper.setSpacing(SPACING.xs)

            badge = QLabel(str(idx + 1))
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setProperty("data-role", "badge")
            badge.setProperty("data-state", "inactive")
            badge.setFixedSize(32, 32)

            label = QLabel(title)
            label.setProperty("data-role", "label")
            label.setProperty("data-state", "inactive")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            apply_typography(label, "body")

            wrapper.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)
            wrapper.addWidget(label)

            layout.addLayout(wrapper, 1)
            self._badges.append(badge)
            self._labels.append(label)

        self.set_active_step(0)

    def set_active_step(self, index: int) -> None:
        for idx, (badge, label) in enumerate(zip(self._badges, self._labels)):
            state = "active" if idx == index else "inactive"
            badge.setProperty("data-state", state)
            label.setProperty("data-state", state)
            badge.style().unpolish(badge)
            badge.style().polish(badge)
            label.style().unpolish(label)
            label.style().polish(label)


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
    def __init__(self, text: str, *, severity: str = "info", parent: QWidget | None = None, animated: bool = False):
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

        self._animated = animated
        self._opacity_effect: QGraphicsOpacityEffect | None = None
        if animated:
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self._opacity_effect.setOpacity(0.0)
            self.setGraphicsEffect(self._opacity_effect)
            self.setMaximumHeight(0)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt compatibility)
        self.label.setText(text)
        if self._animated:
            self._refresh_animation_targets()

    def set_severity(self, severity: str) -> None:
        self.setProperty("data-severity", severity)
        self.style().unpolish(self)
        self.style().polish(self)
        if self._animated:
            self._refresh_animation_targets()

    def animate_in(self) -> None:
        if not self._animated:
            self.setVisible(True)
            return

        self.setVisible(True)
        opacity = self._opacity_effect
        if opacity is None:
            return
        fade = QPropertyAnimation(opacity, b"opacity", self)
        fade.setDuration(220)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutQuad)

        slide = QPropertyAnimation(self, b"maximumHeight", self)
        slide.setDuration(220)
        slide.setStartValue(0)
        slide.setEndValue(self._target_height())
        slide.setEasingCurve(QEasingCurve.Type.OutQuad)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade)
        group.addAnimation(slide)
        group.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def animate_out(self) -> None:
        if not self._animated:
            self.hide()
            return

        opacity = self._opacity_effect
        if opacity is None:
            self.hide()
            return

        fade = QPropertyAnimation(opacity, b"opacity", self)
        fade.setDuration(200)
        fade.setStartValue(opacity.opacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

        slide = QPropertyAnimation(self, b"maximumHeight", self)
        slide.setDuration(200)
        slide.setStartValue(self.maximumHeight())
        slide.setEndValue(0)
        slide.setEasingCurve(QEasingCurve.Type.InOutQuad)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade)
        group.addAnimation(slide)

        def _hide():
            self.hide()
            self.setMaximumHeight(0)

        group.finished.connect(_hide)
        group.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # Internal helpers --------------------------------------------------
    def _refresh_animation_targets(self) -> None:
        if self._animated:
            self.setMaximumHeight(self._target_height())

    def _target_height(self) -> int:
        return max(self.sizeHint().height(), SPACING.lg)


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


class DSDivider(QFrame):
    """Thin divider that respects the design tokens."""

    def __init__(self, *, orientation: Qt.Orientation = Qt.Orientation.Horizontal, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("data-role", "divider")
        self.setFrameShape(
            QFrame.Shape.HLine if orientation == Qt.Orientation.Horizontal else QFrame.Shape.VLine
        )
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setLineWidth(1)


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


class LogoLockup(QFrame):
    """Consistent logo + wordmark lockup for toolbars and dialogs."""

    def __init__(self, title: str = "Beirut POS", subtitle: str = "Café Edition", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("LogoLockup")
        root = QHBoxLayout(self)
        root.setContentsMargins(SPACING.sm, SPACING.xs, SPACING.sm, SPACING.xs)
        root.setSpacing(SPACING.sm)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setScaledContents(True)
        self.icon_label.setProperty("data-role", "logo")

        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(0)

        self.wordmark = QLabel(title)
        self.wordmark.setProperty("data-typo", "title")
        self.wordmark.setStyleSheet(f"letter-spacing: 0.6px; color: {COLORS.text};")

        self.tagline = QLabel(subtitle)
        self.tagline.setProperty("data-typo", "caption")
        self.tagline.setStyleSheet(f"color: {COLORS.text_muted}; letter-spacing: 0.4px;")

        text_box.addWidget(self.wordmark)
        text_box.addWidget(self.tagline)

        root.addWidget(self.icon_label)
        root.addLayout(text_box)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        if pixmap:
            scaled = pixmap.scaled(self.icon_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.icon_label.setPixmap(scaled)
            self.icon_label.setVisible(True)
        else:
            self.icon_label.clear()
            self.icon_label.setVisible(False)

    def set_titles(self, title: str, subtitle: str | None = None) -> None:
        self.wordmark.setText(title)
        if subtitle is not None:
            self.tagline.setText(subtitle)


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
QPushButton#DSButton[data-variant="secondary"] {{ background-color: rgba(255,255,255,0.06); color: {COLORS.text}; border: 1px solid rgba(255,255,255,0.24); }}
QPushButton#DSButton[data-variant="secondary"]:hover {{ background-color: rgba(255,255,255,0.14); }}
QPushButton#DSButton[data-variant="link"] {{ background-color: transparent; color: {accent}; text-decoration: none; padding: {SPACING.xs}px {SPACING.sm}px; }}
QPushButton#DSButton[data-variant="link"]:hover {{ color: {COLORS.text}; text-decoration: underline; }}
QPushButton#DSButton:focus {{ outline: 3px solid rgba(212,160,94,0.72); outline-offset: 2px; box-shadow: 0 0 0 3px rgba(212,160,94,0.22); }}
QPushButton#DSButton:disabled {{ background-color: rgba(110,96,80,0.55); color: rgba(27,15,8,0.45); }}

QToolButton:focus, QAbstractButton:focus {{
    outline: 3px solid rgba(212,160,94,0.72);
    outline-offset: 2px;
    background-color: rgba(212,160,94,0.16);
    color: {COLORS.on_primary};
}}

QLineEdit#DSTextField {{
    background-color: rgba(255,255,255,0.94);
    color: #2A170C;
    border-radius: {RADII.md}px;
    padding: {SPACING.sm}px {SPACING.md}px;
    border: 1px solid rgba(255,255,255,0.16);
    {typography_rule("body")}
}}
QLineEdit#DSTextField:focus {{ border: 2px solid {accent}; box-shadow: 0 0 0 3px rgba(212,160,94,0.25); }}
QLineEdit#DSTextField[data-status="error"] {{ border: 2px solid {COLORS.danger}; box-shadow: 0 0 0 3px rgba(178,70,70,0.28); }}
QLineEdit#DSTextField[data-status="success"] {{ border: 2px solid {COLORS.success}; box-shadow: 0 0 0 2px rgba(46,125,84,0.25); }}

QComboBox#DSSelect {{
    background-color: rgba(255,255,255,0.94);
    color: #2A170C;
    border-radius: {RADII.md}px;
    padding: {SPACING.sm}px {SPACING.md}px;
    border: 1px solid rgba(255,255,255,0.16);
    {typography_rule("body")}
}}
QComboBox#DSSelect:focus {{ border: 2px solid {accent}; box-shadow: 0 0 0 3px rgba(212,160,94,0.25); }}
QComboBox#DSSelect[data-status="error"] {{ border: 2px solid {COLORS.danger}; box-shadow: 0 0 0 3px rgba(178,70,70,0.28); }}
QComboBox#DSSelect[data-status="success"] {{ border: 2px solid {COLORS.success}; box-shadow: 0 0 0 2px rgba(46,125,84,0.25); }}
QComboBox#DSSelect::drop-down {{ border: none; width: 28px; }}
QComboBox#DSSelect::down-arrow {{ width: 12px; height: 12px; margin: 6px; }}

QFrame#DSFormField {{
    border-radius: {RADII.md}px;
    border: 1px solid {COLORS.border};
    background-color: {COLORS.surface_alt};
}}
QFrame#DSFormField[data-focused="true"] {{ border-color: {accent}; box-shadow: 0 0 0 3px rgba(212,160,94,0.25); }}
QFrame#DSFormField[data-status="error"] {{ border-color: {COLORS.danger}; box-shadow: 0 0 0 3px rgba(178,70,70,0.28); background-color: rgba(178,70,70,0.12); }}
QFrame#DSFormField[data-status="success"] {{ border-color: {COLORS.success}; box-shadow: 0 0 0 2px rgba(46,125,84,0.25); background-color: rgba(46,125,84,0.1); }}
QFrame#DSFormField QLabel[data-role="label"] {{ color: {COLORS.text}; {typography_rule("caption")} }}
QFrame#DSFormField QLabel[data-role="helper"] {{ color: {COLORS.text_muted}; }}
QFrame#DSFormField QLabel[data-role="helper"][data-status="error"] {{ color: {COLORS.danger}; font-weight: 700; }}
QFrame#DSFormField QLabel[data-role="helper"][data-status="success"] {{ color: {COLORS.success}; font-weight: 700; }}

QFrame#ProgressStepper {{ border-radius: {RADII.lg}px; border: 1px solid {COLORS.border}; background: {COLORS.surface_alt}; }}
QFrame#ProgressStepper QLabel[data-role="badge"] {{ background: {COLORS.surface}; color: {COLORS.text}; border-radius: {RADII.pill}px; {typography_rule("body")}; }}
QFrame#ProgressStepper QLabel[data-role="badge"][data-state="active"] {{ background: {accent}; color: {COLORS.on_primary}; box-shadow: 0 2px 10px rgba(0,0,0,0.35); }}
QFrame#ProgressStepper QLabel[data-role="label"] {{ color: {COLORS.text_muted}; }}
QFrame#ProgressStepper QLabel[data-role="label"][data-state="active"] {{ color: {COLORS.text}; font-weight: 800; }}

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
QTabBar::tab:focus {{
    outline: 2px solid rgba(212,160,94,0.72);
    outline-offset: 2px;
}}
QTabBar::tab:selected {{ background: {accent}; color: {COLORS.on_primary}; border-color: {accent}; }}
QTabBar::tab:hover {{ background: rgba(255,255,255,0.06); color: {COLORS.text}; }}

QTableWidget#DSTable {{
    background: rgba(255,255,255,0.92);
    border-radius: {RADII.md}px;
    gridline-color: rgba(0,0,0,0.08);
    {typography_rule("body")}
}}
QTableWidget#DSTable:focus {{
    border: 2px solid {accent};
    box-shadow: 0 0 0 3px rgba(212,160,94,0.22);
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
    border: 1px solid {COLORS.border};
    box-shadow: {SHADOWS.raised};
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
QFrame#LogoLockup {{
    background: transparent;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {RADII.md}px;
    padding: {SPACING.xs}px {SPACING.sm}px;
}}
QFrame#LogoLockup QLabel[data-role="logo"] {{
    background: rgba(255,255,255,0.04);
    border-radius: {RADII.lg}px;
    padding: {SPACING.xs}px;
}}
QFrame#SectionCard {{
    border-radius: {RADII.lg}px;
    border: 1px solid {COLORS.border};
    background-color: {COLORS.surface_alt};
    padding: {SPACING.lg}px;
    margin-bottom: {SPACING.sm}px;
    box-shadow: {SHADOWS.soft};
}}
QFrame#InlineToast {{
    border-radius: {RADII.lg}px;
    box-shadow: {SHADOWS.soft};
}}
QFrame[data-role="divider"] {{
    color: {COLORS.border};
    background: {COLORS.border};
    max-height: 1px;
    min-height: 1px;
    margin: {SPACING.sm}px 0;
}}

*[data-typo="display"] {{ {typography_rule("display")} }}
*[data-typo="title"] {{ {typography_rule("title")} }}
*[data-typo="body"] {{ {typography_rule("body")} }}
*[data-typo="caption"] {{ {typography_rule("caption")} }}
"""
