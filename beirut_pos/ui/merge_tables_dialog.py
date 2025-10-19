"""Dialog that lets the operator merge another table into the current one."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ..utils.currency import format_pounds


class MergeTablesDialog(QDialog):
    def __init__(self, current_table: str, candidates: list[tuple[str, int]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("دمج الطاولات")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self._selection: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        intro = QLabel(
            f"اختر الطاولة التي ترغب في دمجها مع الطاولة الحالية ({current_table}).\n"
            "سيتم نقل جميع العناصر وإفراغ الطاولة المختارة."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.combo = QComboBox()
        for code, total in candidates:
            label = f"{code} — {format_pounds(total)}"
            self.combo.addItem(label, code)
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not candidates:
            self.combo.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def accept(self) -> None:
        if self.combo.currentIndex() < 0:
            return
        self._selection = self.combo.currentData()
        super().accept()

    def selected_table(self) -> str | None:
        return self._selection

