from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QLabel,
)


class SugarLevelDialog(QDialog):
    """Simple selector allowing baristas to pick or type a sugar level."""

    def __init__(self, product_name: str, levels: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"درجة السكر — {product_name}")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self._selection: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        intro = QLabel("حدد مستوى السكر للمشروب أو أدخل مستوى مخصصًا.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.combo = QComboBox()
        self.combo.setEditable(False)
        for level in levels:
            cleaned = (level or "").strip()
            if cleaned:
                self.combo.addItem(cleaned)
        if self.combo.count() == 0:
            self.combo.addItem("بدون سكر")
        form.addRow("مستويات جاهزة:", self.combo)

        self.custom = QLineEdit()
        self.custom.setPlaceholderText("اكتب مستوى السكر المخصص (اختياري)")
        form.addRow("مستوى مخصص:", self.custom)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("موافق")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("إلغاء")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        custom = self.custom.text().strip()
        choice = custom or self.combo.currentText().strip()
        if not choice:
            QMessageBox.warning(self, "تنبيه", "يرجى اختيار أو إدخال مستوى السكر.")
            return
        self._selection = choice
        super().accept()

    def selected_level(self) -> str | None:
        return self._selection
