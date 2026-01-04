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
    QSizePolicy,
)
from PyQt6.QtCore import Qt

from beirut_pos.utils.currency import format_pounds, pounds_value

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
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        form = QFormLayout()
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSpacing(12)
        layout.addLayout(form)

        def _configure_field(widget):
            widget.setMinimumWidth(240)
            widget.setMinimumHeight(34)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if isinstance(widget, (QLineEdit, QComboBox)):
                widget.setStyleSheet("padding: 6px 10px;")

        self.size = QComboBox()
        self.size.addItem("صغير", 0)
        self.size.addItem(f"متوسط (+{pounds_value(5)})", 5)
        self.size.addItem(f"كبير (+{pounds_value(9)})", 9)
        _configure_field(self.size)
        form.addRow("الحجم:", self.size)

        self.milk = QComboBox()
        self.milk.addItem("حليب كامل", 0)
        self.milk.addItem("حليب خالي الدسم", 0)
        self.milk.addItem(f"حليب لوز (+{pounds_value(7)})", 7)
        self.milk.addItem(f"حليب صويا (+{pounds_value(6)})", 6)
        _configure_field(self.milk)
        form.addRow("نوع الحليب:", self.milk)

        self.sweetness = QComboBox()
        self.sweetness.addItem("سكر عادي", 0)
        self.sweetness.addItem("بدون سكر", 0)
        self.sweetness.addItem("سكر قليل", 0)
        self.sweetness.addItem("سكر زيادة", 0)
        _configure_field(self.sweetness)
        form.addRow("درجة التحلية:", self.sweetness)

        self.temperature = QComboBox()
        self.temperature.addItem("ساخن", 0)
        self.temperature.addItem("مثلج", 0)
        _configure_field(self.temperature)
        form.addRow("التقديم:", self.temperature)

        self.extra_shot = QCheckBox(f"جرعة إسبرسو إضافية (+{pounds_value(8)})")
        self.whipped = QCheckBox(f"كريمة مخفوقة (+{pounds_value(5)})")
        self.extra_shot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.whipped.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        form.addRow("إضافات:", self.extra_shot)
        form.addRow("", self.whipped)

        self.note = QLineEdit()
        self.note.setPlaceholderText("ملاحظات خاصة (مثلاً بدون قرفة)")
        _configure_field(self.note)
        form.addRow("ملاحظة للبارستا:", self.note)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.preview.setWordWrap(True)
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
            delta += 8
        if self.whipped.isChecked():
            delta += 5
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
        new_price = self._base_price + delta
        note = self._build_note()
        summary = f"السعر بعد الإضافات: {format_pounds(new_price)}"
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
