from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
)


class OrderItemEditor(QDialog):
    """Allow adjusting quantity and note for an existing order item."""

    def __init__(self, product: str, qty: float, note: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"تعديل عنصر — {product}")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self._values: dict | None = None

        form = QFormLayout(self)
        self.qty_field = QDoubleSpinBox()
        self.qty_field.setRange(0, 10_000)
        self.qty_field.setDecimals(2)
        self.qty_field.setSingleStep(0.5)
        self.qty_field.setValue(float(qty))
        self.note_field = QLineEdit(note or "")
        self.note_field.setMaxLength(120)
        form.addRow("الكمية:", self.qty_field)
        form.addRow("ملاحظة:", self.note_field)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self) -> None:
        qty = float(self.qty_field.value())
        note = self.note_field.text().strip()
        self._values = {"qty": qty, "note": note}
        super().accept()

    def get_values(self) -> dict | None:
        return self._values
