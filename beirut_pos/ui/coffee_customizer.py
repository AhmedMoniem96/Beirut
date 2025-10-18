from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QLabel,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt

from ..core.money import cents_to_le, fmt_le


@dataclass
class CoffeeSelection:
    label: str
    price_delta: int
    note: str


class CoffeeCustomizerDialog(QDialog):
    """Collects milk/sweetness/size modifiers for coffee drinks."""

    def __init__(self, product_name: str, base_price_cents: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تخصيص المشروب")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._base_name = product_name
        self._base_price = base_price_cents
        self._result: Optional[CoffeeSelection] = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.size = QComboBox()
        self.size.addItem("صغير", 0)
        self.size.addItem("متوسط (+5.00)", 500)
        self.size.addItem("كبير (+9.00)", 900)
        form.addRow("الحجم:", self.size)

        self.milk = QComboBox()
        self.milk.addItem("حليب كامل", 0)
        self.milk.addItem("حليب خالي الدسم", 0)
        self.milk.addItem("حليب لوز (+7.00)", 700)
        self.milk.addItem("حليب صويا (+6.00)", 600)
        form.addRow("نوع الحليب:", self.milk)

        self.sweetness = QComboBox()
        self.sweetness.addItem("سكر عادي", 0)
        self.sweetness.addItem("بدون سكر", 0)
        self.sweetness.addItem("سكر قليل", 0)
        self.sweetness.addItem("سكر زيادة", 0)
        form.addRow("درجة التحلية:", self.sweetness)

        self.temperature = QComboBox()
        self.temperature.addItem("ساخن", 0)
        self.temperature.addItem("مثلج", 0)
        form.addRow("التقديم:", self.temperature)

        self.extra_shot = QCheckBox("جرعة إسبرسو إضافية (+8.00)")
        self.whipped = QCheckBox("كريمة مخفوقة (+5.00)")
        form.addRow("إضافات:", self.extra_shot)
        form.addRow("", self.whipped)

        self.note = QLineEdit()
        self.note.setPlaceholderText("ملاحظات خاصة (مثلاً بدون قرفة)")
        form.addRow("ملاحظة للبارستا:", self.note)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        for widget in (self.size, self.milk, self.sweetness, self.temperature, self.extra_shot, self.whipped, self.note):
            if hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(self._update_preview)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self._update_preview)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._update_preview)

        self._update_preview()

    def _calc_price_delta(self) -> int:
        delta = 0
        delta += int(self.size.currentData() or 0)
        delta += int(self.milk.currentData() or 0)
        if self.extra_shot.isChecked():
            delta += 800
        if self.whipped.isChecked():
            delta += 500
        return delta

    def _build_note(self) -> str:
        parts: list[str] = []
        milk = self.milk.currentText().split(" (")[0]
        if milk:
            parts.append(milk)
        sweet = self.sweetness.currentText()
        if sweet and sweet != "سكر عادي":
            parts.append(sweet)
        temp = self.temperature.currentText()
        if temp and temp != "ساخن":
            parts.append(temp)
        if self.extra_shot.isChecked():
            parts.append("جرعة إضافية")
        if self.whipped.isChecked():
            parts.append("كريمة")
        custom = self.note.text().strip()
        if custom:
            parts.append(custom)
        return "، ".join(parts)

    def _build_label(self) -> str:
        size = self.size.currentText().split(" (")[0]
        temp = self.temperature.currentText()
        components = [size]
        if temp:
            components.append(temp)
        label = self._base_name
        if components:
            label += f" ({'، '.join(components)})"
        return label

    def _update_preview(self):
        delta = self._calc_price_delta()
        new_price = (self._base_price + delta) / 100
        note = self._build_note()
        summary = f"السعر بعد الإضافات: {fmt_le(cents_to_le(self._base_price + delta))}"
        if note:
            summary += f"\nملاحظة للطباعة: {note}"
        self.preview.setText(summary)

    def accept(self):
        delta = self._calc_price_delta()
        label = self._build_label()
        note = self._build_note()
        self._result = CoffeeSelection(label=label, price_delta=delta, note=note)
        super().accept()

    def get_result(self) -> Optional[CoffeeSelection]:
        return self._result
